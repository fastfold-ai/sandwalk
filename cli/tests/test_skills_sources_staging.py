"""Concurrent specialist skill staging must not raise FileExistsError."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agent.deepagents_runtime.skills_sources import skill_source_dirs_for_names
from agent.skills import list_skills


def test_skill_source_dirs_for_names_reuses_stamp():
    enabled = [s.name for s in list_skills(enabled_only=True)][:8]
    assert enabled
    first = skill_source_dirs_for_names(enabled)
    second = skill_source_dirs_for_names(enabled)
    assert first and first == second
    staging = Path(first[0])
    assert staging.is_dir()
    present = {p.name for p in staging.iterdir() if p.is_dir() or p.is_symlink()}
    assert len(present) >= len(enabled)


def test_skill_source_dirs_for_names_survives_concurrent_calls():
    enabled = [s.name for s in list_skills(enabled_only=True)][:12]
    assert enabled

    def _call() -> list[str]:
        return skill_source_dirs_for_names(enabled)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_call) for _ in range(16)]
        results = [fut.result(timeout=30) for fut in as_completed(futures)]

    assert all(results)
    assert len({tuple(row) for row in results}) == 1
    staging = Path(results[0][0])
    assert staging.is_dir()
