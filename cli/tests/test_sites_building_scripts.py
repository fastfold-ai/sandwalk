"""Focused tests for the bundled sites-building helpers."""

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
    assert sorted(created) == ["src/index.html", "src/shell.css", "src/styles.css"]
    assert (static / "src" / "shell.css").is_file()

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


def test_build_static_site_and_validate_local_references(tmp_path, monkeypatch):
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
    monkeypatch.setenv("SANDWALK_REPORT_DATE", "2026-07-28")

    kind, dist, stamped = build_site.build(project)

    assert kind == "static"
    assert dist == project / "dist"
    assert stamped == "2026-07-28"
    html = (dist / "index.html").read_text(encoding="utf-8")
    assert "2026-07-28" in html
    assert build_site.REPORT_DATE_SENTINEL not in html
    assert 'id="theme-toggle"' in html
    assert "sandwalk-logo" in html
    assert (dist / "shell.css").is_file()
    assert validate_site.validate(dist) == []


def test_build_restores_mangled_shell_markers(tmp_path, monkeypatch):
    project = tmp_path / "site"
    init_site.initialize(project, "static")
    index = project / "src" / "index.html"
    text = index.read_text(encoding="utf-8")
    text = text.replace(
        "<!-- sandwalk:shell:actions -->",
        "<!-- sandwalk:shell:actions -->\n<button type='button'>Light mode</button>",
    )
    text = text.replace(
        "<!-- sandwalk:shell:footer -->",
        "<!-- sandwalk:shell:footer -->\n<footer><p>Generated with Sandwalk</p>",
    )
    # Drop the rest of the original footer until the close marker stays.
    start = text.index("<!-- sandwalk:shell:footer -->")
    end = text.index("<!-- /sandwalk:shell:footer -->")
    text = (
        text[:start]
        + "<!-- sandwalk:shell:footer -->\n<footer><p>Generated with Sandwalk</p>\n"
        + text[end:]
    )
    index.write_text(text, encoding="utf-8")
    monkeypatch.setenv("SANDWALK_REPORT_DATE", "2026-07-29")

    _kind, dist, _stamped = build_site.build(project)
    html = (dist / "index.html").read_text(encoding="utf-8")

    assert "Light mode" not in html
    assert 'id="theme-toggle"' in html
    assert "<p>Generated with Sandwalk</p>" not in html
    assert "sandwalk-logo" in html
    assert "https://sandwalk.sh/" in html
    assert validate_site.validate(dist) == []


def test_validate_rejects_unstamped_report_date_sentinel(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        "<!doctype html><time class='report-date' "
        "datetime='__SANDWALK_REPORT_DATE__'>__SANDWALK_REPORT_DATE__</time>",
        encoding="utf-8",
    )

    errors = validate_site.validate(dist)

    assert any("unresolved report date sentinel" in error for error in errors)


def test_validate_rejects_report_missing_shell(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        """
        <!doctype html>
        <html><body>
          <p class="report-meta">BRIEF • 2026-07-29</p>
          <div class="report-layout"><main id="main"><h1>Report</h1></main></div>
        </body></html>
        """,
        encoding="utf-8",
    )

    errors = validate_site.validate(dist)

    assert any("missing locked shell marker" in error for error in errors)
    assert any("theme-toggle" in error for error in errors)
    assert any("shell.css" in error for error in errors)


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


@pytest.mark.parametrize(
    "script",
    [
        '<script type="module" src="https://cdn.example/report.js"></script>',
        '<script type="module">import lib from "https://cdn.example/lib.js";</script>',
    ],
)
def test_validate_rejects_remote_es_modules(tmp_path, script):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        f"<!doctype html><html><body>{script}</body></html>",
        encoding="utf-8",
    )

    errors = validate_site.validate(dist)

    assert any("remote ES-module import is not allowed" in error for error in errors)


def test_validate_requires_dist_index(tmp_path):
    errors = validate_site.validate(tmp_path / "dist")
    assert len(errors) == 1
    assert "missing required entry point" in errors[0]
