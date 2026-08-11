"""Interactive terminal collector for HITL decisions."""

from __future__ import annotations

import json
import sys
from typing import Any

from agent.hitl.decisions import (
    build_approve,
    build_edit,
    build_reject,
    build_respond,
    validate_decisions,
)


def _stdin_is_tty() -> bool:
    try:
        return bool(sys.stdin and sys.stdin.isatty())
    except Exception:  # noqa: BLE001
        return False


def _prompt_line(prompt: str) -> str:
    try:
        from prompt_toolkit import PromptSession

        return PromptSession().prompt(prompt)
    except ImportError:
        pass
    except (EOFError, KeyboardInterrupt) as exc:
        raise InterruptedError("Approval cancelled.") from exc
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt) as exc:
        raise InterruptedError("Approval cancelled.") from exc


def _allowed_letters(allowed: list[str]) -> list[tuple[str, str]]:
    mapping = [
        ("a", "approve"),
        ("aa", "approve-remaining"),
        ("e", "edit"),
        ("r", "reject"),
        ("s", "respond"),
    ]
    out: list[tuple[str, str]] = []
    for letter, name in mapping:
        if name == "approve-remaining":
            if "approve" in allowed:
                out.append((letter, name))
            continue
        if name in allowed:
            out.append((letter, name))
    return out


def collect_cli_decisions(
    *,
    action_requests: list[dict[str, Any]],
    review_configs: list[dict[str, Any]],
    console: Any = None,
) -> list[dict[str, Any]]:
    """Prompt for one decision per action; auto-reject when stdin is not a TTY."""
    if not _stdin_is_tty():
        decisions = [
            build_reject(
                "Non-interactive session: skill install/remove requires approval. "
                "Re-run in an interactive terminal or use the desktop UI."
            )
            for _ in action_requests
        ]
        return validate_decisions(
            decisions,
            action_requests=action_requests,
            review_configs=review_configs,
        )

    def emit(msg: str) -> None:
        if console is not None and hasattr(console, "print"):
            console.print(msg)
        else:
            print(msg)

    configs_by_name = {
        str(cfg.get("action_name") or ""): cfg for cfg in (review_configs or [])
    }
    raw_decisions: list[dict[str, Any]] = []
    for index, action in enumerate(action_requests):
        name = str(action.get("name") or "tool")
        args = action.get("args") if isinstance(action.get("args"), dict) else {}
        cfg = configs_by_name.get(name) or {}
        allowed = [str(x) for x in (cfg.get("allowed_decisions") or ["approve", "edit", "reject"])]
        letters = _allowed_letters(allowed)
        emit("")
        emit(f"[HITL] Action {index + 1}/{len(action_requests)}: {name}")
        try:
            emit(f"  args: {json.dumps(args, indent=2, default=str)}")
        except Exception:  # noqa: BLE001
            emit(f"  args: {args!r}")
        hint = " / ".join(f"[{letter}]{label}" for letter, label in letters)
        while True:
            choice = _prompt_line(f"  Decision {hint}: ").strip().lower()
            matched = next((label for letter, label in letters if choice in {letter, label}), None)
            if matched is None:
                emit(f"  Enter one of: {', '.join(label for _, label in letters)}")
                continue
            if matched == "approve":
                raw_decisions.append(build_approve())
                break
            if matched == "approve-remaining":
                raw_decisions.append(build_approve(scope="remaining"))
                break
            if matched == "reject":
                reason = _prompt_line("  Reject reason (optional): ").strip()
                raw_decisions.append(build_reject(reason or None))
                break
            if matched == "respond":
                message = _prompt_line("  Response message: ").strip()
                raw_decisions.append(build_respond(message))
                break
            # edit
            emit("  Enter JSON object for tool args (single line or paste):")
            default = json.dumps(args, default=str)
            emit(f"  default: {default}")
            raw = _prompt_line("  args> ").strip() or default
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                emit(f"  Invalid JSON: {exc}")
                continue
            if not isinstance(parsed, dict):
                emit("  Args must be a JSON object.")
                continue
            raw_decisions.append(build_edit(name=name, args=parsed))
            break

    return validate_decisions(
        raw_decisions,
        action_requests=action_requests,
        review_configs=review_configs,
    )
