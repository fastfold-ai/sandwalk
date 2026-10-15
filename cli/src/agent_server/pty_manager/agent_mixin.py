"""Detect which coding-agent CLI (claude / codex / opencode / fx) a PTY is running.

The probe has two tiers:

1. ``tcgetpgrp`` on the master fd — one syscall, microseconds. Tells us the
   foreground process *group*. If it has not changed since the last probe
   there is nothing to do; the shell is still the shell or the agent is
   still the agent.
2. Only when the group changes, resolve what it is. That shells out to
   ``ps`` (≈50 ms on a busy Mac) and must never run on the asyncio loop
   that pumps every PTY's bytes — it goes through ``asyncio.to_thread``.

Before this split the ``ps`` tier ran inline on every output burst, every
2 s tick per attached terminal, and every terminal-list request. With a
dozen terminals open that blocked the event loop for hundreds of
milliseconds per second and every keystroke felt late.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

from agent_server.pty_manager.types import PtySession

# Minimum seconds between pgrp checks of the same PTY (cheap, so frequent).
AGENT_PROBE_INTERVAL_S = 1.0
# After the shell hook reports an agent, the pgrp probe must not clear it
# for this long (the hook fires at preexec, before the agent has exec'd).
HOOK_GRACE_S = 3.0


def _foreground_pgid(master_fd: int) -> int:
    try:
        return os.tcgetpgrp(master_fd)
    except OSError:
        return -1


class PtyAgentMixin:
    _sessions: dict[str, PtySession]

    def _apply_agent(
        self, session: PtySession, kind: str | None, cwd: str | None, *, from_hook: bool = False
    ) -> bool:
        if from_hook:
            session.agent_from_hook_at = time.monotonic() if kind else 0.0
        elif (
            kind is None
            and session.info.agent is not None
            and time.monotonic() - session.agent_from_hook_at < HOOK_GRACE_S
        ):
            # Probe says "shell in foreground" but the hook just said an
            # agent is starting; the agent has not exec'd yet. Keep the hook.
            return False
        changed = kind != session.info.agent or (kind is not None and cwd != session.info.agent_cwd)
        session.info.agent = kind
        session.info.agent_cwd = cwd if kind else None
        return changed

    def refresh_agent(self, session: PtySession, *, force: bool = False) -> bool:
        """Synchronous probe. Cheap path only unless ``force``.

        Returns True when the recorded agent changed. Without ``force`` this
        never shells out: if the foreground group is unchanged the cached
        answer stands; if it changed, the agent is marked unknown (``None``)
        until the async resolver runs. Callers on the event loop should use
        :meth:`refresh_agent_async` instead so ``ps`` runs off-loop.
        """
        now = time.monotonic()
        if not force and now - session.agent_probed_at < AGENT_PROBE_INTERVAL_S:
            return False
        session.agent_probed_at = now
        if session.info.status != "running":
            return self._apply_agent(session, None, None)
        pgid = _foreground_pgid(session.master_fd)
        if pgid == session.agent_pgid and not force:
            return False
        session.agent_pgid = pgid
        if pgid <= 0 or pgid == session.info.pid:
            # Shell itself is in the foreground: no agent, no ps needed.
            return self._apply_agent(session, None, None)
        if not force:
            # Group changed; leave the current answer until the async
            # resolver (ps in a thread) confirms what it is.
            return False
        from agent.external_agents import foreground_agent

        kind, cwd = foreground_agent(session.master_fd, session.info.pid)
        return self._apply_agent(session, kind, cwd)

    async def refresh_agent_async(self, session: PtySession, *, force: bool = False) -> bool:
        """Probe without blocking the loop. ``ps`` runs in a worker thread."""
        now = time.monotonic()
        if not force and now - session.agent_probed_at < AGENT_PROBE_INTERVAL_S:
            return False
        session.agent_probed_at = now
        if session.info.status != "running":
            return self._apply_agent(session, None, None)
        pgid = _foreground_pgid(session.master_fd)
        if pgid == session.agent_pgid and not force:
            return False
        session.agent_pgid = pgid
        if pgid <= 0 or pgid == session.info.pid:
            return self._apply_agent(session, None, None)
        if session.agent_resolving:
            return False
        session.agent_resolving = True
        try:
            from agent.external_agents import foreground_agent

            kind, cwd = await asyncio.to_thread(
                foreground_agent, session.master_fd, session.info.pid
            )
        finally:
            session.agent_resolving = False
        # The group may have moved on while ps ran; only apply if it is
        # still the one we resolved.
        if _foreground_pgid(session.master_fd) != pgid:
            return False
        return self._apply_agent(session, kind, cwd)

    def refresh_agents_for(self, session_id: str) -> None:
        for pty in list(self._sessions.values()):
            if pty.info.session_id == session_id:
                self.refresh_agent(pty)

    def _agent_frame(self, session: PtySession) -> str:
        return json.dumps(
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

    async def _broadcast_agent(self, session: PtySession) -> None:
        frame = self._agent_frame(session)
        stale: list[Any] = []
        for ws in list(session.subscribers):
            try:
                await ws.send_text(frame)
            except Exception:
                stale.append(ws)
        for ws in stale:
            session.subscribers.discard(ws)

    async def _maybe_announce_agent(self, session: PtySession, *, force: bool = False) -> None:
        """Called from the read loop and the attach watcher; broadcasts on change."""
        if await self.refresh_agent_async(session, force=force):
            await self._broadcast_agent(session)

    async def watch_agent_while_attached(self, session: PtySession, websocket: Any) -> None:
        """Probe on a timer while ``websocket`` is attached.

        Output-driven probes miss the common case: a TUI agent prints its
        banner, then sits idle waiting for input. The tick is one syscall
        per attached terminal; ``ps`` only runs when the group flips.
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

    async def type_startup(
        self, session: PtySession, command: str, *, delay_s: float = 0.35
    ) -> None:
        """Type ``command`` + Enter into the PTY once the shell has had a moment to start."""
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
        await self._maybe_announce_agent(session, force=True)
