"""GitHub release lookups and the boot-time "newer catalog version" update cache."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from agent import skills as _skills

logger = logging.getLogger("skills")

_SEMVER_TAG_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")
_UPDATE_CHECK_INTERVAL_S = 24 * 3600

# Mirrors agent.skills.install._GITHUB_SHORTHAND_RE (owner/repo[@subpath] shorthand).
_GITHUB_SHORTHAND_RE = re.compile(r"^(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:@(?P<sub>.+))?$")


def _owner_repo_from_source(source: str) -> str | None:
    """Extract ``owner/repo`` from a GitHub URL or shorthand (drops any @subpath)."""
    s = (source or "").strip()
    if not s:
        return None
    if s.startswith(("http://", "https://", "git@")):
        m = re.search(r"github\.com[:/](?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?(?:/|$)", s)
        return f"{m.group('owner')}/{m.group('repo')}" if m else None
    m = _GITHUB_SHORTHAND_RE.match(s)
    if m:
        return f"{m.group('owner')}/{m.group('repo')}"
    return None


def _tag_tuple(tag: str) -> tuple[int, int, int] | None:
    m = _SEMVER_TAG_RE.search(str(tag or ""))
    return tuple(int(x) for x in m.groups()) if m else None


def _is_newer_tag(latest: str, current: str) -> bool:
    lt, ct = _tag_tuple(latest), _tag_tuple(current)
    if not lt or not ct:
        return False
    return lt > ct


def _http_get_bytes(
    url: str,
    *,
    timeout: float = 120,
    headers: dict[str, str] | None = None,
) -> bytes:
    """Fetch HTTP(S) bytes with certifi-backed TLS (fixes Windows urllib SSL issues)."""
    import httpx

    hdrs = {"User-Agent": "fastfold-agent-cli", **(headers or {})}
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url, headers=hdrs)
        resp.raise_for_status()
        return resp.content


def fetch_latest_release(owner_repo: str, *, timeout_s: float = 2.5) -> dict | None:
    """Return ``{"tag", "published_at", "commit"}`` for a repo's latest GitHub Release.

    Best-effort and network-bound: returns None on any error or when the repo
    has no releases (HTTP 404). Used to surface a version in the /skills table.
    """
    import httpx

    if not owner_repo:
        return None
    url = f"{_skills.GITHUB_API}/repos/{owner_repo}/releases/latest"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "fastfold-agent-cli"}
    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, TimeoutError, ValueError):
        return None
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, dict):
        return None
    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        return None
    commit = ""
    target = data.get("target_commitish")
    if isinstance(target, str) and re.fullmatch(r"[0-9a-fA-F]{7,40}", target.strip()):
        commit = target.strip().lower()
    return {
        "tag": tag,
        "published_at": str(data.get("published_at") or ""),
        "commit": commit,
    }


def fetch_repo_head_sha(owner_repo: str, *, timeout_s: float = 2.5) -> dict | None:
    """Return ``{"sha", "default_branch"}`` for a repo's default-branch HEAD."""
    import httpx

    if not owner_repo:
        return None
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "fastfold-agent-cli"}
    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            meta = client.get(f"{_skills.GITHUB_API}/repos/{owner_repo}", headers=headers)
            if meta.status_code == 404:
                return None
            meta.raise_for_status()
            body = meta.json()
            branch = str((body or {}).get("default_branch") or "main").strip() or "main"
            commits = client.get(
                f"{_skills.GITHUB_API}/repos/{owner_repo}/commits/{branch}",
                headers=headers,
            )
            if commits.status_code == 404:
                return None
            commits.raise_for_status()
            data = commits.json()
    except (httpx.HTTPError, TimeoutError, ValueError):
        return None
    except Exception:  # noqa: BLE001
        return None
    sha = str((data or {}).get("sha") or "").strip().lower()
    if not sha:
        return None
    return {"sha": sha, "default_branch": branch}


_REPO_CHECK_INTERVAL_S = 3600  # 1h — fresher than catalog banner (24h)


def resolve_repo_remote_state(
    owner_repo: str,
    *,
    force: bool = False,
    timeout_s: float = 2.5,
) -> dict:
    """Cached remote state for a GitHub repo: latest release + default HEAD.

    Returns ``{release_tag, release_published_at, head_sha, default_branch, checked_at}``.
    Values may be empty when the network call fails or the repo has no releases.
    """
    owner_repo = str(owner_repo or "").strip()
    if not owner_repo:
        return {}
    cache = _read_update_cache()
    repos = cache.get("repos") if isinstance(cache.get("repos"), dict) else {}
    entry = repos.get(owner_repo) if isinstance(repos.get(owner_repo), dict) else {}
    if entry and not force:
        checked = entry.get("checked_at")
        if checked:
            try:
                last = datetime.fromisoformat(str(checked))
                if (datetime.now(UTC) - last).total_seconds() < _REPO_CHECK_INTERVAL_S:
                    return dict(entry)
            except Exception:  # noqa: BLE001
                pass

    release = fetch_latest_release(owner_repo, timeout_s=timeout_s) or {}
    head = fetch_repo_head_sha(owner_repo, timeout_s=timeout_s) or {}
    fresh = {
        "checked_at": datetime.now(UTC).isoformat(),
        "release_tag": str(release.get("tag") or ""),
        "release_published_at": str(release.get("published_at") or ""),
        "release_commit": str(release.get("commit") or ""),
        "head_sha": str(head.get("sha") or ""),
        "default_branch": str(head.get("default_branch") or ""),
    }
    repos = dict(repos)
    repos[owner_repo] = fresh
    cache = dict(cache)
    cache["repos"] = repos
    # Keep legacy catalog fields in sync for the Fastfold default catalog.
    if owner_repo == _skills.DEFAULT_CATALOG.split("@", 1)[0] and fresh["release_tag"]:
        cache["checked_at"] = fresh["checked_at"]
        cache["latest_release"] = fresh["release_tag"]
        cache["latest_published_at"] = fresh["release_published_at"]
    _write_update_cache(cache)
    return fresh


def check_github_skill_update(
    source: str,
    *,
    installed_release: str | None = None,
    installed_commit: str | None = None,
    force: bool = False,
) -> dict | None:
    """Return update info for a GitHub-sourced skill, or None if up to date / N/A.

    Policy (works for any GitHub skill repo):
    1. Prefer latest GitHub **Release** tag vs installed ``release`` (semver).
    2. Else compare remote default-branch **HEAD** vs installed ``commit``.

    Returns ``{available, channel, latest, installed, owner_repo}`` when an update
    is available. ``channel`` is ``"release"`` or ``"commit"``.
    """
    owner_repo = _owner_repo_from_source(source)
    if not owner_repo:
        return None
    remote = resolve_repo_remote_state(owner_repo, force=force)
    if not remote:
        return None

    installed_tag = str(installed_release or "").strip()
    latest_tag = str(remote.get("release_tag") or "").strip()

    # 1) Release channel — preferred when the repo publishes GitHub Releases.
    if latest_tag and installed_tag:
        if _is_newer_tag(latest_tag, installed_tag):
            return {
                "available": True,
                "channel": "release",
                "latest": latest_tag,
                "installed": installed_tag,
                "owner_repo": owner_repo,
            }
        # Same semver / same tag → current. Do not also nag on HEAD drift.
        if latest_tag.lstrip("v") == installed_tag.lstrip("v") or (
            _tag_tuple(latest_tag)
            and _tag_tuple(latest_tag) == _tag_tuple(installed_tag)
        ):
            return None
        # Non-semver tags that differ — surface as an update.
        if latest_tag != installed_tag:
            return {
                "available": True,
                "channel": "release",
                "latest": latest_tag,
                "installed": installed_tag,
                "owner_repo": owner_repo,
            }
        return None

    if latest_tag and not installed_tag:
        return {
            "available": True,
            "channel": "release",
            "latest": latest_tag,
            "installed": (installed_commit or "")[:7] or "unknown",
            "owner_repo": owner_repo,
        }

    # 2) Commit channel — repos without releases (or no installed release label).
    head = str(remote.get("head_sha") or "").strip().lower()
    current = str(installed_commit or "").strip().lower()
    if head and current and not (
        head == current or head.startswith(current) or current.startswith(head)
    ):
        return {
            "available": True,
            "channel": "commit",
            "latest": head[:7],
            "installed": current[:7],
            "owner_repo": owner_repo,
        }
    return None


def _read_update_cache() -> dict:
    if not _skills.SKILLS_UPDATE_CACHE.exists():
        return {}
    try:
        data = json.loads(_skills.SKILLS_UPDATE_CACHE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _write_update_cache(cache: dict) -> None:
    try:
        _skills.SKILLS_UPDATE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _skills.SKILLS_UPDATE_CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        tmp.replace(_skills.SKILLS_UPDATE_CACHE)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not write skills update cache: %s", exc)


def _installed_catalog_release(catalog: str = _skills.DEFAULT_CATALOG) -> str | None:
    """Return the release tag recorded for the installed Fastfold catalog, if any."""
    owner_repo = catalog.split("@", 1)[0]
    manifest = _skills._read_manifest(_skills.GLOBAL_SKILLS_DIR)
    for meta in (manifest.get("skills") or {}).values():
        if not isinstance(meta, dict):
            continue
        src = str(meta.get("source") or "")
        if _owner_repo_from_source(src) == owner_repo and meta.get("release"):
            return str(meta["release"])
    return None


def get_cached_skills_update(catalog: str = _skills.DEFAULT_CATALOG) -> dict | None:
    """Local-only check (no network) for a newer catalog release.

    Returns ``{"installed", "latest", "published_at"}`` when the cached latest
    release is newer than the installed catalog release, else None. Safe to call
    on the boot path.
    """
    cache = _skills._read_update_cache()
    latest = cache.get("latest_release")
    if not latest:
        return None
    installed = _skills._installed_catalog_release(catalog)
    if not installed:
        return None
    if _is_newer_tag(str(latest), installed):
        return {
            "installed": installed,
            "latest": str(latest),
            "published_at": str(cache.get("latest_published_at") or ""),
        }
    return None


def refresh_skills_update_cache(
    *, catalog: str = _skills.DEFAULT_CATALOG, timeout_s: float = 2.5, force: bool = False
) -> None:
    """Refresh the cached latest catalog release (network). Throttled to 24h.

    Designed to run in a daemon thread so the next boot reads a fresh cache
    without any network on the boot path.
    """
    cache = _skills._read_update_cache()
    if not force:
        checked = cache.get("checked_at")
        if checked:
            try:
                last = datetime.fromisoformat(str(checked))
                if (datetime.now(UTC) - last).total_seconds() < _UPDATE_CHECK_INTERVAL_S:
                    return
            except Exception:  # noqa: BLE001
                pass
    owner_repo = catalog.split("@", 1)[0]
    rel = _skills.fetch_latest_release(owner_repo, timeout_s=timeout_s)
    cache = dict(cache)
    cache["checked_at"] = datetime.now(UTC).isoformat()
    cache["latest_release"] = (rel or {}).get("tag")
    cache["latest_published_at"] = (rel or {}).get("published_at", "")
    _skills._write_update_cache(cache)
