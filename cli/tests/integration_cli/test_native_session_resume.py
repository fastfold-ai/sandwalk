"""Opt-in: the real ``claude`` / ``codex`` binaries resume sessions Sandwalk wrote.

Gated behind ``RUN_CLI_NETWORK=1`` because both CLIs call their model to
answer. Each test uses an isolated config home so nothing lands in the
developer's own history; credentials are copied in read-only for the run.

Checked on Codex 0.162.1 and Claude Code 2.1.300 (Oct 2026).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.cli_network

SECRET = "PELICAN"


def _real_home() -> Path:
    """The user's actual home. conftest points ``$HOME`` at a scratch dir."""
    import pwd

    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def _messages():
    t0 = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
    return [
        SimpleNamespace(role="user", content=f"Remember this secret word: {SECRET}. Just acknowledge.", created_at=t0),
        SimpleNamespace(
            role="assistant",
            content=f"Acknowledged. The secret word is {SECRET}.",
            created_at=t0 + timedelta(seconds=3),
        ),
    ]


@pytest.mark.skipif(shutil.which("codex") is None, reason="codex not installed")
def test_codex_resumes_sandwalk_written_rollout(tmp_path: Path, monkeypatch):
    from agent.external_agents.writers import write_codex_session

    home = tmp_path / "codex-home"
    home.mkdir()
    real = Path(os.environ.get("CODEX_HOME_REAL") or _real_home() / ".codex")
    for name in ("auth.json", "config.toml"):
        if (real / name).is_file():
            shutil.copy(real / name, home / name)
    monkeypatch.setenv("CODEX_HOME", str(home))
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", str(proj)], check=False)

    sid, _path = write_codex_session(cwd=str(proj), title="Secret word", messages=_messages())
    out = subprocess.run(
        ["codex", "exec", "--skip-git-repo-check", "resume", sid, "What was the secret word? Answer with one word."],
        cwd=proj,
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "CODEX_HOME": str(home)},
    )
    assert out.returncode == 0, out.stderr[-800:]
    assert SECRET in out.stdout.upper()
    assert f"session id: {sid}" in out.stderr


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude not installed")
def test_claude_finds_sandwalk_written_transcript(tmp_path: Path, monkeypatch):
    """Claude must *locate* the session. Recall needs API credit, so only the
    lookup is asserted: the failure mode we guard against is
    ``No conversation found with session ID``."""
    from agent.external_agents.writers import write_claude_session

    home = tmp_path / "claude-home"
    home.mkdir()
    real = Path(os.environ.get("CLAUDE_CONFIG_DIR_REAL") or _real_home() / ".claude")
    for name in (".credentials.json", "settings.json"):
        if (real / name).is_file():
            shutil.copy(real / name, home / name)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    proj = tmp_path / "proj"
    proj.mkdir()

    sid, path = write_claude_session(cwd=str(proj), title="Secret word", messages=_messages())
    # Writer resolves symlinks the way Claude does (/tmp -> /private/tmp).
    assert path.parent.name == path.parent.name.replace("/", "-")
    out = subprocess.run(
        ["claude", "--resume", sid, "-p", "What was the secret word? Answer with one word.", "--max-turns", "1"],
        cwd=proj,
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "CLAUDE_CONFIG_DIR": str(home)},
    )
    combined = out.stdout + out.stderr
    assert "No conversation found" not in combined, combined[-800:]
    if out.returncode == 0:
        assert SECRET in out.stdout.upper()
