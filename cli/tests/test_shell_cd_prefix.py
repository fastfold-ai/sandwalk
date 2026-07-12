"""Tests for shell.run working_dir / cd-prefix handling."""

from __future__ import annotations

from tools.shell import _split_cd_prefix, shell_run


class TestSplitCdPrefix:
    def test_extracts_leading_cd(self):
        assert _split_cd_prefix("cd /tmp && python foo.py") == ("/tmp", "python foo.py")

    def test_quoted_dir(self):
        assert _split_cd_prefix('cd "/a b" && ls') == ("/a b", "ls")

    def test_no_prefix(self):
        assert _split_cd_prefix("python foo.py") == (None, "python foo.py")

    def test_keeps_trailing_chain_for_blocking(self):
        # Only the first cd is peeled; the remaining chain is preserved so the
        # safety check can still reject it.
        assert _split_cd_prefix("cd /a && b && c") == ("/a", "b && c")


class TestShellRun:
    def test_cd_prefix_runs_in_dir(self):
        res = shell_run("cd /tmp && echo hello")
        assert res.get("exit_code") == 0
        assert "hello" in res.get("stdout", "")

    def test_working_dir_param(self, tmp_path):
        (tmp_path / "marker.txt").write_text("x")
        res = shell_run("ls", working_dir=str(tmp_path))
        assert res.get("exit_code") == 0
        assert "marker.txt" in res.get("stdout", "")

    def test_missing_working_dir_errors(self):
        res = shell_run("echo hi", working_dir="/definitely/not/here/xyz")
        assert res.get("error") == "invalid_working_dir"

    def test_chained_commands_still_blocked(self):
        res = shell_run("echo a && echo b")
        assert res.get("error") == "blocked_command"

    def test_redirection_still_blocked(self):
        res = shell_run("echo a > /tmp/out.txt")
        assert res.get("error") == "blocked_command"
