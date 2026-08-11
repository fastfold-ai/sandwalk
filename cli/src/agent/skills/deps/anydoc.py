"""Managed Node install for Firecrawl anydoc (convert-documents-to-markdown)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from agent.skills.deps.models import (
    SkillDepCheck,
    SkillDepInstallResult,
    SkillDepSetupStep,
    SkillDepStatus,
)

ADAPTER_ID = "anydoc"
SKILL_NAMES = frozenset({"convert-documents-to-markdown"})
NPM_PACKAGE = "@firecrawl/anydoc"
MIN_NODE_MAJOR = 20
_NODE_VERSION_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")


def _config_dir() -> Path:
    from agent.config import CONFIG_DIR

    return Path(CONFIG_DIR)


def anydoc_home() -> Path:
    return _config_dir() / "skill-deps" / "anydoc"


def anydoc_bin() -> Path:
    return anydoc_home() / "node_modules" / ".bin" / "anydoc"


def preferred_command() -> str:
    """Shell command agents should prefer when the managed binary exists."""
    binary = anydoc_bin()
    if binary.is_file() and os.access(binary, os.X_OK):
        return str(binary)
    return f"npx -y {NPM_PACKAGE}"


def setup_steps() -> list[SkillDepSetupStep]:
    return [
        SkillDepSetupStep(
            title="Install Node.js 20+",
            body=(
                "anydoc ships a native CLI via npm. Install Node 20 or newer "
                "(https://nodejs.org/), then return here to install dependencies."
            ),
        ),
        SkillDepSetupStep(
            title="Install anydoc dependencies",
            body=(
                f"Sandwalk installs `{NPM_PACKAGE}` under "
                "`$SANDWALK_CONFIG_DIR/skill-deps/anydoc/` so the agent can call "
                "`anydoc` without a cold `npx` download every turn. "
                "Fallback: `npx -y @firecrawl/anydoc <file>`."
            ),
        ),
        SkillDepSetupStep(
            title="Run health check",
            body=(
                "Verify Node, the managed binary, and a sample CSV→Markdown "
                "conversion. Reinstall if the check fails after a Node upgrade."
            ),
        ),
    ]


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = 120.0,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=merged,
        check=False,
    )


def _node_major(version_text: str) -> int | None:
    match = _NODE_VERSION_RE.search(version_text or "")
    if not match:
        return None
    return int(match.group(1))


def _find_node() -> tuple[str | None, str]:
    node = shutil.which("node")
    if not node:
        return None, "Node.js not found on PATH"
    try:
        proc = _run([node, "--version"], timeout=10.0)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"Could not run node: {exc}"
    text = (proc.stdout or proc.stderr or "").strip()
    major = _node_major(text)
    if major is None:
        return None, f"Unrecognized node version: {text or '(empty)'}"
    if major < MIN_NODE_MAJOR:
        return None, f"Node {text} found; need v{MIN_NODE_MAJOR}+"
    return node, text


def _find_npm() -> str | None:
    return shutil.which("npm")


def _binary_ready() -> bool:
    path = anydoc_bin()
    return path.is_file() and os.access(path, os.X_OK)


def _sample_csv_path(home: Path) -> Path:
    fixtures = home / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    sample = fixtures / "health.csv"
    if not sample.exists():
        sample.write_text("name,value\nhello,1\n", encoding="utf-8")
    return sample


def _convert_sample(binary: Path) -> tuple[bool, str]:
    sample = _sample_csv_path(anydoc_home())
    try:
        proc = _run(
            [str(binary), str(sample), "--format", "csv"],
            timeout=60.0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Sample convert failed: {exc}"
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return False, err or f"anydoc exited {proc.returncode}"
    out = (proc.stdout or "").strip()
    if "hello" not in out.lower() and "name" not in out.lower():
        return False, "Sample convert produced unexpected output"
    return True, "Sample CSV converted to Markdown"


def doctor() -> SkillDepStatus:
    checks: list[SkillDepCheck] = []
    node, node_detail = _find_node()
    if node:
        checks.append(
            SkillDepCheck(
                name="node",
                status="ok",
                detail=f"Node {node_detail} ({node})",
            )
        )
    else:
        checks.append(
            SkillDepCheck(
                name="node",
                status="missing",
                detail=node_detail,
                fix=f"Install Node.js {MIN_NODE_MAJOR}+ from https://nodejs.org/",
            )
        )

    npm = _find_npm()
    if npm:
        checks.append(
            SkillDepCheck(name="npm", status="ok", detail=f"npm: {npm}")
        )
    else:
        checks.append(
            SkillDepCheck(
                name="npm",
                status="missing",
                detail="npm not found on PATH",
                fix="Install Node.js (includes npm) or ensure npm is on PATH",
            )
        )

    binary = anydoc_bin()
    if _binary_ready():
        checks.append(
            SkillDepCheck(
                name="anydoc_binary",
                status="ok",
                detail=f"Managed binary: {binary}",
            )
        )
        ok, detail = _convert_sample(binary)
        checks.append(
            SkillDepCheck(
                name="sample_convert",
                status="ok" if ok else "error",
                detail=detail,
                fix=(
                    ""
                    if ok
                    else "sandwalk skills deps reinstall convert-documents-to-markdown"
                ),
            )
        )
    else:
        checks.append(
            SkillDepCheck(
                name="anydoc_binary",
                status="missing",
                detail=f"Missing managed binary at {binary}",
                fix="sandwalk skills deps install convert-documents-to-markdown",
            )
        )
        checks.append(
            SkillDepCheck(
                name="sample_convert",
                status="missing",
                detail="Skipped until anydoc is installed",
                fix="Install dependencies first",
            )
        )

    if any(c.status == "error" for c in checks):
        status = "error"
        summary = "anydoc health check failed"
    elif any(c.status == "missing" for c in checks):
        status = "missing"
        summary = "anydoc dependencies are not installed"
    else:
        status = "ok"
        summary = "anydoc dependencies healthy"

    return SkillDepStatus(
        adapter_id=ADAPTER_ID,
        skill_name="convert-documents-to-markdown",
        status=status,
        summary=summary,
        command=preferred_command(),
        checks=checks,
        setup_steps=setup_steps(),
    )


def install(*, force: bool = False) -> SkillDepInstallResult:
    node, node_detail = _find_node()
    if not node:
        status = doctor()
        return SkillDepInstallResult(ok=False, summary=node_detail, status=status)

    npm = _find_npm()
    if not npm:
        status = doctor()
        return SkillDepInstallResult(
            ok=False,
            summary="npm not found on PATH",
            status=status,
        )

    home = anydoc_home()
    home.mkdir(parents=True, exist_ok=True)
    package_json = home / "package.json"
    if force and (home / "node_modules").exists():
        shutil.rmtree(home / "node_modules", ignore_errors=True)

    if not package_json.exists() or force:
        package_json.write_text(
            json.dumps(
                {
                    "name": "sandwalk-skill-deps-anydoc",
                    "private": True,
                    "dependencies": {NPM_PACKAGE: "latest"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    if _binary_ready() and not force:
        status = doctor()
        return SkillDepInstallResult(
            ok=status.status == "ok",
            summary="anydoc already installed",
            status=status,
        )

    try:
        proc = _run(
            [npm, "install", "--no-fund", "--no-audit"],
            cwd=home,
            timeout=300.0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        status = doctor()
        return SkillDepInstallResult(
            ok=False,
            summary=f"npm install failed: {exc}",
            status=status,
        )

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        status = doctor()
        return SkillDepInstallResult(
            ok=False,
            summary=err or f"npm install exited {proc.returncode}",
            status=status,
        )

    if not _binary_ready():
        status = doctor()
        return SkillDepInstallResult(
            ok=False,
            summary=f"npm install finished but binary missing at {anydoc_bin()}",
            status=status,
        )

    status = doctor()
    verb = "Reinstalled" if force else "Installed"
    return SkillDepInstallResult(
        ok=status.status == "ok",
        summary=f"{verb} {NPM_PACKAGE} at {home}",
        status=status,
    )
