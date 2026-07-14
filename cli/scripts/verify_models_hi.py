#!/usr/bin/env python3
"""Live smoke: send \"hi\" to cloud catalog + discovered local models.

Usage (from cli/ with venv active):

    python scripts/verify_models_hi.py
    python scripts/verify_models_hi.py --provider openai --limit 3
    python scripts/verify_models_hi.py --with-tools   # bind a dummy tool (Sol regression)

Skips providers without a configured API key. Prints a pass/fail table to stderr
and JSON summary to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

# Allow running as ``python scripts/verify_models_hi.py`` from cli/.
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _has_key(config: Any, provider: str) -> bool:
    try:
        return bool(str(config.llm_api_key(provider) or "").strip())
    except Exception:
        return False


def _invoke_hi(model: Any, *, with_tools: bool) -> str:
    from langchain_core.messages import HumanMessage

    target = model
    if with_tools:
        from langchain_core.tools import tool

        @tool
        def ping() -> str:
            """Health-check tool used only for smoke tests."""
            return "pong"

        target = model.bind_tools([ping])
    result = target.invoke([HumanMessage(content="hi")])
    content = getattr(result, "content", result)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(str(item))
        text = "".join(parts).strip()
    else:
        text = str(content or "").strip()
    return text[:240]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", help="Only test this provider id")
    parser.add_argument("--limit", type=int, default=0, help="Max models (0=all)")
    parser.add_argument(
        "--with-tools",
        action="store_true",
        help="Bind a dummy tool (catches Sol chat-completions + tools failures)",
    )
    parser.add_argument(
        "--include-local",
        action="store_true",
        default=False,
        help="Include discovered local profile models (Ollama/oMLX). Off by default — local MLX can peg the GPU.",
    )
    parser.add_argument(
        "--no-local",
        action="store_true",
        help="Skip local models (default; kept for compatibility)",
    )
    args = parser.parse_args()

    from agent.config import Config
    from agent.deepagents_runtime import build_chat_model
    from agent.model_catalog import cloud_catalog_models
    from agent_server.models_service import ModelsService

    config = Config.load()
    targets: list[dict[str, Any]] = []

    for entry in cloud_catalog_models():
        provider = entry["provider"]
        if args.provider and provider != args.provider:
            continue
        if not _has_key(config, provider):
            continue
        targets.append(
            {
                "provider": provider,
                "model": entry["id"],
                "label": entry["label"],
                "source": "cloud",
                "profile_id": None,
            }
        )

    # Discovered proxy catalogs (OpenCode Zen) + local OpenAI-compatible profiles.
    try:
        listed = ModelsService().list_models(discover=True, enabled_only=False)
        for item in listed.data:
            if item.provider == "opencode":
                if args.provider and args.provider != "opencode":
                    continue
                if not _has_key(config, "opencode"):
                    continue
                targets.append(
                    {
                        "provider": "opencode",
                        "model": item.id,
                        "label": item.label,
                        "source": "cloud",
                        "profile_id": None,
                    }
                )
                continue
            if item.source != "profile":
                continue
            if args.no_local or not args.include_local:
                continue
            if args.provider and item.provider != args.provider and args.provider != "local":
                continue
            targets.append(
                {
                    "provider": "openai",  # local profiles speak OpenAI-compat
                    "model": item.id,
                    "label": item.label,
                    "source": "profile",
                    "profile_id": item.profile_id,
                }
            )
    except Exception as exc:  # pragma: no cover - discovery best-effort
        print(f"warn: discovery failed: {exc}", file=sys.stderr)

    if args.limit and args.limit > 0:
        targets = targets[: args.limit]

    results: list[dict[str, Any]] = []
    for idx, target in enumerate(targets, start=1):
        provider = target["provider"]
        model_id = target["model"]
        tag = f"[{idx}/{len(targets)}] {provider}/{model_id}"
        print(f"{tag} …", file=sys.stderr, flush=True)
        previous = {
            "llm.provider": config.get("llm.provider"),
            "llm.model": config.get("llm.model"),
            "llm.openai_active_profile": config.get("llm.openai_active_profile"),
        }
        try:
            # Switch OpenAI profile before model so local-backend heal cannot
            # rewrite a cloud model id back to the Ollama/oMLX default.
            if target.get("profile_id"):
                try:
                    config.set_openai_active_profile(str(target["profile_id"]))
                except Exception:
                    pass
            elif provider == "openai":
                try:
                    config.set_openai_active_profile("openai_cloud")
                except Exception:
                    pass
            config.set("llm.provider", provider)
            config.set("llm.model", model_id)
            chat = build_chat_model(config, streaming=False)
            text = _invoke_hi(chat, with_tools=bool(args.with_tools))
            results.append(
                {
                    **target,
                    "ok": True,
                    "preview": text,
                    "error": None,
                }
            )
            print(f"  ok: {text[:80]!r}", file=sys.stderr, flush=True)
        except Exception as exc:
            results.append(
                {
                    **target,
                    "ok": False,
                    "preview": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"  FAIL: {exc}", file=sys.stderr, flush=True)
            if os_environ_debug():
                traceback.print_exc(file=sys.stderr)
        finally:
            for key, value in previous.items():
                if value is None:
                    continue
                try:
                    config.set(key, value)
                except Exception:
                    pass

    passed = sum(1 for row in results if row["ok"])
    failed = len(results) - passed
    summary = {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "with_tools": bool(args.with_tools),
        "results": results,
    }
    print(json.dumps(summary, indent=2))
    print(f"\n{passed}/{len(results)} passed, {failed} failed", file=sys.stderr)
    return 0 if failed == 0 else 1


def os_environ_debug() -> bool:
    import os

    return os.environ.get("VERIFY_MODELS_DEBUG", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


if __name__ == "__main__":
    raise SystemExit(main())
