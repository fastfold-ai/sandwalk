"""Collect HITL decisions from CLI prompts or the headless approval broker."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from agent.hitl.broker import get_approval_broker
from agent.hitl.cli_prompt import collect_cli_decisions

logger = logging.getLogger("hitl")

ProgressCallback = Callable[..., None] | None


def collect_decisions_for_interrupt(
    *,
    session_id: str | None,
    action_requests: list[dict[str, Any]],
    review_configs: list[dict[str, Any]],
    headless: bool,
    progress_callback: ProgressCallback = None,
    console: Any = None,
    interrupt_id: str | None = None,
) -> list[dict[str, Any]]:
    """Block until the human provides decisions for a pending interrupt."""
    if not headless:
        return collect_cli_decisions(
            action_requests=action_requests,
            review_configs=review_configs,
            console=console,
        )

    sid = (session_id or "").strip()
    if not sid:
        # Headless without session cannot wait on the UI — reject safely.
        from agent.hitl.decisions import build_reject, validate_decisions

        return validate_decisions(
            [
                build_reject(
                    "Headless run has no session_id for approvals; "
                    "skill install/remove was rejected."
                )
                for _ in action_requests
            ],
            action_requests=action_requests,
            review_configs=review_configs,
        )

    broker = get_approval_broker()
    iid = broker.begin(
        sid,
        action_requests=action_requests,
        review_configs=review_configs,
        interrupt_id=interrupt_id,
    )
    if progress_callback is not None:
        try:
            progress_callback(
                "approval_required",
                interrupt_id=iid,
                action_requests=action_requests,
                review_configs=review_configs,
            )
        except Exception:  # noqa: BLE001
            logger.debug("approval_required progress callback failed", exc_info=True)
    return broker.wait(sid)
