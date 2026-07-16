"""Route ``/skills/`` execution to the host filesystem instead of Modal.

Skills stay on the host via ``CompositeBackend`` routing — they are never
uploaded into Modal.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from deepagents.backends import CompositeBackend, FilesystemBackend

from agent.sandbox_sync import SKILLS_REMOTE_ROOT

logger = logging.getLogger(__name__)

_SKILLS_EXECUTE_HINT = (
    "Skill scripts are not available inside the Modal sandbox. "
    "Use the shell_run tool with the absolute host path to the skill script "
    "(from the Skills listing), e.g. "
    "`python3 /path/to/skills/<name>/scripts/<script>.py ...`. "
    "Modal `execute` is only for /workspace compute."
)


def _skills_filesystem_root(sources: list[str]) -> Path | None:
    """Build a single host root for CompositeBackend ``/skills/`` routing.

    Later sources override earlier ones on name collision (bundled -> npx -> global).
    """
    existing: list[Path] = []
    for raw in sources:
        path = Path(str(raw)).expanduser().resolve()
        if path.is_dir():
            existing.append(path)
    if not existing:
        return None
    if len(existing) == 1:
        return existing[0]

    staging = Path(tempfile.mkdtemp(prefix="sandwalk-skills-route-"))
    for src in existing:
        try:
            children = list(src.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            dest = staging / child.name
            if dest.exists() or dest.is_symlink():
                if dest.is_symlink() or dest.is_file():
                    dest.unlink(missing_ok=True)
                elif dest.is_dir():
                    shutil.rmtree(dest, ignore_errors=True)
            try:
                dest.symlink_to(child, target_is_directory=True)
            except OSError:
                try:
                    shutil.copytree(child, dest, dirs_exist_ok=True)
                except OSError as exc:
                    logger.warning("Could not stage skill %s: %s", child, exc)
    return staging


def _command_targets_skills(command: str) -> bool:
    text = str(command or "")
    if f"{SKILLS_REMOTE_ROOT}/" in text:
        return True
    # Bare relative forms agents sometimes try.
    return bool(re.search(r"(^|[\s'\"])skills/", text))


def _wrap_composite_execute_for_skills(backend: CompositeBackend, skills_root: Path) -> None:
    """Reject Modal execute for skill paths; optionally rewrite + run on host.

    Prefer host ``shell_run`` (prompted). If the model still uses ``execute`` with
    a ``/skills/...`` path, rewrite to the host skills root and run locally so
    FastFold API scripts keep working with host env/secrets.
    """
    from deepagents.backends.protocol import ExecuteResponse

    original_execute = backend.execute
    host_prefix = str(skills_root.resolve()).rstrip("/") + "/"

    def execute(command: str, *, timeout: int | None = None) -> Any:
        if not _command_targets_skills(command):
            if timeout is not None:
                return original_execute(command, timeout=timeout)
            return original_execute(command)

        host_cmd = str(command).replace(f"{SKILLS_REMOTE_ROOT}/", host_prefix)
        host_cmd = re.sub(r"(^|[\s'\"])skills/", rf"\1{host_prefix}", host_cmd)
        try:
            completed = subprocess.run(
                host_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout or 600,
                check=False,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            return ExecuteResponse(output=output, exit_code=completed.returncode)
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + (exc.stderr or "")
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            return ExecuteResponse(
                output=(output or "") + f"\nTimed out. {_SKILLS_EXECUTE_HINT}",
                exit_code=124,
            )
        except Exception as exc:  # noqa: BLE001
            return ExecuteResponse(
                output=f"{exc}\n{_SKILLS_EXECUTE_HINT}",
                exit_code=1,
            )

    backend.execute = execute  # type: ignore[method-assign]


def _compose_modal_with_local_skills(
    modal_backend: Any,
    skill_source_dirs: list[str],
) -> tuple[Any, list[str], Path | None]:
    """Wrap Modal with a local ``/skills/`` FilesystemBackend route."""
    skills_root = _skills_filesystem_root(skill_source_dirs)
    if skills_root is None:
        return modal_backend, [], None

    skills_fs = FilesystemBackend(root_dir=str(skills_root), virtual_mode=True)
    composite = CompositeBackend(
        default=modal_backend,
        routes={f"{SKILLS_REMOTE_ROOT}/": skills_fs},
    )
    _wrap_composite_execute_for_skills(composite, skills_root)
    return composite, [f"{SKILLS_REMOTE_ROOT}/"], skills_root
