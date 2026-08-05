"""Tests for click-to-open path/URL detection in the transcript TUI."""

from __future__ import annotations

from unittest.mock import patch

from ui.terminal.path_links import (
    iter_link_spans,
    link_at,
    open_link,
    style_link_spans,
)


def test_iter_link_spans_absolute_path_and_url():
    line = (
        "Exported  /Users/juliocesar/Projects/sandwalk/cli/exports/session.md  "
        "see https://cloud.fastfold.ai/job/abc"
    )
    spans = iter_link_spans(line)
    kinds = [s[2] for s in spans]
    targets = [s[3] for s in spans]
    assert kinds == ["path", "url"]
    assert targets[0].endswith("/exports/session.md")
    assert targets[1].startswith("https://")


def test_iter_link_spans_strips_trailing_punct():
    line = "open /Users/me/file.cif."
    spans = iter_link_spans(line)
    assert len(spans) == 1
    assert spans[0][3] == "/Users/me/file.cif"


def test_link_at_column():
    line = "  /Users/me/a.md  "
    assert link_at(line, 0) is None
    hit = link_at(line, 4)
    assert hit is not None
    assert hit[0] == "path"
    assert hit[1] == "/Users/me/a.md"


def test_style_link_spans_underlines_path():
    plain = "/Users/me/out.md"
    frags = [("", plain)]
    styled = style_link_spans(frags, plain)
    assert any(s == "class:transcript-link" for s, _t in styled)
    assert "".join(t for _s, t in styled) == plain


def test_open_link_url_uses_webbrowser():
    with patch("ui.terminal.path_links.webbrowser.open", return_value=True) as open_web:
        assert open_link("url", "https://example.com") is True
        open_web.assert_called_once_with("https://example.com")


def test_open_link_path_uses_open_on_darwin():
    with (
        patch("ui.terminal.path_links.sys.platform", "darwin"),
        patch("ui.terminal.path_links.subprocess.Popen") as popen,
    ):
        assert open_link("path", "/Users/me/file.md") is True
        popen.assert_called_once()
        assert popen.call_args[0][0][:2] == ["open", "/Users/me/file.md"]
