#!/usr/bin/env python3
"""Live Sandwalk mux scale probe (not CI).

Creates 1 chat, then N chats, all on GET /v1/events. Requires a running
agent server.

Usage (from cli/):
    uv run python tests/integration_mux/sandwalk_mux_scale.py
    uv run python tests/integration_mux/sandwalk_mux_scale.py --n 4
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

import httpx

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agent_server.auth_settings import load_settings, resolve_effective_api_key  # noqa: E402

PROMPT = "Hi, what skills do you have"
PROVIDER = "openrouter"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash"


def api_key() -> str:
    settings = load_settings(create_if_missing=False)
    key = resolve_effective_api_key(cli_api_key=None, settings=settings) or ""
    if not key:
        raise SystemExit("No backend API key (`sandwalk auth`).")
    return key


def headers(key: str) -> dict[str, str]:
    return {"authorization": f"Bearer {key}", "content-type": "application/json"}


def sse_frames(resp: httpx.Response):
    buf = ""
    for chunk in resp.iter_text():
        buf += chunk
        while "\n\n" in buf:
            raw, buf = buf.split("\n\n", 1)
            data = "".join(
                line[5:].strip()
                for line in raw.split("\n")
                if line.startswith("data:")
            )
            if data:
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue


def create_session(client: httpx.Client, base: str, model: str, title: str) -> str:
    r = client.post(
        f"{base}/v1/sessions",
        json={
            "title": title,
            "provider": PROVIDER,
            "model": model,
            "clientSurface": "cli",
        },
    )
    r.raise_for_status()
    return r.json()["id"]


def send(client: httpx.Client, base: str, sid: str) -> None:
    r = client.post(f"{base}/v1/sessions/{sid}/messages", json={"content": PROMPT})
    r.raise_for_status()


def wait_runs(
    key: str,
    base: str,
    session_ids: list[str],
    start: dict[str, float],
    sse_ready: threading.Event,
    timeout: float,
) -> dict[str, dict]:
    stats = {
        sid: {
            "first_delta_s": None,
            "completed_s": None,
            "error": None,
            "delta_chars": 0,
        }
        for sid in session_ids
    }
    done: set[str] = set()
    q = httpx.QueryParams({"sessions": ",".join(session_ids), "token": key})
    with httpx.Client(timeout=timeout, headers=headers(key)) as client:
        with client.stream("GET", f"{base}/v1/events", params=q) as resp:
            resp.raise_for_status()
            sse_ready.set()
            deadline = time.perf_counter() + timeout
            for frame in sse_frames(resp):
                if time.perf_counter() > deadline:
                    break
                if frame.get("channel") != "transcript":
                    continue
                sid = frame.get("sessionId")
                event = frame.get("event") or {}
                if sid not in stats:
                    continue
                t0 = start.get(sid)
                if t0 is None:
                    continue
                now = time.perf_counter()
                etype = event.get("type")
                payload = event.get("payload") or {}
                if etype == "assistant.delta":
                    if stats[sid]["first_delta_s"] is None:
                        stats[sid]["first_delta_s"] = now - t0
                    stats[sid]["delta_chars"] += len(str(payload.get("delta") or ""))
                elif etype in {"run.completed", "run.failed", "run.interrupted"}:
                    stats[sid]["completed_s"] = now - t0
                    if etype != "run.completed":
                        stats[sid]["error"] = etype
                    done.add(sid)
                if done >= set(session_ids):
                    break
    return stats


def fmt(row: dict) -> str:
    fd = row["first_delta_s"]
    done = row["completed_s"]
    err = row["error"] or "ok"
    fd_s = f"{fd:.2f}s" if fd is not None else "—"
    done_s = f"{done:.2f}s" if done is not None else "—"
    return f"ttfb={fd_s}  complete={done_s}  chars={row['delta_chars']}  {err}"


def debug_health(client: httpx.Client, base: str) -> None:
    r = client.get(f"{base}/v1/debug/health")
    if r.status_code >= 400:
        print(f"debug/health http={r.status_code}")
        return
    body = r.json()
    print(
        "debug/health "
        f"active_runs={body.get('active_runs')} "
        f"thread_pool={body.get('thread_pool')} "
        f"sse={body.get('connections')}"
    )


def run_wave(
    client: httpx.Client,
    key: str,
    base: str,
    model: str,
    n: int,
    label: str,
    timeout: float,
) -> None:
    ids = [
        create_session(client, base, model, f"mux-scale {label} {i + 1}/{n}")
        for i in range(n)
    ]
    start: dict[str, float] = {}
    sse_ready = threading.Event()
    results: dict[str, dict] = {}

    def reader() -> None:
        results.update(wait_runs(key, base, ids, start, sse_ready, timeout))

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    if not sse_ready.wait(timeout=15):
        raise SystemExit("mux SSE did not become ready")
    t_wave = time.perf_counter()
    for sid in ids:
        start[sid] = time.perf_counter()
        send(client, base, sid)
    debug_health(client, base)
    thread.join(timeout=timeout + 5)
    wall = time.perf_counter() - t_wave
    print(f"\n=== {label}: {n} chat(s)  wall={wall:.2f}s ===")
    for i, sid in enumerate(ids, 1):
        row = results.get(sid) or {
            "first_delta_s": None,
            "completed_s": None,
            "error": "no-result",
            "delta_chars": 0,
        }
        print(f"  [{i}] {sid[:8]}  {fmt(row)}")
    deltas = [
        r["first_delta_s"]
        for r in results.values()
        if r.get("first_delta_s") is not None
    ]
    completes = [
        r["completed_s"] for r in results.values() if r.get("completed_s") is not None
    ]
    if deltas:
        print(
            f"  ttfb  min={min(deltas):.2f}  median={sorted(deltas)[len(deltas) // 2]:.2f}  "
            f"max={max(deltas):.2f}"
        )
    if completes:
        print(
            f"  done  min={min(completes):.2f}  median={sorted(completes)[len(completes) // 2]:.2f}  "
            f"max={max(completes):.2f}"
        )
    print(f"  finished {len(completes)}/{n}")
    debug_health(client, base)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=int(os.environ.get("SANDWALK_MUX_N") or 4))
    parser.add_argument("--model", default=os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SANDWALK_BASE_URL") or "http://127.0.0.1:8787",
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    key = api_key()
    with httpx.Client(timeout=30.0, headers=headers(key)) as client:
        health = client.get(f"{args.base_url}/v1/health").json()
        print(
            f"health={health.get('status')} eventMux={health.get('capabilities', {}).get('eventMux')} "
            f"model={PROVIDER}:{args.model}"
        )
        print(f"prompt={PROMPT!r}")
        debug_health(client, args.base_url)
        run_wave(client, key, args.base_url, args.model, 1, "baseline", args.timeout)
        run_wave(client, key, args.base_url, args.model, args.n, "parallel", args.timeout)


if __name__ == "__main__":
    main()
