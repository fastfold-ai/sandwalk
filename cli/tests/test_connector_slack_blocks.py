"""Rendering an agent reply as Slack Block Kit.

The live agent already emits correct mrkdwn, so the first duty of the converter
is to leave that alone. The rest guards the limits Block Kit imposes that a
plain text post does not.
"""

from __future__ import annotations

import json

from agent_server.connectors.slack_blocks import (
    MAX_BLOCKS,
    SECTION_LIMIT,
    build_blocks,
    fallback_text,
    split_for_sections,
    to_mrkdwn,
)


class TestToMrkdwn:
    def test_leaves_correct_mrkdwn_untouched(self):
        """What the agent actually sends today must survive unchanged."""
        real = (
            "Hi! I'm a research agent for structural biology / computational "
            "work. Main things I can do:\n\n"
            "• *Protein folding & complexes* — submit jobs to FastFold\n"
            "• *Boltz API workflows* — structure + binding prediction\n"
        )
        assert to_mrkdwn(real) == real

    def test_converts_markdown_bold(self):
        assert to_mrkdwn("a **bold** word") == "a *bold* word"
        assert to_mrkdwn("a __bold__ word") == "a *bold* word"

    def test_converts_links(self):
        assert (
            to_mrkdwn("see [the docs](https://x.dev/a)")
            == "see <https://x.dev/a|the docs>"
        )

    def test_converts_headings_to_bold(self):
        assert to_mrkdwn("## Results\nbody") == "*Results*\nbody"

    def test_converts_bullets(self):
        assert to_mrkdwn("- one\n- two") == "• one\n• two"
        assert to_mrkdwn("  - nested") == "  • nested"

    def test_never_rewrites_inside_code(self):
        source = "run `a **b** c` then:\n\n```\nx = [y](z) ** 2\n```"
        assert to_mrkdwn(source) == source

    def test_wraps_tables_in_code_so_columns_survive(self):
        table = "| a | b |\n| - | - |\n| 1 | 2 |"
        out = to_mrkdwn(table)
        assert out.startswith("```") and out.endswith("```")
        assert "| 1 | 2 |" in out

    def test_a_lone_piped_line_is_not_a_table(self):
        assert "```" not in to_mrkdwn("the | character is fine |")

    def test_is_idempotent(self):
        source = "**bold** and [link](https://x.dev) and - item"
        assert to_mrkdwn(to_mrkdwn(source)) == to_mrkdwn(source)

    def test_empty_input(self):
        assert to_mrkdwn("") == ""


class TestSplitting:
    def test_short_text_is_one_section(self):
        assert split_for_sections("hello") == ["hello"]

    def test_splits_on_paragraph_boundaries(self):
        body = "\n\n".join(["x" * 2000, "y" * 2000])
        parts = split_for_sections(body)
        assert len(parts) == 2
        assert all(len(part) <= SECTION_LIMIT for part in parts)

    def test_merges_short_paragraphs_back_together(self):
        parts = split_for_sections("one\n\ntwo\n\nthree")
        assert parts == ["one\n\ntwo\n\nthree"]

    def test_hard_splits_a_paragraph_with_no_breaks(self):
        parts = split_for_sections("z" * 7000)
        assert len(parts) == 3
        assert all(len(part) <= SECTION_LIMIT for part in parts)
        assert "".join(parts) == "z" * 7000

    def test_prefers_word_boundaries(self):
        parts = split_for_sections(" ".join(["word"] * 1200))
        assert all(len(part) <= SECTION_LIMIT for part in parts)
        assert not any(part.startswith(" ") for part in parts)

    def test_blank_input_yields_nothing(self):
        assert split_for_sections("   \n  ") == []


class TestBuildBlocks:
    def test_produces_a_section(self):
        blocks = build_blocks("hello")
        assert blocks[0]["type"] == "section"
        assert blocks[0]["text"] == {"type": "mrkdwn", "text": "hello"}

    def test_empty_reply_produces_no_blocks(self):
        assert build_blocks("  ") == []

    def test_footer_becomes_a_context_block(self):
        blocks = build_blocks("hi", footer="via Sandwalk")
        assert blocks[-1]["type"] == "context"
        assert blocks[-1]["elements"][0]["text"] == "via Sandwalk"

    def test_view_url_becomes_a_link_button(self):
        """A url button carries no action_id, so it needs no interactivity."""
        blocks = build_blocks("hi", view_url="https://sandwalk.sh/s/1")
        button = next(b for b in blocks if b["type"] == "actions")["elements"][0]
        assert button["url"] == "https://sandwalk.sh/s/1"
        assert "action_id" not in button

    def test_no_button_without_a_url(self):
        assert not any(b["type"] == "actions" for b in build_blocks("hi"))

    def test_never_exceeds_slack_block_cap(self):
        blocks = build_blocks(
            "\n\n".join("x" * 2900 for _ in range(80)),
            footer="f",
            view_url="https://x.dev",
        )
        assert len(blocks) <= MAX_BLOCKS

    def test_says_so_when_it_truncates(self):
        blocks = build_blocks("\n\n".join("x" * 2900 for _ in range(80)))
        assert any(
            "truncated" in str(block.get("elements", "")) for block in blocks
        )

    def test_every_section_is_within_the_limit(self):
        blocks = build_blocks("y" * 20000)
        for block in blocks:
            if block["type"] == "section":
                assert len(block["text"]["text"]) <= SECTION_LIMIT

    def test_output_is_json_serialisable(self):
        """It goes over the wire as JSON, so nothing exotic may leak in."""
        json.dumps(build_blocks("hi", footer="f", view_url="https://x.dev"))


class TestFallbackText:
    def test_mirrors_the_message(self):
        assert fallback_text("**hi**") == "*hi*"

    def test_truncates_for_the_notification(self):
        out = fallback_text("z" * 5000)
        assert len(out) <= 3000
        assert out.endswith("…")
