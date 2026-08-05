"""Extract absolute local artifact paths from tool stdout / result text.

Used so shell formatting and the final answer can surface download paths even
when large CloudFront URL lists would otherwise push them past truncation.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Absolute paths ending in common research artifact extensions.
_ABS_FILE_RE = re.compile(
    r"(?:/Users|/home|~)/[^\s\"'\]\,<>]+?\."
    r"(?:cif|pdb|mmcif|svg|png|jpe?g|gif|json|md|csv|tsv|txt|html?|pdf|"
    r"npz|npzz|zip|tar|gz|npy|npz|pkl|fa|fasta|yaml|yml)",
    re.IGNORECASE,
)

_DOWNLOADED_BLOCK_RE = re.compile(
    r"DOWNLOADED_LOCAL_PATHS:\s*\n((?:[^\n]+\n?)*)",
    re.IGNORECASE,
)


def _normalize_path(raw: str) -> str:
    text = str(raw or "").strip().rstrip(".,;:)]}'\"`")
    if text.startswith("file://"):
        text = text[7:]
    return text


def _paths_from_obj(obj: Any) -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        for key in ("local_paths", "paths"):
            val = obj.get(key)
            if isinstance(val, list):
                out.extend(_normalize_path(p) for p in val if isinstance(p, str))
        downloads = obj.get("downloads")
        if isinstance(downloads, dict):
            for item in downloads.get("downloaded") or []:
                if isinstance(item, dict) and isinstance(item.get("path"), str):
                    out.append(_normalize_path(item["path"]))
        for item in obj.get("embedded_downloads") or []:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                out.append(_normalize_path(item["path"]))
        # Nested stdout sometimes embeds another JSON blob.
        for key in ("stdout", "output", "result"):
            nested = obj.get(key)
            if isinstance(nested, str) and nested.strip().startswith(("{", "[")):
                out.extend(extract_local_artifact_paths(nested))
    return out


def extract_local_artifact_paths(text: str) -> list[str]:
    """Return unique absolute-looking local file paths from tool text/JSON."""
    raw = str(text or "")
    if not raw.strip():
        return []

    found: list[str] = []

    block = _DOWNLOADED_BLOCK_RE.search(raw)
    if block:
        for line in block.group(1).splitlines():
            line = _normalize_path(line)
            if line.startswith(("/", "~")):
                found.append(line)

    stripped = raw.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            found.extend(_paths_from_obj(json.loads(stripped)))
        except json.JSONDecodeError:
            pass
    else:
        # shell.run wraps JSON after a summary line — try first `{...}` blob.
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                found.extend(_paths_from_obj(json.loads(raw[start : end + 1])))
            except json.JSONDecodeError:
                pass

    for match in _ABS_FILE_RE.finditer(raw):
        found.append(_normalize_path(match.group(0)))

    # Dedupe preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for path in found:
        if not path or path in seen:
            continue
        # Skip truncated leftovers.
        if "..." in path or "…" in path:
            continue
        seen.add(path)
        out.append(path)
    return out


def _is_session_artifact_path(path: str) -> bool:
    """Prefer workspace downloads over incidental project/skill file reads."""
    lowered = path.replace("\\", "/").lower()
    return (
        "/.sandwalk/workspaces/" in lowered
        or "/artifacts/" in lowered
        or "/exports/" in lowered
    )


def collect_paths_from_tool_calls(tool_calls: list[dict] | None) -> list[str]:
    """Gather local artifact paths from recorded tool call results."""
    found: list[str] = []
    for tc in tool_calls or []:
        if not isinstance(tc, dict):
            continue
        for key in ("local_paths",):
            val = tc.get(key)
            if isinstance(val, list):
                found.extend(_normalize_path(p) for p in val if isinstance(p, str))
        for key in ("result_text", "output", "stdout"):
            val = tc.get(key)
            if isinstance(val, str):
                found.extend(extract_local_artifact_paths(val))
            elif isinstance(val, dict):
                found.extend(_paths_from_obj(val))
                if isinstance(val.get("stdout"), str):
                    found.extend(extract_local_artifact_paths(val["stdout"]))
    seen: set[str] = set()
    out: list[str] = []
    for path in found:
        if not path or path in seen or "..." in path or "…" in path:
            continue
        if not _is_session_artifact_path(path):
            continue
        seen.add(path)
        out.append(path)
    return out


def append_downloaded_artifacts_block(summary: str, paths: list[str]) -> str:
    """Append a deterministic absolute-path list when the answer omitted them."""
    if not paths:
        return summary
    text = str(summary or "")
    missing = [p for p in paths if p not in text]
    if not missing:
        return text
    block = "Downloaded artifacts:\n" + "\n".join(missing)
    if not text.strip():
        return block
    return text.rstrip() + "\n\n" + block
