"""CLI / doctor helpers to probe Modal sandbox connectivity end-to-end."""

from __future__ import annotations

import os
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ProbeStep:
    name: str
    ok: bool
    detail: str


@dataclass
class ProbeReport:
    ok: bool
    steps: list[ProbeStep]
    skipped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "skipped": self.skipped,
            "steps": [
                {"name": s.name, "ok": s.ok, "detail": s.detail} for s in self.steps
            ],
        }


def modal_tokens_present(config: Any | None = None) -> tuple[bool, str]:
    from agent.config import Config, sync_process_env_from_config

    cfg = config or Config.load()
    sync_process_env_from_config(
        cfg,
        only_missing=False,
        config_keys=["compute.modal_token_id", "compute.modal_token_secret"],
    )
    token_id = (os.environ.get("MODAL_TOKEN_ID") or "").strip()
    token_secret = (os.environ.get("MODAL_TOKEN_SECRET") or "").strip()
    if token_id and token_secret:
        return True, "MODAL_TOKEN_ID and MODAL_TOKEN_SECRET are set"
    return False, "Missing MODAL_TOKEN_ID and/or MODAL_TOKEN_SECRET"


def run_modal_sandbox_probe(
    *,
    config: Any | None = None,
    terminate: bool = True,
) -> ProbeReport:
    """Create a Modal sandbox, sync a file, execute, pull, optionally terminate."""
    from agent.config import Config
    from agent.sandbox_backend import resolve_deepagents_backend

    steps: list[ProbeStep] = []
    cfg = config or Config.load()
    present, detail = modal_tokens_present(cfg)
    steps.append(ProbeStep("tokens", present, detail))
    if not present:
        return ProbeReport(ok=False, steps=steps, skipped=True)

    try:
        from agent.sandbox_deps import ensure_modal_deps

        deps_ok, deps_detail = ensure_modal_deps(auto_install=True)
        steps.append(ProbeStep("deps", deps_ok, deps_detail))
        if not deps_ok:
            return ProbeReport(ok=False, steps=steps, skipped=True)
    except Exception as exc:  # noqa: BLE001
        steps.append(ProbeStep("deps", False, str(exc)))
        return ProbeReport(ok=False, steps=steps, skipped=True)

    session_id = f"probe-{uuid.uuid4().hex[:10]}"
    handle = None
    try:
        with tempfile.TemporaryDirectory(prefix="sandwalk-modal-probe-") as tmp:
            root = Path(tmp)
            (root / "hello.txt").write_text("hello-from-host\n", encoding="utf-8")
            skills = root / "skills" / "e2e_probe"
            skills.mkdir(parents=True)
            (skills / "SKILL.md").write_text(
                "---\nname: e2e_probe\ndescription: probe\n---\n\n# Probe\n",
                encoding="utf-8",
            )
            scripts = skills / "scripts"
            scripts.mkdir()
            (scripts / "probe.py").write_text(
                "from pathlib import Path\n"
                "Path('/workspace/out.txt').write_text('probe-ok\\n')\n",
                encoding="utf-8",
            )

            # Temporarily force modal backend for this probe.
            previous = cfg.get("sandbox.backend")
            cfg.set("sandbox.backend", "modal")
            t0 = time.time()
            handle = resolve_deepagents_backend(
                cfg,
                session_id=session_id,
                workspace_root=str(root),
                skill_source_dirs=[str(root / "skills")],
            )
            elapsed = time.time() - t0
            steps.append(
                ProbeStep(
                    "create",
                    handle.kind == "modal",
                    f"sandbox={handle.provider_sandbox_name} in {elapsed:.1f}s",
                )
            )

            cat = handle.backend.execute("cat /workspace/hello.txt", timeout=60)
            output = getattr(cat, "output", str(cat))
            ok_seed = "hello-from-host" in str(output)
            steps.append(
                ProbeStep(
                    "workspace_seed",
                    ok_seed,
                    str(output)[:200] if output else "(empty)",
                )
            )

            # Skills stay on the host via CompositeBackend — never uploaded to Modal.
            skill_md = "/skills/e2e_probe/SKILL.md"
            try:
                read_result = handle.backend.read(skill_md)
                if hasattr(read_result, "file_data") and read_result.file_data:
                    content = str(read_result.file_data)
                else:
                    content = str(read_result)
                ok_skills_local = (
                    getattr(read_result, "error", None) is None
                    and ("e2e_probe" in content or "Probe" in content)
                )
                detail = content[:200]
            except Exception as exc:  # noqa: BLE001
                ok_skills_local = False
                detail = str(exc)
            steps.append(
                ProbeStep(
                    "skills_local_route",
                    ok_skills_local,
                    detail,
                )
            )

            # Modal execute is for /workspace compute only.
            exec_result = handle.backend.execute(
                "python -c \"from pathlib import Path; "
                "Path('/workspace/out.txt').write_text('probe-ok\\n')\"",
                timeout=120,
            )
            exec_out = getattr(exec_result, "output", str(exec_result))
            exit_code = getattr(exec_result, "exit_code", 0)
            ok_exec = int(exit_code or 0) == 0
            steps.append(
                ProbeStep(
                    "workspace_execute",
                    ok_exec,
                    f"exit={exit_code} {str(exec_out)[:160]}",
                )
            )

            pulled = handle.pull()
            out_local = root / "out.txt"
            ok_pull = out_local.is_file() and "probe-ok" in out_local.read_text(
                encoding="utf-8"
            )
            steps.append(
                ProbeStep(
                    "pull",
                    ok_pull,
                    f"pulled={pulled} out_exists={out_local.is_file()}",
                )
            )

            if previous is not None:
                cfg.set("sandbox.backend", previous)
    except Exception as exc:  # noqa: BLE001
        steps.append(ProbeStep("error", False, str(exc)))
        return ProbeReport(ok=False, steps=steps, skipped=False)
    finally:
        if terminate and handle is not None:
            try:
                handle.terminate()
                steps.append(ProbeStep("terminate", True, "terminated"))
            except Exception as exc:  # noqa: BLE001
                steps.append(ProbeStep("terminate", False, str(exc)))

    ok = all(s.ok for s in steps if s.name != "terminate")
    return ProbeReport(ok=ok, steps=steps, skipped=False)
