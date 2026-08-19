#!/usr/bin/env python3
"""Live OpenRouter concurrency probe (not CI).

Hits https://openrouter.ai/api/v1/chat/completions with stream=true.
Compares 1 request vs N concurrent requests for the same model/prompt.

Usage (from cli/):
    uv run python tests/integration_mux/openrouter_concurrent.py
    uv run python tests/integration_mux/openrouter_concurrent.py --n 8
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

PROMPT = "Hi, what skills do you have"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_URL = "https://openrouter.ai/api/v1/key"


def _openrouter_key() -> str:
    env = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if env:
        return env
    src = Path("/Users/juliocesar/Projects/sandwalk/cli/src")
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from agent.config import Config

    key = str(Config.load().get("llm.openrouter_api_key") or "").strip()
    if not key:
        raise SystemExit(
            "Set OPENROUTER_API_KEY or llm.openrouter_api_key in ~/.sandwalk/config.json"
        )
    return key


def _headers(key: str) -> dict[str, str]:
    return {
        "authorization": f"Bearer {key}",
        "content-type": "application/json",
        "HTTP-Referer": "https://sandwalk.ai",
        "X-OpenRouter-Title": "sandwalk-mux-probe",
    }


def _dummy_tools(count: int) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": f"demo_tool_{i}",
                "description": f"Dummy tool {i} for payload-size concurrency tests.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        }
        for i in range(count)
    ]


def _stream_one(
    key: str, model: str, timeout: float, tools: list[dict] | None = None
) -> dict:
    t0 = time.perf_counter()
    ttfb = None
    chars = 0
    status = None
    err = None
    payload = {
        "model": model,
        "stream": True,
        "messages": [{"role": "user", "content": PROMPT}],
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "none"
    with httpx.Client(timeout=timeout) as client:
        with client.stream(
            "POST",
            OR_URL,
            headers=_headers(key),
            json=payload,
        ) as resp:
            status = resp.status_code
            if resp.status_code >= 400:
                body = resp.read().decode("utf-8", errors="replace")[:400]
                err = f"http {resp.status_code}: {body}"
            else:
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    delta = (
                        ((chunk.get("choices") or [{}])[0].get("delta") or {}).get(
                            "content"
                        )
                        or ""
                    )
                    if delta:
                        if ttfb is None:
                            ttfb = time.perf_counter() - t0
                        chars += len(delta)
    return {
        "ttfb_s": ttfb,
        "complete_s": time.perf_counter() - t0,
        "chars": chars,
        "status": status,
        "error": err,
    }


def _print_wave(label: str, rows: list[dict], wall: float) -> None:
    print(f"\n=== {label}  wall={wall:.2f}s ===")
    ttfbs = []
    dones = []
    for i, row in enumerate(rows, 1):
        err = row["error"] or "ok"
        ttfb = f"{row['ttfb_s']:.2f}s" if row["ttfb_s"] is not None else "—"
        done = f"{row['complete_s']:.2f}s"
        print(
            f"  [{i}] ttfb={ttfb}  complete={done}  chars={row['chars']}  "
            f"http={row['status']}  {err}"
        )
        if row["ttfb_s"] is not None:
            ttfbs.append(row["ttfb_s"])
        dones.append(row["complete_s"])
    if ttfbs:
        print(
            f"  ttfb  min={min(ttfbs):.2f}  median={sorted(ttfbs)[len(ttfbs)//2]:.2f}  "
            f"max={max(ttfbs):.2f}"
        )
    print(
        f"  done  min={min(dones):.2f}  median={sorted(dones)[len(dones)//2]:.2f}  "
        f"max={max(dones):.2f}"
    )


def _key_snapshot(key: str) -> None:
    try:
        r = httpx.get(KEY_URL, headers=_headers(key), timeout=20.0)
        if r.status_code >= 400:
            print(f"openrouter /key http={r.status_code}")
            return
        data = r.json().get("data") or r.json()
        limit = data.get("rate_limit") or data.get("rateLimit") or {}
        print(
            "openrouter key: "
            f"limit_remaining={data.get('limit_remaining')} "
            f"rate_limit={limit}"
        )
    except Exception as exc:  # noqa: BLE001
        print(f"openrouter /key skipped: {type(exc).__name__}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=int(os.environ.get("OPENROUTER_CONCURRENCY") or 4))
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL,
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--tools",
        type=int,
        default=0,
        help="Attach N dummy function tools (tool_choice=none) to mimic Sandwalk payload size",
    )
    args = parser.parse_args()
    key = _openrouter_key()
    dummy = _dummy_tools(args.tools) if args.tools > 0 else None
    print(
        f"model={args.model}  prompt={PROMPT!r}  n={args.n}  dummy_tools={args.tools}"
    )
    _key_snapshot(key)

    t0 = time.perf_counter()
    baseline = [_stream_one(key, args.model, args.timeout, dummy)]
    _print_wave("openrouter baseline n=1", baseline, time.perf_counter() - t0)

    t1 = time.perf_counter()
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.n) as pool:
        futs = [
            pool.submit(_stream_one, key, args.model, args.timeout, dummy)
            for _ in range(args.n)
        ]
        for fut in as_completed(futs):
            rows.append(fut.result())
    _print_wave(f"openrouter parallel n={args.n}", rows, time.perf_counter() - t1)


if __name__ == "__main__":
    main()
