#!/usr/bin/env python3
"""Build a static or Vite site into a clean dist directory."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def build(project: Path) -> tuple[str, Path]:
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
    return kind, dist


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="Site project directory")
    args = parser.parse_args(argv)

    try:
        kind, dist = build(Path(args.project))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Built {kind} site at {dist}.", file=sys.stderr)
    print(json.dumps({"ok": True, "kind": kind, "dist": str(dist)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
