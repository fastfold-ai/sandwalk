"""Branch coverage for agent.skills.releases without calling GitHub."""

from __future__ import annotations

import json
import sys
import types
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from agent import skills as skills_mod
from agent.skills import SkillInfo
from agent.skills import releases as rel


class _Resp:
    def __init__(self, status=200, payload=None, content=b"", raise_exc=None, json_exc=None):
        self.status_code = status
        self.content = content
        self._payload = payload
        self._raise_exc = raise_exc
        self._json_exc = json_exc

    def raise_for_status(self):
        if self._raise_exc is not None:
            raise self._raise_exc
        if self.status_code >= 400:
            raise httpx.HTTPError(f"status {self.status_code}")

    def json(self):
        if self._json_exc is not None:
            raise self._json_exc
        return self._payload


def _patch_client(monkeypatch, responder):
    class _Client:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None, params=None):
            return responder(url, headers, params)

    monkeypatch.setattr(httpx, "Client", _Client)
    return _Client


def _raise_timeout(url, headers, params):
    raise TimeoutError("slow")


def _raise_value(url, headers, params):
    return _Resp(json_exc=ValueError("bad json"))


def _raise_runtime(url, headers, params):
    raise RuntimeError("boom")


def _raise_http(url, headers, params):
    raise httpx.HTTPError("down")


@pytest.fixture(autouse=True)
def _isolate_update_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_mod, "SKILLS_UPDATE_CACHE", tmp_path / "skills_update_check.json")


def _cache_path():
    return skills_mod.SKILLS_UPDATE_CACHE


def _write_cache(payload: dict) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_cache() -> dict:
    return json.loads(_cache_path().read_text(encoding="utf-8"))


def test_owner_repo_from_source_urls_and_shorthand():
    assert rel._owner_repo_from_source(None) is None
    assert rel._owner_repo_from_source("   ") is None
    assert rel._owner_repo_from_source("https://gitlab.com/acme/widgets") is None
    assert rel._owner_repo_from_source("https://github.com/") is None
    assert rel._owner_repo_from_source("https://github.com/acme/widgets.git") == "acme/widgets"
    assert rel._owner_repo_from_source("http://github.com/acme/widgets/") == "acme/widgets"
    assert rel._owner_repo_from_source("git@github.com:acme/widgets.git") == "acme/widgets"
    assert rel._owner_repo_from_source("  acme/widgets@skills/fold  ") == "acme/widgets"
    assert rel._owner_repo_from_source("not a source") is None


def test_tag_helpers():
    assert rel._tag_tuple("") is None
    assert rel._tag_tuple(None) is None
    assert rel._tag_tuple("release-v1.2.3-beta") == (1, 2, 3)
    assert rel._is_newer_tag("v1.2.4", "1.2.3") is True
    assert rel._is_newer_tag("v1.2.3", "v1.2.3") is False
    assert rel._is_newer_tag("1.0.0", "v1.0.1") is False
    assert rel._is_newer_tag("nope", "v1.0.0") is False


def test_http_get_bytes_merges_headers(monkeypatch):
    seen = {}

    def responder(url, headers, params):
        seen["url"] = url
        seen["headers"] = headers
        seen["params"] = params
        return _Resp(content=b"zip-bytes")

    client_cls = _patch_client(monkeypatch, responder)
    out = rel._http_get_bytes(
        "https://example.com/a.zip",
        timeout=3.5,
        headers={"Accept": "application/zip", "User-Agent": "custom"},
    )
    assert out == b"zip-bytes"
    assert seen["url"] == "https://example.com/a.zip"
    assert seen["headers"]["Accept"] == "application/zip"
    assert seen["headers"]["User-Agent"] == "custom"
    client = client_cls(timeout=3.5, follow_redirects=True)
    assert client.kwargs["timeout"] == 3.5
    assert client.kwargs["follow_redirects"] is True


def test_fetch_latest_release_404_and_payload_edges(monkeypatch):
    def responder(url, headers, params):
        assert url.endswith("/repos/acme/widgets/releases/latest")
        assert headers["User-Agent"] == "fastfold-agent-cli"
        return _Resp(status=404, payload={"tag_name": "v9"})

    _patch_client(monkeypatch, responder)
    assert rel.fetch_latest_release("acme/widgets", timeout_s=0.2) is None

    def blank_tag(url, headers, params):
        return _Resp(payload={"tag_name": "   ", "published_at": "2026-01-01T00:00:00Z"})

    _patch_client(monkeypatch, blank_tag)
    assert rel.fetch_latest_release("acme/widgets") is None

    def non_str_target(url, headers, params):
        return _Resp(
            payload={
                "tag_name": "v1.0.0",
                "published_at": None,
                "target_commitish": 12345,
            }
        )

    _patch_client(monkeypatch, non_str_target)
    out = rel.fetch_latest_release("acme/widgets")
    assert out["tag"] == "v1.0.0"
    assert out["published_at"] == ""
    assert out["commit"] == ""

    def short_and_padded(url, headers, params):
        return _Resp(
            payload={
                "tag_name": "v2",
                "target_commitish": "  ABCDEF1  ",
            }
        )

    _patch_client(monkeypatch, short_and_padded)
    out = rel.fetch_latest_release("acme/widgets")
    assert out["commit"] == "abcdef1"

    def too_short(url, headers, params):
        return _Resp(payload={"tag_name": "v2", "target_commitish": "abc"})

    _patch_client(monkeypatch, too_short)
    assert rel.fetch_latest_release("acme/widgets")["commit"] == ""

    def not_a_dict(url, headers, params):
        return _Resp(payload=["v1"])

    _patch_client(monkeypatch, not_a_dict)
    assert rel.fetch_latest_release("acme/widgets") is None


def test_fetch_latest_release_error_branches(monkeypatch):
    _patch_client(monkeypatch, _raise_http)
    assert rel.fetch_latest_release("acme/widgets") is None
    _patch_client(monkeypatch, _raise_timeout)
    assert rel.fetch_latest_release("acme/widgets") is None
    _patch_client(monkeypatch, _raise_value)
    assert rel.fetch_latest_release("acme/widgets") is None
    _patch_client(monkeypatch, _raise_runtime)
    assert rel.fetch_latest_release("acme/widgets") is None

    def status_error(url, headers, params):
        return _Resp(status=500, payload={})

    _patch_client(monkeypatch, status_error)
    assert rel.fetch_latest_release("acme/widgets") is None

    class _CtorBoom:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("ctor")

    monkeypatch.setattr(httpx, "Client", _CtorBoom)
    assert rel.fetch_latest_release("acme/widgets") is None
    assert rel.fetch_latest_release("") is None


def test_fetch_repo_head_sha_success_and_defaults(monkeypatch):
    def responder(url, headers, params):
        if url.endswith("/repos/acme/widgets"):
            return _Resp(payload={"default_branch": "develop"})
        if url.endswith("/commits/develop"):
            return _Resp(payload={"sha": "  ABCDEF1234567890  "})
        raise AssertionError(url)

    _patch_client(monkeypatch, responder)
    out = rel.fetch_repo_head_sha("acme/widgets", timeout_s=0.3)
    assert out == {"sha": "abcdef1234567890", "default_branch": "develop"}

    def missing_branch(url, headers, params):
        if url.endswith("/repos/acme/widgets"):
            return _Resp(payload={})
        return _Resp(payload={"sha": "abc1234"})

    _patch_client(monkeypatch, missing_branch)
    out = rel.fetch_repo_head_sha("acme/widgets")
    assert out["default_branch"] == "main"
    assert out["sha"] == "abc1234"

    def blank_branch(url, headers, params):
        if "/commits/" in url:
            assert url.endswith("/commits/main")
            return _Resp(payload={"sha": "deadbeef"})
        return _Resp(payload={"default_branch": "   "})

    _patch_client(monkeypatch, blank_branch)
    assert rel.fetch_repo_head_sha("acme/widgets")["default_branch"] == "main"

    def null_body(url, headers, params):
        if "/commits/" in url:
            return _Resp(payload=None)
        return _Resp(payload=None)

    _patch_client(monkeypatch, null_body)
    assert rel.fetch_repo_head_sha("acme/widgets") is None


def test_fetch_repo_head_sha_errors(monkeypatch):
    assert rel.fetch_repo_head_sha("") is None

    def missing_repo(url, headers, params):
        return _Resp(status=404)

    _patch_client(monkeypatch, missing_repo)
    assert rel.fetch_repo_head_sha("acme/missing") is None

    def missing_commit(url, headers, params):
        if "/commits/" in url:
            return _Resp(status=404)
        return _Resp(payload={"default_branch": "main"})

    _patch_client(monkeypatch, missing_commit)
    assert rel.fetch_repo_head_sha("acme/widgets") is None

    def bad_status(url, headers, params):
        return _Resp(status=500)

    _patch_client(monkeypatch, bad_status)
    assert rel.fetch_repo_head_sha("acme/widgets") is None

    def weird_body(url, headers, params):
        return _Resp(payload=5)

    _patch_client(monkeypatch, weird_body)
    assert rel.fetch_repo_head_sha("acme/widgets") is None

    def empty_sha(url, headers, params):
        if "/commits/" in url:
            return _Resp(payload={"sha": "   "})
        return _Resp(payload={"default_branch": "main"})

    _patch_client(monkeypatch, empty_sha)
    assert rel.fetch_repo_head_sha("acme/widgets") is None

    _patch_client(monkeypatch, _raise_http)
    assert rel.fetch_repo_head_sha("acme/widgets") is None
    _patch_client(monkeypatch, _raise_timeout)
    assert rel.fetch_repo_head_sha("acme/widgets") is None
    _patch_client(monkeypatch, _raise_value)
    assert rel.fetch_repo_head_sha("acme/widgets") is None
    _patch_client(monkeypatch, _raise_runtime)
    assert rel.fetch_repo_head_sha("acme/widgets") is None


def test_fetch_path_latest_commit_success_and_fallbacks(monkeypatch):
    assert rel.fetch_path_latest_commit("", "skills/fold") is None
    assert rel.fetch_path_latest_commit("acme/widgets", "///") is None

    seen = {}

    def author_date(url, headers, params):
        seen["params"] = params
        assert url.endswith("/repos/acme/widgets/commits")
        return _Resp(
            payload=[
                {
                    "sha": "ABCD",
                    "commit": {
                        "author": {"date": "2026-04-01T00:00:00Z"},
                        "committer": {"date": "2026-05-01T00:00:00Z"},
                    },
                }
            ]
        )

    _patch_client(monkeypatch, author_date)
    out = rel.fetch_path_latest_commit(" /acme/widgets/ ", " /skills/fold/ ")
    assert out == {"sha": "abcd", "committed_at": "2026-04-01T00:00:00Z"}
    assert seen["params"] == {"path": "skills/fold", "per_page": 1}

    def committer_only(url, headers, params):
        return _Resp(
            payload=[
                {
                    "sha": "",
                    "commit": {
                        "author": {"date": "   "},
                        "committer": {"date": "2026-05-02T00:00:00Z"},
                    },
                }
            ]
        )

    _patch_client(monkeypatch, committer_only)
    out = rel.fetch_path_latest_commit("acme/widgets", "skills/fold")
    assert out == {"sha": "", "committed_at": "2026-05-02T00:00:00Z"}

    def committer_when_author_missing(url, headers, params):
        return _Resp(
            payload=[
                {
                    "sha": "abc",
                    "commit": {"author": "nope", "committer": {"date": "2026-06-01T00:00:00Z"}},
                }
            ]
        )

    _patch_client(monkeypatch, committer_when_author_missing)
    out = rel.fetch_path_latest_commit("acme/widgets", "skills/fold")
    assert out["committed_at"] == "2026-06-01T00:00:00Z"

    def no_dates(url, headers, params):
        return _Resp(payload=[{"sha": "abc", "commit": {"author": {}, "committer": {}}}])

    _patch_client(monkeypatch, no_dates)
    assert rel.fetch_path_latest_commit("acme/widgets", "skills/fold") is None

    def commit_not_dict(url, headers, params):
        return _Resp(payload=[{"sha": "abc", "commit": "nope"}])

    _patch_client(monkeypatch, commit_not_dict)
    assert rel.fetch_path_latest_commit("acme/widgets", "skills/fold") is None


def test_fetch_path_latest_commit_errors(monkeypatch):
    for status in (401, 403, 404):

        def denied(url, headers, params, status=status):
            return _Resp(status=status)

        _patch_client(monkeypatch, denied)
        assert rel.fetch_path_latest_commit("acme/private", "skills/fold") is None

    def server_error(url, headers, params):
        return _Resp(status=500)

    _patch_client(monkeypatch, server_error)
    assert rel.fetch_path_latest_commit("acme/widgets", "skills/fold") is None

    for bad in (None, [], ["not-a-dict"], {"sha": "abc"}):

        def bad_payload(url, headers, params, bad=bad):
            return _Resp(payload=bad)

        _patch_client(monkeypatch, bad_payload)
        assert rel.fetch_path_latest_commit("acme/widgets", "skills/fold") is None

    _patch_client(monkeypatch, _raise_http)
    assert rel.fetch_path_latest_commit("acme/widgets", "skills/fold") is None
    _patch_client(monkeypatch, _raise_timeout)
    assert rel.fetch_path_latest_commit("acme/widgets", "skills/fold") is None
    _patch_client(monkeypatch, _raise_value)
    assert rel.fetch_path_latest_commit("acme/widgets", "skills/fold") is None
    _patch_client(monkeypatch, _raise_runtime)
    assert rel.fetch_path_latest_commit("acme/widgets", "skills/fold") is None


def test_resolve_bundled_path_commit_cache_hits(monkeypatch):
    calls = []

    def _forbid(owner, path, timeout_s=1.5):
        calls.append(path)
        raise AssertionError("should not fetch")

    monkeypatch.setattr(rel, "fetch_path_latest_commit", _forbid)
    now = datetime.now(UTC).isoformat()
    path = f"{skills_mod.BUNDLED_SKILLS_REPO_PATH}/fold"
    _write_cache(
        {
            "bundled_paths": {
                path: {
                    "checked_at": now,
                    "unavailable": True,
                    "sha": "",
                    "committed_at": "",
                }
            }
        }
    )
    assert rel.resolve_bundled_path_commit("fold") is None
    assert calls == []

    _write_cache(
        {
            "bundled_paths": {
                path: {
                    "checked_at": now,
                    "sha": "abc",
                    "committed_at": "2026-01-01T00:00:00Z",
                    "unavailable": False,
                }
            }
        }
    )
    assert rel.resolve_bundled_path_commit("/fold/") == {
        "sha": "abc",
        "committed_at": "2026-01-01T00:00:00Z",
    }

    _write_cache(
        {
            "bundled_paths": {
                path: {
                    "checked_at": now,
                    "sha": "abc",
                    "committed_at": "",
                    "unavailable": False,
                }
            }
        }
    )
    assert rel.resolve_bundled_path_commit("fold") is None
    assert rel.resolve_bundled_path_commit("") is None
    assert rel.resolve_bundled_path_commit("   ") is None


def test_resolve_bundled_path_commit_refetches_and_writes(monkeypatch):
    calls = []

    def _fetch(owner, path, timeout_s=1.5):
        calls.append((owner, path, timeout_s))
        if path.endswith("/fresh"):
            return {"sha": "fff", "committed_at": "2026-08-01T00:00:00Z"}
        return None

    monkeypatch.setattr(rel, "fetch_path_latest_commit", _fetch)
    stale = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    path = f"{skills_mod.BUNDLED_SKILLS_REPO_PATH}/fresh"
    _write_cache(
        {
            "bundled_paths": ["not-a-dict"],
            "other": 1,
        }
    )
    # Replace with a stale entry plus a non-dict entry via a second write after
    # proving a non-dict map still fetches.
    out = rel.resolve_bundled_path_commit("fresh", timeout_s=0.4)
    assert out == {"sha": "fff", "committed_at": "2026-08-01T00:00:00Z"}
    assert calls[-1][0] == skills_mod.BUNDLED_SKILLS_GITHUB_REPO
    assert calls[-1][1] == path
    assert calls[-1][2] == 0.4
    saved = _read_cache()
    assert saved["other"] == 1
    assert saved["bundled_paths"][path]["unavailable"] is False
    assert saved["bundled_paths"][path]["sha"] == "fff"

    now = datetime.now(UTC).isoformat()
    _write_cache(
        {
            "bundled_paths": {
                path: {
                    "checked_at": now,
                    "unavailable": True,
                }
            }
        }
    )
    forced = rel.resolve_bundled_path_commit("fresh", force=True)
    assert forced["sha"] == "fff"

    _write_cache({"bundled_paths": {path: "not-a-dict"}})
    assert rel.resolve_bundled_path_commit("missing") is None
    missing = f"{skills_mod.BUNDLED_SKILLS_REPO_PATH}/missing"
    assert _read_cache()["bundled_paths"][missing]["unavailable"] is True

    _write_cache(
        {
            "bundled_paths": {
                f"{skills_mod.BUNDLED_SKILLS_REPO_PATH}/bad": {
                    "checked_at": "not-a-date",
                    "committed_at": "2020-01-01T00:00:00Z",
                }
            }
        }
    )
    assert rel.resolve_bundled_path_commit("bad") is None

    naive = f"{skills_mod.BUNDLED_SKILLS_REPO_PATH}/naive"
    _write_cache(
        {
            "bundled_paths": {
                naive: {
                    "checked_at": "2026-01-01T00:00:00",
                    "committed_at": "2020-01-01T00:00:00Z",
                    "sha": "old",
                }
            }
        }
    )
    assert rel.resolve_bundled_path_commit("naive") is None


def test_package_version_and_file_mtime(monkeypatch, tmp_path):
    real = rel.package_version()
    assert real

    mod = types.ModuleType("_version")
    mod.__version__ = "  9.8.7  "
    monkeypatch.setitem(sys.modules, "_version", mod)
    assert rel.package_version() == "9.8.7"

    mod.__version__ = ""
    assert rel.package_version() == "0.0.1"
    mod.__version__ = None
    assert rel.package_version() == "0.0.1"

    broken = types.ModuleType("_version")
    monkeypatch.setitem(sys.modules, "_version", broken)
    assert rel.package_version() == "0.0.1"

    monkeypatch.setitem(sys.modules, "_version", None)
    assert rel.package_version() == "0.0.1"

    skill = tmp_path / "SKILL.md"
    skill.write_text("hello", encoding="utf-8")
    stamp = rel.file_mtime_iso(skill)
    parsed = datetime.fromisoformat(stamp)
    assert parsed.tzinfo is not None
    assert rel.file_mtime_iso(tmp_path / "missing.md") == ""


def test_enrich_bundled_skill_branches(monkeypatch, tmp_path):
    skipped = SkillInfo(name="other", source="global", version=None)
    rel.enrich_bundled_skill(skipped)
    assert skipped.version is None

    def _version():
        return "4.5.6"

    monkeypatch.setattr(rel, "package_version", _version)
    early = SkillInfo(name="early", source="bundled", updated_at="2020-01-01", path=None)
    rel.enrich_bundled_skill(early)
    assert early.version == "4.5.6"
    assert early.updated_at == "2020-01-01"

    calls = []

    def _remote(name, force=False, timeout_s=1.5):
        calls.append(name)
        return {"sha": "deadbeef", "committed_at": "2026-07-01T00:00:00Z"}

    monkeypatch.setattr(rel, "resolve_bundled_path_commit", _remote)
    skill_md = tmp_path / "fold" / "SKILL.md"
    skill_md.parent.mkdir()
    skill_md.write_text("# fold\n", encoding="utf-8")
    kept = SkillInfo(name="fold", source="bundled", version="1.0.0", path=skill_md, commit="keep")
    rel.enrich_bundled_skill(kept)
    assert kept.updated_at == "2026-07-01T00:00:00Z"
    assert kept.commit == "keep"

    filled = SkillInfo(name="fold", source="bundled", version="1.0.0", path=skill_md)
    rel.enrich_bundled_skill(filled)
    assert filled.commit == "deadbeef"
    assert calls == ["fold", "fold"]

    def _remote_blank_sha(name, force=False, timeout_s=1.5):
        return {"sha": "   ", "committed_at": "2026-07-02T00:00:00Z"}

    monkeypatch.setattr(rel, "resolve_bundled_path_commit", _remote_blank_sha)
    blank = SkillInfo(name="fold", source="bundled", version="1.0.0", path=skill_md)
    rel.enrich_bundled_skill(blank)
    assert blank.updated_at == "2026-07-02T00:00:00Z"
    assert blank.commit is None

    broken = SkillInfo(name="x", source="bundled", version="1", path=object())
    with pytest.raises(TypeError):
        rel.enrich_bundled_skill(broken)

    def _no_remote(name, force=False, timeout_s=1.5):
        return None

    monkeypatch.setattr(rel, "resolve_bundled_path_commit", _no_remote)
    local = SkillInfo(name="fold", source="bundled", version="1", path=skill_md)
    rel.enrich_bundled_skill(local)
    assert local.updated_at

    no_path = SkillInfo(name="np", source="bundled", version="1", path=None)
    rel.enrich_bundled_skill(no_path)
    assert no_path.updated_at == ""


def test_resolve_repo_remote_state_cache_and_catalog(monkeypatch):
    calls = {"release": 0, "head": 0}

    def _release(owner, timeout_s=2.5):
        calls["release"] += 1
        return {
            "tag": "v3.1.0",
            "published_at": "2026-09-01T00:00:00Z",
            "commit": "abc1234",
        }

    def _head(owner, timeout_s=2.5):
        calls["head"] += 1
        return {"sha": "fff", "default_branch": "main"}

    monkeypatch.setattr(rel, "fetch_latest_release", _release)
    monkeypatch.setattr(rel, "fetch_repo_head_sha", _head)

    assert rel.resolve_repo_remote_state("  ") == {}
    assert calls == {"release": 0, "head": 0}

    fresh = rel.resolve_repo_remote_state("fastfold-ai/skills", timeout_s=0.2)
    assert fresh["release_tag"] == "v3.1.0"
    assert fresh["release_commit"] == "abc1234"
    assert fresh["head_sha"] == "fff"
    saved = _read_cache()
    assert saved["latest_release"] == "v3.1.0"
    assert saved["latest_published_at"] == "2026-09-01T00:00:00Z"
    assert saved["checked_at"] == fresh["checked_at"]

    again = rel.resolve_repo_remote_state("fastfold-ai/skills")
    assert again["release_tag"] == "v3.1.0"
    assert calls == {"release": 1, "head": 1}

    other = rel.resolve_repo_remote_state("acme/widgets")
    assert other["default_branch"] == "main"
    saved = _read_cache()
    assert "acme/widgets" in saved["repos"]
    assert saved["latest_release"] == "v3.1.0"

    def _empty_release(owner, timeout_s=2.5):
        calls["release"] += 1
        return None

    def _empty_head(owner, timeout_s=2.5):
        calls["head"] += 1
        return None

    monkeypatch.setattr(rel, "fetch_latest_release", _empty_release)
    monkeypatch.setattr(rel, "fetch_repo_head_sha", _empty_head)
    forced = rel.resolve_repo_remote_state("acme/widgets", force=True)
    assert forced["release_tag"] == ""
    assert forced["head_sha"] == ""
    assert _read_cache()["latest_release"] == "v3.1.0"

    stale = (datetime.now(UTC) - timedelta(minutes=6)).isoformat()
    _write_cache(
        {
            "repos": {
                "old/repo": {
                    "checked_at": stale,
                    "release_tag": "v0",
                    "head_sha": "old",
                }
            }
        }
    )
    refreshed = rel.resolve_repo_remote_state("old/repo")
    assert refreshed["release_tag"] == ""
    assert refreshed["head_sha"] == ""

    _write_cache({"repos": {"bad/repo": {"checked_at": "not-a-date", "release_tag": "v9"}}})
    assert rel.resolve_repo_remote_state("bad/repo")["release_tag"] == ""

    _write_cache(
        {
            "repos": {
                "naive/repo": {
                    "checked_at": "2026-01-01T00:00:00",
                    "release_tag": "cached",
                }
            }
        }
    )
    assert rel.resolve_repo_remote_state("naive/repo")["release_tag"] == ""

    _write_cache({"repos": ["nope"]})
    assert rel.resolve_repo_remote_state("list/repo")["default_branch"] == ""

    _write_cache({"repos": {"str/repo": "nope"}})
    assert "checked_at" in rel.resolve_repo_remote_state("str/repo")


def test_check_github_skill_update_channels(monkeypatch):
    state = {"remote": {}}

    def _remote(owner, force=False, timeout_s=2.5):
        return state["remote"]

    monkeypatch.setattr(rel, "resolve_repo_remote_state", _remote)

    assert rel.check_github_skill_update("custom:/tmp/skill") is None
    state["remote"] = {}
    assert rel.check_github_skill_update("acme/widgets") is None

    state["remote"] = None
    assert rel.check_github_skill_update("acme/widgets") is None

    state["remote"] = {"release_tag": "v1.2.0", "head_sha": "aaaaaaaa"}
    newer = rel.check_github_skill_update(
        "https://github.com/acme/widgets.git",
        installed_release="v1.1.0",
        installed_commit="bbbbbbbb",
    )
    assert newer["channel"] == "release"
    assert newer["latest"] == "v1.2.0"
    assert newer["owner_repo"] == "acme/widgets"

    state["remote"] = {"release_tag": "rel-1.2.3", "head_sha": "aaaaaaaa"}
    assert (
        rel.check_github_skill_update("acme/widgets", installed_release="v1.2.3") is None
    )

    state["remote"] = {"release_tag": "nightly", "head_sha": "aaaaaaaa"}
    diff = rel.check_github_skill_update("acme/widgets", installed_release="beta")
    assert diff["channel"] == "release"
    assert diff["latest"] == "nightly"
    assert diff["installed"] == "beta"

    state["remote"] = {"release_tag": "v0.1.0", "head_sha": "aaaaaaaa"}
    older = rel.check_github_skill_update("acme/widgets", installed_release="v9.0.0")
    assert older["available"] is True
    assert older["installed"] == "v9.0.0"

    state["remote"] = {"release_tag": "v2.0.0", "head_sha": "aaaaaaaaaaaaaaaa"}
    unknown = rel.check_github_skill_update("git@github.com:acme/widgets.git")
    assert unknown["installed"] == "unknown"
    short = rel.check_github_skill_update(
        "acme/widgets",
        installed_commit="abcdef1234",
    )
    assert short["installed"] == "abcdef1"
    assert short["channel"] == "release"

    state["remote"] = {"release_tag": "", "head_sha": "1234567890abcdef"}
    drifted = rel.check_github_skill_update(
        "http://github.com/acme/widgets/",
        installed_commit="fedcba9876543210",
    )
    assert drifted["channel"] == "commit"
    assert drifted["latest"] == "1234567"
    assert drifted["installed"] == "fedcba9"

    assert (
        rel.check_github_skill_update("acme/widgets", installed_commit="1234567890abcdef")
        is None
    )
    assert rel.check_github_skill_update("acme/widgets", installed_commit="1234567") is None
    assert (
        rel.check_github_skill_update("acme/widgets", installed_commit="1234567890abcdefEXTRA")
        is None
    )
    assert rel.check_github_skill_update("acme/widgets", installed_commit="") is None
    state["remote"] = {"release_tag": "", "head_sha": ""}
    assert rel.check_github_skill_update("acme/widgets", installed_commit="abc") is None


def test_update_cache_read_write_and_installed_release(monkeypatch):
    assert rel._read_update_cache() == {}
    _cache_path().write_text("[]", encoding="utf-8")
    assert rel._read_update_cache() == {}
    _cache_path().write_text("{", encoding="utf-8")
    assert rel._read_update_cache() == {}

    rel._write_update_cache({"latest_release": "v1.2.3", "n": 1})
    assert _read_cache()["latest_release"] == "v1.2.3"

    blocker = _cache_path().parent / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(skills_mod, "SKILLS_UPDATE_CACHE", blocker / "cache.json")
    rel._write_update_cache({"latest_release": "v9"})
    assert not (blocker / "cache.json").exists()

    def _manifest(_dest):
        return {
            "skills": {
                "bad": "nope",
                "empty": {"source": "fastfold-ai/skills@skills/empty", "release": ""},
                "other": {"source": "someone/else", "release": "v9.9.9"},
                "fold": {"source": "fastfold-ai/skills@skills/fold", "release": "v1.4.0"},
            }
        }

    monkeypatch.setattr(skills_mod, "_read_manifest", _manifest)
    assert rel._installed_catalog_release() == "v1.4.0"
    assert rel._installed_catalog_release("someone/else@skills") == "v9.9.9"

    def _no_skills(_dest):
        return {}

    monkeypatch.setattr(skills_mod, "_read_manifest", _no_skills)
    assert rel._installed_catalog_release() is None


def test_get_cached_and_refresh_skills_update(monkeypatch):
    assert rel.get_cached_skills_update() is None

    def _installed(catalog=skills_mod.DEFAULT_CATALOG):
        return {"fastfold-ai/skills": "v1.0.0", "acme/widgets": ""}.get(
            catalog.split("@", 1)[0]
        )

    monkeypatch.setattr(skills_mod, "_installed_catalog_release", _installed)

    _write_cache({"latest_release": "v1.0.0", "latest_published_at": "2026-01-01T00:00:00Z"})
    assert rel.get_cached_skills_update() is None

    _write_cache({"latest_release": "v1.2.0"})
    found = rel.get_cached_skills_update()
    assert found == {"installed": "v1.0.0", "latest": "v1.2.0", "published_at": ""}

    _write_cache({"latest_release": "v2.0.0"})
    assert rel.get_cached_skills_update("acme/widgets") is None

    recent = datetime.now(UTC).isoformat()
    _write_cache({"checked_at": recent, "latest_release": "v1.0.0", "keep": True})

    def _should_not_fetch(owner, timeout_s=2.5):
        raise AssertionError("throttled refresh fetched")

    monkeypatch.setattr(skills_mod, "fetch_latest_release", _should_not_fetch)
    rel.refresh_skills_update_cache(force=False)
    assert _read_cache()["latest_release"] == "v1.0.0"

    seen = {}

    def _fetch(owner, timeout_s=2.5):
        seen["owner"] = owner
        seen["timeout"] = timeout_s
        return None

    monkeypatch.setattr(skills_mod, "fetch_latest_release", _fetch)
    rel.refresh_skills_update_cache(catalog="acme/widgets@skills/fold", timeout_s=0.4, force=True)
    saved = _read_cache()
    assert seen == {"owner": "acme/widgets", "timeout": 0.4}
    assert saved["latest_release"] is None
    assert saved["latest_published_at"] == ""
    assert saved["keep"] is True

    def _fetch_ok(owner, timeout_s=2.5):
        return {"tag": "v8.0.0", "published_at": "2026-10-01T00:00:00Z"}

    monkeypatch.setattr(skills_mod, "fetch_latest_release", _fetch_ok)
    _write_cache({"checked_at": "not-a-date", "keep": 1})
    rel.refresh_skills_update_cache(force=False)
    saved = _read_cache()
    assert saved["latest_release"] == "v8.0.0"
    assert saved["latest_published_at"] == "2026-10-01T00:00:00Z"
    assert saved["keep"] == 1

    naive = "2026-01-01T00:00:00"
    _write_cache({"checked_at": naive})
    rel.refresh_skills_update_cache(force=False)
    assert _read_cache()["latest_release"] == "v8.0.0"
