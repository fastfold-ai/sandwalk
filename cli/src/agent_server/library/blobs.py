"""Content-addressed blob storage under ~/.sandwalk/library/blobs/."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path


def default_library_root() -> Path:
    return Path.home() / ".sandwalk" / "library"


class LibraryBlobStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or default_library_root()).expanduser().resolve()
        self.blobs_dir = self.root / "blobs"
        self.blobs_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, sha256: str) -> Path:
        return self.blobs_dir / sha256

    def exists(self, sha256: str) -> bool:
        return self.path_for(sha256).is_file()

    def put_bytes(self, data: bytes) -> tuple[str, int]:
        digest = hashlib.sha256(data).hexdigest()
        dest = self.path_for(digest)
        if dest.is_file():
            return digest, len(data)
        fd, tmp_name = tempfile.mkstemp(dir=self.blobs_dir, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp_name, dest)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        return digest, len(data)

    def put_file(self, source: Path) -> tuple[str, int]:
        hasher = hashlib.sha256()
        size = 0
        with source.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
                size += len(chunk)
        digest = hasher.hexdigest()
        dest = self.path_for(digest)
        if dest.is_file():
            return digest, size
        fd, tmp_name = tempfile.mkstemp(dir=self.blobs_dir, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as out, source.open("rb") as inp:
                shutil.copyfileobj(inp, out)
            os.replace(tmp_name, dest)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        return digest, size

    def materialize(self, sha256: str, dest: Path) -> None:
        """Hardlink blob into dest, or copy if hardlink fails."""
        src = self.path_for(sha256)
        if not src.is_file():
            raise FileNotFoundError(f"Library blob missing: {sha256}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        try:
            os.link(src, dest)
        except OSError:
            shutil.copy2(src, dest)

    def maybe_delete_blob(self, sha256: str) -> bool:
        path = self.path_for(sha256)
        if not path.is_file():
            return False
        path.unlink()
        return True
