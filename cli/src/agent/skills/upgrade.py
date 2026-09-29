"""Re-syncing installed skills (catalog, manifest-tracked, and npx) to latest."""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agent import skills as _skills

logger = logging.getLogger("skills")

# Bounded parallelism for network-bound skill syncs (clones/archives). Override
# with FASTFOLD_SKILLS_SYNC_WORKERS.
_DEFAULT_SYNC_WORKERS = 8


def _project_lock_sources(project_root: Path) -> list[str]:
    """Return distinct skill sources recorded in a project's skills-lock.json (npx installs)."""
    lock_file = project_root / "skills-lock.json"
    if not lock_file.exists():
        return []
    try:
        lock = json.loads(lock_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    sources: list[str] = []
    for meta in (lock.get("skills") or {}).values():
        if isinstance(meta, dict) and meta.get("source"):
            src = str(meta["source"]).strip()
            if src and src not in sources:
                sources.append(src)
    return sources


def _clone_repo_once(url: str, ref: str | None, tmp_root: Path) -> tuple[Path | None, str | None, str]:
    """Clone ``url`` once (git, then archive fallback) into ``tmp_root``.

    Returns ``(repo_root, commit, via)``. ``repo_root`` is None when both
    strategies fail.
    """
    import subprocess

    if _skills._git_available():
        try:
            clone_root = tmp_root / "repo"
            commit = _skills._git_clone(url, ref, clone_root)
            return clone_root, commit, "git"
        except subprocess.CalledProcessError as exc:
            logger.debug("group git clone failed for %s: %s", url, exc)
        except Exception as exc:  # noqa: BLE001
            logger.debug("group git install failed for %s: %s", url, exc)

    owner_repo = _skills._owner_repo_from_clone_url(url)
    if owner_repo:
        owner, repo = owner_repo.split("/", 1)
        try:
            repo_root = _skills._download_github_archive(owner, repo, ref, tmp_root)
            return repo_root, None, "archive"
        except Exception as exc:  # noqa: BLE001
            logger.debug("group archive install failed for %s: %s", url, exc)

    return None, None, "git"


def _run_grouped_clones(
    groups: dict,
    group_owner_repo: dict,
    install_item: callable,
    *,
    max_workers: int | None = None,
    notify: callable | None = None,
    label: str = "Updating skills",
    fetch_release: bool = True,
) -> tuple[list[str], list[tuple[str, str]]]:
    """Clone each ``(url, ref)`` group once and install its items in parallel.

    ``groups`` maps ``(url, ref)`` to a list of opaque ``item`` tuples whose
    first element is the source identifier (used for failure reporting).
    ``install_item(repo_root, commit, release_tag, via, item)`` does the per-item
    copy and returns ``(installed_names, failures)``.

    Emits ``"<label> <done>/<total>..."`` progress as each repo finishes so the
    user sees an n/m counter.
    """

    def _notify(msg: str) -> None:
        if notify is not None:
            try:
                notify(msg)
            except Exception:  # noqa: BLE001
                pass

    total = sum(len(items) for items in groups.values())
    done = 0
    installed: list[str] = []
    failures: list[tuple[str, str]] = []
    if not groups:
        return installed, failures

    def _process_group(key, items) -> tuple[list[str], list[tuple[str, str]]]:
        url, ref = key
        owner_repo = group_owner_repo.get(key)
        release_tag = None
        if fetch_release and owner_repo:
            release_info = _skills.fetch_latest_release(owner_repo)
            release_tag = release_info.get("tag") if release_info else None
        # Unpinned groups install the release tag so upgrade matches version labels.
        clone_ref = ref or release_tag
        grp_installed: list[str] = []
        grp_failures: list[tuple[str, str]] = []
        with tempfile.TemporaryDirectory(prefix="fastfold-skill-grp-") as tmp:
            repo_root, commit, via = _skills._clone_repo_once(url, clone_ref, Path(tmp))
            if repo_root is None:
                for item in items:
                    grp_failures.append((item[0], "clone/archive failed"))
                return grp_installed, grp_failures
            for item in items:
                try:
                    ins, fails = install_item(repo_root, commit, release_tag, via, item)
                    grp_installed += ins
                    grp_failures += fails
                except Exception as exc:  # noqa: BLE001
                    grp_failures.append((item[0], str(exc)))
        return grp_installed, grp_failures

    workers = max_workers or int(
        os.environ.get("FASTFOLD_SKILLS_SYNC_WORKERS", _DEFAULT_SYNC_WORKERS) or _DEFAULT_SYNC_WORKERS
    )
    workers = max(1, min(workers, len(groups)))

    if workers == 1:
        for key, items in groups.items():
            gi, gf = _process_group(key, items)
            installed += gi
            failures += gf
            done += len(items)
            _notify(f"{label} {done}/{total}...")
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_process_group, key, items): items for key, items in groups.items()}
            for future in as_completed(futures):
                items = futures[future]
                gi, gf = future.result()
                installed += gi
                failures += gf
                done += len(items)
                _notify(f"{label} {done}/{total}...")

    return installed, failures


def _sync_tracked_sources(
    tracked: list[tuple[str, str]],
    dest: Path,
    *,
    max_workers: int | None = None,
    notify: callable | None = None,
    label: str = "Updating skills",
) -> tuple[list[str], list[tuple[str, str]]]:
    """Install many tracked skill sources efficiently.

    Sources that resolve to the same GitHub repo + ref are cloned **once** and
    every requested subpath is installed from that single clone (instead of one
    clone per skill). Distinct repos are processed in parallel since the work is
    network-bound.

    Returns ``(installed_names, failures)`` where ``failures`` is a list of
    ``(source, reason)``.
    """

    def _notify(msg: str) -> None:
        if notify is not None:
            try:
                notify(msg)
            except Exception:  # noqa: BLE001
                pass

    # Group GitHub sources by (clone_url, ref); keep non-GitHub sources separate.
    groups: dict[tuple[str, str | None], list[tuple[str, str | None]]] = {}
    group_owner_repo: dict[tuple[str, str | None], str | None] = {}
    other_sources: list[str] = []
    for _name, source in tracked:
        src_type = _skills.detect_source_type(source)
        if src_type in {"github", "shorthand"}:
            try:
                url, ref, subpath = _skills._parse_github(source)
            except Exception:  # noqa: BLE001
                other_sources.append(source)
                continue
            key = (url, ref)
            groups.setdefault(key, []).append((source, subpath))
            group_owner_repo.setdefault(key, _skills._owner_repo_from_source(source))
        else:
            other_sources.append(source)

    def _install_item(repo_root, commit, release_tag, via, item):
        source, subpath = item
        result = _skills._install_from_repo_tree(
            repo_root, subpath, dest, source, commit, release_tag, via
        )
        if result.get("ok"):
            return result.get("installed", []), []
        return [], [(source, result.get("summary", "failed"))]

    installed, failures = _run_grouped_clones(
        groups,
        group_owner_repo,
        _install_item,
        max_workers=max_workers,
        notify=notify,
        label=label,
    )

    # Non-GitHub sources: install individually (rare; local paths / bare names).
    for source in other_sources:
        _notify(f"Updating {source}...")
        result = _skills.install_skill(source, dest=dest)
        if result.get("ok"):
            installed += result.get("installed", [])
        else:
            failures.append((source, result.get("summary", "failed")))

    return installed, failures


def _copy_skill_to(skill_dir: Path, dest: Path, target_name: str) -> None:
    """Copy a single resolved skill directory into ``dest/target_name``."""
    target = dest / target_name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        skill_dir, target, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc")
    )


def update_npx_skills_via_git(
    *,
    max_workers: int | None = None,
    notify: callable | None = None,
) -> dict:
    """Refresh npx-installed skills with grouped git clones (one clone per repo).

    ``npx skills update`` reprocesses every skill individually and is the dominant
    cost of an upgrade when many skills share a few repos. This reads the npx
    ``skills-lock.json``, groups skills by their source repo, clones each repo
    once (in parallel), and copies each skill into ``NPX_SKILLS_DIR`` under its
    **existing** (lock) directory name — repo paths often differ from the
    installed name (e.g. ``skills/foo_bar`` vs ``foo-bar``).

    Returns ``{ok, synced, failed, summary}``. ``ok`` is False (with no writes)
    when git is unavailable or the lock has no usable GitHub sources, so the
    caller can fall back to ``npx skills update``.
    """
    lock_path = _skills.NPX_INSTALL_ROOT / "skills-lock.json"
    if not lock_path.exists() or not _skills._git_available():
        return {"ok": False, "synced": 0, "failed": [], "summary": "no lock or git"}
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "synced": 0, "failed": [], "summary": f"unreadable lock: {exc}"}

    entries = lock.get("skills") or {}
    groups: dict[tuple[str, str | None], list[tuple[str, str | None, str]]] = {}
    group_owner_repo: dict[tuple[str, str | None], str | None] = {}
    skipped: list[str] = []
    for name, meta in sorted(entries.items()):
        if not isinstance(meta, dict):
            continue
        source = str(meta.get("source") or "").strip()
        source_type = str(meta.get("sourceType") or "github").strip()
        skill_path = str(meta.get("skillPath") or "").strip()
        if not source or source_type != "github":
            skipped.append(name)
            continue
        # Directory holding SKILL.md within the repo.
        if skill_path.endswith("/SKILL.md"):
            subpath = skill_path[: -len("/SKILL.md")]
        elif skill_path:
            subpath = str(Path(skill_path).parent)
        else:
            subpath = None
        shorthand = f"{source}@{subpath}" if subpath else source
        try:
            url, ref, _sub = _skills._parse_github(shorthand)
        except Exception:  # noqa: BLE001
            skipped.append(name)
            continue
        key = (url, ref)
        groups.setdefault(key, []).append((shorthand, subpath, name))
        group_owner_repo.setdefault(key, _skills._owner_repo_from_source(shorthand))

    if not groups:
        return {"ok": False, "synced": 0, "failed": [], "summary": "no github sources in lock"}

    _skills.NPX_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    def _install_item(repo_root, commit, release_tag, via, item):
        source, subpath, target_name = item
        skill_dirs = _skills._resolve_skill_dirs(repo_root, subpath)
        if not skill_dirs:
            return [], [(source, f"no SKILL.md at {subpath}")]
        _copy_skill_to(skill_dirs[0], _skills.NPX_SKILLS_DIR, target_name)
        return [target_name], []

    installed, failures = _run_grouped_clones(
        groups,
        group_owner_repo,
        _install_item,
        max_workers=max_workers,
        notify=notify,
        label="Updating community skills",
        # npx skills are pinned in the lock; skip the per-repo release lookup.
        fetch_release=False,
    )
    return {
        "ok": True,
        "synced": len(installed),
        "failed": failures,
        "summary": f"Updated {len(installed)} npx skill(s) via git ({len(groups)} repo clone(s)).",
    }


def upgrade_skills(
    *,
    include_catalog: bool = True,
    include_npx: bool = True,
    catalog: str = _skills.DEFAULT_CATALOG,
    project_root: Path | None = None,
    progress: callable | None = None,
) -> dict:
    """Re-sync installed skills to their latest versions.

    1. When ``include_catalog`` is True, installs/refreshes the entire Fastfold
       catalog (adds new skills + overrides existing ones).
    2. Re-installs every other skill recorded in the global manifest from its
       recorded source (overwrites in place).
    3. When ``include_npx`` is True and ``npx`` is available, re-runs
       ``npx skills add`` for each source recorded in the project-local
       ``skills-lock.json`` (skills the Skills CLI installed into .claude/skills).

    ``progress`` is an optional ``callable(str)`` invoked with a human-readable
    phase message (e.g. for driving an animated spinner). It is best-effort and
    never affects the result.

    Returns a dict: added (new names), updated (refreshed names), failed (list of
    (source, reason)), and a human-readable summary.
    """
    from agent.deepagents_runtime.skills_sources import invalidate_skill_sources_cache

    invalidate_skill_sources_cache()

    def _notify(msg: str) -> None:
        if progress is not None:
            try:
                progress(msg)
            except Exception:  # noqa: BLE001
                pass

    dest = _skills.GLOBAL_SKILLS_DIR
    if project_root is None:
        project_root = Path.cwd()
    before = set(_skills.iter_skills(project_root).keys())
    installed_total: list[str] = []
    failed: list[tuple[str, str]] = []

    # 1) Sync the whole Fastfold catalog (one clone: adds new + overrides existing).
    catalog_owner_repo = catalog.split("@", 1)[0]
    if include_catalog:
        _notify(f"Syncing catalog ({catalog_owner_repo})...")
        result = _skills.install_skill(catalog_owner_repo, dest=dest)
        if result.get("ok"):
            installed_total += result.get("installed", [])
        else:
            failed.append((catalog_owner_repo, result.get("summary", "failed")))

    # 2) Update other manifest-tracked skills from their recorded sources.
    #    Sources that share a repo+ref are cloned once and synced in parallel,
    #    so N skills from one repo cost one clone instead of N.
    manifest = _skills._read_manifest(dest)
    tracked: list[tuple[str, str]] = []
    for name, meta in sorted(manifest.get("skills", {}).items()):
        source = (meta or {}).get("source")
        if not source:
            continue
        # Skip skills already refreshed by the catalog sync above.
        if include_catalog and source.split("@", 1)[0] == catalog_owner_repo:
            continue
        tracked.append((name, source))

    if tracked:
        grouped_installed, grouped_failed = _skills._sync_tracked_sources(
            tracked, dest, notify=_notify, label="Updating skills"
        )
        installed_total += grouped_installed
        failed += grouped_failed

    # 3) Update npx-installed skills. Prefer grouped git clones (one clone per
    #    repo, in parallel) over `npx skills update`, which reprocesses every
    #    skill individually and dominates the runtime for large libraries.
    npx_synced = 0
    if include_npx and _skills.NPX_SKILLS_DIR.exists():
        git_result = _skills.update_npx_skills_via_git(notify=_notify)
        if git_result.get("ok"):
            npx_synced = git_result.get("synced", 0)
            failed += git_result.get("failed", [])
        elif _skills._npx_available():
            # Fallback: git unavailable or lock unusable — use the npx CLI.
            _notify("Updating npx-installed skills...")
            result = _skills._npx_update()
            if result.get("ok"):
                npx_synced = len(_skills._scan_dir(_skills.NPX_SKILLS_DIR, "npx"))
            else:
                failed.append(("npx skills update", result.get("summary", "failed")))

    _notify("Finalizing...")

    after = set(_skills.iter_skills(project_root).keys())
    added = sorted(after - before)
    updated = sorted(set(installed_total) - set(added))
    summary = (
        f"Synced skills: {len(updated)} updated, {len(added)} added, "
        f"{npx_synced} npx-synced, {len(failed)} failed."
    )
    return {
        "added": added,
        "updated": updated,
        "npx_synced": npx_synced,
        "failed": failed,
        "summary": summary,
    }
