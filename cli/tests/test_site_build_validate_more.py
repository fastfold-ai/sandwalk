"""Branch coverage for static site build and dist validation."""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from skills.sites_building.scripts import build_site, validate_site


def _report_page(head: str) -> str:
    return (
        "<!doctype html><html><head>"
        f"{head}"
        "</head><body><div class='report-layout'>"
        "<!-- sandwalk:shell:actions -->old actions<!-- /sandwalk:shell:actions -->"
        "<!-- sandwalk:shell:footer -->old footer<!-- /sandwalk:shell:footer -->"
        "</div></body></html>"
    )


def _static_project(tmp_path: Path, html: str) -> Path:
    project = tmp_path / "site"
    source = project / "src"
    source.mkdir(parents=True)
    (source / "index.html").write_text(html, encoding="utf-8")
    return project


def _vite_project(tmp_path: Path, *, lock: bool, modules: bool) -> Path:
    project = tmp_path / "vite"
    project.mkdir()
    (project / "package.json").write_text("{}\n", encoding="utf-8")
    if lock:
        (project / "package-lock.json").write_text("{}\n", encoding="utf-8")
    if modules:
        (project / "node_modules").mkdir()
    return project


def test_report_date_rejects_bad_override_and_defaults_when_unset(monkeypatch):
    monkeypatch.setenv("SANDWALK_REPORT_DATE", "not-a-date")
    with pytest.raises(ValueError, match="SANDWALK_REPORT_DATE must be YYYY-MM-DD"):
        build_site.report_date()

    monkeypatch.setenv("SANDWALK_REPORT_DATE", "   ")
    expected = datetime.now(UTC).date().isoformat()
    assert build_site.report_date() == expected

    monkeypatch.delenv("SANDWALK_REPORT_DATE", raising=False)
    assert build_site.report_date() == datetime.now(UTC).date().isoformat()


def test_stamp_report_date_skips_unreadable_files_and_rejects_bad_days(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "page.html").write_text("<!-- __SANDWALK_REPORT_DATE__ -->", encoding="utf-8")
    (root / "empty.html").write_text("<p>no sentinel</p>", encoding="utf-8")
    (root / "app.mjs").write_text("const day = '__SANDWALK_REPORT_DATE__';\n", encoding="utf-8")
    (root / "skip.txt").write_text("__SANDWALK_REPORT_DATE__", encoding="utf-8")
    (root / "bad.css").write_bytes(b"__SANDWALK_REPORT_DATE__\xff")
    (root / "nested.js").mkdir()

    assert build_site.stamp_report_date(root, day="2020-01-02") == "2020-01-02"
    assert "2020-01-02" in (root / "page.html").read_text(encoding="utf-8")
    assert "2020-01-02" in (root / "app.mjs").read_text(encoding="utf-8")
    assert "no sentinel" in (root / "empty.html").read_text(encoding="utf-8")
    assert (root / "skip.txt").read_text(encoding="utf-8") == "__SANDWALK_REPORT_DATE__"
    assert (root / "bad.css").read_bytes().endswith(b"\xff")

    with pytest.raises(ValueError, match="report date must be YYYY-MM-DD"):
        build_site.stamp_report_date(root, day="yesterday")


def test_apply_requires_shell_stylesheet(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site, "_FRAGMENTS", tmp_path / "no-fragments")
    with pytest.raises(ValueError, match="missing shell stylesheet"):
        build_site.apply_report_shell(tmp_path / "dist")


def test_apply_requires_shell_fragments(tmp_path, monkeypatch):
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    (fragments / "shell.css").write_text(".report-layout{}\n", encoding="utf-8")
    monkeypatch.setattr(build_site, "_FRAGMENTS", fragments)
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        _report_page("<title>Report</title>"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing shell fragment"):
        build_site.apply_report_shell(dist)


def test_apply_without_index_or_report_markup_is_a_noop(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert build_site.apply_report_shell(empty) == []

    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "index.html").write_text("<!doctype html><p>Notes</p>", encoding="utf-8")
    assert build_site.apply_report_shell(plain) == []
    assert not (plain / "shell.css").exists()


def test_apply_requires_markers(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        "<!doctype html><html><head></head><body><p class='report-meta'>Meta</p></body></html>",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="report shell markers missing"):
        build_site.apply_report_shell(dist)

    assert (dist / "shell.css").is_file()
    assert "theme-toggle" not in (dist / "index.html").read_text(encoding="utf-8")


def test_apply_links_shell_css_next_to_styles(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        _report_page('<title>Report</title><link rel="stylesheet" href="styles.css" />'),
        encoding="utf-8",
    )

    applied = build_site.apply_report_shell(dist)
    html = (dist / "index.html").read_text(encoding="utf-8")

    assert applied == ["shell.css", "shell.css-link", "shell:actions", "shell:footer"]
    assert 'href="styles.css" />\n    <link rel="stylesheet" href="shell.css" />' in html
    assert "old actions" not in html
    assert "old footer" not in html
    assert 'id="theme-toggle"' in html
    assert "sandwalk-logo" in html
    assert (dist / "favicon.svg").is_file()
    assert 'rel="icon"' in html


def test_apply_links_shell_css_before_head_close(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(_report_page("<title>Report</title>"), encoding="utf-8")

    applied = build_site.apply_report_shell(dist)
    html = (dist / "index.html").read_text(encoding="utf-8")

    assert "shell.css-link" in applied
    assert 'href="shell.css" />\n  </head>' in html


@pytest.mark.parametrize(
    "link",
    [
        '<link rel="stylesheet" href="shell.css" />',
        "<link rel='stylesheet' href='shell.css' />",
    ],
)
def test_apply_keeps_existing_shell_link(tmp_path, link):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        _report_page(f"<title>Report</title>{link}"),
        encoding="utf-8",
    )

    applied = build_site.apply_report_shell(dist)

    assert "shell.css" in applied
    assert "shell:actions" in applied
    assert "shell:footer" in applied
    assert "shell.css-link" not in applied


def test_ensure_favicon_inserts_link_and_copies_asset(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        "<html><head><title>T</title></head><body></body></html>",
        encoding="utf-8",
    )

    html = build_site.ensure_favicon(dist)

    assert 'rel="icon"' in html
    assert html.index('rel="icon"') < html.index("<title>")
    assert (dist / "favicon.svg").is_file()
    assert 'rel="icon"' in (dist / "index.html").read_text(encoding="utf-8")

    original = (dist / "favicon.svg").read_bytes()
    again = build_site.ensure_favicon(dist, html)
    assert again.count('rel="icon"') == 1
    assert (dist / "favicon.svg").read_bytes() == original
    assert build_site.ensure_favicon(dist, "") == ""


def test_ensure_favicon_uses_head_when_title_is_absent(tmp_path):
    dist = tmp_path / "head"
    dist.mkdir()

    html = build_site.ensure_favicon(dist, "<html><head></head><body></body></html>")

    assert 'rel="icon"' in html
    assert html.index('rel="icon"') < html.index("</head>")
    assert not (dist / "index.html").exists()
    assert (dist / "favicon.svg").is_file()


def test_ensure_favicon_keeps_existing_icon_and_file(tmp_path):
    dist = tmp_path / "keep"
    dist.mkdir()
    (dist / "favicon.svg").write_text("keep", encoding="utf-8")
    (dist / "index.html").write_text("<p>only</p>", encoding="utf-8")

    html = build_site.ensure_favicon(dist)

    assert html == "<p>only</p>"
    assert (dist / "index.html").read_text(encoding="utf-8") == "<p>only</p>"
    assert (dist / "favicon.svg").read_text(encoding="utf-8") == "keep"

    double = '<link rel="icon" href="favicon.svg">'
    single = "<link rel='icon' href='favicon.svg'>"
    assert build_site.ensure_favicon(dist, double) == double
    assert build_site.ensure_favicon(dist, single) == single


def test_ensure_favicon_without_fragment_or_index(tmp_path, monkeypatch):
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    monkeypatch.setattr(build_site, "_FRAGMENTS", fragments)
    dist = tmp_path / "dist"
    dist.mkdir()

    html = build_site.ensure_favicon(dist, "<html><head><title>T</title></head></html>")

    assert 'rel="icon"' in html
    assert not (dist / "favicon.svg").exists()
    assert not (dist / "index.html").exists()

    blank = tmp_path / "blank"
    blank.mkdir()
    assert build_site.ensure_favicon(blank) == ""


def test_build_static_replaces_dist_and_stamps(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDWALK_REPORT_DATE", "2026-04-01")
    project = _static_project(
        tmp_path,
        "<!doctype html><html><head><title>Day __SANDWALK_REPORT_DATE__</title></head></html>",
    )
    stale = project / "dist" / "stale.txt"
    stale.parent.mkdir()
    stale.write_text("gone", encoding="utf-8")

    kind, dist, stamped = build_site.build(project)

    assert kind == "static"
    assert stamped == "2026-04-01"
    assert dist == (project / "dist").resolve()
    html = (dist / "index.html").read_text(encoding="utf-8")
    assert "2026-04-01" in html
    assert 'rel="icon"' in html
    assert (dist / "favicon.svg").is_file()
    assert not stale.exists()


def test_build_rejects_missing_project_and_static_entry(tmp_path):
    with pytest.raises(ValueError, match="project directory not found"):
        build_site.build(tmp_path / "missing")

    project = tmp_path / "site"
    project.mkdir()
    with pytest.raises(ValueError, match="static entry point not found"):
        build_site.build(project)


def _patch_npm(monkeypatch, run) -> None:
    monkeypatch.setattr(build_site.subprocess, "run", run)


def test_vite_build_uses_npm_ci_when_lockfile_present(tmp_path, monkeypatch):
    project = _vite_project(tmp_path, lock=True, modules=False)
    calls: list[list[str]] = []

    def fake_run(command, cwd, check):
        assert check is True
        assert Path(cwd) == project.resolve()
        calls.append(list(command))
        if list(command)[:3] == ["npm", "run", "build"]:
            dist = Path(cwd) / "dist"
            dist.mkdir()
            (dist / "index.html").write_text("<!doctype html><title>Vite</title>", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    _patch_npm(monkeypatch, fake_run)
    kind, dist, _stamped = build_site.build(project)

    assert kind == "vite-react"
    assert calls == [
        ["npm", "ci", "--no-audit", "--no-fund"],
        ["npm", "run", "build"],
    ]
    assert (dist / "index.html").is_file()
    assert (dist / "favicon.svg").is_file()


def test_vite_build_uses_npm_install_without_lockfile(tmp_path, monkeypatch):
    project = _vite_project(tmp_path, lock=False, modules=False)
    calls: list[list[str]] = []

    def fake_run(command, cwd, check):
        del check
        calls.append(list(command))
        if list(command)[:3] == ["npm", "run", "build"]:
            dist = Path(cwd) / "dist"
            dist.mkdir()
            (dist / "index.html").write_text("<!doctype html><title>Vite</title>", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    _patch_npm(monkeypatch, fake_run)
    kind, _dist, _stamped = build_site.build(project)

    assert kind == "vite-react"
    assert calls[0] == ["npm", "install", "--no-audit", "--no-fund"]
    assert calls[1] == ["npm", "run", "build"]


def test_vite_build_skips_install_when_dependencies_exist(tmp_path, monkeypatch):
    project = _vite_project(tmp_path, lock=True, modules=True)
    calls: list[list[str]] = []

    def fake_run(command, cwd, check):
        del check
        calls.append(list(command))
        dist = Path(cwd) / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<!doctype html><title>Vite</title>", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    _patch_npm(monkeypatch, fake_run)
    kind, _dist, _stamped = build_site.build(project)

    assert kind == "vite-react"
    assert calls == [["npm", "run", "build"]]


def test_vite_build_requires_index_output(tmp_path, monkeypatch):
    project = _vite_project(tmp_path, lock=False, modules=True)

    def fake_run(command, cwd, check):
        del command, check
        (Path(cwd) / "dist").mkdir()
        return subprocess.CompletedProcess(["npm"], 0)

    _patch_npm(monkeypatch, fake_run)
    with pytest.raises(ValueError, match="build did not create"):
        build_site.build(project)


def test_main_builds_static_site(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SANDWALK_REPORT_DATE", "2026-04-01")
    project = _static_project(
        tmp_path,
        "<!doctype html><html><head><title>Ready</title></head></html>",
    )

    assert build_site.main([str(project)]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["kind"] == "static"
    assert payload["reportDate"] == "2026-04-01"
    assert Path(payload["dist"]) == (project / "dist").resolve()
    assert "Built static site" in captured.err


def test_main_reports_value_os_and_process_errors(tmp_path, monkeypatch, capsys):
    assert build_site.main([str(tmp_path / "missing")]) == 1
    assert "Error:" in capsys.readouterr().err

    project = _static_project(tmp_path, "<!doctype html><title>X</title>")
    (project / "dist").write_text("not-a-directory", encoding="utf-8")
    assert build_site.main([str(project)]) == 1
    assert "Error:" in capsys.readouterr().err

    vite = _vite_project(tmp_path, lock=False, modules=True)

    def fake_run(command, cwd, check):
        del cwd, check
        raise subprocess.CalledProcessError(2, command)

    _patch_npm(monkeypatch, fake_run)
    assert build_site.main([str(vite)]) == 1
    assert "Error:" in capsys.readouterr().err


def test_build_module_entrypoint(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("SANDWALK_REPORT_DATE", raising=False)
    project = _static_project(tmp_path, "<!doctype html><title>Entry</title>")
    script = build_site.__file__
    assert script is not None
    monkeypatch.setattr(sys, "argv", [script, str(project)])

    with pytest.raises(SystemExit) as caught:
        runpy.run_path(script, run_name="__main__")

    assert caught.value.code == 0
    assert '"ok": true' in capsys.readouterr().out


def test_validate_parser_references_symlinks_and_unreadable_files(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.png").write_bytes(b"png")
    (dist / "linked").symlink_to(outside, target_is_directory=True)
    (dist / "ok.txt").write_text("ok", encoding="utf-8")
    (dist / "style.css").write_text(
        'body { background: url("ok.txt"); }\n'
        'div { background: url("missing-css.png"); }\n'
        "span { background: url(//cdn.example/x.png); }\n",
        encoding="utf-8",
    )
    (dist / "bad.css").write_bytes(b"\xff")
    (dist / "dir.css").mkdir()
    (dist / "plain.js").write_text("console.log(1)\n", encoding="utf-8")
    (dist / "bad.js").write_bytes(b"\xff")
    (dist / "date.mjs").write_text("const day = '__SANDWALK_REPORT_DATE__';\n", encoding="utf-8")
    (dist / "bad.html").write_bytes(b"\xff")
    (dist / "folder.html").mkdir()
    sub = dist / "sub"
    sub.mkdir()
    (sub / "note.txt").write_text("note", encoding="utf-8")
    (sub / "page.html").write_text(
        "<p class='report-meta'>Meta</p>"
        "<time class='report-date' datetime='YYYY-MM-DD'>YYYY-MM-DD</time>"
        "<a href='note.txt'>note</a>",
        encoding="utf-8",
    )
    (dist / "index.html").write_text(
        """<!doctype html>
        <html><head><title>Refs</title></head><body>
          <style>h1 { background: url("from-style.png"); }</style>
          <div style="background-image: url('from-attr.png')"></div>
          <img srcset="from-srcset.png 480w, from-srcset-2.png 2x" alt="">
          <img alt src="">
          <video poster="poster.png"></video>
          <a href="   ">blank</a>
          <a href="#local">hash</a>
          <a href="https://example.com/a">https</a>
          <a href="mailto:a@b.c">mail</a>
          <a href="tel:123">tel</a>
          <a href="data:text/plain,hi">data</a>
          <a href="javascript:alert(1)">js</a>
          <a href="//cdn.example/app.js">proto</a>
          <a href="?q=1">query</a>
          <a href="dir\\file.png">slash</a>
          <img src="linked/secret.png" alt="">
          <img src="ok.txt" alt="" />
          <script type="module" src="local.js"></script>
          <script type="module">const value = 1;</script>
        </body></html>
        """,
        encoding="utf-8",
    )

    errors = validate_site.validate(dist)
    joined = "\n".join(errors)

    assert "from-style.png" in joined
    assert "from-attr.png" in joined
    assert "from-srcset.png" in joined
    assert "from-srcset-2.png" in joined
    assert "poster.png" in joined
    assert "missing local asset: 'local.js'" in joined
    assert "remote ES-module import is not allowed (local.js)" not in joined
    assert "uses a backslash" in joined
    assert "unsupported URL scheme or protocol-relative URL" in joined
    assert "symlinks are not allowed: linked" in joined
    assert "reference escapes dist: 'linked/secret.png'" in joined
    assert "cannot read bad.html" in joined
    assert "cannot read folder.html" in joined
    assert "cannot read bad.js" in joined
    assert "cannot read bad.css" in joined
    assert "cannot read dir.css" in joined
    assert "missing-css.png" in joined
    assert "date.mjs: unresolved report date sentinel" in joined
    assert "sub/page.html: report date still uses placeholder" in joined
    assert "missing locked shell marker" not in joined
    assert "'ok.txt'" not in joined
    assert "'?q=1'" not in joined
    assert "plain.js" not in joined


def test_validate_report_shell_css_must_keep_locked_selectors(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "shell.css").write_text(
        ".report-layout { display: grid; }\n.toc { display: block; }\n",
        encoding="utf-8",
    )
    (dist / "index.html").write_text(
        """<!doctype html>
        <html><head>
          <link rel="stylesheet" href="shell.css" />
          <title>Report</title>
        </head><body>
          <!-- sandwalk:shell:actions --><!-- /sandwalk:shell:actions -->
          <!-- sandwalk:shell:footer --><!-- /sandwalk:shell:footer -->
          <div id="theme-toggle"></div>
          <div class="report-actions"></div>
          <div class="report-layout">
            <nav class="toc">
              <p class="toc-title">Contents</p>
              <a href="#section">Section</a>
            </nav>
            <img class="sandwalk-logo" alt="" src="data:image/svg+xml,x">
            <a href="https://sandwalk.sh/">Sandwalk</a>
          </div>
        </body></html>
        """,
        encoding="utf-8",
    )

    errors = validate_site.validate(dist)
    joined = "\n".join(errors)

    assert "shell.css: missing .report-actions rules" in joined
    assert "shell.css: missing .sandwalk-logo rules" in joined
    assert "missing .report-layout" not in joined
    assert "missing .toc rules" not in joined
    assert "missing locked shell marker" not in joined
    assert "nav.toc must include" not in joined


def test_validate_main_success_and_failure(tmp_path, capsys):
    assert validate_site.main([str(tmp_path / "missing")]) == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert "missing required entry point" in payload["errors"][0]
    assert captured.err.startswith("ERROR:")

    dist = tmp_path / "dist"
    (dist / "nested").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><p>ok</p>", encoding="utf-8")
    (dist / "nested" / "note.txt").write_text("n", encoding="utf-8")

    assert validate_site.main([str(dist)]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload == {"dist": str(dist.resolve()), "files": 2, "ok": True}
    assert f"Validated 2 file(s) in {dist.resolve()}." in captured.err


def test_validate_module_entrypoint(tmp_path, monkeypatch, capsys):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><p>ok</p>", encoding="utf-8")
    script = validate_site.__file__
    assert script is not None
    monkeypatch.setattr(sys, "argv", [script, str(dist)])

    with pytest.raises(SystemExit) as caught:
        runpy.run_path(script, run_name="__main__")

    assert caught.value.code == 0
    assert '"ok": true' in capsys.readouterr().out
