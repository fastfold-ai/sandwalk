"""Tests for the TraceRenderer and helper functions."""

from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from ui.traces import TraceRenderer, format_args, format_duration, truncate_output


# ---------------------------------------------------------------------------
# format_args
# ---------------------------------------------------------------------------

class TestFormatArgs:
    def test_empty(self):
        assert format_args(None) == ""
        assert format_args({}) == ""

    def test_basic(self):
        result = format_args({"gene": "CRBN", "top_n": 20})
        assert 'gene="CRBN"' in result
        assert "top_n=20" in result

    def test_omits_private_keys(self):
        result = format_args({"gene": "CRBN", "_session": "obj", "_prior": {}})
        assert "gene" in result
        assert "_session" not in result
        assert "_prior" not in result

    def test_truncates_long_values(self):
        long_val = "C" * 100
        result = format_args({"smiles": long_val}, max_value_len=50)
        assert "..." in result
        assert len(result) < 200

    def test_non_string_values(self):
        result = format_args({"n": 10, "flag": True})
        assert "n=10" in result
        assert "flag=True" in result


# ---------------------------------------------------------------------------
# truncate_output
# ---------------------------------------------------------------------------

class TestTruncateOutput:
    def test_empty(self):
        assert truncate_output("") == ""

    def test_short_text_unchanged(self):
        text = "Found 20 co-essential genes."
        assert truncate_output(text) == text

    def test_long_text_truncated(self):
        text = "A" * 500
        result = truncate_output(text, max_chars=200)
        assert result.startswith("A" * 200)
        assert "500 chars total" in result

    def test_exact_boundary(self):
        text = "B" * 200
        assert truncate_output(text, max_chars=200) == text


# ---------------------------------------------------------------------------
# TraceRenderer
# ---------------------------------------------------------------------------

def _captured_console():
    """Create a Console that captures output to a StringIO buffer.

    Uses ``no_color=True`` so assertions can match plain text.
    """
    buf = StringIO()
    console = Console(file=buf, no_color=True, width=120)
    return console, buf


class TestTraceRendererStart:
    def test_contains_tool_name(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_tool_start("target.coessentiality", {"gene": "CRBN"})
        output = buf.getvalue()
        assert "target.coessentiality" in output

    def test_contains_args(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_tool_start("target.coessentiality", {"gene": "CRBN"})
        output = buf.getvalue()
        assert "CRBN" in output

    def test_running_indicator(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_tool_start("target.coessentiality")
        output = buf.getvalue()
        assert "\u25b8" in output  # ▸

    def test_strips_mcp_prefix(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_tool_start("mcp__ct-tools__target.coessentiality")
        output = buf.getvalue()
        assert "mcp__ct-tools__" not in output
        assert "target.coessentiality" in output


class TestTraceRendererComplete:
    def test_contains_tool_name_and_timing(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_tool_complete(
            "target.coessentiality",
            {"gene": "CRBN"},
            "Found 20 co-essential genes.",
            2.3,
        )
        output = buf.getvalue()
        assert "target.coessentiality" in output
        assert "2.3s" in output

    def test_contains_result_summary(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_tool_complete(
            "target.coessentiality",
            {},
            "Found 20 co-essential genes. Top: COPS5, DDB1",
            1.0,
        )
        output = buf.getvalue()
        assert "Found 20" in output

    def test_checkmark_indicator(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_tool_complete("tool.name", {}, "result", 1.0)
        output = buf.getvalue()
        assert "\u2713" in output  # ✓

    def test_truncates_long_result(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_tool_complete("tool.name", {}, "X" * 500, 1.0)
        output = buf.getvalue()
        assert "500 chars total" in output


class TestTraceRendererError:
    def test_contains_tool_name_and_error(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_tool_error(
            "expression.pathway_enrichment",
            "API key missing",
        )
        output = buf.getvalue()
        assert "expression.pathway_enrichment" in output
        assert "API key missing" in output

    def test_error_indicator(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_tool_error("tool.name", "error")
        output = buf.getvalue()
        assert "\u2717" in output  # ✗


class TestTraceRendererReasoning:
    def test_render_reasoning_uses_markdown_helper(self):
        console, _ = _captured_console()
        renderer = TraceRenderer(console, config={"ui.mermaid.enabled": True})
        with patch("ui.traces.print_markdown_with_mermaid") as mock_print:
            renderer.render_reasoning("reasoning text")
        mock_print.assert_called_once_with(
            console,
            "reasoning text",
            config={"ui.mermaid.enabled": True},
        )


class TestFormatDuration:
    def test_subsecond_shows_ms(self):
        assert format_duration(0.042) == "42ms"
        assert format_duration(0.0) == "0ms"

    def test_seconds(self):
        assert format_duration(2.34) == "2.3s"

    def test_minutes(self):
        assert format_duration(65) == "1m 5s"

    def test_negative_clamped(self):
        assert format_duration(-5) == "0ms"


class TestRenderTodos:
    def test_renders_checklist_with_statuses(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_todos([
            {"content": "done step", "status": "completed"},
            {"content": "active step", "status": "in_progress"},
            {"content": "later step", "status": "pending"},
            {"content": "weird", "status": "bogus"},
        ])
        output = buf.getvalue()
        assert "todos" in output
        assert "1/4" in output
        assert "done step" in output
        assert "active step" in output
        assert "[x]" in output
        assert "[~]" in output

    def test_ignores_empty_or_non_list(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_todos(None)
        renderer.render_todos([])
        renderer.render_todos("not a list")
        assert buf.getvalue() == ""

    def test_skips_non_dict_and_blank_entries(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_todos(["skip", {"content": "", "status": "pending"}, {"content": "keep"}])
        output = buf.getvalue()
        assert "keep" in output


class TestRenderReasoningEdgeCases:
    def test_empty_text_noop(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_reasoning("   ")
        assert buf.getvalue() == ""

    def test_markdown_failure_falls_back_to_plain_print(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        with patch("ui.traces.print_markdown_with_mermaid", side_effect=RuntimeError("boom")):
            renderer.render_reasoning("plain reasoning")
        assert "plain reasoning" in buf.getvalue()


class TestRenderTaskEvents:
    def test_render_task_started(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_task_started("task-1", "folding job", task_type="fold")
        output = buf.getvalue()
        assert "task-1" in output
        assert "fold" in output
        assert "folding job" in output

    def test_render_task_progress_with_usage(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_task_progress(
            "task-2",
            "running",
            usage={"total_tokens": 1234, "tool_uses": 7},
            last_tool_name="fold.create",
        )
        output = buf.getvalue()
        assert "task-2" in output
        assert "1234 tokens" in output
        assert "7 tool calls" in output
        assert "fold.create" in output

    def test_render_task_notification_completed(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_task_notification("task-3", "completed", "all done", "/tmp/out.txt")
        output = buf.getvalue()
        assert "\u2713" in output
        assert "completed" in output
        assert "all done" in output
        assert "/tmp/out.txt" in output

    def test_render_task_notification_failed_and_other(self):
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_task_notification("task-4", "failed")
        renderer.render_task_notification("task-5", "running")
        output = buf.getvalue()
        assert "\u2717" in output
        assert "\u25a0" in output


class TestTraceRendererSnapshot:
    """Snapshot test: render a sequence of traces and compare to golden file."""

    @staticmethod
    def _render_sequence():
        console, buf = _captured_console()
        renderer = TraceRenderer(console)
        renderer.render_tool_start("target.coessentiality", {"gene": "CRBN"})
        renderer.render_tool_complete(
            "target.coessentiality",
            {"gene": "CRBN"},
            "Found 20 co-essential genes.",
            2.3,
        )
        renderer.render_tool_error(
            "expression.pathway_enrichment",
            "API key missing",
        )
        return buf.getvalue()

    def test_snapshot_matches(self, tmp_path):
        """Generate golden file on first run, compare on subsequent runs."""
        import pathlib
        golden_path = pathlib.Path(__file__).parent / "fixtures" / "trace_snapshot.txt"
        output = self._render_sequence()

        if not golden_path.exists():
            golden_path.parent.mkdir(parents=True, exist_ok=True)
            golden_path.write_text(output)
            pytest.skip("Golden file created — rerun to compare")

        expected = golden_path.read_text()
        assert output == expected, (
            f"Trace output changed. Delete {golden_path} to regenerate.\n"
            f"Got:\n{output}\nExpected:\n{expected}"
        )
