#!/usr/bin/env python3
"""Initialize a lightweight static or Vite/React site."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

TEMPLATES = ("static", "vite-react")
_IGNORED_EXISTING = {".DS_Store", ".git"}


def initialize(target: Path, template: str) -> list[str]:
    target = target.expanduser().resolve()
    source = Path(__file__).resolve().parent.parent / "templates" / template
    target.mkdir(parents=True, exist_ok=True)
    existing = [item.name for item in target.iterdir() if item.name not in _IGNORED_EXISTING]
    if existing:
        raise ValueError(f"target is not empty: {target}")

    created: list[str] = []
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        destination = target / relative
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item, destination)
        created.append(relative.as_posix())
    if template == "static":
        shell = Path(__file__).resolve().parent.parent / "fragments" / "shell.css"
        destination = target / "src" / "shell.css"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(shell, destination)
        path = "src/shell.css"
        if path not in created:
            created.append(path)
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="Empty directory to initialize")
    parser.add_argument("--template", choices=TEMPLATES, default="static")
    args = parser.parse_args(argv)

    try:
        created = initialize(Path(args.target), args.template)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    result = {
        "ok": True,
        "project": str(Path(args.target).expanduser().resolve()),
        "template": args.template,
        "created": created,
    }
    print(f"Initialized {args.template} site.", file=sys.stderr)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
