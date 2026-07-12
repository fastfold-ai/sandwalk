#!/usr/bin/env python3
"""Scaffold a new agent skill directory with a template SKILL.md.

Usage:
    python scripts/init_skill.py <skill-name> [--path DIR]

Writes status to stderr and the created skill directory path to stdout.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

_SKILL_TEMPLATE = """\
---
name: {name}
description: TODO one sentence describing what this skill does and when to use it (include trigger phrases).
---

# {title}

## Overview
TODO brief description of the skill.

## When to Use This Skill
- TODO trigger condition
- TODO trigger condition

## Workflow
1. TODO first step
2. TODO second step

## Resources
- TODO link to references/ or scripts/ if used
"""


def _title_from_name(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").title()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold a new agent skill.")
    parser.add_argument("name", help="Skill name (kebab-case, e.g. my-new-skill)")
    parser.add_argument("--path", default=".", help="Output directory (default: cwd)")
    parser.add_argument("--with-scripts", action="store_true", help="Also create a scripts/ folder")
    args = parser.parse_args(argv)

    name = args.name.strip()
    if not _NAME_RE.match(name):
        print(
            f"Error: invalid skill name '{name}'. Use lowercase letters, digits, and hyphens.",
            file=sys.stderr,
        )
        return 2

    out_root = Path(args.path).expanduser().resolve()
    skill_dir = out_root / name
    if skill_dir.exists():
        print(f"Error: {skill_dir} already exists.", file=sys.stderr)
        return 1

    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        _SKILL_TEMPLATE.format(name=name, title=_title_from_name(name)),
        encoding="utf-8",
    )
    (skill_dir / "references").mkdir(exist_ok=True)
    if args.with_scripts:
        (skill_dir / "scripts").mkdir(exist_ok=True)

    print(f"Created skill scaffold at {skill_dir}", file=sys.stderr)
    print(str(skill_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
