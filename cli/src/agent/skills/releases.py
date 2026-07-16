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
    """Return ``{"tag", "published_at"}`` for a repo's latest GitHub Release.

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
    return {"tag": tag, "published_at": str(data.get("published_at") or "")}


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
    _skills._write_update_cache(
        {
            "checked_at": datetime.now(UTC).isoformat(),
            "latest_release": (rel or {}).get("tag"),
            "latest_published_at": (rel or {}).get("published_at", ""),
        }
    )
