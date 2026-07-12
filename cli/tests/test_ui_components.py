"""Tests for ui.markdown and ui.status display helpers."""

from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rich.console import Console
from rich.markdown import Markdown

from ui.markdown import (
    LeftMarkdown,
    _neaten_mermaid_source,
    _split_mermaid_fences,
    print_markdown_with_mermaid,
)
from ui.status import SPINNERS, ThinkingStatus, apply_gradient


class TestLeftMarkdown:
    def test_renders_heading(self):
        console = Console(file=StringIO(), force_terminal=True, width=80)
        md = LeftMarkdown("# Title\n\nBody text")
        console.print(md)
        output = console.file.getvalue()
        assert "Title" in output


class TestMermaidMarkdown:
    def test_neaten_mermaid_source_strips_html_and_entities(self):
        source = "\n".join(
            [
                "flowchart TD",
                '    A["All<br/>Binders"] --> B["API<BR>Auth?"]',
                '    B --> C["Tom &amp; Jerry &lt;tag&gt;"]',
            ]
        )
        cleaned = _neaten_mermaid_source(source)
        assert "<br/>" not in cleaned.lower()
        assert "<br>" not in cleaned.lower()
        assert "&amp;" not in cleaned
        assert "All Binders" in cleaned
        assert "API Auth?" in cleaned
        assert "Tom & Jerry" in cleaned

    def test_neaten_mermaid_source_preserves_structure(self):
        source = "flowchart LR\n    A --> B\n    B --> C"
        assert _neaten_mermaid_source(source) == source

    def test_print_markdown_with_mermaid_neatens_before_render(self):
        console = MagicMock()
        captured = {}

        def _fake_render_rich(src, **_kwargs):
            captured["src"] = src
            return "diagram-output"

        with patch("termaid.render_rich", side_effect=_fake_render_rich):
            print_markdown_with_mermaid(
                console,
                '```mermaid\nflowchart TD\n  A["All<br/>Binders"] --> B\n```\n',
            )
        assert "<br/>" not in captured["src"]
        assert "All Binders" in captured["src"]

    def test_split_mermaid_fences(self):
        sections = _split_mermaid_fences(
            "Intro\n```mermaid\ngraph LR\nA-->B\n```\nOutro\n"
        )
        assert sections[0] == ("markdown", "Intro\n")
        assert sections[1][0] == "mermaid"
        assert "graph LR" in sections[1][1]
        assert sections[2] == ("markdown", "Outro\n")

    def test_split_mermaid_fence_unclosed_falls_back_to_markdown(self):
        sections = _split_mermaid_fences("Before\n```mermaid\ngraph LR\nA-->B\n")
        assert len(sections) == 1
        assert sections[0][0] == "markdown"
        assert sections[0][1].startswith("Before\n```mermaid")

    def test_print_markdown_with_mermaid_renders_diagram(self):
        console = MagicMock()
        with patch("termaid.render_rich", return_value="diagram-output"):
            print_markdown_with_mermaid(
                console,
                "Intro\n```mermaid\ngraph LR\nA-->B\n```\n",
            )
        assert any(call.args and call.args[0] == "diagram-output" for call in console.print.call_args_list)

    def test_print_markdown_with_mermaid_fallbacks_to_fence(self):
        console = MagicMock()
        with patch("termaid.render_rich", side_effect=RuntimeError("bad rich")), patch(
            "termaid.render", side_effect=RuntimeError("bad plain")
        ):
            print_markdown_with_mermaid(
                console,
                "```mermaid\ngraph LR\nA-->B\n```\n",
            )
        markdown_calls = [
            call.args[0]
            for call in console.print.call_args_list
            if call.args and isinstance(call.args[0], Markdown)
        ]
        assert markdown_calls
        assert "```mermaid" in markdown_calls[0].markup

    def test_print_markdown_with_mermaid_disabled(self):
        console = MagicMock()
        cfg = SimpleNamespace(
            get=lambda key, default=None: (
                False if key == "ui.mermaid.enabled" else default
            )
        )
        print_markdown_with_mermaid(
            console,
            "```mermaid\ngraph LR\nA-->B\n```\n",
            config=cfg,
        )
        markdown_calls = [
            call.args[0]
            for call in console.print.call_args_list
            if call.args and isinstance(call.args[0], Markdown)
        ]
        assert markdown_calls
        assert "```mermaid" in markdown_calls[0].markup


class TestStatusHelpers:
    def test_apply_gradient_empty(self):
        text = apply_gradient("")
        assert str(text) == ""

    def test_apply_gradient_colored(self):
        text = apply_gradient("Analyzing", elapsed_s=0.5)
        assert "Analyzing" in str(text)

    def test_spinners_defined(self):
        assert "dna_helix" in SPINNERS
        assert len(SPINNERS["dna_helix"]["frames"]) > 0

    def test_thinking_status_context_manager(self, captured_console):
        console, buf = captured_console
        with ThinkingStatus(console, "planning"):
            pass
        # Context manager should complete without error
        assert True
