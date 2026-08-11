"""Shared helpers for trace capture: session paths, meta parsing, plot embedding."""

import base64
import json
import logging
import mimetypes
from pathlib import Path

from agent.config import CONFIG_DIR

logger = logging.getLogger("trace_store")

# Marker used by MCP handlers to embed structured metadata in tool results
TRACE_META_MARKER = "\n__CT_TRACE_META__\n"

# Maximum file size for base64 embedding (10 MB)
_MAX_EMBED_BYTES = 10 * 1024 * 1024


def sessions_dir() -> Path:
    """Return the sessions directory, creating it if needed."""
    d = CONFIG_DIR / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def parse_trace_meta(result_text: str) -> dict | None:
    """Extract __CT_TRACE_META__ JSON from a tool result string.

    Returns the parsed dict, or None if no marker found.
    """
    if TRACE_META_MARKER not in result_text:
        return None
    try:
        _, meta_json = result_text.split(TRACE_META_MARKER, 1)
        return json.loads(meta_json.strip())
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("Failed to parse trace meta: %s", e)
        return None


def embed_plots(event: dict) -> None:
    """Read plot files and add base64-encoded data to the event in-place."""
    plots = event.get("plots", [])
    if not plots:
        return

    embedded = []
    for plot_path_str in plots:
        plot_path = Path(plot_path_str)
        if not plot_path.exists():
            logger.warning("Plot file missing at capture time: %s", plot_path)
            continue
        if plot_path.stat().st_size > _MAX_EMBED_BYTES:
            logger.warning(
                "Plot file too large for embedding (%d bytes): %s",
                plot_path.stat().st_size,
                plot_path,
            )
            continue

        mime, _ = mimetypes.guess_type(str(plot_path))
        if mime is None:
            suffix_map = {
                ".png": "image/png",
                ".svg": "image/svg+xml",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".pdf": "application/pdf",
            }
            mime = suffix_map.get(plot_path.suffix.lower(), "application/octet-stream")

        try:
            data = base64.b64encode(plot_path.read_bytes()).decode("ascii")
            embedded.append({
                "filename": plot_path.name,
                "mime": mime,
                "data": data,
            })
        except OSError as e:
            logger.warning("Failed to read plot file %s: %s", plot_path, e)

    if embedded:
        event["plots_base64"] = embedded
