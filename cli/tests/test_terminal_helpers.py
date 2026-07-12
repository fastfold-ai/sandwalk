"""Tests for module-level helper functions in ui/terminal.py."""

from unittest.mock import patch

import pytest

from ui.terminal import (  # type: ignore[import-untyped]
    DATASET_CANDIDATES,
    _extract_llm_suggestions,
    _get_workflow_names,
    _is_openai_managed_base_url,
    build_mention_context,
    extract_mentions,
)


class TestIsOpenaiManagedBaseUrl:
    def test_empty_or_none_is_managed(self):
        assert _is_openai_managed_base_url(None) is True
        assert _is_openai_managed_base_url("") is True
        assert _is_openai_managed_base_url("   ") is True

    def test_openai_hosts(self):
        assert _is_openai_managed_base_url("https://api.openai.com/v1") is True
        assert _is_openai_managed_base_url("https://gateway.openai.com/v1") is True
        assert _is_openai_managed_base_url("https://foo.bar.openai.com/v1") is True

    def test_custom_hosts_not_managed(self):
        assert _is_openai_managed_base_url("http://localhost:11434/v1") is False
        assert _is_openai_managed_base_url("http://ai-server.tailnet:8888/v1") is False
        assert _is_openai_managed_base_url("https://api.together.xyz/v1") is False

    def test_malformed_url_returns_false(self):
        assert _is_openai_managed_base_url("not-a-url") is False


class TestGetWorkflowNames:
    def test_loads_from_workflows_module(self):
        with patch("agent.workflows.WORKFLOWS", {"target_validation": {}, "compound_safety": {}}):
            names = _get_workflow_names()
        assert names == frozenset({"target_validation", "compound_safety"})

    def test_returns_nonempty_when_workflows_available(self):
        names = _get_workflow_names()
        assert isinstance(names, frozenset)
        assert len(names) >= 1


class TestExtractMentions:
    def test_tool_mentions(self):
        query, tools, datasets, workflows = extract_mentions(
            "Run @target.druggability on @depmap for TP53"
        )
        assert "target.druggability" in tools
        assert "depmap" in datasets
        assert "TP53" in query
        assert workflows == []

    def test_workflow_mention(self):
        with patch(
            "ui.terminal._get_workflow_names",
            return_value=frozenset({"target_validation"}),
        ):
            query, tools, datasets, workflows = extract_mentions(
                "Please run @target_validation workflow"
            )
        assert "target_validation" in workflows
        assert "workflow" in query.lower() or query == "Please run workflow"

    def test_strips_mentions_and_collapses_spaces(self):
        query, _, _, _ = extract_mentions("  @prism   @safety.classify   check   cpd_A  ")
        assert "@" not in query
        assert "  " not in query
        assert query == "check cpd_A"

    def test_dataset_candidates_registered(self):
        names = {d[0] for d in DATASET_CANDIDATES}
        assert "depmap" in names
        assert "prism" in names


class TestBuildMentionContext:
    def test_tools_section(self):
        ctx = build_mention_context(["target.druggability"], [], [])
        assert "target.druggability" in ctx
        assert "MUST include" in ctx

    def test_datasets_section(self):
        ctx = build_mention_context([], ["depmap"], [])
        assert "depmap" in ctx
        assert "DepMap" in ctx

    def test_workflows_section(self):
        fake_wf = {
            "target_validation": {
                "description": "Validate a potential drug target",
                "steps": [{"tool": "target.coessentiality"}, {"tool": "literature.pubmed_search"}],
            }
        }
        with patch("agent.workflows.WORKFLOWS", fake_wf):
            ctx = build_mention_context([], [], ["target_validation"])
        assert "target_validation" in ctx
        assert "target.coessentiality" in ctx

    def test_empty_inputs(self):
        assert build_mention_context([], [], []) == ""

    def test_workflow_missing_entry_ignored(self):
        with patch("agent.workflows.WORKFLOWS", {}):
            ctx = build_mention_context([], [], ["target_validation"])
        assert ctx == ""


class TestExtractLlmSuggestions:
    def test_extracts_bullets_from_suggested_next_steps(self):
        text = """
## Analysis Summary
Some findings here.

## Suggested Next Steps
- Profile **"TP53 dependency in AML"** across lineages
- Run combination synergy for venetoclax pairs
- 1. Validate biomarker panel with external cohort
"""
        suggestions = _extract_llm_suggestions(text)
        assert len(suggestions) >= 2
        assert any("TP53" in s for s in suggestions)

    def test_extracts_quoted_follow_up_items(self):
        text = """
**Suggested next steps**
* Explore **"BRAF V600E resistance mechanisms"** in melanoma
"""
        suggestions = _extract_llm_suggestions(text)
        assert any("BRAF" in s for s in suggestions)

    def test_stops_at_next_heading(self):
        text = """
## Follow-up Questions
- First actionable query about KRAS G12C inhibitors

## References
- Paper one
"""
        suggestions = _extract_llm_suggestions(text)
        assert len(suggestions) <= 5
        assert all("References" not in s for s in suggestions)

    def test_empty_or_no_section(self):
        assert _extract_llm_suggestions("No suggestions here.") == []
        assert _extract_llm_suggestions("") == []

    def test_caps_at_five_suggestions(self):
        lines = "\n".join(f"- Suggestion number {i} with enough text" for i in range(10))
        text = f"## Suggested Next Steps\n{lines}"
        assert len(_extract_llm_suggestions(text)) <= 5
