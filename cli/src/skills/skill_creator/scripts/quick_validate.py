#!/usr/bin/env python3
"""Validate an agent skill's SKILL.md frontmatter and naming.

Usage:
    python scripts/quick_validate.py <path/to/skill> [--strict]

Exit code 0 on success, 1 on validation failure, 2 on usage error.
Warnings (e.g. leftover TODOs) are errors only with --strict.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_ALLOWED_KEYS = {"name", "description", "tags", "license", "allowed-tools", "metadata", "compatibility"}


def _parse_frontmatter(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return fields
    end = stripped.find("\n---", 3)
    if end == -1:
        return fields
    block = stripped[3:end]
    for line in block.splitlines():
        if ":" in line and not line.startswith((" ", "\t", "-")):
            key = line.split(":", 1)[0].strip()
            value = line.split(":", 1)[1].strip()
            fields[key] = value
    return fields


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a skill's SKILL.md.")
    parser.add_argument("path", help="Path to the skill directory (or SKILL.md)")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = parser.parse_args(argv)

    target = Path(args.path).expanduser().resolve()
    skill_md = target / "SKILL.md" if target.is_dir() else target
    if not skill_md.exists():
        print(f"Error: SKILL.md not found at {target}", file=sys.stderr)
        return 2

    content = skill_md.read_text(encoding="utf-8")
    errors: list[str] = []
    warnings: list[str] = []

    fields = _parse_frontmatter(content)
    if not fields:
        errors.append("Missing or malformed YAML frontmatter (--- ... ---).")

    name = fields.get("name", "").strip().strip('"').strip("'")
    if not name:
        errors.append("Frontmatter is missing required 'name'.")
    elif not _NAME_RE.match(name):
        errors.append(f"Invalid 'name' value '{name}'. Use lowercase letters, digits, and hyphens.")

    description = fields.get("description", "").strip().strip('"').strip("'")
    if not description:
        errors.append("Frontmatter is missing required 'description'.")
    elif description.upper().startswith("TODO"):
        warnings.append("'description' still contains a TODO placeholder.")

    for key in fields:
        if key not in _ALLOWED_KEYS:
            warnings.append(f"Unexpected frontmatter key '{key}'.")

    if "TODO" in content:
        warnings.append("Body still contains TODO placeholders.")

    for w in warnings:
        print(f"WARN: {w}", file=sys.stderr)
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)

    if errors or (args.strict and warnings):
        print("Validation failed.", file=sys.stderr)
        return 1

    print(f"OK: {skill_md} is valid.", file=sys.stderr)
    print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
