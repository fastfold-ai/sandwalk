"""Tests for Agent vs Plan mode prompt helpers."""

from __future__ import annotations

from pathlib import Path

from agent.system_prompt.mode_section import build_mode_section, list_recent_plan_files


def test_build_mode_section_plan_requires_mermaid_and_todos():
    text = build_mode_section(plan_mode=True, workspace_path="/tmp/ws")
    assert "Active Mode: Plan mode" in text
    assert "write_todos" in text
    assert "```mermaid" in text
    assert "flowchart TD" in text
    assert "/tmp/ws/plans" in text
    assert "Do not execute the plan" in text


def test_build_mode_section_agent_lists_pending_plans(tmp_path: Path):
    plans = tmp_path / "plans"
    plans.mkdir()
    older = plans / "older.md"
    newer = plans / "newer.md"
    older.write_text("# Older\n", encoding="utf-8")
    newer.write_text("# Newer\n", encoding="utf-8")
    # Ensure newer is newer by mtime.
    older.touch()
    newer.write_text("# Newer plan\n", encoding="utf-8")

    listed = list_recent_plan_files(str(tmp_path))
    assert listed[0] == "plans/newer.md"
    text = build_mode_section(plan_mode=False, workspace_path=str(tmp_path))
    assert "Active Mode: Agent mode" in text
    assert "plans/newer.md" in text
