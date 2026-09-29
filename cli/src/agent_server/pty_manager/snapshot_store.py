"""FAS-107 X4 Capa 2 · Terminal buffer snapshot persistence.

**Approach:** raw byte log del PTY guardado por `session_id`. Al reabrir
la app, el frontend hace `xterm.resize(currentCols, currentRows)` y
después `xterm.write(rawBytes)` — xterm procesa cada byte con las dims
ACTUALES del cliente y aplica su reflow interno correctamente. Esto
elimina el bug de "layout roto" del approach anterior (que serializaba
con dims viejas y las escribía en dims nuevas).

Indexado por `session_id` (no por `pty_id`) porque el PTY se recrea
al reabrir la app (proceso muere con Cmd+Q). El "cuaderno visual" del
terminal debe sobrevivir a la muerte del PTY.

Almacenamiento: un archivo binario por `session_id` en
`SANDWALK_TERMINAL_SNAPSHOTS_DIR` (Tauri lo setea al `app_data_dir` en
boot), o fallback `~/.sandwalk/terminal-snapshots/`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


def _snapshots_dir() -> Path:
    """Resolve the on-disk directory for snapshot files."""
    override = os.environ.get("SANDWALK_TERMINAL_SNAPSHOTS_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".sandwalk" / "terminal-snapshots"


def _snapshot_path(session_id: str) -> Path:
    safe_id = session_id.replace("/", "_").replace("..", "_")
    return _snapshots_dir() / f"{safe_id}.bin"


def read_snapshot(session_id: str) -> bytes | None:
    """Return the persisted raw byte log, or `None` if none exists."""
    path = _snapshot_path(session_id)
    if not path.exists():
        return None
    try:
        return path.read_bytes()
    except OSError as exc:
        log.warning("Failed to read snapshot %s: %s", path, exc)
        return None


def write_snapshot(session_id: str, data: bytes) -> None:
    """Persist raw PTY output bytes to disk. Idempotent."""
    directory = _snapshots_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("Failed to create snapshots dir %s: %s", directory, exc)
        return
    path = _snapshot_path(session_id)
    try:
        path.write_bytes(data)
    except OSError as exc:
        log.warning("Failed to write snapshot %s: %s", path, exc)


def delete_snapshot(session_id: str) -> None:
    """Remove a snapshot file when the terminal is deleted upstream."""
    path = _snapshot_path(session_id)
    if not path.exists():
        return
    try:
        path.unlink()
    except OSError as exc:
        log.warning("Failed to delete snapshot %s: %s", path, exc)
