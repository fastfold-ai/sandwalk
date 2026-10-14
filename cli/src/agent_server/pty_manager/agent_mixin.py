"""Detect which coding-agent CLI (claude / codex / opencode / fx) a PTY is running.

The probe reads the PTY's foreground process group and asks ``ps`` for its
command. That is cheap but not free, so it is rate-limited per PTY and only
runs when the UI reads the terminal list or when output is flowing.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from agent_server.pty_manager.types import PtySession

# Minimum seconds between probes of the same PTY.
AGENT_PROBE_INTERVAL_S = 2.0


class PtyAgentMixin:
    _sessions: dict[str, PtySession]

    def refresh_agent(self, session: PtySession, *, force: bool = False) -> bool:
        """Re-probe the foreground agent. Returns True when it changed."""
        now = time.monotonic()
        if not force and now - session.agent_probed_at < AGENT_PROBE_INTERVAL_S:
            return False
        session.agent_probed_at = now
        if session.info.status != "running":
            changed = session.info.agent is not None
            session.info.agent = None
            session.info.agent_cwd = None
            return changed
        from agent.external_agents import foreground_agent

        kind, cwd = foreground_agent(session.master_fd, session.info.pid)
        changed = kind != session.info.agent or (kind is not None and cwd != session.info.agent_cwd)
        session.info.agent = kind
        session.info.agent_cwd = cwd if kind else None
        return changed

    def refresh_agents_for(self, session_id: str) -> None:
        for pty in list(self._sessions.values()):
            if pty.info.session_id == session_id:
                self.refresh_agent(pty)

    async def _maybe_announce_agent(self, session: PtySession) -> None:
        """Called from the read loop; broadcasts ``agent.changed`` when it flips."""
        if not self.refresh_agent(session):
            return
        frame = json.dumps(
            {
                "type": "pty.event",
                "terminalId": session.info.session_id,
                "event": {
                    "kind": "agent.changed",
                    "agent": session.info.agent,
                    "agentCwd": session.info.agent_cwd,
                },
            }
        )
        stale: list[Any] = []
        for ws in list(session.subscribers):
            try:
                await ws.send_text(frame)
            except Exception:
                stale.append(ws)
        for ws in stale:
            session.subscribers.discard(ws)

    async def watch_agent_while_attached(self, session: PtySession, websocket: Any) -> None:
        """Probe on a timer while ``websocket`` is attached.

        Output-driven probes miss the common case: a TUI agent prints its
        banner, then sits idle waiting for input. A 2 s tick costs one ``ps``
        per attached terminal and keeps the tab icon honest.
        """
        try:
            while websocket in session.subscribers and session.info.status == "running":
                await asyncio.sleep(AGENT_PROBE_INTERVAL_S)
                if websocket not in session.subscribers:
                    break
                await self._maybe_announce_agent(session)
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001 - never let a probe kill the attach loop
            pass

    async def type_startup(self, session: PtySession, command: str, *, delay_s: float = 0.35) -> None:
        """Type ``command`` + Enter into the PTY once the shell has had a moment to start."""
        import os

        text = str(command or "").strip()
        if not text:
            return
        await asyncio.sleep(delay_s)
        if session.info.status != "running":
            return
        try:
            os.write(session.master_fd, (text + "\r").encode("utf-8"))
        except OSError:
            return
        # The agent takes a beat to exec; probe shortly after so the first
        # terminal list already carries the icon.
        await asyncio.sleep(0.8)
        session.agent_probed_at = 0.0
        await self._maybe_announce_agent(session)
