"""Web-facing adapter around the CLI's canonical skill manager.

This is a package so catalog listing, Vercel OIDC auth, skills.sh search,
catalog detail/audit, and local install/remove/upgrade can live in their own
modules; :class:`SkillsService` composes them via mixins in
:mod:`agent_server.skills_service.core`. Import from
``agent_server.skills_service`` as before — this module re-exports the
public API.

``list_skills``, ``skill_info``, ``install_skill``, ``remove_skill``,
``upgrade_skills``, ``set_skill_enabled``, ``Config``, and ``urlopen`` stay
bound at this package-root level so tests that monkeypatch
``agent_server.skills_service.<name>`` keep working, and so mixin methods can
look up the patched versions through this package's namespace rather than a
direct import, matching this module's behavior from before the split.
"""

from __future__ import annotations

from urllib.request import urlopen

from agent.config import Config
from agent.skills import (
    install_skill,
    list_skills,
    remove_skill,
    set_skill_enabled,
    skill_info,
    upgrade_skills,
)
from agent_server.skills_service.core import SkillsService

__all__ = [
    "Config",
    "SkillsService",
    "install_skill",
    "list_skills",
    "remove_skill",
    "set_skill_enabled",
    "skill_info",
    "upgrade_skills",
    "urlopen",
]
