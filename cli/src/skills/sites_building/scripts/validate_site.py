#!/usr/bin/env python3
"""Validate a static dist entry point and its local asset references."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

_ATTRIBUTES = {"href", "src", "poster"}
_REMOTE_SCHEMES = {"data", "http", "https", "mailto", "tel"}
_CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)
_REMOTE_MODULE_IMPORT = re.compile(
    r"""\bimport\s+(?:[^;]*?\s+from\s+)?["']https?://""",
    re.IGNORECASE | re.DOTALL,
)
_REPORT_DATE_SENTINEL = "__SANDWALK_REPORT_DATE__"
_REPORT_DATE_PLACEHOLDER = re.compile(
    r"""(?:class=["']report-date["'][^>]*datetime=["']YYYY-MM-DD["']"""
    r"""|datetime=["']YYYY-MM-DD["'][^>]*class=["']report-date["']"""
    r"""|>YYYY-MM-DD</time>)""",
    re.IGNORECASE,
)
_SHELL_MARKERS = ("sandwalk:shell:actions", "sandwalk:shell:footer")
_REPORT_SHELL_REQUIRED = (
    ('id="theme-toggle"', "fixed Theme control (#theme-toggle)"),
    ("report-actions", "report-actions theme control container"),
    ("report-layout", "report-layout grid shell"),
    ('class="toc', "nav.toc table of contents"),
    ("toc-title", "TOC title"),
    ("sandwalk-logo", "Sandwalk SVG footer logo"),
    ("sandwalk.sh", "Sandwalk footer link"),
    ("shell.css", "locked shell stylesheet"),
)


class _References(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[tuple[str, str]] = []
        self.styles: list[str] = []
        self.remote_modules: list[str] = []
        self._in_style = False
        self._in_module = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_attrs(attrs)
        lowered = tag.lower()
        if lowered == "style":
            self._in_style = True
        if lowered == "script":
            attributes = {name.lower(): value for name, value in attrs}
            if (attributes.get("type") or "").lower() == "module":
                source = attributes.get("src") or ""
                if urlsplit(source).scheme.lower() in {"http", "https"}:
                    self.remote_modules.append(source)
                elif not source:
                    self._in_module = True

    def handle_startendtag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_attrs(attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style":
            self._in_style = False
        elif tag.lower() == "script":
            self._in_module = False

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self.styles.append(data)
        elif self._in_module and _REMOTE_MODULE_IMPORT.search(data):
            self.remote_modules.append("inline remote import")

    def _handle_attrs(self, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if not value:
                continue
            lowered = name.lower()
            if lowered in _ATTRIBUTES:
                self.values.append((lowered, value))
            elif lowered == "srcset":
                for candidate in value.split(","):
                    url = candidate.strip().split(maxsplit=1)[0]
                    if url:
                        self.values.append((lowered, url))
            elif lowered == "style":
                self.styles.append(value)


def _css_references(text: str) -> list[str]:
    return [match.group(2).strip() for match in _CSS_URL.finditer(text)]


def _local_path(value: str) -> tuple[PurePosixPath | None, str | None]:
    value = value.strip()
    if not value or value.startswith("#"):
        return None, None
    if "\\" in value:
        return None, "uses a backslash"
    parsed = urlsplit(value)
    if parsed.scheme.lower() in _REMOTE_SCHEMES:
        return None, None
    if parsed.scheme or parsed.netloc:
        return None, "uses an unsupported URL scheme or protocol-relative URL"
    decoded = unquote(parsed.path)
    if not decoded:
        return None, None
    path = PurePosixPath(decoded)
    if path.is_absolute():
        return None, "must be relative, not root-relative"
    if ".." in path.parts:
        return None, "contains parent traversal"
    return path, None


def validate(dist: Path) -> list[str]:
    dist = dist.expanduser().resolve()
    errors: list[str] = []
    index = dist / "index.html"
    if not index.is_file():
        return [f"missing required entry point: {index}"]

    for item in dist.rglob("*"):
        if item.is_symlink():
            errors.append(f"symlinks are not allowed: {item.relative_to(dist).as_posix()}")

    pages = sorted(dist.rglob("*.html"))
    stylesheets = sorted(dist.rglob("*.css"))
    scripts = sorted(
        path
        for path in dist.rglob("*")
        if path.is_file() and path.suffix.lower() in {".js", ".mjs"}
    )
    references: list[tuple[Path, str]] = []
    for page in pages:
        try:
            text = page.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"cannot read {page.relative_to(dist).as_posix()}: {exc}")
            continue
        label = page.relative_to(dist).as_posix()
        if _REPORT_DATE_SENTINEL in text:
            errors.append(
                f"{label}: unresolved report date sentinel "
                f"{_REPORT_DATE_SENTINEL!r}; run build_site.py before validate"
            )
        if _REPORT_DATE_PLACEHOLDER.search(text):
            errors.append(
                f"{label}: report date still uses placeholder YYYY-MM-DD; "
                "keep __SANDWALK_REPORT_DATE__ and run build_site.py"
            )
        looks_like_report = "report-layout" in text or "report-meta" in text
        if looks_like_report and label == "index.html":
            for marker in _SHELL_MARKERS:
                if marker not in text:
                    errors.append(
                        f"{label}: missing locked shell marker {marker!r}; "
                        "keep sandwalk:shell comments from the static starter"
                    )
            for needle, description in _REPORT_SHELL_REQUIRED:
                if needle not in text:
                    errors.append(
                        f"{label}: missing {description}; "
                        "do not reinvent the report shell"
                    )
            if not re.search(
                r'<nav[^>]*\bclass="[^"]*\btoc\b[^"]*"[^>]*>'
                r'[\s\S]*?<a[^>]+href="#[^"]+"',
                text,
                re.IGNORECASE,
            ):
                errors.append(
                    f"{label}: nav.toc must include in-page section links"
                )
            css_path = dist / "shell.css"
            if not css_path.is_file():
                errors.append(
                    f"{label}: missing shell.css; run build_site.py to restore "
                    "the locked report layout stylesheet"
                )
            else:
                css = css_path.read_text(encoding="utf-8")
                for selector in (
                    ".report-layout",
                    ".report-actions",
                    ".toc",
                    ".sandwalk-logo",
                ):
                    if selector not in css:
                        errors.append(
                            f"shell.css: missing {selector} rules for the "
                            "locked report shell"
                        )
        parser = _References()
        parser.feed(text)
        for source in parser.remote_modules:
            errors.append(
                f"{label}: remote ES-module import is not allowed ({source}); "
                "use a local module or pinned classic browser bundle"
            )
        references.extend((page, value) for _name, value in parser.values)
        for style in parser.styles:
            references.extend((page, value) for value in _css_references(style))
    for script in scripts:
        try:
            text = script.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"cannot read {script.relative_to(dist).as_posix()}: {exc}")
            continue
        if _REPORT_DATE_SENTINEL in text:
            label = script.relative_to(dist).as_posix()
            errors.append(
                f"{label}: unresolved report date sentinel "
                f"{_REPORT_DATE_SENTINEL!r}; run build_site.py before validate"
            )
    for stylesheet in stylesheets:
        try:
            text = stylesheet.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"cannot read {stylesheet.relative_to(dist).as_posix()}: {exc}")
            continue
        references.extend((stylesheet, value) for value in _css_references(text))

    for owner, value in references:
        path, reason = _local_path(value)
        label = owner.relative_to(dist).as_posix()
        if reason:
            errors.append(f"{label}: unsafe local reference {value!r} ({reason})")
            continue
        if path is None:
            continue
        target = (owner.parent / Path(*path.parts)).resolve()
        if dist != target and dist not in target.parents:
            errors.append(f"{label}: reference escapes dist: {value!r}")
        elif not target.is_file():
            errors.append(f"{label}: missing local asset: {value!r}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", help="Build output directory")
    args = parser.parse_args(argv)

    errors = validate(Path(args.dist))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(json.dumps({"ok": False, "errors": errors}, sort_keys=True))
        return 1

    dist = Path(args.dist).expanduser().resolve()
    files = sum(1 for item in dist.rglob("*") if item.is_file())
    print(f"Validated {files} file(s) in {dist}.", file=sys.stderr)
    print(json.dumps({"ok": True, "dist": str(dist), "files": files}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
