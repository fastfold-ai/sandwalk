#!/usr/bin/env python3
"""Measure chat/API latency while Dashboard Bench is inflight.

Reads the packaged-app API key from Sandwalk settings (never printed).
Exit 0 when local-path budgets pass. First-token time is reported separately
because that is the remote provider, not the local isolation contract.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8787"
HEALTH_P95_MS = 40.0
REVISION_P95_MS = 80.0
POST_MS = 400.0
RUN_STARTED_MS = 800.0
BUSY_409_MS = 80.0


def _settings() -> dict:
    path = (
        Path.home()
        / "Library"
        / "Application Support"
        / "Sandwalk"
        / "settings.json"
    )
    return json.loads(path.read_text())


def _key() -> str:
    return str(_settings()["auth"]["api_key"])


def _req(method: str, path: str, data: dict | None = None, timeout: float = 15.0):
    headers = {
        "Authorization": f"Bearer {_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = None if data is None else json.dumps(data).encode()
    request = urllib.request.Request(
        BASE + path, data=body, headers=headers, method=method
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            ms = (time.perf_counter() - started) * 1000
            payload = json.loads(raw) if raw else None
            return response.status, payload, ms
    except urllib.error.HTTPError as exc:
        ms = (time.perf_counter() - started) * 1000
        raw = exc.read()
        try:
            payload = json.loads(raw) if raw else {"detail": raw.decode()}
        except json.JSONDecodeError:
            payload = {"detail": raw.decode(errors="replace")}
        return exc.code, payload, ms


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    index = max(0, int(round((len(ordered) - 1) * 0.95)))
    return ordered[index]


def _wait_healthy(timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            status, payload, ms = _req("GET", "/v1/health", timeout=2)
            if status == 200:
                print(f"health ok {ms:.1f}ms version={payload.get('version')}")
                return
            last = f"{status} {payload}"
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
        time.sleep(1)
    raise SystemExit(f"API never became healthy: {last}")


def main() -> int:
    resume_id = (sys.argv[1] if len(sys.argv) > 1 else "").strip() or None
    _wait_healthy()

    status, active, _ = _req("GET", "/v1/bench/runs/active")
    print(
        "bench before",
        "running=",
        active.get("running"),
        "phase=",
        active.get("phase"),
        "inflight=",
        len(active.get("inflight") or []),
        "paused=",
        len(active.get("paused") or []),
        "resumable=",
        active.get("resumableRunId"),
    )
    if resume_id or active.get("resumableRunId"):
        rid = resume_id or active.get("resumableRunId")
        status, payload, ms = _req("POST", f"/v1/bench/runs/{rid}/resume")
        print(f"resume {rid} -> {status} {ms:.1f}ms {payload}")
        time.sleep(1.5)
        _, active, _ = _req("GET", "/v1/bench/runs/active")
        print(
            "bench after resume running=",
            active.get("running"),
            "inflight=",
            [
                item.get("runId")
                for item in (active.get("inflight") or [])
            ],
            "progress=",
            (active.get("lastProgress") or {}).get("message"),
        )

    health_samples = []
    revision_samples = []
    for _ in range(20):
        status, _, ms = _req("GET", "/v1/health")
        assert status == 200
        health_samples.append(ms)
        status, _, ms = _req("GET", "/v1/sessions/revision")
        assert status == 200
        revision_samples.append(ms)

    status, session, ms = _req(
        "POST", "/v1/sessions", {"title": "perf probe", "clientSurface": "ui"}
    )
    print(f"create session {status} {ms:.1f}ms")
    assert status == 201, session
    sid = session["id"]

    post_ms_status, posted, post_ms = _req(
        "POST", f"/v1/sessions/{sid}/messages", {"content": "Reply with the single word pong."}
    )
    print(f"chat POST {post_ms_status} {post_ms:.1f}ms")
    assert post_ms_status == 202, posted

    busy_status, busy_payload, busy_ms = _req(
        "POST", f"/v1/sessions/{sid}/messages", {"content": "so?"}
    )
    print(f"follow-up POST {busy_status} {busy_ms:.1f}ms")

    started_at = time.perf_counter()
    run_started_ms = None
    first_delta_ms = None
    deadline = time.time() + 90
    cursor = 0
    while time.time() < deadline:
        status, payload, poll_ms = _req(
            "GET",
            f"/v1/sessions/{sid}/events/history",
            timeout=10,
        )
        events = (payload or {}).get("data") or []
        for event in events:
            seq = int(event.get("sequence") or 0)
            if seq <= cursor:
                continue
            cursor = seq
            et = event.get("type")
            elapsed = (time.perf_counter() - started_at) * 1000
            if et == "run.started" and run_started_ms is None:
                run_started_ms = elapsed
                print(f"  event run.started +{elapsed:.0f}ms (history {poll_ms:.1f}ms)")
            if et == "assistant.delta" and first_delta_ms is None:
                first_delta_ms = elapsed
                print(f"  event assistant.delta +{elapsed:.0f}ms")
        if first_delta_ms is not None:
            break
        time.sleep(0.05)

    print("--- measured ---")
    print(f"health p95 { _p95(health_samples):.1f}ms  max {max(health_samples):.1f}ms")
    print(f"revision p95 { _p95(revision_samples):.1f}ms  max {max(revision_samples):.1f}ms")
    print(f"chat POST {post_ms:.1f}ms")
    print(f"run.started {run_started_ms}")
    print(f"first assistant.delta {first_delta_ms}")
    print(f"busy follow-up {busy_status} {busy_ms:.1f}ms")

    failures = []
    if _p95(health_samples) >= HEALTH_P95_MS:
        failures.append(f"health p95 {_p95(health_samples):.1f}ms")
    if _p95(revision_samples) >= REVISION_P95_MS:
        failures.append(f"revision p95 {_p95(revision_samples):.1f}ms")
    if post_ms >= POST_MS:
        failures.append(f"chat POST {post_ms:.1f}ms")
    if run_started_ms is None or run_started_ms >= RUN_STARTED_MS:
        failures.append(f"run.started {run_started_ms}")
    if busy_status not in {202, 409}:
        failures.append(f"follow-up status {busy_status} {busy_payload}")
    if busy_status == 409 and busy_ms >= BUSY_409_MS:
        failures.append(f"409 too slow {busy_ms:.1f}ms")
    if failures:
        print("FAIL local isolation:", "; ".join(failures))
        return 1
    print("PASS local isolation (provider TTFT is informational)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
