"""Best-effort import of shared-fork files into a fresh session workspace."""

from __future__ import annotations

from pathlib import Path


def import_shared_fork_files(session_id: str, workspace: Path) -> None:
    """Best-effort: copy forked share files into the session workspace."""
    try:
        from agent.config import Config
        from agent.trajectory import Trajectory

        trajectory = Trajectory.load(session_id)
    except Exception:
        return
    if trajectory is None:
        return
    usage = trajectory.get_usage_data() if hasattr(trajectory, "get_usage_data") else {}
    share_id = str((usage or {}).get("imported_from_share_id") or "").strip()
    if not share_id:
        return

    existing = [
        path
        for path in workspace.rglob("*")
        if path.is_file() and path.name not in {".DS_Store"}
    ]
    if existing:
        return

    candidates: list[Path] = []
    try:
        cfg = Config.load()
        output_root = Path(
            str(cfg.get("sandbox.output_dir") or (Path.cwd() / "outputs"))
        ).expanduser().resolve()
        candidates.append(output_root / "shared_forks" / share_id)
    except Exception:
        pass
    candidates.append((Path.cwd() / "outputs" / "shared_forks" / share_id).resolve())

    import shutil

    for candidate in candidates:
        if not candidate.is_dir():
            continue
        for child in candidate.iterdir():
            destination = workspace / child.name
            try:
                if child.is_dir():
                    shutil.copytree(child, destination, dirs_exist_ok=True)
                else:
                    shutil.copy2(child, destination)
            except Exception:
                continue
        return
