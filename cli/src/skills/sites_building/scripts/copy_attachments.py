#!/usr/bin/env python3
"""Copy referenced local attachments into a site's local asset directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def copy_attachments(
    project: Path,
    attachments: list[Path],
    asset_dir: str | None = None,
) -> list[dict[str, str]]:
    project = project.expanduser().resolve()
    if not project.is_dir():
        raise ValueError(f"project directory not found: {project}")
    relative_assets = asset_dir or ("public/assets" if (project / "package.json").is_file() else "src/assets")
    destination_root = (project / relative_assets).resolve()
    if project not in destination_root.parents:
        raise ValueError("asset directory must stay inside the project")
    destination_root.mkdir(parents=True, exist_ok=True)

    copied: list[dict[str, str]] = []
    for raw in attachments:
        source = raw.expanduser().resolve()
        if not source.is_file():
            raise ValueError(f"attachment is not a file: {source}")
        digest = _digest(source)
        name = _SAFE_NAME.sub("-", source.name).strip(".-") or f"attachment-{digest[:8]}"
        destination = destination_root / name
        if destination.exists() and _digest(destination) != digest:
            suffix = source.suffix
            stem = _SAFE_NAME.sub("-", source.stem).strip(".-") or "attachment"
            destination = destination_root / f"{stem}-{digest[:8]}{suffix}"
        if not destination.exists():
            shutil.copyfile(source, destination)
        public_relative = destination.relative_to(project).as_posix()
        if public_relative.startswith(("public/", "src/")):
            public_relative = public_relative.split("/", 1)[1]
        copied.append(
            {
                "source": str(source),
                "path": public_relative,
                "sha256": digest,
            }
        )
    return copied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="Site project directory")
    parser.add_argument("attachments", nargs="+", help="Attachment files to copy")
    parser.add_argument("--asset-dir", help="Project-relative destination directory")
    args = parser.parse_args(argv)

    try:
        copied = copy_attachments(
            Path(args.project),
            [Path(value) for value in args.attachments],
            args.asset_dir,
        )
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Copied {len(copied)} attachment(s).", file=sys.stderr)
    print(json.dumps({"ok": True, "assets": copied}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
