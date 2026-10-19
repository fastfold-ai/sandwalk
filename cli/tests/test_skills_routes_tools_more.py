"""Cover remaining branches in skills auth/search, discovery, config mutation, and file/target tools.

HTTP and config persistence are mocked. Nothing here writes the developer ~/.sandwalk.
"""

from __future__ import annotations

import io
import json
import tarfile
import time
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from agent.config import Config
from agent.skills import SkillInfo
from agent.skills import discover as discover_mod
from agent_server.models import CatalogSkill
from agent_server.skills_service import SkillsService
from agent_server.skills_service import auth as auth_mod
from agent_server.skills_service import search as search_mod
from tools.files_ops import copy_file, create_directory, extract_archive, move_file
from tools.target_druggability import druggability


def _jwt(payload: dict) -> str:
    import base64

    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"hdr.{body}.sig"


class _Body:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeConfig:
    def __init__(self):
        self.values: dict = {}
        self.saved = False

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def save(self):
        self.saved = True


def _http_error(code: int, body: bytes = b"", *, read_error: bool = False) -> HTTPError:
    err = HTTPError("https://skills.sh/x", code, "err", hdrs=None, fp=io.BytesIO(body))
    if read_error:
        def _read():
            raise OSError("unread")

        err.read = _read  # type: ignore[method-assign]
    return err


def _write_skill(
    base: Path,
    dirname: str,
    *,
    name: str | None = None,
    description: str = "desc",
    tags: str = "",
    author: str = "",
    category: str = "",
    version: str = "",
    updated: str = "",
) -> Path:
    folder = base / dirname
    folder.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"name: {name or dirname}", f"description: {description}"]
    if tags:
        lines.append(f"tags: {tags}")
    if author:
        lines.append(f"author: {author}")
    if category:
        lines.append(f"category: {category}")
    if version:
        lines.append(f"version: {version}")
    if updated:
        lines.append(f"updated: {updated}")
    lines += ["---", "", "# skill"]
    (folder / "SKILL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return folder


def _isolate_skill_dirs(monkeypatch, tmp_path: Path) -> dict[str, Path]:
    dirs = {
        "bundled": tmp_path / "bundled",
        "npx": tmp_path / "npx",
        "global": tmp_path / "global",
    }
    for path in dirs.values():
        path.mkdir()
    monkeypatch.setattr(discover_mod._skills, "BUNDLED_SKILLS_DIR", dirs["bundled"])
    monkeypatch.setattr(discover_mod._skills, "NPX_SKILLS_DIR", dirs["npx"])
    monkeypatch.setattr(discover_mod._skills, "GLOBAL_SKILLS_DIR", dirs["global"])
    monkeypatch.setattr(
        "agent.skills.releases.enrich_bundled_skill",
        lambda info: setattr(info, "version", info.version or "patched"),
    )
    return dirs


class _BadPath:
    def __fspath__(self):
        raise OSError("unresolvable")


# ─── skills.sh auth ─────────────────────────────────────────────────────────


def test_jwt_expired_rejects_malformed_tokens():
    assert auth_mod.AuthMixin._jwt_expired("not-a-jwt") is False
    assert auth_mod.AuthMixin._jwt_expired(_jwt({"exp": "soon"})) is False
    assert auth_mod.AuthMixin._jwt_expired("a.!!!.c") is False
    assert auth_mod.AuthMixin._jwt_expired(_jwt({"exp": 10})) is True


def test_refresh_vercel_oidc_token_persists_and_errors(monkeypatch):
    saved = _FakeConfig()
    synced = {}
    monkeypatch.setattr(auth_mod.Config, "load", lambda: saved)
    monkeypatch.setattr(
        "agent.config.sync_process_env_from_config",
        lambda cfg: synced.setdefault("cfg", cfg),
    )
    monkeypatch.setattr(
        "agent_server.integrations_service.IntegrationsService._vercel_workspace_dir",
        lambda: Path("/tmp/vercel-workspace"),
    )

    monkeypatch.setattr(
        "agent_server.integrations_service.IntegrationsService._fetch_vercel_oidc_token_via_cli",
        lambda workspace: ("", "cli missing"),
    )
    with pytest.raises(RuntimeError, match="cli missing"):
        auth_mod.AuthMixin._refresh_vercel_oidc_token()

    monkeypatch.setattr(
        "agent_server.integrations_service.IntegrationsService._fetch_vercel_oidc_token_via_cli",
        lambda workspace: (None, ""),
    )
    with pytest.raises(RuntimeError, match="VERCEL_OIDC_TOKEN"):
        auth_mod.AuthMixin._refresh_vercel_oidc_token()

    monkeypatch.setattr(
        "agent_server.integrations_service.IntegrationsService._fetch_vercel_oidc_token_via_cli",
        lambda workspace: ("oidc-fresh", None),
    )
    token = auth_mod.AuthMixin._refresh_vercel_oidc_token()
    assert token == "oidc-fresh"
    assert saved.values["api.vercel_oidc_token"] == "oidc-fresh"
    assert saved.saved is True
    assert synced["cfg"] is saved


def test_skills_sh_token_force_refresh_and_live_token(monkeypatch):
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    calls = {"n": 0}

    def refresh(cls):
        calls["n"] += 1
        return "refreshed"

    monkeypatch.setattr(auth_mod.AuthMixin, "_refresh_vercel_oidc_token", classmethod(refresh))
    assert auth_mod.AuthMixin._skills_sh_token(force_refresh=True) == "refreshed"

    live = _jwt({"exp": int(time.time()) + 10_000})
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", live)
    monkeypatch.setattr(auth_mod.Config, "load", lambda: _FakeConfig())
    assert auth_mod.AuthMixin._skills_sh_token() == live
    assert calls["n"] == 1


def test_skills_sh_token_expired_refresh_failures(monkeypatch):
    expired = _jwt({"exp": int(time.time()) - 500})
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", expired)
    monkeypatch.setattr(auth_mod.Config, "load", lambda: _FakeConfig())

    def refresh(cls):
        raise RuntimeError("nope")

    monkeypatch.setattr(auth_mod.AuthMixin, "_refresh_vercel_oidc_token", classmethod(refresh))
    with pytest.raises(RuntimeError, match="expired"):
        auth_mod.AuthMixin._skills_sh_token()

    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="not configured"):
        auth_mod.AuthMixin._skills_sh_token()


def test_skills_sh_request_json_error_paths(monkeypatch):
    svc = SkillsService()
    monkeypatch.setattr(
        SkillsService,
        "_skills_sh_token",
        lambda self, force_refresh=False: "tok",
    )

    def fail_refresh(self, force_refresh=False):
        if force_refresh:
            raise RuntimeError("refresh down")
        return "tok"

    monkeypatch.setattr(SkillsService, "_skills_sh_token", fail_refresh)

    def raise_401(request, timeout=8):
        raise _http_error(401)

    monkeypatch.setattr("agent_server.skills_service.urlopen", raise_401)
    with pytest.raises(RuntimeError, match="refresh down"):
        svc._skills_sh_request_json("https://skills.sh/api", operation="search")

    monkeypatch.setattr(SkillsService, "_skills_sh_token", lambda self, force_refresh=False: "tok")
    with pytest.raises(RuntimeError, match="token rejected"):
        svc._skills_sh_request_json("https://skills.sh/api", operation="search")

    def raise_404(request, timeout=8):
        raise _http_error(404, b"missing skill")

    monkeypatch.setattr("agent_server.skills_service.urlopen", raise_404)
    with pytest.raises(LookupError, match="missing skill"):
        svc._skills_sh_request_json("https://skills.sh/api", operation="detail")

    def raise_404_blank(request, timeout=8):
        raise _http_error(404, b"   ")

    monkeypatch.setattr("agent_server.skills_service.urlopen", raise_404_blank)
    with pytest.raises(LookupError, match="Not found"):
        svc._skills_sh_request_json("https://skills.sh/api", operation="detail")

    def raise_500(request, timeout=8):
        raise _http_error(500, b"boom")

    monkeypatch.setattr("agent_server.skills_service.urlopen", raise_500)
    with pytest.raises(RuntimeError, match=r"failed \(500\). boom"):
        svc._skills_sh_request_json("https://skills.sh/api", operation="search")

    def raise_500_unread(request, timeout=8):
        raise _http_error(500, read_error=True)

    monkeypatch.setattr("agent_server.skills_service.urlopen", raise_500_unread)
    with pytest.raises(RuntimeError, match=r"failed \(500\)\.$"):
        svc._skills_sh_request_json("https://skills.sh/api", operation="search")

    def raise_url(request, timeout=8):
        raise URLError("down")

    monkeypatch.setattr("agent_server.skills_service.urlopen", raise_url)
    with pytest.raises(RuntimeError, match="unavailable"):
        svc._skills_sh_request_json("https://skills.sh/api", operation="search")

    def bad_json(request, timeout=8):
        return _Body(b"not-json")

    monkeypatch.setattr("agent_server.skills_service.urlopen", bad_json)
    with pytest.raises(RuntimeError, match="invalid response"):
        svc._skills_sh_request_json("https://skills.sh/api", operation="search")

    def not_object(request, timeout=8):
        return _Body(b"[1]")

    monkeypatch.setattr("agent_server.skills_service.urlopen", not_object)
    with pytest.raises(RuntimeError, match="invalid response"):
        svc._skills_sh_request_json("https://skills.sh/api", operation="search")

    def ok(request, timeout=8):
        return _Body(b'{"data":[]}')

    monkeypatch.setattr("agent_server.skills_service.urlopen", ok)
    assert svc._skills_sh_request_json("https://skills.sh/api", operation="search") == {"data": []}


# ─── skills.sh search ───────────────────────────────────────────────────────


def test_catalog_payload_skips_bad_shapes():
    assert search_mod._catalog_skills_from_payload(["nope"]) == []
    assert search_mod._catalog_skills_from_payload({"data": "nope"}) == []
    skills = search_mod._catalog_skills_from_payload(
        {
            "data": [
                "skip",
                {
                    "id": "1",
                    "slug": "fold",
                    "name": "Fold",
                    "source": "acme/skills",
                    "installs": 3,
                    "installUrl": None,
                    "url": "https://skills.sh/fold",
                },
            ]
        }
    )
    assert len(skills) == 1
    assert skills[0].install_url is None
    assert skills[0].url == "https://skills.sh/fold"


def test_fetch_all_time_total_cache_and_parse(monkeypatch):
    search_mod._all_time_total_cache = (time.time(), 99)

    def refuse_network(request, timeout=15):
        raise AssertionError("network")

    monkeypatch.setattr("agent_server.skills_service.urlopen", refuse_network)
    assert search_mod._fetch_skills_sh_all_time_total() == 99

    search_mod._all_time_total_cache = (time.time() - 10_000, 77)

    def fail(request, timeout=15):
        raise URLError("down")

    monkeypatch.setattr("agent_server.skills_service.urlopen", fail)
    assert search_mod._fetch_skills_sh_all_time_total() == 77

    search_mod._all_time_total_cache = None
    assert search_mod._fetch_skills_sh_all_time_total() == 0

    def page(request, timeout=15):
        return _Body(b'prefix allTimeTotal": 12345 suffix')

    monkeypatch.setattr("agent_server.skills_service.urlopen", page)
    assert search_mod._fetch_skills_sh_all_time_total() == 12345
    assert search_mod._all_time_total_cache[1] == 12345

    search_mod._all_time_total_cache = (time.time() - 10_000, 55)

    def nomatch(request, timeout=15):
        return _Body(b"no badge")

    monkeypatch.setattr("agent_server.skills_service.urlopen", nomatch)
    assert search_mod._fetch_skills_sh_all_time_total() == 55

    search_mod._all_time_total_cache = None
    assert search_mod._fetch_skills_sh_all_time_total() == 0

    search_mod._all_time_total_cache = (time.time(), 0)

    def escaped(request, timeout=15):
        return _Body(b'allTimeTotal\\": 8')

    monkeypatch.setattr("agent_server.skills_service.urlopen", escaped)
    assert search_mod._fetch_skills_sh_all_time_total() == 8


def test_search_catalog_lookup_and_bounds(monkeypatch):
    captured = {}

    def fake(self, endpoint, operation=""):
        captured["endpoint"] = endpoint
        if "q=ok" in endpoint:
            return {"data": [{"id": "1", "slug": "ok", "name": "Ok", "source": "a/b", "installs": 2}]}
        raise LookupError("missing")

    monkeypatch.setattr(SkillsService, "_skills_sh_request_json", fake)
    svc = SkillsService()
    assert svc.search_catalog("a") == []
    assert svc.search_catalog("fold", limit=0) == []
    assert "limit=1" in captured["endpoint"]
    assert svc.search_catalog("fold", limit=99) == []
    assert "limit=50" in captured["endpoint"]
    found = svc.search_catalog("ok", limit=3)
    assert found[0].slug == "ok"


def test_leaderboard_invalid_view_and_empty_pagination(monkeypatch):
    search_mod._all_time_total_cache = (time.time(), 1000)
    captured = {}

    def fake(self, endpoint, operation=""):
        captured["endpoint"] = endpoint
        if "page=2" in endpoint:
            raise LookupError("gone")
        return {"data": [{"id": "1", "slug": "s", "name": "S", "source": "a/b", "installs": 1}]}

    monkeypatch.setattr(SkillsService, "_skills_sh_request_json", fake)
    svc = SkillsService()
    board = svc.list_catalog_leaderboard(view="NOPE", page=-4, per_page=0)
    assert board.view == "all-time"
    assert board.page == 0
    assert board.per_page == 1
    assert board.total == 1
    assert board.all_time_total == 1000
    assert "view=all-time" in captured["endpoint"]

    empty = svc.list_catalog_leaderboard(view="hot", page=2, per_page=500)
    assert empty.data == []
    assert empty.per_page == 100
    assert empty.all_time_total == 1000
    assert "per_page=100" in captured["endpoint"]


def test_installs_from_search_filters(monkeypatch):
    svc = SkillsService()
    assert svc._installs_from_search("acme/skills", "   ") is None

    def boom(self, query, limit=12):
        raise RuntimeError("down")

    monkeypatch.setattr(SkillsService, "search_catalog", boom)
    assert svc._installs_from_search("acme/skills", "fold") is None

    def results(self, query, limit=12):
        return [
            CatalogSkill(id="1", slug="other", name="other", source="acme/skills", installs=9, source_type="git"),
            CatalogSkill(id="2", slug="fold", name="Fold", source="else/skills", installs=50, source_type="git"),
            CatalogSkill(id="3", slug="fold", name="fold", source="acme/skills", installs=4, source_type="git"),
            CatalogSkill(id="4", slug="fold", name="fold", source="acme_skills", installs=11, source_type="git"),
        ]

    monkeypatch.setattr(SkillsService, "search_catalog", results)
    assert svc._installs_from_search("acme/skills", "fold") == 4
    assert svc._installs_from_search("", "fold") == 50


# ─── skill discovery ────────────────────────────────────────────────────────


def test_scan_dir_edges(monkeypatch, tmp_path):
    missing = tmp_path / "absent"
    assert discover_mod._scan_dir(missing, "global") == {}

    base = tmp_path / "global"
    _write_skill(base, "plain", version="0.1", updated="2020-01-01")
    (base / "note.txt").write_text("skip", encoding="utf-8")
    (base / "empty-dir").mkdir()
    monkeypatch.setattr(discover_mod._skills, "_read_manifest", lambda dest: ["nope"])
    plain = discover_mod._scan_dir(base, "global")
    assert plain["plain"].version == "0.1"
    assert plain["plain"].updated_at == "2020-01-01"

    _write_skill(base, "meta", author="Ada", version="fm", updated="old")
    monkeypatch.setattr(
        discover_mod._skills,
        "_read_manifest",
        lambda dest: {
            "skills": {
                "meta": {
                    "source": "acme/skills@skills/meta",
                    "installed_at": "2024-01-02",
                    "release": "v2",
                    "commit": "abc",
                },
                "plain": "not-a-dict",
            }
        },
    )
    enriched = discover_mod._scan_dir(base, "global")
    assert enriched["meta"].source == "acme/skills@skills/meta"
    assert enriched["meta"].author == "Ada"
    assert enriched["meta"].version == "v2"
    assert enriched["meta"].commit == "abc"
    assert enriched["meta"].updated_at == "2024-01-02"

    _write_skill(base, "nover", version="from-fm")
    monkeypatch.setattr(
        discover_mod._skills,
        "_read_manifest",
        lambda dest: {"skills": {"nover": {"source": "acme/skills", "commit": ""}}},
    )
    no_release = discover_mod._scan_dir(base, "global")
    assert no_release["nover"].version == "from-fm"
    assert no_release["nover"].commit is None

    local = tmp_path / "local"
    _write_skill(local, "draft", author="user")
    _write_skill(local, "kept", author="Ada")
    monkeypatch.setattr(
        discover_mod._skills,
        "_read_manifest",
        lambda dest: {"skills": {"draft": {"source": "/tmp/skill-drafts/draft"}, "kept": {"source": "/tmp/workspaces/kept"}}},
    )
    created = discover_mod._scan_dir(local, "global")
    assert created["draft"].category == discover_mod._skills.USER_CREATED_CATEGORY
    assert created["draft"].author != "user"
    assert created["kept"].author == "Ada"
    assert created["kept"].category == discover_mod._skills.USER_CREATED_CATEGORY

    npx = tmp_path / "npx"
    _write_skill(npx, "cal")
    monkeypatch.setattr(
        discover_mod._skills,
        "_npx_lock_sources",
        lambda: {"cal": "owner/repo@cal"},
    )
    monkeypatch.setattr(discover_mod._skills, "_read_manifest", lambda dest: {"skills": {}})
    locked = discover_mod._scan_dir(npx, "npx")
    assert locked["cal"].source == "owner/repo@cal"
    assert locked["cal"].author == "owner"

    bundled = tmp_path / "bundled"
    _write_skill(bundled, "builtin", version="1.2.3")
    seen = {}
    monkeypatch.setattr(
        "agent.skills.releases.enrich_bundled_skill",
        lambda info: seen.setdefault("name", info.name),
    )
    discover_mod._scan_dir(bundled, "bundled")
    assert seen["name"] == "builtin"


def test_scan_project_and_iter_skills(monkeypatch, tmp_path):
    project = tmp_path / "proj"
    assert discover_mod._scan_project(project) == {}
    locked = project / ".claude" / "skills"
    _write_skill(locked, "proj-skill")
    _write_skill(locked, "bare")
    (project / "skills-lock.json").write_text(
        json.dumps(
            {
                "skills": {
                    "proj-skill": {
                        "source": "acme/repo",
                        "sourceType": "github",
                        "skillPath": "skills/proj-skill/SKILL.md",
                    },
                    "bare": {},
                    "missing": {"source": "acme/repo"},
                }
            }
        ),
        encoding="utf-8",
    )
    scanned = discover_mod._scan_project(project)
    assert scanned["proj-skill"].source.startswith("acme/repo")
    assert scanned["bare"].source == "project"
    assert "missing" not in scanned

    dirs = _isolate_skill_dirs(monkeypatch, tmp_path)
    _write_skill(dirs["bundled"], "only-bundled", description="bundled")
    _write_skill(dirs["global"], "shared", name="shared", description="global")
    _write_skill(dirs["npx"], "npx-only")
    monkeypatch.setattr(discover_mod._skills, "_disabled_skill_names", lambda: {"shared"})
    monkeypatch.chdir(project)
    merged = discover_mod.iter_skills(project_root=None)
    assert merged["shared"].enabled is False
    assert merged["only-bundled"].source == "bundled"
    enabled = discover_mod.iter_skills(project, enabled_only=True)
    assert "shared" not in enabled
    assert "only-bundled" in enabled
    assert "only-bundled" in discover_mod.installed_skill_names(project)
    names = discover_mod.user_installed_skill_names(project)
    assert "npx-only" in discover_mod.user_installed_skill_names()
    assert "only-bundled" not in names
    assert "npx-only" in names
    assert discover_mod.skill_info("no-such-skill", project) is None
    assert discover_mod.skill_info("SHARED", project).description == "global"
    listed = discover_mod.list_skills(project, enabled_only=True)
    assert all(item.enabled for item in listed)


def test_collapse_rank_and_resolve():
    bad = SkillInfo(name="x", source="global", path=_BadPath())  # type: ignore[arg-type]
    assert discover_mod._skill_source_tier_rank(bad) == 4
    assert discover_mod._skill_source_tier_rank(SkillInfo(name="p", source="project-extra")) == 1
    assert discover_mod._skill_source_tier_rank(SkillInfo(name="p", source="project")) == 1
    assert discover_mod._skill_source_tier_rank(SkillInfo(name="n", source="npx")) == 3
    assert discover_mod._skill_source_tier_rank(SkillInfo(name="b", source="bundled")) == 0
    assert discover_mod._skill_source_tier_rank(SkillInfo(name="o", source="marketplace")) == 2

    low = SkillInfo(name="fold", source="bundled")
    high = SkillInfo(name="fold", source="global", version="1", updated_at="2024")
    same = SkillInfo(name="fold", source="project", version="1", updated_at="2024")
    undated = SkillInfo(name="fold", source="project", version="1", updated_at="")
    unversioned = SkillInfo(name="fold", source="project", updated_at="2025")
    assert discover_mod._prefer_duplicate_skill(low, high) is high
    assert discover_mod._prefer_duplicate_skill(high, low) is high
    assert discover_mod._prefer_duplicate_skill(unversioned, same) is same
    assert discover_mod._prefer_duplicate_skill(same, unversioned) is same
    assert discover_mod._prefer_duplicate_skill(undated, same) is same
    assert discover_mod._prefer_duplicate_skill(same, undated) is same
    assert discover_mod._prefer_duplicate_skill(same, SkillInfo(name="fold", source="project", version="1", updated_at="2024")) is same

    collapsed = discover_mod._collapse_skills_by_name(
        {"fold": low, "fold_extra": high, "   ": SkillInfo(name="   ")}
    )
    assert list(collapsed) == ["fold"]
    assert collapsed["fold"] is high
    kept = discover_mod._collapse_skills_by_name({"fold": high, "fold_extra": low})
    assert kept["fold"] is high

    skills = {"Foo_Bar": SkillInfo(name="Other")}
    assert discover_mod._resolve_skill_key("Foo_Bar", skills) == "Foo_Bar"
    assert discover_mod._resolve_skill_key("foo_bar", skills) == "Foo_Bar"
    assert discover_mod._resolve_skill_key("other", skills) == "Foo_Bar"
    assert discover_mod._resolve_skill_key("foo-bar", skills) == "Foo_Bar"
    assert discover_mod._resolve_skill_key("foo-bar", {"dir": SkillInfo(name="foo_bar")}) == "dir"
    assert discover_mod._resolve_skill_key("missing", skills) is None


def test_discover_skills_filters_and_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(discover_mod._skills, "_git_available", lambda: False)
    assert discover_mod.discover_skills("q") == []

    def clone_flat(url, ref, destination):
        _write_skill(destination, "alpha", description="reports", tags="protein")
        _write_skill(destination, "beta", description="other", tags="docs")
        return "sha"

    monkeypatch.setattr(discover_mod._skills, "_git_available", lambda: True)
    monkeypatch.setattr(discover_mod._skills, "_git_clone", clone_flat)
    tagged = discover_mod.discover_skills("protein", catalog="owner/catalog")
    assert [row["name"] for row in tagged] == ["alpha"]
    described = discover_mod.discover_skills("report", catalog="owner/catalog")
    assert described[0]["install_source"] == "owner/catalog@skills/alpha"
    everything = discover_mod.discover_skills(catalog="owner/catalog")
    assert len(everything) == 2

    def explode(url, ref, destination):
        raise RuntimeError("clone failed")

    monkeypatch.setattr(discover_mod._skills, "_git_clone", explode)
    assert discover_mod.discover_skills() == []

    calls = {"n": 0}

    def discover(query, catalog="cat"):
        calls["n"] += 1
        if calls["n"] == 1:
            return [{"name": "exact", "install_source": "owner/repo@skills/exact"}]
        return []

    monkeypatch.setattr(discover_mod._skills, "discover_skills", discover)
    assert discover_mod._resolve_name_to_source("exact") == "owner/repo@skills/exact"
    monkeypatch.setattr(discover_mod._skills, "discover_skills", lambda *a, **k: [])
    assert discover_mod._resolve_name_to_source("missing") is None


def test_discover_ecosystem_edges(monkeypatch):
    assert discover_mod.discover_ecosystem_skills("  ")["ok"] is False
    monkeypatch.setattr(discover_mod._skills, "_npx_available", lambda: False)
    assert "Node/npx" in discover_mod.discover_ecosystem_skills("fold")["summary"]

    monkeypatch.setattr(discover_mod._skills, "_npx_available", lambda: True)

    def explode(*args, **kwargs):
        raise TimeoutError("slow")

    monkeypatch.setattr(discover_mod.subprocess, "run", explode)
    failed = discover_mod.discover_ecosystem_skills("fold")
    assert failed["ok"] is False
    assert "slow" in failed["summary"]

    class Proc:
        returncode = 2
        stdout = (
            "\x1b[31mowner/repo@skills/nested/tool  12K installs\x1b[0m\n"
            "owner/repo@skills/nested/tool  12K installs\n"
            "other/repo\n"
            "https://skills.sh/owner/repo\n"
            "└ leftover\n"
        )
        stderr = "noise"

    monkeypatch.setattr(discover_mod.subprocess, "run", lambda *a, **k: Proc())
    found = discover_mod.discover_ecosystem_skills("calendar")
    assert found["ok"] is True
    sources = [row["install_source"] for row in found["results"]]
    assert sources == ["owner/repo@skills/nested/tool", "other/repo"]
    assert found["results"][0]["name"] == "tool"
    assert found["results"][1]["name"] == "repo"

    class Empty:
        returncode = 3
        stdout = "no matches here\n"
        stderr = ""

    monkeypatch.setattr(discover_mod.subprocess, "run", lambda *a, **k: Empty())
    none = discover_mod.discover_ecosystem_skills("zzz")
    assert none["results"] == []
    assert "exit 3" in none["summary"]


def test_tier_rank_uses_directory_parents(monkeypatch, tmp_path):
    global_dir = tmp_path / "global"
    npx_dir = tmp_path / "npx"
    global_dir.mkdir()
    npx_dir.mkdir()
    monkeypatch.setattr(discover_mod._skills, "GLOBAL_SKILLS_DIR", global_dir)
    monkeypatch.setattr(discover_mod._skills, "NPX_SKILLS_DIR", npx_dir)
    skill_md = global_dir / "fold" / "SKILL.md"
    skill_md.parent.mkdir()
    skill_md.write_text("---\nname: fold\n---\n", encoding="utf-8")
    info = SkillInfo(name="fold", source="bundled", path=skill_md)
    assert discover_mod._skill_source_tier_rank(info) == 4
    npx_md = npx_dir / "cal" / "SKILL.md"
    npx_md.parent.mkdir()
    npx_md.write_text("---\nname: cal\n---\n", encoding="utf-8")
    assert discover_mod._skill_source_tier_rank(SkillInfo(name="cal", source="bundled", path=npx_md)) == 3


# ─── config mutation ────────────────────────────────────────────────────────


def test_config_set_profiles_coercion_and_keys():
    cfg = Config(data={})
    with pytest.raises(ValueError, match="Invalid agent.profile"):
        cfg.set("agent.profile", "nope")
    cfg.set("agent.profile", "research")
    assert cfg.get("agent.profile") == "research"
    assert cfg.get("agent.quality_gate_strict") is False

    active = cfg.get("llm.openai_active_profile")
    cfg.set("llm.openai_active_profile", active)
    cfg.set("llm.openai_default_profile", active)
    with pytest.raises(ValueError, match="Unknown OpenAI profile"):
        cfg.set("llm.openai_active_profile", "missing-profile")

    profiles = cfg.get("llm.openai_profiles")
    cfg.set("llm.openai_profiles", json.dumps(profiles))
    assert isinstance(cfg.get("llm.openai_profiles"), dict)
    with pytest.raises(ValueError, match="valid JSON"):
        cfg.set("llm.openai_profiles", "{")
    with pytest.raises(ValueError, match="JSON object"):
        cfg.set("llm.openai_profiles", [])
    with pytest.raises(ValueError, match="JSON object"):
        cfg.set("llm.openai_profiles", "  ")

    cfg.set("llm.reasoning_fast", "yes")
    assert cfg.get("llm.reasoning_fast") is True
    cfg.set("llm.reasoning_fast", 0)
    assert cfg.get("llm.reasoning_fast") is False
    cfg.set("sandbox.cpu_cores", "1.5")
    assert cfg.get("sandbox.cpu_cores") == 1.5
    cfg.set("agent.max_iterations", "4")
    assert cfg.get("agent.max_iterations") == 4

    cfg.set("llm.anthropic_api_key", "  sk-ant-test  ")
    assert cfg.get("llm.anthropic_api_key") == "sk-ant-test"
    cfg.set("llm.openai_base_url", "https://example.com/v1/")
    # Active cloud profile projects the legacy base URL back to empty.
    assert cfg.get("llm.openai_base_url") is None
    cfg.set("llm.openai_compatible_backend", "ollama")
    assert cfg.get("llm.openai_compatible_backend") is None
    cfg.set("llm.openai_compatible_api_key", "sk-local")
    assert cfg._data["llm.openai_compatible_api_key"] == "sk-local"

    cfg.set("llm.openai_api_key", "sk-cloud-key")
    cloud = cfg.get("llm.openai_profiles")["openai_cloud"]
    assert cloud["api_key"] == "sk-cloud-key"
    cfg.set("ui.custom_note", "hello")
    assert cfg.get("ui.custom_note") == "hello"


def test_config_set_rejects_flagged_api_key(monkeypatch):
    monkeypatch.setattr(Config, "validate_llm_api_key", classmethod(lambda cls, *a, **k: "bad key"))
    cfg = Config(data={})
    with pytest.raises(ValueError, match="bad key"):
        cfg.set("llm.openai_api_key", "sk-test")


def test_config_unset_profiles_and_keys():
    cfg = Config(data={})
    cfg.set("llm.openai_api_key", "sk-cloud-key")
    cfg.set("llm.openai_base_url", "https://example.com/v1")
    cfg.set("llm.openai_compatible_backend", "ollama")
    cfg.set("ui.custom_note", "hello")

    cfg.unset("llm.openai_profiles")
    assert "openai_cloud" in cfg.get("llm.openai_profiles")

    cfg.unset("llm.openai_active_profile")
    assert cfg.get("llm.openai_active_profile")

    cfg.unset("llm.openai_base_url")
    assert cfg.get("llm.openai_base_url") is None
    cfg.unset("llm.openai_compatible_api_key")
    assert cfg.get("llm.openai_compatible_api_key") is None

    cfg.set("llm.openai_api_key", "sk-cloud-key")
    cfg.unset("llm.openai_api_key")
    cloud = cfg.get("llm.openai_profiles")["openai_cloud"]
    assert cloud.get("api_key") in {None, ""}
    assert "llm.openai_api_key" in cfg._unset_keys

    cfg.unset("ui.custom_note")
    assert "ui.custom_note" not in cfg._data
    assert "ui.custom_note" in cfg._unset_keys
    cfg.unset("ui.custom_note")


# ─── file ops ───────────────────────────────────────────────────────────────


def test_move_and_copy_edges(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "a.txt"
    src.write_text("hello", encoding="utf-8")
    denied = move_file(source_path="/etc/passwd", dest_path="b.txt")
    assert denied["error"] == "path_not_allowed"
    denied_dst = move_file(source_path="a.txt", dest_path="/etc/passwd")
    assert denied_dst["error"] == "path_not_allowed"

    secret = tmp_path / ".env"
    secret.write_text("k=v", encoding="utf-8")
    assert move_file(source_path=".env", dest_path="safe.txt")["error"] == "path_protected"
    assert copy_file(source_path="a.txt", dest_path=".env")["error"] == "path_protected"

    assert move_file(source_path="missing.txt", dest_path="b.txt")["error"] == "file_not_found"
    (tmp_path / "dirsrc").mkdir()
    assert move_file(source_path="dirsrc", dest_path="b.txt")["error"] == "is_directory"
    (tmp_path / "exists.txt").write_text("x", encoding="utf-8")
    assert move_file(source_path="a.txt", dest_path="exists.txt")["error"] == "file_exists"
    (tmp_path / "destdir").mkdir()
    assert move_file(source_path="a.txt", dest_path="destdir", overwrite=True)["error"] == "is_directory"

    def fail_replace(self, target):
        raise OSError("busy")

    monkeypatch.setattr(Path, "replace", fail_replace)
    assert "busy" in move_file(source_path="a.txt", dest_path="moved.txt")["error"]
    monkeypatch.undo()
    monkeypatch.chdir(tmp_path)

    moved = move_file(source_path="a.txt", dest_path="nested/moved.txt", overwrite=True)
    assert "error" not in moved
    assert (tmp_path / "nested" / "moved.txt").read_text(encoding="utf-8") == "hello"

    copy_src = tmp_path / "nested" / "moved.txt"
    assert copy_file(source_path="/etc/passwd", dest_path="c.txt")["error"] == "path_not_allowed"
    assert copy_file(source_path=str(copy_src), dest_path="/etc/passwd")["error"] == "path_not_allowed"
    assert copy_file(source_path="nope.txt", dest_path="c.txt")["error"] == "file_not_found"
    assert copy_file(source_path="dirsrc", dest_path="c.txt")["error"] == "is_directory"
    (tmp_path / "c.txt").write_text("old", encoding="utf-8")
    assert copy_file(source_path=str(copy_src), dest_path="c.txt")["error"] == "file_exists"
    assert copy_file(source_path=str(copy_src), dest_path="destdir", overwrite=True)["error"] == "is_directory"

    def fail_copy(*args, **kwargs):
        raise OSError("copy failed")

    monkeypatch.setattr("tools.files_ops.shutil.copy2", fail_copy)
    assert "copy failed" in copy_file(source_path=str(copy_src), dest_path="d.txt")["error"]
    monkeypatch.undo()
    monkeypatch.chdir(tmp_path)
    copied = copy_file(source_path=str(copy_src), dest_path="c.txt", overwrite=True)
    assert copied["destination"].endswith("c.txt")
    assert Path(copied["destination"]).read_text(encoding="utf-8") == "hello"


def test_create_directory_edges(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert create_directory(path="/etc/nope")["error"] == "path_not_allowed"
    assert create_directory(path=".env")["error"] == "path_protected"
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    assert create_directory(path="file.txt")["error"] == "is_file"
    ready = create_directory(path="reports")
    assert "error" not in ready
    again = create_directory(path="reports", exist_ok=True)
    assert "error" not in again
    assert create_directory(path="reports", exist_ok=False)["error"] == "file_exists"

    def fail_mkdir(self, parents=False, exist_ok=False):
        raise OSError("denied")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)
    assert "denied" in create_directory(path="other")["error"]


def test_extract_archive_edges(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert extract_archive("missing.zip")["error"] == "file_not_found"

    capsule = tmp_path / "capsule"
    capsule.mkdir()
    archive = capsule / "remote.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("keep.txt", "ok")
        zf.writestr("skip.log", "no")

    class _Session:
        def __init__(self, extra):
            self.config = self
            self._extra = extra

        def get(self, key, default=None):
            if key == "sandbox.extra_read_dirs":
                return self._extra
            return default

    found = extract_archive("remote.zip", destination="from-extra", _session=_Session(f"/tmp/missing,{capsule}"))
    assert found["extracted_count"] == 2

    inside = extract_archive(str(archive), destination=str(tmp_path / "inside"))
    assert "inside" in inside["destination"]
    outside = extract_archive(str(archive), destination=str(tmp_path.parent / "outside-extract"))
    assert Path(outside["destination"]).resolve() == tmp_path.resolve()

    real_mkdir = Path.mkdir

    def mkdir(self, parents=False, exist_ok=False):
        if self.resolve() != tmp_path.resolve():
            raise PermissionError("denied")
        return real_mkdir(self, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    fallback = extract_archive(str(archive), destination="blocked")
    assert Path(fallback["destination"]).resolve() == tmp_path.resolve()
    monkeypatch.undo()
    monkeypatch.chdir(tmp_path)

    patterned = extract_archive(str(archive), destination="pat", pattern="*.txt")
    assert patterned["extracted_count"] == 1
    assert "pattern" in patterned["summary"]

    tar_path = tmp_path / "bundle.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        for name, data in (("keep.txt", b"a"), ("skip.log", b"b")):
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    tar_result = extract_archive(str(tar_path), destination="tarpat", pattern="*.txt")
    assert tar_result["extracted_count"] == 1

    bz = tmp_path / "bundle.tar.bz2"
    with tarfile.open(bz, "w:bz2") as tf:
        info = tarfile.TarInfo(name="one.txt")
        payload = b"z"
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))
    assert extract_archive(str(bz), destination="bz")["extracted_count"] == 1

    (tmp_path / "file.rar").write_bytes(b"nope")
    assert extract_archive("file.rar")["error"] == "unsupported_format"
    (tmp_path / "bad.zip").write_bytes(b"not a zip")
    assert "error" in extract_archive("bad.zip")
    (tmp_path / "bad.tar").write_bytes(b"not a tar")
    assert "error" in extract_archive("bad.tar")


# ─── target druggability ────────────────────────────────────────────────────


def _uniprot_entry(
    *,
    keywords: list[str] | None = None,
    domains: list[str] | None = None,
    locations: list[str] | None = None,
    xrefs: list[dict] | None = None,
    features: list[dict] | None = None,
    protein_name: str | None = "Example protein",
):
    feats = features
    if feats is None:
        feats = [{"type": "Domain", "description": name} for name in (domains or [])]
    comments = [{"commentType": "FUNCTION", "text": "ignored"}]
    locs = [{"location": {"value": ""}}]
    locs += [{"location": {"value": loc}} for loc in (locations or [])]
    comments.append({"commentType": "SUBCELLULAR LOCATION", "subcellularLocations": locs})
    entry = {
        "primaryAccession": "P00001",
        "keywords": [{"name": name} for name in (keywords or [])],
        "features": feats,
        "comments": comments,
        "uniProtKBCrossReferences": xrefs or [],
    }
    if protein_name is not None:
        entry["proteinDescription"] = {
            "recommendedName": {"fullName": {"value": protein_name}}
        }
    return {"results": [entry]}


def _patch_uniprot(monkeypatch, payload=None, *, status=200, error=None, bad_json=False):
    class Resp:
        status_code = status

        def json(self):
            if bad_json:
                raise ValueError("bad json")
            return payload

    monkeypatch.setattr(
        "tools.target_druggability.request",
        lambda *a, **k: (None, error) if error else (Resp(), None),
    )


def test_druggability_transport_errors(monkeypatch):
    _patch_uniprot(monkeypatch, error="timeout")
    err = druggability(gene="BRAF")
    assert "timeout" in err["error"]

    _patch_uniprot(monkeypatch, status=503)
    http = druggability(gene="BRAF")
    assert "HTTP 503" in http["error"]

    _patch_uniprot(monkeypatch, bad_json=True)
    bad = druggability(gene="BRAF")
    assert "Invalid UniProt" in bad["error"]

    _patch_uniprot(monkeypatch, payload={"results": []})
    missing = druggability(gene="NOGENE")
    assert "No UniProt entry found" in missing["error"]


@pytest.mark.parametrize(
    ("keyword", "protein_class"),
    [
        ("protein kinase", "kinase"),
        ("gpcr", "GPCR"),
        ("ion channel", "ion_channel"),
        ("nuclear receptor", "nuclear_receptor"),
        ("protease", "protease"),
        ("phosphatase", "phosphatase"),
        ("transferase", "transferase"),
        ("transcription factor", "transcription_factor"),
        ("scaffold", "scaffold_adaptor"),
    ],
)
def test_druggability_protein_classes(monkeypatch, keyword, protein_class):
    _patch_uniprot(monkeypatch, _uniprot_entry(keywords=[keyword]))
    result = druggability(gene="GENE1")
    assert result["protein_class"] == protein_class
    assert result["score_breakdown"]["protein_class"] > 0


def test_druggability_scores_classifications(monkeypatch):
    xrefs = [{"database": "ChEMBL", "id": f"CHEMBL{i}"} for i in range(4)]
    xrefs += [{"database": "PDB", "id": f"{i:04d}"} for i in range(25)]
    xrefs.append({"database": "Pfam", "id": "PF0001"})
    features = [
        {"type": "Domain", "description": "Protein kinase"},
        {"type": "Transmembrane", "description": "Helical"},
    ]
    _patch_uniprot(
        monkeypatch,
        _uniprot_entry(
            keywords=["kinase"],
            locations=["Cell membrane"],
            xrefs=xrefs,
            features=features,
            protein_name=None,
        ),
    )
    high = druggability(gene="BRAF")
    assert high["classification"] == "highly druggable"
    assert high["protein_name"] == "BRAF"
    assert high["structural_coverage"]["pdb_count"] == 25
    assert len(high["structural_coverage"]["pdb_ids"]) == 20
    assert high["score_breakdown"]["known_ligands"] == 0.25
    assert high["score_breakdown"]["structural_data"] == 0.15
    assert high["transmembrane_regions"] == 1
    assert high["surface_accessible"] is True
    assert "ChEMBL" in high["reasoning"]
    assert "PDB" in high["reasoning"]
    assert "Surface-accessible" in high["reasoning"]

    _patch_uniprot(monkeypatch, _uniprot_entry(keywords=["protease"]))
    mid = druggability(gene="PROT")
    assert mid["classification"] == "druggable" or mid["druggability_score"] >= 0.15

    _patch_uniprot(monkeypatch, _uniprot_entry(keywords=["phosphatase"], locations=["Secreted"]))
    challenging = druggability(gene="PHOS")
    assert challenging["classification"] in {"druggable", "challenging"}

    _patch_uniprot(monkeypatch, _uniprot_entry(keywords=["other-thing"]))
    low = druggability(gene="UNK")
    assert low["protein_class"] == "other"
    assert "limited druggability" in low["reasoning"]
    assert "No ChEMBL" in low["reasoning"]
    assert "No PDB" in low["reasoning"]
    assert low["classification"] == "undruggable (with current modalities)"
