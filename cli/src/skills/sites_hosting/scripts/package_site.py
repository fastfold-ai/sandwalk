#!/usr/bin/env python3
"""Create and verify a deterministic Sandwalk Sites archive and manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

MAX_BYTES = 100 * 1024 * 1024
MAX_FILES = 10_000
_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_SECRET_NAMES = {
    "credentials",
    "credentials.json",
    "id_dsa",
    "id_ed25519",
    "id_rsa",
    "secrets",
    "secrets.json",
    "service-account.json",
    "service_account.json",
}
_SECRET_SUFFIXES = {".jks", ".key", ".p12", ".pem", ".pfx"}
_SECRET_PATTERN = re.compile(
    r"(^|[._-])(api[_-]?key|credential|credentials|private[_-]?key|secret|secrets)([._-]|$)",
    re.IGNORECASE,
)


class PackageError(ValueError):
    """Raised when site output or a package is unsafe or invalid."""


def _safe_path(value: str) -> PurePosixPath:
    if not value or "\\" in value or "\x00" in value:
        raise PackageError(f"unsafe path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or path.parts != tuple(part for part in path.parts if part not in {"", ".", ".."}):
        raise PackageError(f"path traversal is not allowed: {value!r}")
    if any(part.startswith(".") for part in path.parts):
        raise PackageError(f"dotfiles are not allowed: {value!r}")
    lowered = path.name.lower()
    if (
        lowered in _SECRET_NAMES
        or Path(lowered).suffix in _SECRET_SUFFIXES
        or _SECRET_PATTERN.search(lowered)
    ):
        raise PackageError(f"possible secret file is not allowed: {value!r}")
    return path


def _digest(path: Path) -> tuple[int, str]:
    size = 0
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_BYTES:
                raise PackageError(f"expanded output exceeds {MAX_BYTES} bytes")
            digest.update(chunk)
    return size, digest.hexdigest()


def build_manifest(dist: Path) -> dict[str, object]:
    source = dist.expanduser()
    if source.is_symlink() or not source.is_dir():
        raise PackageError("dist must be a regular directory")
    source = source.resolve()
    index = source / "index.html"
    if not index.is_file() or index.is_symlink():
        raise PackageError("dist/index.html must be a regular file")

    files: list[dict[str, object]] = []
    expanded = 0
    for item in sorted(source.rglob("*"), key=lambda value: value.relative_to(source).as_posix()):
        relative = item.relative_to(source).as_posix()
        _safe_path(relative)
        if item.is_symlink():
            raise PackageError(f"symlinks are not allowed: {relative!r}")
        if item.is_dir():
            continue
        if not item.is_file():
            raise PackageError(f"only regular files are allowed: {relative!r}")
        if len(files) >= MAX_FILES:
            raise PackageError(f"file count exceeds {MAX_FILES}")
        size, digest = _digest(item)
        expanded += size
        if expanded > MAX_BYTES:
            raise PackageError(f"expanded output exceeds {MAX_BYTES} bytes")
        files.append({"bytes": size, "path": relative, "sha256": digest})

    return {
        "expanded_bytes": expanded,
        "file_count": len(files),
        "files": files,
        "format": "sandwalk-sites-manifest",
        "version": 1,
    }


def _manifest_bytes(manifest: dict[str, object]) -> bytes:
    return (json.dumps(manifest, separators=(",", ":"), sort_keys=True) + "\n").encode()


def _write_archive(dist: Path, archive: Path, manifest: dict[str, object]) -> None:
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as bundle:
        for entry in manifest["files"]:
            if not isinstance(entry, dict):
                raise PackageError("manifest contains an invalid file entry")
            relative = str(entry["path"])
            info = zipfile.ZipInfo(relative, date_time=_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.flag_bits |= 0x800
            with (dist / Path(*PurePosixPath(relative).parts)).open("rb") as source:
                bundle.writestr(info, source.read())


def validate_package(archive: Path, manifest_path: Path) -> dict[str, object]:
    if archive.is_symlink() or manifest_path.is_symlink():
        raise PackageError("archive and manifest must not be symlinks")
    if archive.stat().st_size > MAX_BYTES:
        raise PackageError(f"archive exceeds {MAX_BYTES} bytes")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"cannot read manifest: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != "sandwalk-sites-manifest":
        raise PackageError("unsupported manifest format")
    expected = manifest.get("files")
    if not isinstance(expected, list):
        raise PackageError("manifest files must be a list")
    if len(expected) > MAX_FILES:
        raise PackageError(f"file count exceeds {MAX_FILES}")

    actual: list[dict[str, object]] = []
    expanded = 0
    try:
        with zipfile.ZipFile(archive, "r") as bundle:
            infos = bundle.infolist()
            if len(infos) != len({info.filename for info in infos}):
                raise PackageError("archive contains duplicate paths")
            for info in infos:
                path = _safe_path(info.filename)
                mode = info.external_attr >> 16
                if info.is_dir() or stat.S_ISLNK(mode):
                    raise PackageError(f"directories and symlinks are not allowed: {info.filename!r}")
                if info.flag_bits & 0x1:
                    raise PackageError(f"encrypted files are not allowed: {info.filename!r}")
                if info.compress_type != zipfile.ZIP_STORED or info.date_time != _TIMESTAMP:
                    raise PackageError(f"archive entry is not deterministic: {info.filename!r}")
                digest = hashlib.sha256()
                size = 0
                with bundle.open(info, "r") as source:
                    while chunk := source.read(1024 * 1024):
                        size += len(chunk)
                        expanded += len(chunk)
                        if expanded > MAX_BYTES:
                            raise PackageError(f"expanded output exceeds {MAX_BYTES} bytes")
                        digest.update(chunk)
                actual.append(
                    {"bytes": size, "path": path.as_posix(), "sha256": digest.hexdigest()}
                )
    except (OSError, zipfile.BadZipFile) as exc:
        raise PackageError(f"cannot read archive: {exc}") from exc

    actual.sort(key=lambda entry: str(entry["path"]))
    if actual != expected:
        raise PackageError("archive contents do not exactly match the manifest")
    if manifest.get("file_count") != len(actual) or manifest.get("expanded_bytes") != expanded:
        raise PackageError("manifest totals do not match the archive")
    return manifest


def package(dist: Path, archive: Path, manifest_path: Path) -> dict[str, object]:
    source = dist.expanduser().resolve()
    archive = archive.expanduser().resolve()
    manifest_path = manifest_path.expanduser().resolve()
    if archive == manifest_path:
        raise PackageError("archive and manifest paths must differ")
    if archive == source or source in archive.parents or manifest_path == source or source in manifest_path.parents:
        raise PackageError("archive and manifest must be outside dist")
    archive.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(source)

    temporary: list[Path] = []
    try:
        with tempfile.NamedTemporaryFile(dir=archive.parent, delete=False) as handle:
            archive_tmp = Path(handle.name)
        temporary.append(archive_tmp)
        with tempfile.NamedTemporaryFile(dir=manifest_path.parent, delete=False) as handle:
            manifest_tmp = Path(handle.name)
            handle.write(_manifest_bytes(manifest))
        temporary.append(manifest_tmp)
        _write_archive(source, archive_tmp, manifest)
        validate_package(archive_tmp, manifest_tmp)
        os.replace(archive_tmp, archive)
        temporary.remove(archive_tmp)
        os.replace(manifest_tmp, manifest_path)
        temporary.remove(manifest_tmp)
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", help="Exact dist directory to package")
    parser.add_argument("archive", help="Output .zip path (must be outside dist)")
    parser.add_argument(
        "--manifest",
        help="Output manifest path (default: <archive>.manifest.json)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate an existing archive and manifest; dist is ignored",
    )
    args = parser.parse_args(argv)
    archive = Path(args.archive)
    manifest_path = Path(args.manifest or f"{args.archive}.manifest.json")
    try:
        manifest = (
            validate_package(archive.expanduser().resolve(), manifest_path.expanduser().resolve())
            if args.validate_only
            else package(Path(args.dist), archive, manifest_path)
        )
    except (OSError, PackageError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    result = {
        "archive": str(archive.expanduser().resolve()),
        "expanded_bytes": manifest["expanded_bytes"],
        "file_count": manifest["file_count"],
        "manifest": str(manifest_path.expanduser().resolve()),
        "ok": True,
    }
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
