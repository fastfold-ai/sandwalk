"""Source detection and git/archive/npx skill installation, plus manifest I/O."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path

from agent import skills as _skills

logger = logging.getLogger("skills")

# Serializes manifest read-modify-write so parallel installs don't corrupt it.
_MANIFEST_LOCK = threading.Lock()

_GITHUB_SHORTHAND_RE = re.compile(r"^(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:@(?P<sub>.+))?$")
_CLONE_TIMEOUT_S = 120


# ─── Source parsing ─────────────────────────────────────────────────────────
def detect_source_type(source: str) -> str:
    """Classify a skill source string: 'local', 'github', 'shorthand', or 'name'."""
    s = (source or "").strip()
    if not s:
        return "name"
    if s.startswith(("./", "../", "/", "~")) or Path(s).expanduser().exists():
        return "local"
    if s.startswith("http://") or s.startswith("https://") or s.startswith("git@"):
        return "github"
    if "/" in s and _GITHUB_SHORTHAND_RE.match(s):
        return "shorthand"
    return "name"


def _parse_github(source: str) -> tuple[str, str | None, str | None]:
    """Return (clone_url, ref, subpath) for a GitHub URL or shorthand."""
    s = source.strip()

    # Shorthand: owner/repo[@subpath]
    m = _GITHUB_SHORTHAND_RE.match(s)
    if m and not s.startswith(("http", "git@")):
        owner, repo, sub = m.group("owner"), m.group("repo"), m.group("sub")
        repo = repo[:-4] if repo.endswith(".git") else repo
        return f"https://github.com/{owner}/{repo}.git", None, sub

    # Full URL, optionally with /tree/<ref>/<subpath>
    url = s
    ref: str | None = None
    sub: str | None = None
    tree = re.search(r"github\.com[:/](?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?(?:/tree/(?P<ref>[^/]+)(?:/(?P<sub>.+))?)?/?$", s)
    if tree:
        owner = tree.group("owner")
        repo = tree.group("repo")
        ref = tree.group("ref")
        sub = tree.group("sub")
        url = f"https://github.com/{owner}/{repo}.git"
    return url, ref, sub


# ─── Install ────────────────────────────────────────────────────────────────
def _git_available() -> bool:
    return shutil.which("git") is not None


def _npx_available() -> bool:
    return shutil.which("npx") is not None


def _noninteractive_git_env() -> dict:
    """Env that prevents git from blocking on interactive auth/SSH prompts.

    Without this, a transient 403 / auth challenge on an otherwise public clone
    makes ``git`` hang forever waiting for a username/password on stdin, which
    the subprocess timeout can't always interrupt cleanly. Failing fast lets us
    fall back to the GitHub archive download instead of stalling the upgrade.
    """
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"
    env["GCM_INTERACTIVE"] = "never"
    env.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes -oStrictHostKeyChecking=no")
    return env


def _git_clone(url: str, ref: str | None, dest: Path) -> str | None:
    """Shallow clone ``url`` into ``dest``. Returns the commit SHA or None."""
    cmd = ["git", "clone", "--depth", "1"]
    if ref:
        cmd += ["--branch", ref]
    cmd += [url, str(dest)]
    env = _noninteractive_git_env()
    subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        timeout=_CLONE_TIMEOUT_S,
        stdin=subprocess.DEVNULL,
        env=env,
    )
    try:
        out = subprocess.run(
            ["git", "-C", str(dest), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=30,
            stdin=subprocess.DEVNULL, env=env,
        )
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def _resolve_skill_dirs(root: Path, subpath: str | None) -> list[Path]:
    """Find skill directories (containing SKILL.md) within a cloned repo."""
    base = (root / subpath) if subpath else root
    if not base.exists():
        base = root

    # Single skill directly at base.
    if (base / "SKILL.md").exists():
        return [base]

    # Otherwise treat children (depth 1) with SKILL.md as a pack.
    if base.exists() and base.is_dir():
        found = [
            c
            for c in sorted(base.iterdir())
            if c.is_dir() and (c / "SKILL.md").exists()
        ]
        if found:
            return found

    # Monorepo convention: skills live under a 'skills/' folder
    # (e.g. fastfold-ai/skills with skills/<name>/SKILL.md). Mirrors discover_skills().
    skills_dir = base / "skills"
    if skills_dir.exists():
        found = [
            c
            for c in sorted(skills_dir.iterdir())
            if c.is_dir() and (c / "SKILL.md").exists()
        ]
        if found:
            return found

    # Skills.sh / curated layouts may nest skills (e.g. skills/.curated/<name>).
    # When a specific subpath was requested, search by the final folder name.
    if subpath:
        wanted = _skills._normalize_skill_lookup(Path(subpath).name)
        if wanted:
            matches: list[Path] = []
            for skill_md in root.rglob("SKILL.md"):
                parent = skill_md.parent
                if _skills._normalize_skill_lookup(parent.name) == wanted:
                    matches.append(parent)
            if matches:
                # Prefer shallower paths when multiple matches exist.
                matches.sort(key=lambda path: (len(path.parts), str(path)))
                return [matches[0]]
    return []


def _read_manifest(dest: Path) -> dict:
    path = dest / _skills.MANIFEST_FILENAME
    if not path.exists():
        return {"version": 1, "skills": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "skills" not in data:
            data["skills"] = {}
        return data
    except Exception:  # noqa: BLE001
        return {"version": 1, "skills": {}}


def _write_manifest(dest: Path, manifest: dict) -> None:
    path = dest / _skills.MANIFEST_FILENAME
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    tmp.replace(path)


def _record_install(
    dest: Path,
    name: str,
    source: str,
    commit: str | None,
    release: str | None = None,
) -> None:
    entry = {
        "source": source,
        "commit": commit,
        "installed_at": datetime.now(UTC).isoformat(),
    }
    if release:
        entry["release"] = release
    # Hold the lock across the read-modify-write so concurrent installs can't
    # clobber each other's manifest entries.
    with _MANIFEST_LOCK:
        manifest = _skills._read_manifest(dest)
        manifest["skills"][name] = entry
        _skills._write_manifest(dest, manifest)


def _npx_target(source: str) -> tuple[str, str | None, bool]:
    """Map a skill source to (npx_target, skill_name, whole_repo) for `npx skills add`.

    - ``owner/repo@subpath`` -> (``owner/repo``, ``<last path segment>``, False)
    - GitHub ``/tree/<ref>/<path>`` URL -> (url, None, False)  # URL targets one skill
    - whole-repo shorthand/URL -> (source, None, True)
    """
    s = (source or "").strip()
    if s.startswith(("http://", "https://", "git@")):
        return s, None, ("/tree/" not in s)
    if "@" in s:
        repo, sub = s.split("@", 1)
        name = sub.rstrip("/").split("/")[-1] or None
        return repo, name, False
    return s, None, True


def _run_npx_add(target: str, skill_names: list[str] | None = None, whole: bool = False) -> None:
    """Run `npx skills add` non-interactively, pinned to the fastfold-owned dir."""
    _skills.NPX_INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
    cmd = ["npx", "-y", "skills", "add", target, "-a", "claude-code", "--copy", "-y"]
    if skill_names:
        for name in skill_names:
            cmd += ["--skill", name]
    elif whole:
        cmd += ["--skill", "*"]
    subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        timeout=_CLONE_TIMEOUT_S,
        stdin=subprocess.DEVNULL,
        cwd=str(_skills.NPX_INSTALL_ROOT),
    )


def npx_add(target: str, skill_names: list[str] | None = None, whole: bool = False) -> dict:
    """Install one or more skills from a single repo/URL via `npx skills add`."""
    if not _skills._npx_available():
        return {"ok": False, "summary": "npx is not available.", "via": "npx"}
    try:
        _skills._run_npx_add(target, skill_names, whole)
        what = f"{target}" + (f" (skills: {', '.join(skill_names)})" if skill_names else " (all)" if whole else "")
        return {
            "ok": True,
            "installed": list(skill_names or []),
            "summary": f"Installed {what} via npx into {_skills.NPX_SKILLS_DIR}.",
            "via": "npx",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "summary": f"npx skills add timed out for {target}.", "via": "npx"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": f"npx skills add failed: {exc}", "via": "npx"}


def _npx_install(source: str) -> dict:
    """Install a single source via npx (handles owner/repo@subpath via --skill)."""
    target, skill, whole = _npx_target(source)
    return _skills.npx_add(target, [skill] if skill else None, whole)


def _npx_update() -> dict:
    """Update all npx-installed skills in the fastfold-owned dir (`npx skills update`)."""
    if not _skills._npx_available():
        return {"ok": False, "summary": "npx is not available."}
    try:
        subprocess.run(
            ["npx", "-y", "skills", "update", "-y"],
            check=True, capture_output=True, text=True,
            timeout=_CLONE_TIMEOUT_S, stdin=subprocess.DEVNULL, cwd=str(_skills.NPX_INSTALL_ROOT),
        )
        return {"ok": True, "summary": "Updated npx-installed skills."}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": f"npx skills update failed: {exc}"}


def _owner_repo_from_clone_url(url: str) -> str | None:
    m = re.search(r"github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?$", url)
    if not m:
        return None
    return f"{m.group('owner')}/{m.group('repo')}"


def _format_git_error(exc: subprocess.CalledProcessError) -> str:
    detail = (exc.stderr or exc.stdout or str(exc)).strip()
    if len(detail) > 200:
        detail = detail[:197] + "..."
    return detail or "git clone failed"


def _download_github_archive(owner: str, repo: str, ref: str | None, extract_parent: Path) -> Path:
    """Download and extract a GitHub repo archive without git."""
    import io
    import zipfile

    import httpx

    ref_key = ref or "HEAD"
    url = f"https://codeload.github.com/{owner}/{repo}/zip/{ref_key}"
    try:
        data = _skills._http_get_bytes(url, timeout=_CLONE_TIMEOUT_S)
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"GitHub archive download failed (HTTP {exc.response.status_code})") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"GitHub archive download failed: {exc}") from exc

    extract_parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(extract_parent)
    roots = [p for p in extract_parent.iterdir() if p.is_dir()]
    if len(roots) == 1:
        return roots[0]
    if not roots:
        raise RuntimeError("GitHub archive contained no directories")
    return extract_parent


def _install_from_repo_tree(
    repo_root: Path,
    subpath: str | None,
    dest: Path,
    source: str,
    commit: str | None,
    release_tag: str | None,
    via: str,
) -> dict:
    skill_dirs = _resolve_skill_dirs(repo_root, subpath)
    if not skill_dirs:
        return {
            "ok": False,
            "summary": (
                f"No SKILL.md found in {source}. "
                "This skill may have been removed or moved in the source repository "
                "or Skills.sh listing."
            ),
            "via": via,
        }
    installed = _copy_skill_dirs(skill_dirs, dest, source, commit, release_tag)
    return {
        "ok": True,
        "installed": installed,
        "summary": f"Installed {len(installed)} skill(s) to {dest}: {', '.join(installed)}.",
        "via": via,
    }


def _install_github_source(
    source: str,
    url: str,
    ref: str | None,
    subpath: str | None,
    dest: Path,
    release_tag: str | None,
) -> dict:
    """Install a GitHub source via git clone, archive download, then optional npx."""
    errors: list[str] = []

    if _skills._git_available():
        try:
            with tempfile.TemporaryDirectory(prefix="fastfold-skill-") as tmp:
                clone_root = Path(tmp) / "repo"
                commit = _skills._git_clone(url, ref, clone_root)
                return _install_from_repo_tree(
                    clone_root, subpath, dest, source, commit, release_tag, "git"
                )
        except subprocess.CalledProcessError as exc:
            logger.debug("git clone failed: %s", exc)
            errors.append(f"git clone failed: {_format_git_error(exc)}")
        except Exception as exc:  # noqa: BLE001
            logger.debug("git install failed: %s", exc)
            errors.append(f"git install failed: {exc}")

    owner_repo = _owner_repo_from_clone_url(url)
    if owner_repo:
        owner, repo = owner_repo.split("/", 1)
        try:
            with tempfile.TemporaryDirectory(prefix="fastfold-skill-") as tmp:
                extract_parent = Path(tmp)
                repo_root = _skills._download_github_archive(owner, repo, ref, extract_parent)
                return _install_from_repo_tree(
                    repo_root, subpath, dest, source, None, release_tag, "archive"
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("GitHub archive install failed: %s", exc)
            errors.append(str(exc))

    if _skills._npx_available():
        result = _skills._npx_install(source)
        if result.get("ok"):
            return result
        errors.append(result.get("summary", "npx install failed"))

    summary = errors[0] if len(errors) == 1 else "; ".join(errors)
    if not summary:
        summary = "Could not install skill from GitHub."
    return {"ok": False, "summary": summary, "via": "git"}


def install_skill(
    source: str,
    *,
    dest: Path | None = None,
    prefer_npx: bool = False,
    manifest_source: str | None = None,
) -> dict:
    """Install a skill from a GitHub URL/shorthand, local path, or catalog name.

    By default uses a native ``git clone``, then GitHub archive download, then
    ``npx skills add`` when available. When ``prefer_npx`` is True and ``npx`` is
    available, tries ``npx skills add`` first and falls back to git/archive.

    ``manifest_source`` overrides the recorded install source (e.g. ``custom``
    for agent-authored skills so the UI does not pin a session workspace path).

    Returns a dict with keys: ok, installed (list of names), summary.
    """
    source = (source or "").strip()
    if not source:
        return {"ok": False, "summary": "No skill source provided."}

    dest = dest or _skills.GLOBAL_SKILLS_DIR
    dest.mkdir(parents=True, exist_ok=True)

    src_type = detect_source_type(source)

    # Resolve a bare name against the catalog before installing.
    if src_type == "name":
        match = _skills._resolve_name_to_source(source)
        if not match:
            return {"ok": False, "summary": f"Could not find a skill named '{source}' in the catalog."}
        source = match
        src_type = detect_source_type(source)

    if src_type == "local":
        return _install_local(source, dest, manifest_source=manifest_source)

    url, ref, subpath = _parse_github(source)

    # Prefer npx when requested. npx handles both whole-repo and specific-skill
    # installs (the latter via --skill, derived from our owner/repo@subpath shorthand).
    if prefer_npx and _skills._npx_available():
        result = _skills._npx_install(source)
        if result.get("ok"):
            return result
        logger.debug("npx skills add failed, falling back to git/archive: %s", result.get("summary"))

    owner_repo = _skills._owner_repo_from_source(source)
    release_info = _skills.fetch_latest_release(owner_repo) if owner_repo else None
    release_tag = release_info.get("tag") if release_info else None
    # Unpinned installs track the latest GitHub Release (not floating HEAD),
    # so the labeled version matches the content that was copied.
    install_ref = ref or release_tag
    return _install_github_source(source, url, install_ref, subpath, dest, release_tag)


def _install_local(
    source: str,
    dest: Path,
    *,
    manifest_source: str | None = None,
) -> dict:
    base = Path(source).expanduser().resolve()
    if not base.exists():
        return {"ok": False, "summary": f"Local path does not exist: {source}"}

    # .zip / .skill archives — same shape as UI upload install.
    if base.is_file() and base.suffix.lower() in {".zip", ".skill"}:
        return _install_local_archive(
            base, dest, manifest_source=manifest_source
        )

    skill_dirs = _resolve_skill_dirs(base, None)
    if not skill_dirs:
        return {"ok": False, "summary": f"No SKILL.md found at {source}."}
    recorded = (manifest_source or "").strip() or str(base)
    installed = _copy_skill_dirs(skill_dirs, dest, recorded, None)
    return {
        "ok": True,
        "installed": installed,
        "summary": f"Installed {len(installed)} skill(s) to {dest}: {', '.join(installed)}.",
        "via": "local",
    }


def _install_local_archive(
    archive_path: Path,
    dest: Path,
    *,
    manifest_source: str | None = None,
) -> dict:
    """Extract a .zip/.skill bundle and install skill dirs found inside."""
    import zipfile

    with tempfile.TemporaryDirectory(prefix="sandwalk-skill-zip-") as tmp:
        extract_dir = Path(tmp) / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(archive_path) as archive:
                extract_root = extract_dir.resolve()
                for member in archive.infolist():
                    target = (extract_dir / member.filename).resolve()
                    if target != extract_root and extract_root not in target.parents:
                        return {
                            "ok": False,
                            "summary": "Archive contains invalid file paths.",
                        }
                archive.extractall(extract_dir)
        except zipfile.BadZipFile:
            return {
                "ok": False,
                "summary": "Archive is not a valid .zip/.skill bundle.",
            }
        skill_dirs = _resolve_skill_dirs(extract_dir, None)
        if not skill_dirs:
            # Nested single folder common in GitHub zip downloads.
            children = [p for p in extract_dir.iterdir() if p.is_dir()]
            if len(children) == 1:
                skill_dirs = _resolve_skill_dirs(children[0], None)
        if not skill_dirs:
            return {
                "ok": False,
                "summary": f"No SKILL.md found inside archive {archive_path.name}.",
            }
        recorded = (manifest_source or "").strip() or str(archive_path)
        installed = _copy_skill_dirs(skill_dirs, dest, recorded, None)
        return {
            "ok": True,
            "installed": installed,
            "summary": (
                f"Installed {len(installed)} skill(s) from archive "
                f"{archive_path.name}: {', '.join(installed)}."
            ),
            "via": "local-archive",
        }


def _copy_skill_dirs(
    skill_dirs: list[Path],
    dest: Path,
    source: str,
    commit: str | None,
    release: str | None = None,
) -> list[str]:
    installed: list[str] = []
    for sd in skill_dirs:
        name = sd.name
        target = dest / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(sd, target, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        _record_install(dest, name, source, commit, release)
        installed.append(name)
    return installed
