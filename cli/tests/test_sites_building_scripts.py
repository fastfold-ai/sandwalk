"""Focused tests for the bundled sites-building helpers."""

from pathlib import Path

import pytest

from skills.sites_building.scripts import (
    build_site,
    copy_attachments,
    init_site,
    validate_site,
)


def test_initialize_static_and_vite_templates(tmp_path):
    static = tmp_path / "static"
    created = init_site.initialize(static, "static")
    assert created == ["src/index.html", "src/styles.css"]
    assert "Skip to content" in (static / "src/index.html").read_text(encoding="utf-8")

    vite = tmp_path / "vite"
    created = init_site.initialize(vite, "vite-react")
    assert "package.json" in created
    assert "src/App.jsx" in created
    assert 'base: "./"' in (vite / "vite.config.js").read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="target is not empty"):
        init_site.initialize(static, "static")


def test_copy_attachments_uses_local_assets_and_handles_collisions(tmp_path):
    project = tmp_path / "site"
    init_site.initialize(project, "static")
    first = tmp_path / "one" / "result plot.png"
    second = tmp_path / "two" / "result plot.png"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    copied = copy_attachments.copy_attachments(project, [first, second])

    assert copied[0]["path"] == "assets/result-plot.png"
    assert copied[1]["path"].startswith("assets/result-plot-")
    assert copied[0]["sha256"] != copied[1]["sha256"]
    for item in copied:
        assert (project / "src" / item["path"]).read_bytes() in {b"first", b"second"}


def test_build_static_site_and_validate_local_references(tmp_path):
    project = tmp_path / "site"
    init_site.initialize(project, "static")
    assets = project / "src" / "assets"
    assets.mkdir()
    (assets / "figure.png").write_bytes(b"image")
    index = project / "src" / "index.html"
    index.write_text(
        index.read_text(encoding="utf-8").replace(
            "</main>",
            '<img src="assets/figure.png" alt="Result summary" width="40" height="30">\n'
            "</main>",
        ),
        encoding="utf-8",
    )

    kind, dist = build_site.build(project)

    assert kind == "static"
    assert dist == project / "dist"
    assert validate_site.validate(dist) == []


def test_validate_reports_missing_and_unsafe_references(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        """
        <!doctype html>
        <link rel="stylesheet" href="missing.css">
        <img src="../outside.png" alt="">
        <div style="background-image: url('/root.png')"></div>
        """,
        encoding="utf-8",
    )

    errors = validate_site.validate(dist)

    assert any("missing local asset: 'missing.css'" in error for error in errors)
    assert any("contains parent traversal" in error for error in errors)
    assert any("must be relative, not root-relative" in error for error in errors)


def test_validate_requires_dist_index(tmp_path):
    errors = validate_site.validate(tmp_path / "dist")
    assert len(errors) == 1
    assert "missing required entry point" in errors[0]
