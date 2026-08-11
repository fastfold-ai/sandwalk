"""Unit tests for /skills modal helpers."""

from __future__ import annotations

from types import SimpleNamespace

from ui.terminal.skills_modal import (
    build_skill_rows,
    first_selectable_index,
    insert_skill_into_compose,
    lean_description,
    run_skills_modal,
    skill_insert_token,
    skill_meta_label,
)


def _skill(
    name: str,
    *,
    enabled: bool = True,
    description: str = "",
    author: str = "",
    version: str = "",
    source: str = "bundled",
):
    return SimpleNamespace(
        name=name,
        enabled=enabled,
        description=description,
        author=author,
        version=version or None,
        source=source,
        category="bundled",
        updated_at="",
        tags=[],
        path=None,
        icon=None,
    )


def test_lean_description_truncates():
    assert lean_description("short") == "short"
    long = "word " * 40
    out = lean_description(long, max_len=20)
    assert len(out) <= 20
    assert out.endswith("…")


def test_skill_meta_label_omits_missing_version_and_author():
    info = _skill("fold", enabled=True, author="", version="", source="bundled")
    # bundled falls back to sandwalk author via display_author
    label = skill_meta_label(info)
    assert label.startswith("on")
    assert "Version not available" not in label


def test_skill_meta_label_includes_author_and_version():
    info = _skill(
        "fold",
        enabled=False,
        author="fastfold-ai",
        version="1.1.5",
        source="fastfold-ai/skills@skills/fold",
    )
    assert skill_meta_label(info) == "off · fastfold-ai · 1.1.5"


def test_build_skill_rows_sections_enabled_disabled():
    skills = [
        _skill("a", enabled=True, description="Alpha skill"),
        _skill("b", enabled=False, description="Beta skill"),
    ]
    rows = build_skill_rows(skills)
    titles = [r.title for r in rows]
    assert titles[0] == "Enabled"
    assert any(r.kind == "skill" and r.title == "a" for r in rows)
    assert "Disabled" in titles
    assert any(r.kind == "skill" and r.title == "b" for r in rows)


def test_build_skill_rows_search_filters():
    skills = [
        _skill("fold", description="protein folding"),
        _skill("md_openmm", description="molecular dynamics"),
    ]
    rows = build_skill_rows(skills, query="protein")
    names = [r.title for r in rows if r.kind == "skill"]
    assert names == ["fold"]


def test_first_selectable_skips_headers():
    skills = [_skill("fold")]
    rows = build_skill_rows(skills)
    assert rows[0].kind == "header"
    assert first_selectable_index(rows) == 1


def test_run_skills_modal_skips_under_pytest():
    assert run_skills_modal(object()) is False


def test_skill_insert_token():
    assert skill_insert_token("fold") == "skill: fold"
    assert skill_insert_token("  md_openmm_calvados ") == "skill: md_openmm_calvados"


def test_insert_skill_into_compose_adds_trailing_space():
    class _Doc:
        text_before_cursor = "hello"

    class _Buf:
        def __init__(self):
            self.document = _Doc()
            self.parts: list[str] = []

        def insert_text(self, text: str) -> None:
            self.parts.append(text)

    buf = _Buf()
    term = SimpleNamespace(_transcript_buffer=buf)
    insert_skill_into_compose(term, "fold")
    assert "".join(buf.parts) == " skill: fold "
