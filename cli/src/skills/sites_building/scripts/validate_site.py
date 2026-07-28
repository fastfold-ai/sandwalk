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


class _References(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[tuple[str, str]] = []
        self.styles: list[str] = []
        self._in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_attrs(attrs)
        if tag.lower() == "style":
            self._in_style = True

    def handle_startendtag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_attrs(attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self.styles.append(data)

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
    references: list[tuple[Path, str]] = []
    for page in pages:
        parser = _References()
        try:
            parser.feed(page.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"cannot read {page.relative_to(dist).as_posix()}: {exc}")
            continue
        references.extend((page, value) for _name, value in parser.values)
        for style in parser.styles:
            references.extend((page, value) for value in _css_references(style))
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
