"""
Skill management for fastfold-agent-cli.

Single source of truth for discovering, loading, installing, and removing
agent skills. A *skill* is a directory containing a ``SKILL.md`` file (plus
optional ``scripts/``, ``references/``, ``assets/``).

Skills are resolved from three tiers (highest priority first):

1. **global**  — ``~/.sandwalk/skills/`` (where ``skill add`` installs).
2. **project** — ``<cwd>/.claude/skills/`` gated by ``<cwd>/skills-lock.json``
   (legacy/back-compat; read-only here).
3. **bundled** — ``src/skills/`` shipped inside the package.

Higher tiers override lower tiers on a name collision.

Installation is native (``git clone``), with GitHub archive download when git
is unavailable or clone fails, and an optional fallback to the external
``npx skills`` CLI when Node.js is installed.

This is a package split by responsibility:

- ``models``   — ``SkillInfo``, SKILL.md frontmatter parsing, display helpers.
- ``discover`` — tier merging/scanning, name resolution, catalog discovery.
- ``prompt``   — the adaptive "Installed Agent Skills" prompt section.
- ``mentions`` — slash/chip skill mentions → activation hint + SKILL.md preload.
- ``install``  — source detection, git/archive/npx installation, manifest I/O.
- ``releases`` — GitHub release lookups and the boot-time update cache.
- ``upgrade``  — re-syncing installed skills to their latest versions.
- ``remove``   — enable/disable state and uninstalling skills.

Externally this still behaves like a single flat module: ``from agent.skills
import <anything>`` and ``agent.skills.<name>`` monkeypatches (used pervasively
across the test suite) keep working because submodules resolve shared
helpers/constants through ``agent.skills`` itself at call time (see the
``from agent import skills as _skills`` import in each submodule) instead of
baking in a reference at import time.
"""

from __future__ import annotations

import logging
from pathlib import Path

from agent.config import CONFIG_DIR

logger = logging.getLogger("skills")

# ─── Locations ────────────────────────────────────────────────────────────
GLOBAL_SKILLS_DIR = CONFIG_DIR / "skills"
BUNDLED_SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"
MANIFEST_FILENAME = ".installed.json"
SKILL_STATE_FILENAME = "skills-state.json"

# Fastfold-controlled directory for `npx skills add` installs. We pin the Skills
# CLI's working directory to NPX_INSTALL_ROOT and target the `claude-code` agent in
# project scope, so files land in a single fastfold-owned location (not the user's
# global ~/.claude/skills). The loader reads NPX_SKILLS_DIR as its own tier.
NPX_INSTALL_ROOT = CONFIG_DIR
NPX_SKILLS_DIR = CONFIG_DIR / ".claude" / "skills"

# Default discovery catalog (GitHub ``owner/repo``); skills live under ``skills/``.
DEFAULT_CATALOG = "fastfold-ai/skills"

# Curated skill collections, grouped by provider. Each ``source`` is a
# GitHub shorthand installable via ``install_skill`` (native git or npx). Installing
# a whole-repo source batch-installs all skills it contains.
# Fastfold AI is first so users can reinstall featured skills after deleting them.
SUGGESTED_SKILL_SOURCES = [
    {
        "provider": "Fastfold AI",
        "source": "fastfold-ai/skills",
        "url": "https://github.com/fastfold-ai/skills",
        "description": "Official Fastfold AI skills for folding, design, and MD",
    },
    {
        "provider": "K-Dense-AI",
        "source": "K-Dense-AI/scientific-agent-skills",
        "url": "https://github.com/K-Dense-AI/scientific-agent-skills",
        "description": "Scientific agent skills collection",
    },
    {
        "provider": "Anthropic",
        "source": "anthropics/life-sciences",
        "url": "https://github.com/anthropics/life-sciences#skills",
        "description": "Anthropic life-sciences skills",
    },
    {
        "provider": "DeepMind",
        "source": "google-deepmind/science-skills",
        "url": "https://github.com/google-deepmind/science-skills",
        "description": "Google DeepMind science skills",
    },
    {
        "provider": "Hugging Face",
        "source": "huggingface/skills",
        "url": "https://github.com/huggingface/skills",
        "description": "Hub skills for models, datasets, training, evals, and Gradio",
    },
]

# ─── GitHub releases + update cache ─────────────────────────────────────────
GITHUB_API = "https://api.github.com"
SKILLS_UPDATE_CACHE = CONFIG_DIR / "skills_update_check.json"

# ─── Prompt index cache ─────────────────────────────────────────────────────
SKILLS_PROMPT_INDEX_CACHE = CONFIG_DIR / "skills_prompt_index.json"

from .models import (  # noqa: E402
    USER_CREATED_CATEGORY,
    SkillInfo,
    _derive_author,
    _npx_lock_sources,
    _read_skills_lock,
    _source_from_lock_meta,
    display_author,
    display_updated,
    display_version,
    is_user_created_skill,
    local_skill_author_name,
    parse_skill_md,
)
from .prompt import (  # noqa: E402
    _build_skill_catalog,
    _build_skill_token_index,
    _format_selected_skill_section,
    _path_signature,
    _read_prompt_index_cache,
    _read_text_prefix,
    _score_skill_query_match,
    _skill_script_names,
    _tokenize_skill_text,
    _write_prompt_index_cache,
    build_skills_prompt,
)
from .discover import (  # noqa: E402
    _collapse_skills_by_name,
    _normalize_skill_lookup,
    _prefer_duplicate_skill,
    _resolve_name_to_source,
    _resolve_skill_key,
    _scan_dir,
    _scan_project,
    _skill_source_tier_rank,
    discover_ecosystem_skills,
    discover_skills,
    installed_skill_names,
    iter_skills,
    list_skills,
    skill_info,
    user_installed_skill_names,
)
from .install import (  # noqa: E402
    _copy_skill_dirs,
    _download_github_archive,
    _format_git_error,
    _git_available,
    _git_clone,
    _install_from_repo_tree,
    _install_github_source,
    _install_local,
    _noninteractive_git_env,
    _npx_available,
    _npx_install,
    _npx_target,
    _npx_update,
    _owner_repo_from_clone_url,
    _parse_github,
    _read_manifest,
    _record_install,
    _resolve_skill_dirs,
    _run_npx_add,
    _write_manifest,
    detect_source_type,
    install_skill,
    npx_add,
)
from .releases import (  # noqa: E402
    _http_get_bytes,
    _installed_catalog_release,
    _is_newer_tag,
    _owner_repo_from_source,
    _read_update_cache,
    _tag_tuple,
    _write_update_cache,
    check_github_skill_update,
    fetch_latest_release,
    fetch_repo_head_sha,
    get_cached_skills_update,
    refresh_skills_update_cache,
    resolve_repo_remote_state,
)
from .upgrade import (  # noqa: E402
    _clone_repo_once,
    _copy_skill_to,
    _project_lock_sources,
    _run_grouped_clones,
    _sync_tracked_sources,
    update_npx_skills_via_git,
    upgrade_skills,
)
from .remove import (  # noqa: E402
    _clear_skill_enabled_state,
    _disabled_skill_names,
    _read_skill_state,
    _set_disabled_skill_names,
    _skill_state_path,
    _write_skill_state,
    remove_all_skills,
    remove_skill,
    set_skill_enabled,
)
from .mentions import (  # noqa: E402
    build_skill_mention_context,
    extract_skill_mentions,
)

__all__ = [
    "SkillInfo",
    "USER_CREATED_CATEGORY",
    "parse_skill_md",
    "display_author",
    "display_updated",
    "display_version",
    "is_user_created_skill",
    "local_skill_author_name",
    "iter_skills",
    "list_skills",
    "skill_info",
    "installed_skill_names",
    "user_installed_skill_names",
    "discover_skills",
    "discover_ecosystem_skills",
    "build_skills_prompt",
    "build_skill_mention_context",
    "extract_skill_mentions",
    "detect_source_type",
    "install_skill",
    "npx_add",
    "fetch_latest_release",
    "fetch_repo_head_sha",
    "resolve_repo_remote_state",
    "check_github_skill_update",
    "get_cached_skills_update",
    "refresh_skills_update_cache",
    "upgrade_skills",
    "update_npx_skills_via_git",
    "remove_skill",
    "remove_all_skills",
    "set_skill_enabled",
    "CONFIG_DIR",
    "GLOBAL_SKILLS_DIR",
    "BUNDLED_SKILLS_DIR",
    "NPX_SKILLS_DIR",
    "NPX_INSTALL_ROOT",
    "MANIFEST_FILENAME",
    "SKILL_STATE_FILENAME",
    "DEFAULT_CATALOG",
    "SUGGESTED_SKILL_SOURCES",
    "GITHUB_API",
    "SKILLS_UPDATE_CACHE",
    "SKILLS_PROMPT_INDEX_CACHE",
]
