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

    def test_short_and_chain_allowed(self):
        res = shell_run("echo a && echo b")
        assert res.get("error") != "blocked_command"
        assert res.get("exit_code") == 0
        assert "a" in res.get("stdout", "")
        assert "b" in res.get("stdout", "")

    def test_file_redirection_outside_workspace_blocked(self):
        res = shell_run("echo a > /tmp/out.txt")
        assert res.get("error") == "blocked_command"

    def test_file_redirection_into_workspace_allowed(self, tmp_path, monkeypatch):
        workspace = tmp_path / "ws"
        (workspace / "artifacts").mkdir(parents=True)
        monkeypatch.setenv("SANDWALK_SESSION_WORKSPACE", str(workspace))
        out = workspace / "artifacts" / "saved.txt"
        res = shell_run(f'echo downloaded > "{out}" && echo ok')
        assert res.get("error") != "blocked_command"
        assert res.get("exit_code") == 0
        assert out.read_text().strip() == "downloaded"

    def test_semicolon_chain_in_workspace(self, tmp_path, monkeypatch):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        monkeypatch.setenv("SANDWALK_SESSION_WORKSPACE", str(workspace))
        res = shell_run("echo one; echo two")
        assert res.get("error") != "blocked_command"
        assert res.get("exit_code") == 0
        assert "one" in res.get("stdout", "")
        assert "two" in res.get("stdout", "")

    def test_or_fallback_allowed(self):
        res = shell_run("false || echo fallback")
        assert res.get("error") != "blocked_command"
        assert res.get("exit_code") == 0
        assert "fallback" in res.get("stdout", "")
