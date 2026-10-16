"""Unit tests for the PTY OSC parser and terminal snapshot store (FAS-107)."""

from __future__ import annotations

import time

import pytest

from agent_server.pty_manager import osc_parser
from agent_server.pty_manager.osc_parser import OscParser, PtyEvent
from agent_server.pty_manager.snapshot_store import (
    delete_snapshot,
    read_snapshot,
    write_snapshot,
)

BEL = b"\x07"
ST = b"\x1b\\"


def _kinds(events: list[PtyEvent]) -> list[str]:
    return [event.kind for event in events]


class TestOsc133:
    def test_command_started_and_finished_with_exit_code(self) -> None:
        parser = OscParser()
        events = parser.feed(b"\x1b]133;C" + BEL + b"ls -la\r\n" + b"\x1b]133;D;0" + BEL)
        assert _kinds(events) == ["command.started", "command.finished"]
        assert events[1].exit_code == 0

    def test_non_zero_exit_code(self) -> None:
        parser = OscParser()
        events = parser.feed(b"\x1b]133;D;127" + BEL)
        assert events == [PtyEvent(kind="command.finished", exit_code=127)]

    def test_finished_without_exit_code(self) -> None:
        events = OscParser().feed(b"\x1b]133;D" + BEL)
        assert events == [PtyEvent(kind="command.finished", exit_code=None)]

    def test_malformed_exit_code_is_none(self) -> None:
        events = OscParser().feed(b"\x1b]133;D;abc" + BEL)
        assert events[0].exit_code is None

    def test_prompt_markers_a_and_b_are_ignored(self) -> None:
        events = OscParser().feed(b"\x1b]133;A" + BEL + b"\x1b]133;B" + BEL)
        assert events == []

    def test_st_terminator(self) -> None:
        events = OscParser().feed(b"\x1b]133;D;2" + ST)
        assert events == [PtyEvent(kind="command.finished", exit_code=2)]


class TestChunking:
    def test_sequence_split_across_chunks(self) -> None:
        parser = OscParser()
        assert parser.feed(b"prompt$ \x1b") == []
        assert parser.feed(b"]133;D") == []
        assert parser.feed(b";4") == []
        events = parser.feed(BEL + b"more output")
        assert events == [PtyEvent(kind="command.finished", exit_code=4)]

    def test_st_split_between_esc_and_backslash(self) -> None:
        parser = OscParser()
        assert parser.feed(b"\x1b]9;hello\x1b") == []
        events = parser.feed(b"\\")
        assert events == [PtyEvent(kind="notify", body="hello")]

    def test_esc_inside_payload_that_is_not_st_is_kept(self) -> None:
        # ESC followed by something other than '\' is payload, not a terminator.
        parser = OscParser()
        events = parser.feed(b"\x1b]9;a\x1bZb" + BEL)
        assert events == [PtyEvent(kind="notify", body="a\x1bZb")]

    def test_stray_esc_does_not_open_osc(self) -> None:
        parser = OscParser()
        assert parser.feed(b"\x1b[31mred\x1b[0m") == []
        # Parser is back to a clean state and still detects a real OSC.
        assert _kinds(parser.feed(b"\x1b]133;C" + BEL)) == ["command.started"]

    def test_plain_output_yields_nothing(self) -> None:
        assert OscParser().feed(b"hello world\r\n" * 100) == []


class TestNotifications:
    def test_osc9_body(self) -> None:
        events = OscParser().feed(b"\x1b]9;Build finished" + BEL)
        assert events == [PtyEvent(kind="notify", body="Build finished")]

    def test_osc9_without_separator_is_ignored(self) -> None:
        assert OscParser().feed(b"\x1b]9" + BEL) == []

    def test_osc777_title_and_body(self) -> None:
        events = OscParser().feed(b"\x1b]777;notify;Deploy;All green" + BEL)
        assert events == [PtyEvent(kind="notify", title="Deploy", body="All green")]

    def test_osc777_title_only(self) -> None:
        events = OscParser().feed(b"\x1b]777;notify;Deploy" + BEL)
        assert events == [PtyEvent(kind="notify", title="Deploy", body=None)]

    def test_osc777_other_subcommands_ignored(self) -> None:
        assert OscParser().feed(b"\x1b]777;progress;50" + BEL) == []

    def test_osc777_sandwalk_agent_hook_started(self) -> None:
        events = OscParser().feed(b"\x1b]777;notify;Sandwalk;agent;claude;started" + BEL)
        assert events == [PtyEvent(kind="agent.hook", agent="claude")]

    def test_osc777_sandwalk_agent_hook_exited(self) -> None:
        events = OscParser().feed(b"\x1b]777;notify;Sandwalk;agent;codex;exited" + BEL)
        assert events == [PtyEvent(kind="agent.hook", agent=None)]

    def test_osc777_sandwalk_agent_hook_unknown_kind_ignored(self) -> None:
        assert OscParser().feed(b"\x1b]777;notify;Sandwalk;agent;gemini;started" + BEL) == []

    def test_osc777_sandwalk_title_without_agent_is_plain_notify(self) -> None:
        events = OscParser().feed(b"\x1b]777;notify;Sandwalk;done" + BEL)
        assert events == [PtyEvent(kind="notify", title="Sandwalk", body="done")]

    def test_unknown_osc_ignored(self) -> None:
        assert OscParser().feed(b"\x1b]0;window title" + BEL) == []

    def test_invalid_utf8_payload_is_replaced_not_raised(self) -> None:
        events = OscParser().feed(b"\x1b]9;\xff\xfe" + BEL)
        assert events[0].kind == "notify"
        assert "\ufffd" in (events[0].body or "")


class TestSafety:
    def test_runaway_payload_is_dropped(self) -> None:
        parser = OscParser()
        huge = b"\x1b]9;" + b"x" * (osc_parser._MAX_OSC_PAYLOAD + 10) + BEL
        assert parser.feed(huge) == []
        # Clean state afterwards.
        assert _kinds(parser.feed(b"\x1b]133;C" + BEL)) == ["command.started"]

    def test_stale_open_sequence_times_out(self, monkeypatch: pytest.MonkeyPatch) -> None:
        parser = OscParser()
        now = [1000.0]
        monkeypatch.setattr(osc_parser.time, "monotonic", lambda: now[0])
        assert parser.feed(b"\x1b]777;notify;never closes") == []
        now[0] += osc_parser._OSC_HOLD_TIMEOUT_SEC + 1
        # The next chunk resets the stale sequence; its bytes are plain output.
        assert parser.feed(b"$ ") == []
        assert _kinds(parser.feed(b"\x1b]133;D;0" + BEL)) == ["command.finished"]

    def test_real_monotonic_clock_is_used_by_default(self) -> None:
        before = time.monotonic()
        parser = OscParser()
        parser.feed(b"\x1b]9;")
        assert parser._osc_started_at is not None
        assert parser._osc_started_at >= before


class TestShellIntegration:
    """The rc files written for spawned PTYs must emit the OSC 133 markers
    the parser above understands, and the zsh hook must register even when
    `add-zsh-hook` is not preloaded."""

    def test_zsh_and_bash_rc_emit_osc133(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        import agent.config as config_mod
        from agent_server.pty_manager.shell_env import terminal_dot_dir

        monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path, raising=False)
        zdot = terminal_dot_dir()
        assert zdot == tmp_path / "terminal-dot"

        zshrc = (zdot / ".zshrc").read_text()
        assert "autoload -Uz add-zsh-hook" in zshrc
        assert "add-zsh-hook precmd _fastfold_osc133_precmd" in zshrc
        assert "add-zsh-hook preexec _fastfold_osc133_preexec" in zshrc
        assert "precmd_functions+=(_fastfold_set_prompt _fastfold_osc133_precmd)" in zshrc
        assert r"printf '\e]133;D;%s\a'" in zshrc
        assert r"printf '\e]133;C\a'" in zshrc
        # Autoload must run before the availability check (hook never
        # registered otherwise).
        assert zshrc.index("autoload -Uz add-zsh-hook") < zshrc.index(
            "if typeset -f add-zsh-hook"
        )

        bashrc = (zdot / ".bashrc").read_text()
        assert "PROMPT_COMMAND=\"_fastfold_osc133_precmd;" in bashrc
        assert "trap '_fastfold_osc133_preexec' DEBUG" in bashrc
        assert r"printf '\e]133;D;%s\a'" in bashrc

        # The rc files round-trip through the parser: D;<rc> then C.
        parser = OscParser()
        events = parser.feed(b"\x1b]133;D;0\x07\x1b]133;A\x07\x1b]133;C\x07")
        assert _kinds(events) == ["command.finished", "command.started"]

    def test_preferred_shell_falls_back_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from agent_server.pty_manager.shell_env import preferred_shell

        monkeypatch.setenv("SHELL", "/definitely/not/a/shell")
        shell = preferred_shell()
        assert shell in {"/bin/zsh", "/bin/bash", "/bin/sh"}


class TestSnapshotStore:
    def test_round_trip_and_delete(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SANDWALK_TERMINAL_SNAPSHOTS_DIR", str(tmp_path / "snaps"))
        assert read_snapshot("term_a") is None
        write_snapshot("term_a", b"\x1b[32m$ \x1b[0mls\r\n")
        assert read_snapshot("term_a") == b"\x1b[32m$ \x1b[0mls\r\n"
        write_snapshot("term_a", b"replaced")
        assert read_snapshot("term_a") == b"replaced"
        delete_snapshot("term_a")
        assert read_snapshot("term_a") is None
        # Deleting twice is a no-op.
        delete_snapshot("term_a")

    def test_session_id_is_sanitized(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        snaps = tmp_path / "snaps"
        monkeypatch.setenv("SANDWALK_TERMINAL_SNAPSHOTS_DIR", str(snaps))
        write_snapshot("../evil/../id", b"x")
        files = sorted(p.name for p in snaps.iterdir())
        assert files == ["__evil___id.bin"]
        assert not (tmp_path / "evil").exists()

    def test_defaults_to_home_when_env_unset(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.delenv("SANDWALK_TERMINAL_SNAPSHOTS_DIR", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        write_snapshot("term_b", b"hi")
        assert (tmp_path / ".sandwalk" / "terminal-snapshots" / "term_b.bin").read_bytes() == b"hi"
