#!/usr/bin/env python3
"""Build a static or Vite site into a clean dist directory."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

REPORT_DATE_SENTINEL = "__SANDWALK_REPORT_DATE__"
_REPORT_DATE_ENV = "SANDWALK_REPORT_DATE"
_STAMP_SUFFIXES = {".html", ".js", ".mjs", ".css"}
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHELL_BLOCK = re.compile(
    r"<!--\s*sandwalk:shell:(?P<name>actions|footer)\s*-->"
    r".*?"
    r"<!--\s*/sandwalk:shell:(?P=name)\s*-->",
    re.DOTALL | re.IGNORECASE,
)
_FRAGMENTS = Path(__file__).resolve().parent.parent / "fragments"


def report_date() -> str:
    override = (os.environ.get(_REPORT_DATE_ENV) or "").strip()
    if override:
        if not _ISO_DATE.fullmatch(override):
            raise ValueError(
                f"{_REPORT_DATE_ENV} must be YYYY-MM-DD, got {override!r}"
            )
        return override
    return datetime.now(UTC).date().isoformat()


def stamp_report_date(root: Path, day: str | None = None) -> str:
    """Replace report-date sentinels under root; return the stamped ISO date."""
    iso = day if day is not None else report_date()
    if not _ISO_DATE.fullmatch(iso):
        raise ValueError(f"report date must be YYYY-MM-DD, got {iso!r}")
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _STAMP_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if REPORT_DATE_SENTINEL not in text:
            continue
        path.write_text(
            text.replace(REPORT_DATE_SENTINEL, iso),
            encoding="utf-8",
        )
    return iso


def _fragment(name: str) -> str:
    path = _FRAGMENTS / name
    if not path.is_file():
        raise ValueError(f"missing shell fragment: {path}")
    return path.read_text(encoding="utf-8").strip() + "\n"


def apply_report_shell(dist: Path) -> list[str]:
    """Restore locked report shell CSS and HTML markers in dist."""
    applied: list[str] = []
    shell_css = _FRAGMENTS / "shell.css"
    if not shell_css.is_file():
        raise ValueError(f"missing shell stylesheet: {shell_css}")

    index = dist / "index.html"
    if not index.is_file():
        return applied
    html = index.read_text(encoding="utf-8")
    looks_like_report = "report-layout" in html or "report-meta" in html
    if not looks_like_report:
        return applied

    shutil.copyfile(shell_css, dist / "shell.css")
    applied.append("shell.css")

    if 'href="shell.css"' not in html and "href='shell.css'" not in html:
        html = html.replace(
            'href="styles.css" />',
            'href="styles.css" />\n    <link rel="stylesheet" href="shell.css" />',
            1,
        )
        if 'href="shell.css"' not in html:
            html = html.replace(
                "</head>",
                '    <link rel="stylesheet" href="shell.css" />\n  </head>',
                1,
            )
        applied.append("shell.css-link")

    fragments = {
        "actions": _fragment("report_actions.html"),
        "footer": _fragment("report_footer.html"),
    }
    found: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        name = match.group("name").lower()
        found.add(name)
        applied.append(f"shell:{name}")
        return (
            f"<!-- sandwalk:shell:{name} -->\n"
            f"{fragments[name]}"
            f"<!-- /sandwalk:shell:{name} -->"
        )

    html = _SHELL_BLOCK.sub(replace, html)
    missing = sorted(set(fragments) - found)
    if missing:
        raise ValueError(
            "report shell markers missing from index.html: "
            + ", ".join(f"sandwalk:shell:{name}" for name in missing)
            + ". Keep the starter markers; only edit main content and TOC links."
        )

    html = ensure_favicon(dist, html)
    index.write_text(html, encoding="utf-8")
    return applied


def ensure_favicon(dist: Path, html: str | None = None) -> str:
    """Ensure dist has favicon.svg and index.html links it."""
    index = dist / "index.html"
    if html is None:
        html = index.read_text(encoding="utf-8") if index.is_file() else ""
    favicon = _FRAGMENTS / "favicon.svg"
    if favicon.is_file() and not (dist / "favicon.svg").is_file():
        shutil.copyfile(favicon, dist / "favicon.svg")
    if html and 'rel="icon"' not in html and "rel='icon'" not in html:
        html = html.replace(
            "<title>",
            '<link rel="icon" href="favicon.svg" type="image/svg+xml" />\n    <title>',
            1,
        )
        if 'rel="icon"' not in html:
            html = html.replace(
                "</head>",
                '    <link rel="icon" href="favicon.svg" type="image/svg+xml" />\n  </head>',
                1,
            )
        if index.is_file():
            index.write_text(html, encoding="utf-8")
    return html


def build(project: Path) -> tuple[str, Path, str]:
    project = project.expanduser().resolve()
    if not project.is_dir():
        raise ValueError(f"project directory not found: {project}")

    dist = project / "dist"
    if dist.exists():
        shutil.rmtree(dist)

    if (project / "package.json").is_file():
        if not (project / "node_modules").is_dir():
            command = ["npm", "install", "--no-audit", "--no-fund"]
            if (project / "package-lock.json").is_file():
                command = ["npm", "ci", "--no-audit", "--no-fund"]
            subprocess.run(command, cwd=project, check=True)
        subprocess.run(["npm", "run", "build"], cwd=project, check=True)
        kind = "vite-react"
    else:
        source = project / "src"
        if not (source / "index.html").is_file():
            raise ValueError(f"static entry point not found: {source / 'index.html'}")
        shutil.copytree(source, dist)
        kind = "static"

    if not (dist / "index.html").is_file():
        raise ValueError(f"build did not create {dist / 'index.html'}")
    apply_report_shell(dist)
    ensure_favicon(dist)
    stamped = stamp_report_date(dist)
    return kind, dist, stamped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="Site project directory")
    args = parser.parse_args(argv)

    try:
        kind, dist, stamped = build(Path(args.project))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Built {kind} site at {dist}.", file=sys.stderr)
    print(
        json.dumps(
            {
                "ok": True,
                "kind": kind,
                "dist": str(dist),
                "reportDate": stamped,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
