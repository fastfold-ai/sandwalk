"""omics: shared download + optional-dependency helpers. Split from tools/omics.py."""
import logging
import shutil
from pathlib import Path

from agent.config import CONFIG_DIR

logger = logging.getLogger("tools.omics")

def _downloads_dir() -> Path:
    """Return (and create) the downloads directory."""
    from agent.config import Config

    config = Config.load()
    base = config.get("data.downloads_dir", None)
    if base:
        d = Path(base).expanduser()
    else:
        d = CONFIG_DIR / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _max_download_mb() -> int:
    """Return the configured max download size in MB."""
    from agent.config import Config

    config = Config.load()
    return int(config.get("data.max_download_mb", 500))


def _stream_download(url: str, dest_path: Path, max_mb: int | None = None) -> tuple[Path | None, str | None]:
    """Stream-download a file with size cap.

    Returns (path, None) on success or (None, error_string) on failure.
    """
    import httpx

    if max_mb is None:
        max_mb = _max_download_mb()

    max_bytes = max_mb * 1024 * 1024
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")

    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as resp:
            resp.raise_for_status()

            # Check Content-Length if available
            content_length = resp.headers.get("content-length")
            if content_length and int(content_length) > max_bytes:
                return None, (
                    f"File size ({int(content_length) // (1024*1024)} MB) "
                    f"exceeds limit ({max_mb} MB). "
                    f"Increase with: sandwalk config set data.max_download_mb <value>"
                )

            downloaded = 0
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        tmp_path.unlink(missing_ok=True)
                        return None, (
                            f"Download exceeded size limit ({max_mb} MB). "
                            f"Increase with: sandwalk config set data.max_download_mb <value>"
                        )
                    f.write(chunk)

        # Atomic rename
        shutil.move(str(tmp_path), str(dest_path))
        return dest_path, None

    except httpx.HTTPStatusError as exc:
        tmp_path.unlink(missing_ok=True)
        return None, f"HTTP {exc.response.status_code}: {str(exc)[:200]}"
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        return None, f"Download failed: {str(exc)[:200]}"


def _check_scanpy():
    """Check if scanpy is available."""
    try:
        import scanpy as sc

        return sc
    except Exception as exc:
        logger.debug("scanpy unavailable or failed to import: %s", exc)
        return None


def _check_pydeseq2():
    """Check if pyDESeq2 is available."""
    try:
        import pydeseq2.dds  # noqa: F401
        import pydeseq2.ds  # noqa: F401

        return True
    except Exception as exc:
        logger.debug("pyDESeq2 unavailable or failed to import: %s", exc)
        return False


def _check_muon():
    """Check if muon is available."""
    try:
        import muon

        return muon
    except Exception as exc:
        logger.debug("muon unavailable or failed to import: %s", exc)
        return None


def _check_episcanpy():
    """Check if episcanpy is available."""
    try:
        import episcanpy.api as epi

        return epi
    except Exception as exc:
        logger.debug("episcanpy unavailable or failed to import: %s", exc)
        return None
