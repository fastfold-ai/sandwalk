"""Stateful parser for OSC sequences of interest in the PTY stream.

Handles three families of escape sequences the PTY may emit:

- **OSC 133** (Semantic Prompt) — command lifecycle markers written by
  the shell integration script (`shell_env.py`). Emits:
    * `command.started` when `\\e]133;C\\a` is seen (preexec).
    * `command.finished` with `exit_code` when `\\e]133;D;<n>\\a` is
      seen (precmd of the *next* prompt). Duration is computed by
      the caller using its own `time.monotonic()`.
- **OSC 9** — Growl/iTerm notification: `\\e]9;<body>\\a`. Body is
  the plain notification text; no title.
- **OSC 777** — extended notify: `\\e]777;notify;<title>;<body>\\a`.

Design notes:
- Bytes may arrive split across chunks (a shell prompt often flushes
  in pieces). The parser buffers *only* the tail bytes that could be
  part of an in-flight sequence — everything else stays in the raw
  output stream unchanged.
- Terminators supported: BEL (`\\x07`) and ST (`\\x1b\\x5c`).
- Payloads are decoded as UTF-8 with `errors="replace"`; a malformed
  sequence never crashes the read loop.
- The parser is intentionally *non-consuming* of the raw stream — the
  bytes still go to xterm; the frontend receives the parsed event on
  a parallel WebSocket frame. Rationale: xterm ignores OSC 133 by
  default, so leaving the bytes in the stream is harmless and keeps
  the terminal buffer identical to what the shell wrote.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

# ESC ] introduces an OSC sequence.
_ESC = 0x1B
_OSC_INTRODUCER = 0x5D  # ']'
_BEL = 0x07
_BACKSLASH = 0x5C  # part of ST terminator: ESC '\'

# Safety cap: no legitimate OSC we care about is longer than a few KB.
# Runaway sequences (e.g. an OSC 133 D with a broken/huge payload) get
# dropped silently instead of ballooning memory.
_MAX_OSC_PAYLOAD = 4096

# FAS-107 · Fase 1j · timeout de sequence hold. Complementa
# `_MAX_OSC_PAYLOAD`: si el `\x07` o el ST nunca llegan pero los bytes
# entran de a uno lentamente (no supera el cap de 4KB en horas), el
# buffer quedaba en RAM indefinido. Con este timeout, si un OSC no
# cierra en 5s se descarta y el parser vuelve a estado limpio.
_OSC_HOLD_TIMEOUT_SEC = 5.0


PtyEventKind = Literal["command.started", "command.finished", "notify", "agent.hook"]

# Title our own shell hooks put in OSC 777 so agent markers never surface
# as user notifications: `777;notify;Sandwalk;agent;<kind>;started|exited`.
_HOOK_TITLE = "Sandwalk"
_HOOK_AGENTS = frozenset({"claude", "codex", "opencode", "fx", "hermes"})


@dataclass
class PtyEvent:
    """A structured event emitted by the parser."""

    kind: PtyEventKind
    # OSC 133 D
    exit_code: int | None = None
    # OSC 9 / OSC 777
    title: str | None = None
    body: str | None = None
    # agent.hook: which CLI, and None when it exited
    agent: str | None = None


@dataclass
class OscParser:
    """Stream-friendly OSC parser. Feed bytes, get events."""

    _buf: bytearray = field(default_factory=bytearray)
    _in_osc: bool = False
    _pending_esc: bool = False
    # When True the parser saw ESC inside an OSC payload and is waiting
    # for '\\' to complete the ST terminator.
    _in_st_terminator: bool = False
    # FAS-107 · Fase 1j · timestamp del OSC introducer (`\e]`). Se
    # chequea al recibir cada chunk; si excede `_OSC_HOLD_TIMEOUT_SEC`
    # sin cerrarse, el parser resetea. `None` cuando no hay OSC en curso.
    _osc_started_at: float | None = None

    def feed(self, chunk: bytes) -> list[PtyEvent]:
        """Consume a chunk of raw PTY output and return detected events.

        The chunk itself is *not* mutated or filtered — it should still
        be forwarded to subscribers as-is. Only the parser's internal
        state advances.
        """
        events: list[PtyEvent] = []
        # Descartar OSC en curso si lleva demasiado tiempo abierto.
        # Protege contra scripts que emiten `\e]777;` y nunca cierran
        # con `\x07` — sin este check, el buffer crecería hasta el cap
        # de 4KB en RAM (posiblemente en múltiples terminales).
        if (
            self._in_osc
            and self._osc_started_at is not None
            and time.monotonic() - self._osc_started_at > _OSC_HOLD_TIMEOUT_SEC
        ):
            self._reset()
        for byte in chunk:
            if not self._in_osc:
                if self._pending_esc and byte == _OSC_INTRODUCER:
                    self._pending_esc = False
                    self._in_osc = True
                    self._osc_started_at = time.monotonic()
                    self._buf.clear()
                elif byte == _ESC:
                    self._pending_esc = True
                else:
                    self._pending_esc = False
                continue

            # Inside an OSC payload.
            if self._in_st_terminator:
                self._in_st_terminator = False
                if byte == _BACKSLASH:
                    self._finalize(events)
                    continue
                # False alarm: the ESC was payload after all. Put it
                # back so it participates in downstream length limits.
                self._buf.append(_ESC)
                # fallthrough to normal byte handling for `byte`
            if byte == _BEL:
                self._finalize(events)
                continue
            if byte == _ESC:
                self._in_st_terminator = True
                continue
            if len(self._buf) >= _MAX_OSC_PAYLOAD:
                # Runaway payload — abort this sequence.
                self._reset()
                continue
            self._buf.append(byte)

        return events

    def _finalize(self, events: list[PtyEvent]) -> None:
        payload = self._buf.decode("utf-8", errors="replace")
        self._reset()
        event = _parse_payload(payload)
        if event is not None:
            events.append(event)

    def _reset(self) -> None:
        self._buf.clear()
        self._in_osc = False
        self._pending_esc = False
        self._in_st_terminator = False
        self._osc_started_at = None


def _parse_payload(payload: str) -> PtyEvent | None:
    """Turn a decoded OSC payload (without introducer/terminator) into an event."""
    if not payload:
        return None
    ident, sep, rest = payload.partition(";")
    if ident == "133":
        # OSC 133 subcommand lives in `rest[0]`. Only C and D are
        # interesting for notifications — A/B are prompt markers with
        # no lifecycle meaning here.
        if not rest:
            return None
        sub = rest[0]
        if sub == "C":
            return PtyEvent(kind="command.started")
        if sub == "D":
            # Format is either "D" (no exit code) or "D;<n>".
            exit_code: int | None = None
            after = rest[1:]
            if after.startswith(";"):
                try:
                    exit_code = int(after[1:].strip())
                except ValueError:
                    exit_code = None
            return PtyEvent(kind="command.finished", exit_code=exit_code)
        return None
    if ident == "9":
        # OSC 9;<body>
        if not sep:
            return None
        return PtyEvent(kind="notify", body=rest)
    if ident == "777":
        # OSC 777;notify;<title>;<body>
        if not sep:
            return None
        kind, sep2, tail = rest.partition(";")
        if kind != "notify" or not sep2:
            return None
        title, sep3, body = tail.partition(";")
        if title == _HOOK_TITLE and sep3 and body.startswith("agent;"):
            # Our shell hook: `agent;<kind>;started` | `agent;<kind>;exited`.
            parts = body.split(";", 2)
            agent = parts[1] if len(parts) > 1 else ""
            state = parts[2] if len(parts) > 2 else ""
            if agent not in _HOOK_AGENTS:
                return None
            return PtyEvent(kind="agent.hook", agent=agent if state == "started" else None)
        return PtyEvent(kind="notify", title=title, body=body if sep3 else None)
    return None
