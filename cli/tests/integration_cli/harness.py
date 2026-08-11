"""HOME-isolated helpers for real ``sandwalk`` subprocess functional tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

CLI_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TIMEOUT_S = 45

# Featured Fastfold catalog sources used by setup / specialists.
FOLD_SKILL_SOURCE = "fastfold-ai/skills@skills/fold"
BOLTZ_SKILL_SOURCE = "fastfold-ai/skills@skills/boltz"
MD_SKILL_SOURCE = "fastfold-ai/skills@skills/md_openmm_calvados"
BOLTZGEN_SKILL_SOURCE = "fastfold-ai/skills@skills/protein_design_boltzgen"

# Optional sibling checkout: ../skills/skills/fold (not vendored in sandwalk).
SIBLING_SKILLS_FOLD = CLI_ROOT.parent.parent / "skills" / "skills" / "fold"


def resolve_sandwalk_bin() -> Path:
    """Prefer the venv console script next to the active interpreter.

    Do not ``Path.resolve()`` the interpreter first — in uv venvs ``python`` is a
    symlink into the shared CPython install, and the console scripts live beside
    the symlink in ``.venv/bin/``.
    """
    candidates = [
        Path(sys.executable).parent / "sandwalk",
        CLI_ROOT / ".venv" / "bin" / "sandwalk",
    ]
    which = shutil.which("sandwalk")
    if which:
        candidates.append(Path(which))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    pytest.fail(
        f"sandwalk executable not found near {sys.executable} or on PATH; "
        "install the editable package (uv sync / pip install -e .). "
        f"Tried: {', '.join(str(c) for c in candidates)}"
    )


def run_sandwalk(
    *args: str,
    home: Path,
    cwd: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
    extra_env: dict[str, str] | None = None,
    clear_modal_env: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a real ``sandwalk`` process with an isolated HOME (no shared config)."""
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)  # Windows
    env["TERM"] = "dumb"
    # Avoid interactive prompts / pager noise.
    env["CI"] = "1"
    env["NO_COLOR"] = "1"
    if clear_modal_env:
        env.pop("MODAL_TOKEN_ID", None)
        env.pop("MODAL_TOKEN_SECRET", None)
    if extra_env:
        env.update(extra_env)

    cmd: Sequence[str] = [str(resolve_sandwalk_bin()), *args]
    return subprocess.run(
        list(cmd),
        cwd=str(cwd or home),
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout or ''}{result.stderr or ''}"


def assert_ok(result: subprocess.CompletedProcess[str], *, label: str = "") -> None:
    """Fail with full stdout/stderr when exit code is non-zero."""
    if result.returncode == 0:
        return
    prefix = f"{label}: " if label else ""
    raise AssertionError(
        f"{prefix}expected exit 0, got {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )


def assert_no_unknown_config(result: subprocess.CompletedProcess[str], key: str) -> None:
    text = combined_output(result)
    needle = f"Unknown config key '{key}'"
    assert needle not in text, f"Unexpected config warning in CLI output:\n{text}"


def config_set(home: Path, cwd: Path, key: str, value: str) -> None:
    result = run_sandwalk("config", "set", key, value, home=home, cwd=cwd)
    assert_ok(result, label=f"config set {key}")


def write_minimal_skill(root: Path, name: str = "demo-skill") -> Path:
    """Create a tiny local skill directory with SKILL.md for offline installs."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Offline demo skill for CLI functional tests.\n---\n\n"
        f"# {name}\n\nUse only in automated tests.\n",
        encoding="utf-8",
    )
    return skill_dir


def skill_installed_on_disk(home: Path, name: str) -> bool:
    skill_md = home / ".sandwalk" / "skills" / name / "SKILL.md"
    return skill_md.is_file()


def sibling_fold_skill_dir() -> Path | None:
    """Return a local fold skill path if a sibling skills repo is checked out."""
    if SIBLING_SKILLS_FOLD.is_dir() and (SIBLING_SKILLS_FOLD / "SKILL.md").is_file():
        return SIBLING_SKILLS_FOLD
    return None


def free_tcp_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_sandwalk(
    *args: str,
    home: Path,
    cwd: Path | None = None,
    clear_modal_env: bool = True,
) -> subprocess.Popen[str]:
    """Start a long-running ``sandwalk`` process (caller must terminate)."""
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["TERM"] = "dumb"
    env["CI"] = "1"
    env["NO_COLOR"] = "1"
    if clear_modal_env:
        env.pop("MODAL_TOKEN_ID", None)
        env.pop("MODAL_TOKEN_SECRET", None)
    return subprocess.Popen(
        [str(resolve_sandwalk_bin()), *args],
        cwd=str(cwd or home),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def wait_http_ok(url: str, *, timeout_s: float = 30.0) -> str:
    """Poll ``url`` until HTTP 200; return response body text."""
    import time
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + timeout_s
    last_err = "no attempt"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if resp.status == 200:
                    return body
                last_err = f"HTTP {resp.status}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = str(exc)
        time.sleep(0.25)
    raise AssertionError(f"Timed out waiting for {url}: {last_err}")


_LLM_KEY_CANDIDATES: tuple[tuple[str, str], ...] = (
    ("anthropic", "llm.anthropic_api_key"),
    ("openai", "llm.openai_api_key"),
    ("google", "llm.google_api_key"),
)


def _llm_from_env() -> tuple[str, str, str] | None:
    """Return (provider, config_key, api_key) from process env, if any."""
    mapping = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    for provider, config_key in _LLM_KEY_CANDIDATES:
        value = (os.environ.get(mapping[provider]) or "").strip()
        if value:
            return (provider, config_key, value)
    return None


def _llm_from_local_config() -> tuple[str, str, str] | None:
    """Return (provider, config_key, api_key) from the developer's real ~/.sandwalk.

    Uses the real ``Path.home()`` (pytest process home), not the isolated test HOME.
    Prefers the configured ``llm.provider`` when that provider has a key.
    """
    path = Path.home() / ".sandwalk" / "config.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None

    preferred = str(data.get("llm.provider") or "").strip().lower()
    ordered = sorted(
        _LLM_KEY_CANDIDATES,
        key=lambda item: 0 if item[0] == preferred else 1,
    )
    for provider, config_key in ordered:
        value = data.get(config_key)
        if isinstance(value, str) and value.strip():
            return (provider, config_key, value.strip())
    return None


def detect_llm_env() -> tuple[str, str, str] | None:
    """Return (provider, config_key, api_key) from env or local ~/.sandwalk config."""
    return _llm_from_env() or _llm_from_local_config()
