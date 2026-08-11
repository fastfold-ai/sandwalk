"""Markdown theme + local path unwrapping for the transcript TUI."""

from __future__ import annotations

from ui.markdown.links import expose_markdown_links, strip_osc8_hyperlinks
from ui.markdown.paths import (
    looks_like_local_path,
    resolve_local_path,
    unwrap_path_code_spans,
)
from ui.markdown.theme import markdown_rich_theme


def test_markdown_code_theme_drops_on_black_chip():
    light = markdown_rich_theme("light")
    dark = markdown_rich_theme("dark")
    assert "on black" not in str(light.styles["markdown.code"]).lower()
    assert "on black" not in str(dark.styles["markdown.code"]).lower()
    assert "#0284c7" in str(light.styles["markdown.code"])
    assert "#7dd3fc" in str(dark.styles["markdown.code"])


def test_looks_like_local_path():
    assert looks_like_local_path("artifacts/fold/job/model.cif")
    assert looks_like_local_path("/tmp/out.cif")
    assert looks_like_local_path("~/Projects/sandwalk/cli/x.pdb")
    assert not looks_like_local_path("artifacts/fold/1e4200a0-...")
    assert not looks_like_local_path("https://cloud.fastfold.ai/job/1")
    assert not looks_like_local_path("/help")


def test_unwrap_path_code_spans_expands_workspace_relative(tmp_path):
    ws = tmp_path / "session"
    ws.mkdir()
    text = "Saved to `artifacts/fold/job/model_0.cif` and `/help` stays code."
    out = unwrap_path_code_spans(text, workspace=str(ws))
    assert str(ws / "artifacts/fold/job/model_0.cif") in out
    assert "`/help`" in out
    assert looks_like_local_path("/help") is False


def test_resolve_local_path_absolute():
    assert resolve_local_path("/tmp/a.cif").endswith("a.cif")


def test_expose_markdown_links_shows_bare_url():
    text = (
        "- [Dashboard / Viewer](https://cloud.fastfold.ai/job/abc?shared=true)\n"
        "- [Primary CIF](https://artifacts.fastfold.ai/x/output.cif)"
    )
    out = expose_markdown_links(text)
    assert "8;id=" not in out
    assert "Dashboard / Viewer: https://cloud.fastfold.ai/job/abc?shared=true" in out
    assert "Primary CIF: https://artifacts.fastfold.ai/x/output.cif" in out
    assert "](" not in out


def test_strip_osc8_hyperlinks_removes_rich_wrappers():
    raw = (
        "\x1b]8;id=144809;https://cloud.fastfold.ai/job/abc?shared=true\x1b\\"
        "\x1b[4mDashboard / Viewer\x1b[0m"
        "\x1b]8;;\x1b\\"
    )
    out = strip_osc8_hyperlinks(raw)
    assert "8;id=" not in out
    assert "https://cloud.fastfold.ai" not in out  # URL was only in OSC payload
    assert "Dashboard / Viewer" in out


def test_markdown_to_styled_lines_no_osc8_garbage():
    from ui.terminal.transcript.render import markdown_to_styled_lines

    lines = markdown_to_styled_lines(
        "- [Dashboard / Viewer](https://cloud.fastfold.ai/job/abc?shared=true)",
        width=100,
        colored=True,
    )
    plain = "\n".join("".join(t for _s, t in frags) for frags in lines)
    assert "8;id=" not in plain
    assert "8;;" not in plain
    assert "https://cloud.fastfold.ai/job/abc?shared=true" in plain
    assert "Dashboard / Viewer" in plain
