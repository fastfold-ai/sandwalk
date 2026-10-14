"""Which agent CLIs are installed, and which one a PTY is running right now."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from agent.external_agents.types import AGENT_BINARIES, AGENT_KINDS, AGENT_LABELS, ExternalAgentKind

# Process names (``ps -o comm``) that identify each agent. ``claude`` and
# ``codex`` are single native binaries; ``opencode`` and ``fx`` too. Node-based
# launchers show up as ``node`` with the script in argv, handled by _argv_kind.
_PROC_NAMES: dict[str, ExternalAgentKind] = {
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "fx": "fx",
}


def binary_for(kind: str) -> str | None:
    name = AGENT_BINARIES.get(kind)
    return shutil.which(name) if name else None


def installed_agents() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind in AGENT_KINDS:
        path = binary_for(kind)
        rows.append(
            {
                "kind": kind,
                "label": AGENT_LABELS[kind],
                "installed": bool(path),
                "path": path,
            }
        )
    return rows


def _ps_in_group(pgid: int) -> str | None:
    """List processes in a process group.

    GNU ``ps`` (Linux CI) treats ``-g`` as a session id; the process group
    flag there is ``--pgrp``. BSD ``ps`` (macOS) has no ``--pgrp`` and uses
    ``-g`` for the process group. Try GNU first and fall back.
    """
    attempts = (
        ["ps", "-o", "pid=,comm=,args=", "--pgrp", str(pgid)],
        ["ps", "-o", "pid=,comm=,args=", "-g", str(pgid)],
    )
    for argv in attempts:
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if completed.returncode == 0 and completed.stdout.strip():
            return completed.stdout
    return None


def _argv_kind(argv: str) -> ExternalAgentKind | None:
    parts = argv.split()
    if not parts:
        return None
    for part in parts[:3]:
        base = Path(part).name.lower()
        if base in _PROC_NAMES:
            return _PROC_NAMES[base]
    return None


def foreground_agent(master_fd: int, shell_pid: int) -> tuple[ExternalAgentKind | None, str | None]:
    """Return (agent kind, cwd) for the process group in the foreground of a PTY.

    Uses ``tcgetpgrp`` on the master side to find the foreground process
    group, then ``ps`` to read its command. Returns ``(None, None)`` when the
    shell itself is in the foreground or the lookup fails.
    """
    try:
        pgid = os.tcgetpgrp(master_fd)
    except OSError:
        return None, None
    if pgid <= 0 or pgid == shell_pid:
        return None, None
    out = _ps_in_group(pgid)
    if out is None:
        return None, None
    kind: ExternalAgentKind | None = None
    pid: int | None = None
    for line in out.splitlines():
        fields = line.split(None, 2)
        if len(fields) < 2:
            continue
        comm = Path(fields[1]).name.lower()
        found = _PROC_NAMES.get(comm) or (_argv_kind(fields[2]) if len(fields) > 2 else None)
        if found:
            kind = found
            try:
                pid = int(fields[0])
            except ValueError:
                pid = None
            break
    if kind is None:
        return None, None
    return kind, _cwd_of(pid)


def _cwd_of(pid: int | None) -> str | None:
    if not pid:
        return None
    proc = Path(f"/proc/{pid}/cwd")
    if proc.exists():
        try:
            return os.readlink(proc)
        except OSError:
            return None
    try:
        out = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in out.splitlines():
        if line.startswith("n/"):
            return line[1:]
    return None
