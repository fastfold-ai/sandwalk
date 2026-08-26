"""FAS-107 X4 Capa 2 · Terminal buffer snapshot persistence.

Warp/iTerm2/VSCode pattern: at Cmd+Q the frontend serializes each
xterm buffer with `@xterm/addon-serialize` and PUTs the string here.
On reopen the frontend GETs the string back and does `term.write(...)`
before connecting the WebSocket — the buffer looks identical to how
the user left it. The PTY itself is fresh (no process persistence);
only the visual state survives.

Storage layout: one plain text file per (session_id, pty_id) tuple in
`SANDWALK_TERMINAL_SNAPSHOTS_DIR` (defaults to
`~/.sandwalk/terminal-snapshots/`). The filename escapes both ids so
they never collide.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


def _snapshots_dir() -> Path:
    """Resolve the on-disk directory for snapshot files.

    Priority:
    1. `SANDWALK_TERMINAL_SNAPSHOTS_DIR` env var (Tauri sets this to
       `app_data_dir/terminal-snapshots` at boot for consistency with
       macOS conventions).
    2. Fallback to `~/.sandwalk/terminal-snapshots/` so CLI-only usage
       still works.
    """
    override = os.environ.get("SANDWALK_TERMINAL_SNAPSHOTS_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".sandwalk" / "terminal-snapshots"


def _snapshot_path(session_id: str, pty_id: str) -> Path:
    # Escape the separator to avoid path traversal or collision on
    # weird ids. The double underscore is unlikely in real ids.
    safe_session = session_id.replace("/", "_").replace("..", "_")
    safe_pty = pty_id.replace("/", "_").replace("..", "_")
    return _snapshots_dir() / f"{safe_session}__{safe_pty}.txt"


def read_snapshot(session_id: str, pty_id: str) -> str | None:
    """Return the persisted snapshot, or `None` if none exists."""
    path = _snapshot_path(session_id, pty_id)
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("Failed to read snapshot %s: %s", path, exc)
        return None


def write_snapshot(session_id: str, pty_id: str, data: str) -> None:
    """Persist the serialized xterm buffer to disk. Idempotent."""
    directory = _snapshots_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("Failed to create snapshots dir %s: %s", directory, exc)
        return
    path = _snapshot_path(session_id, pty_id)
    try:
        path.write_text(data, encoding="utf-8")
    except OSError as exc:
        log.warning("Failed to write snapshot %s: %s", path, exc)


def delete_snapshot(session_id: str, pty_id: str) -> None:
    """Remove a snapshot file when the terminal is deleted upstream."""
    path = _snapshot_path(session_id, pty_id)
    if not path.exists():
        return
    try:
        path.unlink()
    except OSError as exc:
        log.warning("Failed to delete snapshot %s: %s", path, exc)
