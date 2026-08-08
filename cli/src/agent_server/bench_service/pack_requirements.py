"""Check pack coverage skills/MCPs against the local install."""

from __future__ import annotations

from typing import Any


def required_skills_mcps(pack: Any) -> tuple[list[str], list[str]]:
    """Return required skill/MCP ids from pack coverage (or question union)."""
    raw = getattr(pack, "raw", None) or {}
    coverage = raw.get("coverage") if isinstance(raw, dict) else None
    coverage = coverage if isinstance(coverage, dict) else {}
    skills = [str(item).strip() for item in (coverage.get("skills") or []) if str(item).strip()]
    mcps = [str(item).strip() for item in (coverage.get("mcps") or []) if str(item).strip()]
    if not skills:
        skills = sorted(
            {
                str(name).strip()
                for question in (getattr(pack, "questions", None) or [])
                for name in (getattr(question, "skills", None) or [])
                if str(name).strip()
            }
        )
    if not mcps:
        mcps = sorted(
            {
                str(name).strip()
                for question in (getattr(pack, "questions", None) or [])
                for name in (getattr(question, "mcps", None) or [])
                if str(name).strip()
            }
        )
    return skills, mcps


def missing_pack_requirements(
    pack: Any,
    *,
    store: Any | None = None,
) -> tuple[list[str], list[str]]:
    """Return (missing_skills, missing_mcps) that are not installed+enabled."""
    required_skills, required_mcps = required_skills_mcps(pack)
    if not required_skills and not required_mcps:
        return [], []

    ready_skills = _enabled_skill_names()
    ready_mcps = _enabled_mcp_ids(store)

    missing_skills = [
        name for name in required_skills if name.lower() not in ready_skills
    ]
    missing_mcps = [name for name in required_mcps if name.lower() not in ready_mcps]
    return missing_skills, missing_mcps


def skip_warning_message(
    missing_skills: list[str],
    missing_mcps: list[str],
) -> str | None:
    """Soft catalog warning: suite stays runnable; matching questions are skipped."""
    if not missing_skills and not missing_mcps:
        return None
    bits: list[str] = []
    if missing_mcps:
        bits.append(f"MCPs: {', '.join(missing_mcps)}")
    if missing_skills:
        bits.append(f"skills: {', '.join(missing_skills)}")
    detail = "; ".join(bits)
    return (
        f"Missing {detail}. Questions that require them will be skipped."
    )


def question_missing_requirements(
    question: Any,
    *,
    ready_skills: set[str] | None = None,
    ready_mcps: set[str] | None = None,
    store: Any | None = None,
) -> tuple[list[str], list[str]]:
    """Per-question missing skill/MCP names (empty ⇒ runnable)."""
    skills_ready = ready_skills if ready_skills is not None else _enabled_skill_names()
    mcps_ready = ready_mcps if ready_mcps is not None else _enabled_mcp_ids(store)
    need_skills = [
        str(name).strip()
        for name in (getattr(question, "skills", None) or [])
        if str(name).strip()
    ]
    need_mcps = [
        str(name).strip()
        for name in (getattr(question, "mcps", None) or [])
        if str(name).strip()
    ]
    miss_skills = [name for name in need_skills if name.lower() not in skills_ready]
    miss_mcps = [name for name in need_mcps if name.lower() not in mcps_ready]
    return miss_skills, miss_mcps


def partition_cells_by_requirements(
    cells: list[Any],
    *,
    store: Any | None = None,
) -> tuple[list[Any], list[dict[str, Any]]]:
    """Split matrix cells into runnable vs skipped (missing skill/MCP)."""
    ready_skills = _enabled_skill_names()
    ready_mcps = _enabled_mcp_ids(store)
    runnable: list[Any] = []
    skipped: list[dict[str, Any]] = []
    for cell in cells:
        question = getattr(cell, "question", None)
        if question is None:
            runnable.append(cell)
            continue
        miss_skills, miss_mcps = question_missing_requirements(
            question,
            ready_skills=ready_skills,
            ready_mcps=ready_mcps,
        )
        if not miss_skills and not miss_mcps:
            runnable.append(cell)
            continue
        reason_bits: list[str] = []
        if miss_mcps:
            reason_bits.append(f"MCPs: {', '.join(miss_mcps)}")
        if miss_skills:
            reason_bits.append(f"skills: {', '.join(miss_skills)}")
        skipped.append(
            {
                "cell": cell,
                "missing_skills": miss_skills,
                "missing_mcps": miss_mcps,
                "reason": "Missing " + "; ".join(reason_bits),
            }
        )
    return runnable, skipped


def _enabled_skill_names() -> set[str]:
    try:
        from agent.skills import list_skills

        skills = list(list_skills(enabled_only=False))
    except Exception:
        return set()
    ready: set[str] = set()
    for skill in skills:
        name = str(getattr(skill, "name", "") or "").strip()
        if not name:
            continue
        if bool(getattr(skill, "enabled", True)):
            ready.add(name.lower())
    return ready


def _enabled_mcp_ids(store: Any | None) -> set[str]:
    if store is None:
        return set()
    try:
        servers = list(store.list_mcp_servers(enabled_only=False))
    except Exception:
        return set()
    ready: set[str] = set()
    for server in servers:
        if not bool(getattr(server, "enabled", False)):
            continue
        for value in (
            getattr(server, "catalog_id", None),
            getattr(server, "name", None),
            getattr(server, "id", None),
        ):
            text = str(value or "").strip().lower()
            if text:
                ready.add(text)
    return ready
