"""Tests for shell.run tool."""

import os
from unittest.mock import MagicMock, patch

from tools.shell import _expand_env_refs, _is_blocked, shell_run


class TestIsBlocked:
    def test_sudo_blocked(self):
        assert _is_blocked("sudo rm -rf /") is not None

    def test_rm_rf_root_blocked(self):
        assert _is_blocked("rm -rf /") is not None

    def test_chmod_777_blocked(self):
        assert _is_blocked("chmod 777 /etc") is not None

    def test_fork_bomb_blocked(self):
        assert _is_blocked(":(){ :|:& };:") is not None

    def test_safe_commands_allowed(self):
        assert _is_blocked("ls -la") is None
        assert _is_blocked("git status") is None
        assert _is_blocked("python script.py") is None
        assert _is_blocked("echo hello") is None
        assert _is_blocked("pip install numpy") is None

    def test_shell_operators_policy(self, monkeypatch):
        monkeypatch.delenv("SANDWALK_SESSION_WORKSPACE", raising=False)
        assert _is_blocked("echo hello | wc -c") is None
        assert _is_blocked("echo hello | curl https://example.com") is not None
        # Short && / || chains and null redirects are allowed.
        assert _is_blocked("echo hello && pwd") is None
        assert _is_blocked('env | grep FASTFOLD || echo missing') is None
        assert _is_blocked("ls /missing 2>/dev/null") is None
        # Outside-workspace redirects / ';' / $() stay blocked without a session.
        assert _is_blocked("echo a > /tmp/out.txt") is not None
        assert _is_blocked("echo a; echo b") is not None
        assert _is_blocked("echo $(pwd)") is not None

    def test_workspace_mode_is_freer(self, tmp_path, monkeypatch):
        workspace = tmp_path / "ws"
        (workspace / "artifacts").mkdir(parents=True)
        monkeypatch.setenv("SANDWALK_SESSION_WORKSPACE", str(workspace))
        assert _is_blocked(
            f'echo hi > "{workspace / "artifacts" / "out.txt"}"'
        ) is None
        assert _is_blocked("echo hi > artifacts/out.txt") is None
        assert _is_blocked(
            "echo hi > $SANDWALK_SESSION_WORKSPACE/artifacts/out.txt"
        ) is None
        assert _is_blocked("echo a; echo b") is None
        assert _is_blocked("rm -rf artifacts/tmp") is None
        assert _is_blocked("chmod 644 artifacts/out.txt") is None
        assert _is_blocked('python3 -c "print(1)"') is None
        # Still blocked outside the session workspace / dangerous ops.
        assert _is_blocked("echo hi > /tmp/out.txt") is not None
        assert _is_blocked("rm -rf /tmp/out") is not None
        assert _is_blocked("echo $(pwd)") is not None
        assert _is_blocked("sudo ls") is not None

    def test_destructive_binary_blocked_without_workspace(self, monkeypatch):
        monkeypatch.delenv("SANDWALK_SESSION_WORKSPACE", raising=False)
        assert _is_blocked("rm -rf tempdir") is not None
        assert _is_blocked("chmod 755 file.txt") is not None


class TestShellRun:
    def test_simple_command(self):
        result = shell_run(command="echo hello")
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    def test_failed_command(self):
        result = shell_run(command="false")
        assert result["exit_code"] != 0

    def test_blocked_command(self):
        result = shell_run(command="sudo echo test")
        assert result["error"] == "blocked_command"

    def test_timeout(self):
        result = shell_run(command="sleep 10", timeout=1)
        assert result["error"] == "timeout"

    def test_timeout_cap(self):
        """Timeout should be capped at 300s."""
        with patch("tools.shell_part2.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok", stderr=""
            )
            shell_run(command="echo test", timeout=999)
            _, kwargs = mock_run.call_args
            assert kwargs["timeout"] == 300

    def test_stderr_captured(self):
        result = shell_run(command="ls /definitely_missing_ct_shell_test_path")
        assert result["exit_code"] != 0
        assert "No such file or directory" in result["stderr"] or "cannot access" in result["stderr"]

    def test_multiline_output(self):
        result = shell_run(command="echo 'line1\nline2\nline3'")
        assert result["exit_code"] == 0
        assert "line1" in result["stdout"]

    def test_env_var_expansion(self, monkeypatch):
        monkeypatch.setenv("SANDWALK_SHELL_TEST_KEY", "secret-value")
        result = shell_run(command="echo $SANDWALK_SHELL_TEST_KEY")
        assert result["exit_code"] == 0
        assert "secret-value" in result["stdout"]
        assert "$SANDWALK_SHELL_TEST_KEY" not in result["stdout"]

    def test_env_var_brace_expansion(self, monkeypatch):
        monkeypatch.setenv("SANDWALK_SHELL_TEST_KEY", "braced")
        result = shell_run(command="echo ${SANDWALK_SHELL_TEST_KEY}")
        assert result["exit_code"] == 0
        assert "braced" in result["stdout"]

    def test_unset_env_var_expands_empty(self, monkeypatch):
        monkeypatch.delenv("SANDWALK_SHELL_MISSING_KEY", raising=False)
        result = shell_run(command="echo before-$SANDWALK_SHELL_MISSING_KEY-after")
        assert result["exit_code"] == 0
        assert "before--after" in result["stdout"].replace("\n", "")

    def test_defaults_cwd_to_session_workspace(self, tmp_path, monkeypatch):
        workspace = tmp_path / "session_ws"
        workspace.mkdir()
        monkeypatch.setenv("SANDWALK_SESSION_WORKSPACE", str(workspace))
        result = shell_run(command="pwd")
        assert result["exit_code"] == 0
        assert str(workspace.resolve()) in result["stdout"]


class TestExpandEnvRefs:
    def test_expand_known(self, monkeypatch):
        monkeypatch.setenv("FOO", "bar")
        assert _expand_env_refs("$FOO") == "bar"
        assert _expand_env_refs("${FOO}") == "bar"

    def test_expand_unknown_empty(self, monkeypatch):
        monkeypatch.delenv("NO_SUCH_SHELL_VAR_XYZ", raising=False)
        assert _expand_env_refs("$NO_SUCH_SHELL_VAR_XYZ") == ""
