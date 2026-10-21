"""Capy meta-agent: hidden session, light prompt, management tools."""

from __future__ import annotations

from pathlib import Path

CAPY_SOURCE = "capy"
CAPY_TITLE = "Capy"
CAPY_PROMPT_PATH = Path(__file__).with_name("prompt.txt")

CAPY_TOOL_NAMES = [
    "capy.spawn_sessions",
    "capy.send_message",
    "capy.list_sessions",
    "capy.read_session",
    "capy.summarize_session",
    "capy.seed_session",
    "capy.open_split",
    "capy.skills_list",
    "capy.skills_install",
    "capy.skills_set_enabled",
    "capy.mcp_list",
    "capy.app_status",
    "capy.server_restart",
    "capy.bench_catalog",
    "capy.bench_status",
    "capy.bench_launch",
    "capy.bench_install",
    "capy.bench_results",
    "capy.bench_inspect",
    "capy.doctor",
    "capy.list_projects",
    "capy.create_project",
    "capy.move_session",
    "capy.list_external_sessions",
    "capy.import_external_session",
    "capy.launch_external_agent",
    "capy.handoff_session",
    "capy.list_specialists",
    "capy.memory_search",
    "capy.memory_manage",
    "capy.wiki_digest",
    "capy.distill_session",
    "capy.create_skill_from_memory",
]

# Deep Agents builtins Capy must not see (no sandbox / PTC).
CAPY_EXCLUDED_DEEPAGENTS_TOOLS = frozenset(
    {
        "write_todos",
        "execute",
        "task",
        "ls",
        "read_file",
        "write_file",
        "edit_file",
        "glob",
        "grep",
        "shell",
    }
)

_deps = None


def bind_capy_deps(deps) -> None:
    global _deps
    _deps = deps


def capy_deps():
    if _deps is None:
        raise RuntimeError("Capy is not bound to the agent server.")
    return _deps


def load_capy_prompt() -> str:
    return CAPY_PROMPT_PATH.read_text(encoding="utf-8").strip()


def is_capy_session(session) -> bool:
    return bool(session) and str(getattr(session, "source", "") or "") == CAPY_SOURCE


def hidden_session_sources() -> tuple[str, str]:
    return ("bench", CAPY_SOURCE)
