"""Tests for the native skills management system (ct.agent.skills + tooling)."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent import skills as skills_mod

_REAL_FETCH_LATEST_RELEASE = skills_mod.fetch_latest_release


@pytest.fixture(autouse=True)
def _isolate_npx_dir(monkeypatch, tmp_path_factory):
    """Point the npx install dir at an empty temp dir so tests never touch ~/.fastfold-cli."""
    root = tmp_path_factory.mktemp("npx_root")
    monkeypatch.setattr(skills_mod, "NPX_INSTALL_ROOT", root)
    monkeypatch.setattr(skills_mod, "NPX_SKILLS_DIR", root / ".claude" / "skills")
    # Never hit the network for GitHub release lookups during tests.
    monkeypatch.setattr(skills_mod, "fetch_latest_release", lambda *a, **k: None)
    monkeypatch.setattr(skills_mod, "SKILLS_UPDATE_CACHE", root / "skills_update_check.json")


def _write_skill(base: Path, name: str, description: str = "", tags: str = "") -> Path:
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    fm = [f"name: {name}"]
    if description:
        fm.append(f"description: {description}")
    if tags:
        fm.append(f"tags: [{tags}]")
    (d / "SKILL.md").write_text(
        "---\n" + "\n".join(fm) + "\n---\n\n# " + name + "\n\nbody\n",
        encoding="utf-8",
    )
    return d


# ─── Source detection ──────────────────────────────────────────────────────
def test_detect_source_type_github_url():
    assert skills_mod.detect_source_type("https://github.com/owner/repo") == "github"


def test_detect_source_type_shorthand():
    assert skills_mod.detect_source_type("owner/repo@skills/foo") == "shorthand"


def test_detect_source_type_name():
    assert skills_mod.detect_source_type("fold") == "name"


def test_detect_source_type_local(tmp_path):
    assert skills_mod.detect_source_type(str(tmp_path)) == "local"


# ─── GitHub parsing ────────────────────────────────────────────────────────
def test_parse_github_shorthand_with_subpath():
    url, ref, sub = skills_mod._parse_github("fastfold-ai/skills@skills/fold")
    assert url == "https://github.com/fastfold-ai/skills.git"
    assert ref is None
    assert sub == "skills/fold"


def test_parse_github_tree_url():
    url, ref, sub = skills_mod._parse_github(
        "https://github.com/owner/repo/tree/main/skills/foo"
    )
    assert url == "https://github.com/owner/repo.git"
    assert ref == "main"
    assert sub == "skills/foo"


# ─── Skill dir resolution ──────────────────────────────────────────────────
def test_resolve_skill_dirs_whole_repo_under_skills_folder(tmp_path):
    """A whole-repo clone with skills under skills/<name>/ resolves all skills."""
    repo = tmp_path / "repo"
    (repo / "skills").mkdir(parents=True)
    _write_skill(repo / "skills", "fold", "Fold skill")
    _write_skill(repo / "skills", "boltz", "Boltz skill")
    # Repo root has non-skill files (mimics fastfold-ai/skills layout).
    (repo / "README.md").write_text("readme", encoding="utf-8")

    dirs = skills_mod._resolve_skill_dirs(repo, None)
    names = sorted(d.name for d in dirs)
    assert names == ["boltz", "fold"]


def test_resolve_skill_dirs_single_skill_at_base(tmp_path):
    base = tmp_path / "one"
    _write_skill(base, "solo")
    dirs = skills_mod._resolve_skill_dirs(base / "solo", None)
    assert [d.name for d in dirs] == ["solo"]


def test_resolve_skill_dirs_subpath(tmp_path):
    repo = tmp_path / "repo"
    _write_skill(repo / "skills", "fold")
    dirs = skills_mod._resolve_skill_dirs(repo, "skills/fold")
    assert [d.name for d in dirs] == ["fold"]


def test_resolve_skill_dirs_nested_curated_by_name(tmp_path):
    repo = tmp_path / "repo"
    _write_skill(repo / "skills" / ".curated", "linear")
    dirs = skills_mod._resolve_skill_dirs(repo, "skills/linear")
    assert [d.name for d in dirs] == ["linear"]
    assert dirs[0].parent.name == ".curated"


# ─── Frontmatter parsing ───────────────────────────────────────────────────
def test_parse_skill_md_reads_name_description_tags(tmp_path):
    d = _write_skill(tmp_path, "my-skill", "Does a thing", "a, b")
    info = skills_mod.parse_skill_md(d / "SKILL.md")
    assert info.name == "my-skill"
    assert info.description == "Does a thing"
    assert info.tags == ["a", "b"]


# ─── Display helpers (author/updated/version) ──────────────────────────────
def test_display_version_missing_shows_not_available():
    info = skills_mod.SkillInfo(name="x", version=None)
    assert skills_mod.display_version(info) == "Version not available"


def test_display_version_with_release_tag():
    info = skills_mod.SkillInfo(name="x", version="v1.2.0")
    assert skills_mod.display_version(info) == "v1.2.0"


def test_display_author_and_updated_fallbacks():
    bundled = skills_mod.SkillInfo(name="x", source="bundled")
    assert skills_mod.display_author(bundled) == "fastfold-ai"
    npx = skills_mod.SkillInfo(name="y", source="npx")
    assert skills_mod.display_author(npx) == "-"
    assert skills_mod.display_updated(npx) == "-"
    dated = skills_mod.SkillInfo(name="z", updated_at="2026-06-18T10:00:00+00:00")
    assert skills_mod.display_updated(dated) == "2026-06-18"


def test_derive_author_from_sources():
    assert skills_mod._derive_author("fastfold-ai/skills@skills/fold") == "fastfold-ai"
    assert skills_mod._derive_author("https://github.com/owner/repo/tree/main") == "owner"
    assert skills_mod._derive_author("/local/path") == "local"


def test_scan_dir_enriches_from_manifest(tmp_path):
    base = tmp_path / "global"
    _write_skill(base, "fold", "Fold skill")
    skills_mod._write_manifest(
        base,
        {
            "version": 1,
            "skills": {
                "fold": {
                    "source": "fastfold-ai/skills@skills/fold",
                    "installed_at": "2026-06-18T10:00:00+00:00",
                    "release": "v1.0.0",
                }
            },
        },
    )
    out = skills_mod._scan_dir(base, "global")
    assert out["fold"].author == "fastfold-ai"
    assert out["fold"].version == "v1.0.0"
    assert out["fold"].updated_at.startswith("2026-06-18")


# ─── Update cache (boot notice) ────────────────────────────────────────────
def test_get_cached_skills_update_reports_newer(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path / "global")
    monkeypatch.setattr(skills_mod, "_installed_catalog_release", lambda catalog=skills_mod.DEFAULT_CATALOG: "v1.0.0")
    monkeypatch.setattr(
        skills_mod, "_read_update_cache",
        lambda: {"latest_release": "v1.1.0", "latest_published_at": "2026-06-18T00:00:00Z"},
    )
    res = skills_mod.get_cached_skills_update()
    assert res == {"installed": "v1.0.0", "latest": "v1.1.0", "published_at": "2026-06-18T00:00:00Z"}


def test_get_cached_skills_update_none_when_up_to_date(monkeypatch):
    monkeypatch.setattr(skills_mod, "_installed_catalog_release", lambda catalog=skills_mod.DEFAULT_CATALOG: "v1.1.0")
    monkeypatch.setattr(skills_mod, "_read_update_cache", lambda: {"latest_release": "v1.1.0"})
    assert skills_mod.get_cached_skills_update() is None


def test_get_cached_skills_update_none_without_installed_release(monkeypatch):
    monkeypatch.setattr(skills_mod, "_installed_catalog_release", lambda catalog=skills_mod.DEFAULT_CATALOG: None)
    monkeypatch.setattr(skills_mod, "_read_update_cache", lambda: {"latest_release": "v9.9.9"})
    assert skills_mod.get_cached_skills_update() is None


# ─── Tier override ─────────────────────────────────────────────────────────
def test_iter_skills_global_overrides_bundled(tmp_path, monkeypatch):
    bundled = tmp_path / "bundled"
    global_dir = tmp_path / "global"
    _write_skill(bundled, "shared", "bundled version")
    _write_skill(bundled, "only_bundled", "bundled only")
    _write_skill(global_dir, "shared", "global version")

    monkeypatch.setattr(skills_mod, "BUNDLED_SKILLS_DIR", bundled)
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", global_dir)

    merged = skills_mod.iter_skills(project_root=tmp_path / "noproject")
    assert merged["shared"].source == "global"
    assert merged["shared"].description == "global version"
    assert merged["only_bundled"].source == "bundled"


def test_iter_skills_collapses_underscore_hyphen_duplicates(tmp_path, monkeypatch):
    global_dir = tmp_path / "global"
    npx_dir = tmp_path / "npx"
    # Same frontmatter name, different directory naming across tiers.
    underscored = global_dir / "alphagenome_single_variant_analysis"
    underscored.mkdir(parents=True)
    (underscored / "SKILL.md").write_text(
        "---\nname: alphagenome-single-variant-analysis\n"
        "description: global copy\n---\n\n# Alpha\n",
        encoding="utf-8",
    )
    (global_dir / skills_mod.MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "version": 1,
                "skills": {
                    "alphagenome_single_variant_analysis": {
                        "source": "https://github.com/google-deepmind/science-skills",
                        "release": "v1.0.5",
                        "installed_at": "2026-07-11T00:00:00+00:00",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    hyphenated = npx_dir / "alphagenome-single-variant-analysis"
    hyphenated.mkdir(parents=True)
    (hyphenated / "SKILL.md").write_text(
        "---\nname: alphagenome-single-variant-analysis\n"
        "description: npx copy\n---\n\n# Alpha\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(skills_mod, "BUNDLED_SKILLS_DIR", tmp_path / "bundled")
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", global_dir)
    monkeypatch.setattr(skills_mod, "NPX_SKILLS_DIR", npx_dir)

    merged = skills_mod.iter_skills(project_root=tmp_path / "noproject")
    names = [info.name for info in merged.values()]
    assert names.count("alphagenome-single-variant-analysis") == 1
    winner = next(info for info in merged.values() if info.name == "alphagenome-single-variant-analysis")
    assert winner.version == "v1.0.5"
    assert "global copy" in winner.description


# ─── Install (local) + remove ──────────────────────────────────────────────
def test_install_local_and_remove(tmp_path, monkeypatch):
    src = tmp_path / "src"
    _write_skill(src, "cool-skill", "A cool skill")
    dest = tmp_path / "global"
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", dest)

    result = skills_mod.install_skill(str(src / "cool-skill"))
    assert result["ok"] is True
    assert "cool-skill" in result["installed"]
    assert (dest / "cool-skill" / "SKILL.md").exists()
    assert (dest / skills_mod.MANIFEST_FILENAME).exists()

    removed = skills_mod.remove_skill("cool-skill")
    assert removed["ok"] is True
    assert not (dest / "cool-skill").exists()


def test_install_local_missing_path(tmp_path, monkeypatch):
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path / "global")
    result = skills_mod.install_skill(str(tmp_path / "does-not-exist-skill"))
    assert result["ok"] is False


def test_remove_skill_not_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path / "global")
    result = skills_mod.remove_skill("nope")
    assert result["ok"] is False


# ─── build_skills_prompt ───────────────────────────────────────────────────
def test_build_skills_prompt_includes_content(tmp_path, monkeypatch):
    bundled = tmp_path / "bundled"
    _write_skill(bundled, "alpha", "Alpha skill")
    monkeypatch.setattr(skills_mod, "BUNDLED_SKILLS_DIR", bundled)
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path / "noglobal")
    prompt = skills_mod.build_skills_prompt(
        project_root=tmp_path / "noproject", user_request="alpha skill"
    )
    assert "Installed Agent Skills" in prompt
    # Catalog always lists the skill; a matching request also pulls in full content.
    assert "`alpha`" in prompt
    assert "Skill: `alpha`" in prompt


def test_build_skills_prompt_rewrites_script_paths_absolute(tmp_path, monkeypatch):
    global_dir = tmp_path / "global"
    d = global_dir / "boltz"
    (d / "scripts").mkdir(parents=True)
    (d / "scripts" / "workflow_api.py").write_text("print('x')", encoding="utf-8")
    (d / "scripts" / "fetch_cif.py").write_text("print('x')", encoding="utf-8")
    (d / "SKILL.md").write_text(
        "---\nname: boltz\ndescription: d\n---\n\nRun `python scripts/workflow_api.py new` and `scripts/fetch_cif.py`.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(skills_mod, "BUNDLED_SKILLS_DIR", tmp_path / "nobundled")
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", global_dir)
    prompt = skills_mod.build_skills_prompt(
        project_root=tmp_path / "noproject", user_request="boltz workflow"
    )
    abs_prefix = str(d)
    assert f"python {abs_prefix}/scripts/workflow_api.py" in prompt
    assert f"`{abs_prefix}/scripts/fetch_cif.py`" in prompt
    assert "python scripts/" not in prompt


# ─── Agent tool: skills.manage ─────────────────────────────────────────────
def test_skills_manage_tool_registered():
    from tools import registry, ensure_loaded

    ensure_loaded()
    assert registry.get_tool("skills.manage") is not None


def test_skills_manage_install_blocked_without_flag(monkeypatch):
    from tools.skills import manage

    session = MagicMock()
    session.config.get.return_value = False
    result = manage(action="install", source="owner/repo@skills/foo", _session=session)
    assert result.get("blocked") is True
    assert result.get("ok") is False


def test_skills_manage_find_uses_discover(monkeypatch):
    from tools import skills as skills_tool

    monkeypatch.setattr(
        skills_mod,
        "discover_skills",
        lambda query=None: [{"name": "foo", "description": "d", "tags": [], "install_source": "o/r@skills/foo"}],
    )
    result = skills_tool.manage(action="find", query="foo")
    assert "foo" in result["summary"]
    assert result["results"][0]["name"] == "foo"


def test_skills_manage_install_allowed_calls_install(monkeypatch):
    from tools.skills import manage

    called = {}

    def fake_install(source, **kwargs):
        called["source"] = source
        return {"ok": True, "installed": ["foo"], "summary": "ok"}

    monkeypatch.setattr(skills_mod, "install_skill", fake_install)
    session = MagicMock()
    session.config.get.return_value = True
    result = manage(action="install", source="owner/repo@skills/foo", _session=session)
    assert result["ok"] is True
    assert called["source"] == "owner/repo@skills/foo"


# ─── CLI ───────────────────────────────────────────────────────────────────
def test_cli_skill_add_local(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from cli import app

    src = tmp_path / "src"
    _write_skill(src, "cli-skill", "CLI installed skill")
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path / "global")

    runner = CliRunner()
    result = runner.invoke(app, ["skills", "add", str(src / "cli-skill")])
    assert result.exit_code == 0
    assert (tmp_path / "global" / "cli-skill" / "SKILL.md").exists()


def test_cli_skill_singular_alias_still_works(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from cli import app

    src = tmp_path / "src"
    _write_skill(src, "legacy-skill", "Legacy alias skill")
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path / "global")

    runner = CliRunner()
    result = runner.invoke(app, ["skill", "add", str(src / "legacy-skill")])
    assert result.exit_code == 0
    assert (tmp_path / "global" / "legacy-skill" / "SKILL.md").exists()


def test_cli_add_skill_alias(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from cli import app

    src = tmp_path / "src"
    _write_skill(src, "alias-skill", "Alias installed skill")
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path / "global")

    runner = CliRunner()
    result = runner.invoke(app, ["add", "skills", str(src / "alias-skill")])
    assert result.exit_code == 0
    assert (tmp_path / "global" / "alias-skill" / "SKILL.md").exists()


# ─── Terminal slash helpers ────────────────────────────────────────────────
def test_install_skill_prefer_npx_uses_npx_first(monkeypatch):
    calls = {}
    monkeypatch.setattr(skills_mod, "_npx_available", lambda: True)
    monkeypatch.setattr(skills_mod, "_git_available", lambda: True)

    def fake_npx(source):
        calls["npx"] = source
        return {"ok": True, "installed": [], "summary": "via npx", "via": "npx"}

    monkeypatch.setattr(skills_mod, "_npx_install", fake_npx)
    # Whole-repo source (no @subpath) -> npx is used first.
    result = skills_mod.install_skill("K-Dense-AI/scientific-agent-skills", prefer_npx=True)
    assert result["via"] == "npx"
    assert calls["npx"] == "K-Dense-AI/scientific-agent-skills"


def test_install_skill_prefer_npx_handles_subpath_via_skill_flag(monkeypatch):
    # Subpath sources now go through npx too (converted to --skill <name>).
    monkeypatch.setattr(skills_mod, "_npx_available", lambda: True)
    captured = {}

    def fake_run_npx_add(target, skill_names=None, whole=False):
        captured["target"] = target
        captured["skills"] = skill_names
        captured["whole"] = whole

    monkeypatch.setattr(skills_mod, "_run_npx_add", fake_run_npx_add)
    result = skills_mod.install_skill("fastfold-ai/skills@skills/fold", prefer_npx=True)
    assert result["via"] == "npx"
    assert captured["target"] == "fastfold-ai/skills"
    assert captured["skills"] == ["fold"]


def test_npx_target_parsing():
    assert skills_mod._npx_target("fastfold-ai/skills@skills/fold") == ("fastfold-ai/skills", "fold", False)
    assert skills_mod._npx_target("anthropics/life-sciences") == ("anthropics/life-sciences", None, True)
    t, s, whole = skills_mod._npx_target("https://github.com/o/r/tree/main/skills/x")
    assert whole is False and s is None


def test_install_skill_prefer_npx_falls_back_to_git(monkeypatch, tmp_path):
    # npx present but fails -> git path used
    monkeypatch.setattr(skills_mod, "_npx_available", lambda: True)
    monkeypatch.setattr(skills_mod, "_git_available", lambda: True)
    monkeypatch.setattr(skills_mod, "_npx_install", lambda source: {"ok": False, "summary": "npx boom"})
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path / "global")

    captured = {}

    def fake_clone(url, ref, dest):
        # source subpath is skills/fold -> create dest/skills/fold/SKILL.md
        _write_skill(dest / "skills", "fold", "Fold skill")
        captured["url"] = url
        return "abc123"

    monkeypatch.setattr(skills_mod, "_git_clone", fake_clone)
    result = skills_mod.install_skill("fastfold-ai/skills@skills/fold", prefer_npx=True)
    assert result["ok"] is True
    assert result["via"] == "git"
    assert "fold" in result["installed"]


def test_install_skill_uses_archive_when_git_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_mod, "_npx_available", lambda: False)
    monkeypatch.setattr(skills_mod, "_git_available", lambda: False)
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path / "global")
    monkeypatch.setattr(skills_mod, "fetch_latest_release", lambda _owner_repo: None)

    def fake_download(owner, repo, ref, extract_parent):
        repo_root = extract_parent / f"{repo}-main"
        _write_skill(repo_root / "skills", "fold", "Fold skill")
        return repo_root

    monkeypatch.setattr(skills_mod, "_download_github_archive", fake_download)
    result = skills_mod.install_skill("fastfold-ai/skills@skills/fold", prefer_npx=False)
    assert result["ok"] is True
    assert result["via"] == "archive"
    assert "fold" in result["installed"]


def test_install_skill_git_failure_falls_back_to_archive_without_npx(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_mod, "_npx_available", lambda: False)
    monkeypatch.setattr(skills_mod, "_git_available", lambda: True)
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path / "global")
    monkeypatch.setattr(skills_mod, "fetch_latest_release", lambda _owner_repo: None)
    monkeypatch.setattr(
        skills_mod,
        "_git_clone",
        lambda *args, **kwargs: (_ for _ in ()).throw(subprocess.CalledProcessError(1, "git")),
    )

    def fake_download(owner, repo, ref, extract_parent):
        repo_root = extract_parent / f"{repo}-main"
        _write_skill(repo_root / "skills", "boltz", "Boltz skill")
        return repo_root

    monkeypatch.setattr(skills_mod, "_download_github_archive", fake_download)
    result = skills_mod.install_skill("fastfold-ai/skills", prefer_npx=False)
    assert result["ok"] is True
    assert result["via"] == "archive"
    assert "boltz" in result["installed"]


def test_setup_prompt_install_skills_with_explicit_arg(monkeypatch):
    import cli

    installed = []
    monkeypatch.setattr(cli, "_install_skill_sources", lambda sources: installed.extend(sources))
    cli._prompt_install_skills(skills_arg="fastfold-ai/skills@skills/fold, owner/repo@skills/x", skip=False)
    assert installed == ["fastfold-ai/skills@skills/fold", "owner/repo@skills/x"]


def test_setup_prompt_install_skills_skip(monkeypatch):
    import cli

    called = {"discover": False}
    monkeypatch.setattr(skills_mod, "discover_skills", lambda *a, **k: called.__setitem__("discover", True) or [])
    cli._prompt_install_skills(skills_arg=None, skip=True)
    assert called["discover"] is False


def test_setup_install_skill_sources_batches_npx_by_repo(monkeypatch):
    import cli

    monkeypatch.setattr("agent.skills._npx_available", lambda: True)
    calls = []

    def fake_npx_add(target, skill_names=None, whole=False):
        calls.append((target, tuple(skill_names or ()), whole))
        return {"ok": True, "summary": f"installed {target}", "via": "npx"}

    monkeypatch.setattr("agent.skills.npx_add", fake_npx_add)
    cli._install_skill_sources([
        "fastfold-ai/skills@skills/fold",
        "fastfold-ai/skills@skills/protein_design_boltzgen",
        "anthropics/life-sciences",
    ])
    # Two catalog skills batched into one fastfold-ai/skills call; community repo separate.
    assert ("fastfold-ai/skills", ("fold", "protein_design_boltzgen"), False) in calls
    assert ("anthropics/life-sciences", (), True) in calls


def test_upgrade_skills_syncs_catalog_and_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path)
    monkeypatch.setattr(skills_mod, "_git_available", lambda: True)
    monkeypatch.setattr(skills_mod, "_npx_available", lambda: False)
    monkeypatch.setattr(
        skills_mod,
        "_read_manifest",
        lambda dest: {
            "version": 1,
            "skills": {
                "fold": {"source": "fastfold-ai/skills@skills/fold"},
                "kdense": {"source": "K-Dense-AI/scientific-agent-skills"},
            },
        },
    )
    calls = []

    def fake_install(source, dest=None, prefer_npx=False):
        calls.append(source)
        return {"ok": True, "installed": [source.split("/")[-1]], "summary": "ok", "via": "git"}

    monkeypatch.setattr(skills_mod, "install_skill", fake_install)
    # Manifest-tracked (non-catalog) sources now flow through the grouped sync,
    # which clones each repo once. Record those separately.
    synced = []

    def fake_sync(tracked, dest, **kwargs):
        synced.extend(src for _name, src in tracked)
        return [src.split("/")[-1] for _n, src in tracked], []

    monkeypatch.setattr(skills_mod, "_sync_tracked_sources", fake_sync)
    states = [{}, {"a": object(), "b": object()}]
    monkeypatch.setattr(skills_mod, "iter_skills", lambda *a, **k: states.pop(0) if states else {})

    res = skills_mod.upgrade_skills()
    # Catalog synced once; the manifest 'fold' (same owner/repo as catalog) is skipped.
    assert calls.count("fastfold-ai/skills") == 1
    # Non-catalog manifest source is re-installed (via the grouped sync).
    assert "K-Dense-AI/scientific-agent-skills" in synced
    assert "added" in res and "updated" in res and "failed" in res


def test_upgrade_skills_invokes_progress_callback(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path)
    monkeypatch.setattr(skills_mod, "_git_available", lambda: True)
    monkeypatch.setattr(skills_mod, "_npx_available", lambda: False)
    monkeypatch.setattr(skills_mod, "_read_manifest", lambda dest: {"version": 1, "skills": {}})
    monkeypatch.setattr(
        skills_mod, "install_skill",
        lambda source, dest=None, prefer_npx=False: {"ok": True, "installed": [], "summary": "ok"},
    )
    monkeypatch.setattr(skills_mod, "iter_skills", lambda *a, **k: {})
    messages = []
    skills_mod.upgrade_skills(progress=messages.append)
    assert any("Syncing catalog" in m for m in messages)
    # A failing callback must never break the upgrade.
    res = skills_mod.upgrade_skills(progress=lambda _m: (_ for _ in ()).throw(RuntimeError("boom")))
    assert "summary" in res


def test_upgrade_skills_no_catalog_only_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path)
    monkeypatch.setattr(skills_mod, "_git_available", lambda: True)
    monkeypatch.setattr(skills_mod, "_npx_available", lambda: False)
    monkeypatch.setattr(
        skills_mod,
        "_read_manifest",
        lambda dest: {"version": 1, "skills": {"kdense": {"source": "K-Dense-AI/scientific-agent-skills"}}},
    )
    synced = []

    def fake_sync(tracked, dest, **kwargs):
        synced.extend(src for _name, src in tracked)
        return [], []

    monkeypatch.setattr(skills_mod, "_sync_tracked_sources", fake_sync)
    monkeypatch.setattr(skills_mod, "iter_skills", lambda *a, **k: {})
    skills_mod.upgrade_skills(include_catalog=False)
    # No catalog sync; the manifest source goes through the grouped sync.
    assert synced == ["K-Dense-AI/scientific-agent-skills"]


def test_sync_tracked_sources_clones_each_repo_once(monkeypatch, tmp_path):
    """Many skills from the same repo+ref should trigger exactly one clone."""
    monkeypatch.setattr(skills_mod, "_git_available", lambda: True)
    monkeypatch.setattr(skills_mod, "fetch_latest_release", lambda *a, **k: None)

    clone_calls = []

    def fake_clone(url, ref, tmp_root):
        clone_calls.append((url, ref))
        return tmp_root / "repo", "deadbeef", "git"

    monkeypatch.setattr(skills_mod, "_clone_repo_once", fake_clone)

    installed_subpaths = []

    def fake_tree(repo_root, subpath, dest, source, commit, release_tag, via):
        installed_subpaths.append(subpath)
        return {"ok": True, "installed": [subpath.split("/")[-1]], "summary": "ok", "via": via}

    monkeypatch.setattr(skills_mod, "_install_from_repo_tree", fake_tree)

    # 3 skills from one repo + 1 from another => 2 clones total.
    tracked = [
        ("a", "ClawBio/ClawBio@skills/a"),
        ("b", "ClawBio/ClawBio@skills/b"),
        ("c", "ClawBio/ClawBio@skills/c"),
        ("d", "OtherOrg/repo@skills/d"),
    ]
    installed, failures = skills_mod._sync_tracked_sources(tracked, tmp_path, max_workers=4)

    assert len(clone_calls) == 2  # one clone per unique repo, not per skill
    assert sorted(installed) == ["a", "b", "c", "d"]
    assert failures == []


def test_sync_tracked_sources_reports_clone_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_mod, "_git_available", lambda: True)
    monkeypatch.setattr(skills_mod, "fetch_latest_release", lambda *a, **k: None)
    monkeypatch.setattr(skills_mod, "_clone_repo_once", lambda url, ref, tmp_root: (None, None, "git"))

    tracked = [("a", "ClawBio/ClawBio@skills/a"), ("b", "ClawBio/ClawBio@skills/b")]
    installed, failures = skills_mod._sync_tracked_sources(tracked, tmp_path, max_workers=1)

    assert installed == []
    assert {src for src, _reason in failures} == {
        "ClawBio/ClawBio@skills/a",
        "ClawBio/ClawBio@skills/b",
    }


def test_noninteractive_git_env_disables_prompts(monkeypatch):
    monkeypatch.delenv("GIT_TERMINAL_PROMPT", raising=False)
    monkeypatch.delenv("GIT_ASKPASS", raising=False)
    monkeypatch.delenv("GCM_INTERACTIVE", raising=False)
    monkeypatch.delenv("GIT_SSH_COMMAND", raising=False)

    env = skills_mod._noninteractive_git_env()

    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_ASKPASS"] == "echo"
    assert env["GCM_INTERACTIVE"] == "never"
    assert "BatchMode=yes" in env["GIT_SSH_COMMAND"]


def test_clone_repo_once_prefers_git(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_mod, "_git_available", lambda: True)
    monkeypatch.setattr(skills_mod, "_git_clone", lambda url, ref, dest: "abc123")

    root, commit, via = skills_mod._clone_repo_once(
        "https://github.com/owner/repo.git", "main", tmp_path
    )

    assert root == tmp_path / "repo"
    assert commit == "abc123"
    assert via == "git"


@pytest.mark.parametrize("git_error", [
    subprocess.CalledProcessError(1, ["git", "clone"]),
    RuntimeError("git unavailable"),
])
def test_clone_repo_once_falls_back_to_archive(monkeypatch, tmp_path, git_error):
    monkeypatch.setattr(skills_mod, "_git_available", lambda: True)
    monkeypatch.setattr(
        skills_mod, "_git_clone", lambda *args, **kwargs: (_ for _ in ()).throw(git_error)
    )
    archive = tmp_path / "repo-main"
    monkeypatch.setattr(
        skills_mod,
        "_download_github_archive",
        lambda owner, repo, ref, parent: archive,
    )

    root, commit, via = skills_mod._clone_repo_once(
        "https://github.com/owner/repo.git", None, tmp_path
    )

    assert (root, commit, via) == (archive, None, "archive")


def test_clone_repo_once_reports_total_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_mod, "_git_available", lambda: False)
    monkeypatch.setattr(
        skills_mod,
        "_download_github_archive",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("archive failed")),
    )

    assert skills_mod._clone_repo_once(
        "https://github.com/owner/repo.git", None, tmp_path
    ) == (None, None, "git")


def test_run_grouped_clones_handles_item_and_notify_errors(monkeypatch):
    repo = Path("/tmp/fake-repo")
    monkeypatch.setattr(
        skills_mod, "_clone_repo_once", lambda *args: (repo, "abc123", "git")
    )
    monkeypatch.setattr(
        skills_mod, "fetch_latest_release", lambda owner_repo: {"tag": "v1.2.3"}
    )
    seen = []

    def install_item(repo_root, commit, release, via, item):
        seen.append((repo_root, commit, release, via, item))
        if item[0] == "boom":
            raise RuntimeError("copy failed")
        return [item[0]], []

    installed, failures = skills_mod._run_grouped_clones(
        {("https://github.com/owner/repo.git", None): [("ok",), ("boom",)]},
        {("https://github.com/owner/repo.git", None): "owner/repo"},
        install_item,
        max_workers=1,
        notify=lambda message: (_ for _ in ()).throw(RuntimeError(message)),
    )

    assert installed == ["ok"]
    assert failures == [("boom", "copy failed")]
    assert seen[0][2] == "v1.2.3"


def test_run_grouped_clones_empty():
    assert skills_mod._run_grouped_clones({}, {}, lambda *args: None) == ([], [])


def test_sync_tracked_sources_installs_other_sources(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_mod, "detect_source_type", lambda source: "local")
    calls = []

    def install(source, dest=None):
        calls.append((source, dest))
        if source == "bad":
            return {"ok": False, "summary": "not found"}
        return {"ok": True, "installed": ["local-skill"]}

    monkeypatch.setattr(skills_mod, "install_skill", install)
    messages = []
    installed, failures = skills_mod._sync_tracked_sources(
        [("good", "local"), ("bad", "bad")],
        tmp_path,
        notify=messages.append,
    )

    assert installed == ["local-skill"]
    assert failures == [("bad", "not found")]
    assert calls == [("local", tmp_path), ("bad", tmp_path)]
    assert messages == ["Updating local...", "Updating bad..."]


def test_update_npx_skills_via_git_from_lock(monkeypatch, tmp_path):
    root = tmp_path / "npx-root"
    skills_dir = root / ".claude" / "skills"
    monkeypatch.setattr(skills_mod, "NPX_INSTALL_ROOT", root)
    monkeypatch.setattr(skills_mod, "NPX_SKILLS_DIR", skills_dir)
    monkeypatch.setattr(skills_mod, "_git_available", lambda: True)
    root.mkdir()
    (root / "skills-lock.json").write_text(
        json.dumps({
            "skills": {
                "alpha-installed": {
                    "source": "owner/repo",
                    "sourceType": "github",
                    "skillPath": "skills/alpha/SKILL.md",
                },
                "beta-installed": {
                    "source": "owner/repo",
                    "sourceType": "github",
                    "skillPath": "skills/beta/SKILL.md",
                },
                "ignored": {"source": "local/path", "sourceType": "local"},
                "malformed": "not-a-dict",
            }
        }),
        encoding="utf-8",
    )

    def clone(url, ref, temporary_root):
        repo = temporary_root / "repo"
        _write_skill(repo / "skills", "alpha", "Alpha")
        _write_skill(repo / "skills", "beta", "Beta")
        return repo, "abc123", "git"

    monkeypatch.setattr(skills_mod, "_clone_repo_once", clone)
    result = skills_mod.update_npx_skills_via_git(max_workers=1)

    assert result["ok"] is True
    assert result["synced"] == 2
    assert result["failed"] == []
    assert (skills_dir / "alpha-installed" / "SKILL.md").exists()
    assert (skills_dir / "beta-installed" / "SKILL.md").exists()
    # A refresh replaces the existing target directories.
    refreshed = skills_mod.update_npx_skills_via_git(max_workers=1)
    assert refreshed["synced"] == 2


def test_update_npx_skills_via_git_reports_bad_lock_and_missing_skill(monkeypatch, tmp_path):
    root = tmp_path / "npx-root"
    monkeypatch.setattr(skills_mod, "NPX_INSTALL_ROOT", root)
    monkeypatch.setattr(skills_mod, "NPX_SKILLS_DIR", root / ".claude" / "skills")
    monkeypatch.setattr(skills_mod, "_git_available", lambda: True)

    assert skills_mod.update_npx_skills_via_git()["ok"] is False
    root.mkdir()
    lock = root / "skills-lock.json"
    lock.write_text("{bad json", encoding="utf-8")
    assert "unreadable lock" in skills_mod.update_npx_skills_via_git()["summary"]

    lock.write_text(
        json.dumps({
            "skills": {
                "local-only": {"source": "local/path", "sourceType": "local"}
            }
        }),
        encoding="utf-8",
    )
    assert "no github sources" in skills_mod.update_npx_skills_via_git()["summary"]

    lock.write_text(
        json.dumps({
            "skills": {
                "missing": {
                    "source": "owner/repo",
                    "sourceType": "github",
                    "skillPath": "skills/missing/SKILL.md",
                }
            }
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        skills_mod,
        "_clone_repo_once",
        lambda url, ref, temporary_root: (temporary_root / "repo", None, "archive"),
    )
    result = skills_mod.update_npx_skills_via_git(max_workers=1)
    assert result["ok"] is True
    assert result["synced"] == 0
    assert result["failed"][0][0].endswith("@skills/missing")


def test_discover_skills_clones_catalog_and_filters(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_mod, "_git_available", lambda: True)

    def clone(url, ref, destination):
        _write_skill(destination / "skills", "fold", "Protein folding", "protein,structure")
        _write_skill(destination / "skills", "report", "Publish reports", "reporting")
        return "abc123"

    monkeypatch.setattr(skills_mod, "_git_clone", clone)

    results = skills_mod.discover_skills("protein", catalog="owner/catalog")

    assert [result["name"] for result in results] == ["fold"]
    assert results[0]["install_source"] == "owner/catalog@skills/fold"
    assert skills_mod._resolve_name_to_source("fold", catalog="owner/catalog").endswith(
        "@skills/fold"
    )


def test_discover_skills_handles_unavailable_git_and_clone_failure(monkeypatch):
    monkeypatch.setattr(skills_mod, "_git_available", lambda: False)
    assert skills_mod.discover_skills() == []

    monkeypatch.setattr(skills_mod, "_git_available", lambda: True)
    monkeypatch.setattr(
        skills_mod,
        "_git_clone",
        lambda *args: (_ for _ in ()).throw(RuntimeError("clone failed")),
    )
    assert skills_mod.discover_skills() == []


def test_resolve_name_to_source_uses_loose_match(monkeypatch):
    calls = []

    def discover(query, catalog):
        calls.append((query, catalog))
        return [{"name": "folding", "install_source": "owner/repo@skills/folding"}]

    monkeypatch.setattr(skills_mod, "discover_skills", discover)
    assert skills_mod._resolve_name_to_source("fold", catalog="owner/repo") == (
        "owner/repo@skills/folding"
    )
    assert len(calls) == 2


def test_upgrade_skills_runs_npx_update(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path / "global")
    npx_dir = tmp_path / "npx" / ".claude" / "skills"
    _write_skill(npx_dir, "life", "Life")
    monkeypatch.setattr(skills_mod, "NPX_SKILLS_DIR", npx_dir)
    monkeypatch.setattr(skills_mod, "_git_available", lambda: False)
    monkeypatch.setattr(skills_mod, "_npx_available", lambda: True)
    monkeypatch.setattr(skills_mod, "_read_manifest", lambda dest: {"version": 1, "skills": {}})
    monkeypatch.setattr(skills_mod, "iter_skills", lambda *a, **k: {})
    updated = {"ran": False}
    monkeypatch.setattr(skills_mod, "_npx_update", lambda: updated.__setitem__("ran", True) or {"ok": True, "summary": "ok"})
    res = skills_mod.upgrade_skills(project_root=tmp_path)
    assert updated["ran"] is True
    assert res["npx_synced"] == 1  # one skill in the npx dir


def test_upgrade_skills_collects_catalog_git_and_npx_failures(monkeypatch, tmp_path):
    global_dir = tmp_path / "global"
    npx_dir = tmp_path / "npx" / ".claude" / "skills"
    npx_dir.mkdir(parents=True)
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", global_dir)
    monkeypatch.setattr(skills_mod, "NPX_SKILLS_DIR", npx_dir)
    monkeypatch.setattr(
        skills_mod,
        "install_skill",
        lambda *args, **kwargs: {"ok": False, "summary": "catalog unavailable"},
    )
    monkeypatch.setattr(
        skills_mod,
        "_read_manifest",
        lambda dest: {
            "version": 1,
            "skills": {
                "missing-source": {},
                "community": {"source": "owner/repo@skills/community"},
            },
        },
    )
    monkeypatch.setattr(
        skills_mod,
        "_sync_tracked_sources",
        lambda *args, **kwargs: ([], [("owner/repo", "sync failed")]),
    )
    monkeypatch.setattr(
        skills_mod,
        "update_npx_skills_via_git",
        lambda **kwargs: {
            "ok": True,
            "synced": 2,
            "failed": [("npx-source", "copy failed")],
        },
    )
    monkeypatch.setattr(skills_mod, "iter_skills", lambda *args, **kwargs: {})

    result = skills_mod.upgrade_skills(project_root=tmp_path)

    assert result["npx_synced"] == 2
    assert ("fastfold-ai/skills", "catalog unavailable") in result["failed"]
    assert ("owner/repo", "sync failed") in result["failed"]
    assert ("npx-source", "copy failed") in result["failed"]


def test_upgrade_skills_records_npx_fallback_failure(monkeypatch, tmp_path):
    npx_dir = tmp_path / ".claude" / "skills"
    npx_dir.mkdir(parents=True)
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path / "global")
    monkeypatch.setattr(skills_mod, "NPX_SKILLS_DIR", npx_dir)
    monkeypatch.setattr(skills_mod, "_read_manifest", lambda dest: {"skills": {}})
    monkeypatch.setattr(skills_mod, "iter_skills", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        skills_mod,
        "install_skill",
        lambda *args, **kwargs: {"ok": True, "installed": []},
    )
    monkeypatch.setattr(
        skills_mod,
        "update_npx_skills_via_git",
        lambda **kwargs: {"ok": False},
    )
    monkeypatch.setattr(skills_mod, "_npx_available", lambda: True)
    monkeypatch.setattr(
        skills_mod,
        "_npx_update",
        lambda: {"ok": False, "summary": "npx failed"},
    )

    result = skills_mod.upgrade_skills(project_root=tmp_path)

    assert ("npx skills update", "npx failed") in result["failed"]


def test_cli_skill_upgrade(monkeypatch):
    from typer.testing import CliRunner
    from cli import app

    monkeypatch.setattr(
        "agent.skills.upgrade_skills",
        lambda include_catalog=True, include_npx=True, progress=None: {"added": ["x"], "updated": ["y"], "npx_synced": 0, "failed": [], "summary": "ok"},
    )
    runner = CliRunner()
    result = runner.invoke(app, ["skills", "upgrade"])
    assert result.exit_code == 0
    assert "Added" in result.stdout and "Updated" in result.stdout


def test_remove_all_skills_clears_global_and_project(monkeypatch, tmp_path):
    global_dir = tmp_path / "global"
    _write_skill(global_dir, "fold", "Fold")
    _write_skill(global_dir, "boltz", "Boltz")
    skills_mod._write_manifest(global_dir, {"version": 1, "skills": {"fold": {"source": "x"}}})
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", global_dir)

    # project-local lock-gated skill
    proj = tmp_path / "proj"
    claude = proj / ".claude" / "skills"
    _write_skill(claude, "life", "Life")
    (proj / "skills-lock.json").write_text('{"version":1,"skills":{"life":{"source":"anthropics/life-sciences"}}}', encoding="utf-8")

    names = skills_mod.user_installed_skill_names(project_root=proj)
    assert set(names) == {"fold", "boltz", "life"}

    result = skills_mod.remove_all_skills(project_root=proj)
    assert result["ok"] is True
    assert set(result["removed"]) == {"fold", "boltz", "life"}
    assert not (global_dir / "fold").exists()
    assert not (global_dir / "boltz").exists()
    assert not (claude / "life").exists()
    # manifest reset
    assert skills_mod._read_manifest(global_dir)["skills"] == {}


def test_cli_skill_delete_all_requires_confirmation(monkeypatch):
    from typer.testing import CliRunner
    from cli import app

    monkeypatch.setattr("agent.skills.user_installed_skill_names", lambda *a, **k: ["fold", "boltz"])
    called = {"removed": False}
    monkeypatch.setattr(
        "agent.skills.remove_all_skills",
        lambda *a, **k: called.__setitem__("removed", True) or {"ok": True, "removed": ["fold", "boltz"], "summary": "Removed 2 skill(s)."},
    )
    runner = CliRunner()
    # Decline confirmation -> nothing removed
    result = runner.invoke(app, ["skills", "delete", "--all"], input="n\n")
    assert result.exit_code == 0
    assert called["removed"] is False
    # Confirm with --yes -> removes
    result2 = runner.invoke(app, ["skills", "delete", "--all", "--yes"])
    assert result2.exit_code == 0
    assert called["removed"] is True


def test_provider_label_for_source():
    from cli import _provider_label_for_source

    assert _provider_label_for_source("fastfold-ai/skills@skills/fold") == "Fastfold"
    assert _provider_label_for_source("anthropics/life-sciences") == "Anthropic"
    assert _provider_label_for_source("google-deepmind/science-skills") == "DeepMind"
    assert _provider_label_for_source("K-Dense-AI/scientific-agent-skills") == "K-Dense-AI"
    assert _provider_label_for_source("https://github.com/anthropics/life-sciences/tree/main/skills") == "Anthropic"
    assert _provider_label_for_source("someuser/their-skills") == "someuser"


def test_suggested_skill_sources_present():
    providers = {s["provider"] for s in skills_mod.SUGGESTED_SKILL_SOURCES}
    assert {"K-Dense-AI", "Anthropic", "DeepMind"} <= providers
    for s in skills_mod.SUGGESTED_SKILL_SOURCES:
        assert "/" in s["source"]
        assert s["url"].startswith("https://github.com/")


def test_setup_select_suggested_sources_inline(monkeypatch):
    import cli

    # Non-tty -> inline numbered prompt; pick 'all'
    monkeypatch.setattr("builtins.input", lambda _: "all")
    sources = cli._select_suggested_sources()
    assert "K-Dense-AI/scientific-agent-skills" in sources
    assert "anthropics/life-sciences" in sources
    assert "google-deepmind/science-skills" in sources


def test_terminal_add_skill_invokes_install(monkeypatch):
    from ui.terminal import InteractiveTerminal

    t = InteractiveTerminal.__new__(InteractiveTerminal)
    t.console = MagicMock()

    captured = {}

    def fake_install(source):
        captured["source"] = source
        return {"ok": True, "summary": "done"}

    monkeypatch.setattr(skills_mod, "install_skill", fake_install)
    t._add_skill("owner/repo@skills/foo")
    assert captured["source"] == "owner/repo@skills/foo"


def test_terminal_upgrade_skills_invokes_upgrade(monkeypatch):
    from ui.terminal import InteractiveTerminal

    t = InteractiveTerminal.__new__(InteractiveTerminal)
    t.console = MagicMock()

    called = {"ran": False}

    def fake_upgrade(*a, **k):
        called["ran"] = True
        return {"added": ["fold"], "updated": [], "npx_synced": 0, "failed": [], "summary": "ok"}

    monkeypatch.setattr(skills_mod, "upgrade_skills", fake_upgrade)
    t._upgrade_skills()
    assert called["ran"] is True


def test_resolve_skill_dirs_missing_subpath_falls_back_to_root(tmp_path):
    repo = tmp_path / "repo"
    _write_skill(repo / "skills", "fold")
    dirs = skills_mod._resolve_skill_dirs(repo, "not/here")
    assert [d.name for d in dirs] == ["fold"]


def test_resolve_skill_dirs_returns_empty_when_no_skill_layout(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    assert skills_mod._resolve_skill_dirs(repo, None) == []


def test_record_install_persists_release_metadata(tmp_path):
    dest = tmp_path / "global"
    dest.mkdir(parents=True)
    skills_mod._record_install(
        dest,
        "fold",
        "fastfold-ai/skills@skills/fold",
        "abc123",
        release="v1.2.3",
    )
    manifest = skills_mod._read_manifest(dest)
    assert manifest["skills"]["fold"]["release"] == "v1.2.3"


def test_owner_repo_from_source_handles_empty_and_unknown():
    assert skills_mod._owner_repo_from_source("") is None
    assert (
        skills_mod._owner_repo_from_source(
            "https://github.com/fastfold-ai/skills/tree/main/skills/fold"
        )
        == "fastfold-ai/skills"
    )
    assert skills_mod._owner_repo_from_source("not-a-github-source") is None


def test_is_newer_tag_returns_false_for_invalid_versions():
    assert skills_mod._is_newer_tag("not-semver", "v1.0.0") is False
    assert skills_mod._is_newer_tag("v1.1.0", "bad") is False


def test_installed_catalog_release_skips_non_dict_manifest_entries(monkeypatch):
    monkeypatch.setattr(
        skills_mod,
        "_read_manifest",
        lambda _dest: {
            "skills": {
                "bad-entry": "not-a-dict",
                "fold": {
                    "source": "fastfold-ai/skills@skills/fold",
                    "release": "v1.0.0",
                },
            }
        },
    )
    assert skills_mod._installed_catalog_release() == "v1.0.0"


def test_get_cached_skills_update_none_without_latest_release(monkeypatch):
    monkeypatch.setattr(
        skills_mod,
        "_installed_catalog_release",
        lambda catalog=skills_mod.DEFAULT_CATALOG: "v1.0.0",
    )
    monkeypatch.setattr(skills_mod, "_read_update_cache", lambda: {})
    assert skills_mod.get_cached_skills_update() is None


def test_refresh_skills_update_cache_invalid_checked_at_still_refreshes(monkeypatch):
    monkeypatch.setattr(skills_mod, "_read_update_cache", lambda: {"checked_at": "not-a-date"})
    monkeypatch.setattr(
        skills_mod,
        "fetch_latest_release",
        lambda owner_repo, timeout_s=2.5: {
            "tag": "v1.2.0",
            "published_at": "2026-06-18T00:00:00Z",
        },
    )
    written = {}
    monkeypatch.setattr(skills_mod, "_write_update_cache", lambda cache: written.update(cache))

    skills_mod.refresh_skills_update_cache(force=False)

    assert written["latest_release"] == "v1.2.0"
    assert written["latest_published_at"] == "2026-06-18T00:00:00Z"
    assert "checked_at" in written


def test_read_update_cache_invalid_json_returns_empty():
    skills_mod.SKILLS_UPDATE_CACHE.write_text("{bad-json", encoding="utf-8")
    assert skills_mod._read_update_cache() == {}


def test_write_update_cache_persists_json_file():
    payload = {"latest_release": "v2.0.0"}
    skills_mod._write_update_cache(payload)
    raw = skills_mod.SKILLS_UPDATE_CACHE.read_text(encoding="utf-8")
    assert '"latest_release": "v2.0.0"' in raw


def test_http_get_bytes_uses_httpx_client(monkeypatch):
    captured = {}

    class _Resp:
        def raise_for_status(self):
            return None

        @property
        def content(self):
            return b"payload"

    class _Client:
        def __init__(self, *args, **kwargs):
            captured["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            captured["url"] = url
            captured["headers"] = headers
            return _Resp()

    monkeypatch.setattr("httpx.Client", _Client)
    out = skills_mod._http_get_bytes("https://example.com/archive.zip", timeout=12.5)
    assert out == b"payload"
    assert captured["url"] == "https://example.com/archive.zip"
    assert captured["headers"]["User-Agent"] == "fastfold-agent-cli"
    assert captured["client_kwargs"]["follow_redirects"] is True


def test_fetch_latest_release_returns_none_without_owner_repo():
    assert _REAL_FETCH_LATEST_RELEASE("") is None


def test_fetch_latest_release_success(monkeypatch):
    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"tag_name": "v1.2.3", "published_at": "2026-06-18T00:00:00Z"}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            return _Resp()

    monkeypatch.setattr("httpx.Client", _Client)
    out = _REAL_FETCH_LATEST_RELEASE("fastfold-ai/skills", timeout_s=0.1)
    assert out == {"tag": "v1.2.3", "published_at": "2026-06-18T00:00:00Z"}


def test_fetch_latest_release_returns_none_on_url_error(monkeypatch):
    import httpx

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            raise httpx.ConnectError("down")

    monkeypatch.setattr("httpx.Client", _Client)
    assert _REAL_FETCH_LATEST_RELEASE("fastfold-ai/skills", timeout_s=0.1) is None


def test_fetch_latest_release_returns_none_on_non_dict_payload(monkeypatch):
    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return ["not-a-dict"]

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            return _Resp()

    monkeypatch.setattr("httpx.Client", _Client)
    assert _REAL_FETCH_LATEST_RELEASE("fastfold-ai/skills", timeout_s=0.1) is None


def test_fetch_latest_release_returns_none_when_tag_missing(monkeypatch):
    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"published_at": "2026-06-18T00:00:00Z"}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            return _Resp()

    monkeypatch.setattr("httpx.Client", _Client)
    assert _REAL_FETCH_LATEST_RELEASE("fastfold-ai/skills", timeout_s=0.1) is None


def test_read_update_cache_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_mod, "SKILLS_UPDATE_CACHE", tmp_path / "does-not-exist.json")
    assert skills_mod._read_update_cache() == {}


def test_write_update_cache_logs_debug_on_write_failure(monkeypatch):
    from pathlib import Path

    debug = MagicMock()
    monkeypatch.setattr(skills_mod.logger, "debug", debug)
    monkeypatch.setattr(Path, "write_text", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    skills_mod._write_update_cache({"latest_release": "v9.9.9"})
    debug.assert_called_once()


def test_installed_catalog_release_returns_none_when_no_match(monkeypatch):
    monkeypatch.setattr(
        skills_mod,
        "_read_manifest",
        lambda _dest: {
            "skills": {
                "other": {
                    "source": "someone-else/skills@skills/other",
                    "release": "v1.0.0",
                }
            }
        },
    )
    assert skills_mod._installed_catalog_release() is None
