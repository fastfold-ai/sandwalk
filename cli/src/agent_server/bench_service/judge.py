"""LLM judge + checklist heuristics for agent bench rows."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def heuristic_checklist(
    tool_names: list[str],
    checklist: list[dict[str, Any]],
) -> dict[str, bool]:
    """Pass checklist items that only require tool-name matches."""
    joined = " ".join(tool_names).lower()
    out: dict[str, bool] = {}
    for item in checklist:
        item_id = str(item.get("id") or "")
        if not item_id:
            continue
        if item.get("judge"):
            continue
        patterns = [str(x).lower() for x in (item.get("require_tools") or [])]
        if not patterns:
            continue
        ok = False
        for pat in patterns:
            if pat.endswith("*"):
                prefix = pat[:-1]
                if any(t.lower().startswith(prefix) or prefix in t.lower() for t in tool_names):
                    ok = True
                    break
            elif pat in joined:
                ok = True
                break
        out[item_id] = ok
    return out


def run_llm_judge(
    *,
    evidence: str,
    ideal: str | None,
    rubric: str | None,
    checklist: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Ask the configured chat model to score evidence. Best-effort."""
    try:
        from agent.config import Config
        from agent.deepagents_runtime.chat_model import build_chat_model
    except Exception as exc:  # noqa: BLE001
        logger.warning("judge import failed: %s", exc)
        return {"overall_pass": False, "error": str(exc), "items": []}

    config = Config.load()
    model = build_chat_model(config)
    checklist = checklist or []
    rubric_text = (rubric or "").strip()
    if not rubric_text and ideal:
        rubric_text = f"The correct answer is approximately: {ideal}"
    if not rubric_text and checklist:
        rubric_text = "Checklist:\n" + "\n".join(
            f"- {item.get('id')}: {item.get('description') or item.get('id')}"
            for item in checklist
        )
    prompt = (
        "You are grading an agent transcript for a benchmark. "
        "Return ONLY JSON: "
        '{"overall_pass": bool, "items": [{"id": str, "pass": bool, "reason": str}], '
        '"predicted": str}.\n\n'
        f"Rubric:\n{rubric_text}\n\n"
        f"Evidence:\n{evidence[:12000]}\n"
    )
    try:
        # LangChain chat models
        resp = model.invoke(prompt)
        text = getattr(resp, "content", None) or str(resp)
        if isinstance(text, list):
            text = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in text
            )
        return _parse_judge_json(str(text))
    except Exception as exc:  # noqa: BLE001
        logger.warning("judge call failed: %s", exc)
        return {"overall_pass": False, "error": str(exc), "items": []}


def _parse_judge_json(text: str) -> dict[str, Any]:
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return {"overall_pass": False, "items": [], "raw": text[:2000]}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"overall_pass": False, "items": [], "raw": text[:2000]}
    if not isinstance(data, dict):
        return {"overall_pass": False, "items": [], "raw": text[:2000]}
    data.setdefault("overall_pass", False)
    data.setdefault("items", [])
    return data


def collect_tool_names_from_events(events: list[Any]) -> list[str]:
    names: list[str] = []
    for event in events:
        et = getattr(event, "type", None) or (event.get("type") if isinstance(event, dict) else None)
        payload = getattr(event, "payload", None)
        if payload is None and isinstance(event, dict):
            payload = event.get("payload")
        if et in {"tool.started", "tool.completed", "tool_call"} and isinstance(payload, dict):
            name = payload.get("name") or payload.get("tool")
            if name:
                names.append(str(name))
    return names
