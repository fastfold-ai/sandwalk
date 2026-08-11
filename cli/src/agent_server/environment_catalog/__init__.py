"""Allowlists for Environment page package management.

Core CLI dependencies are locked. Skill/tool extras (+ known tool orphans)
are the only packages users may install or uninstall from the dashboard.

Split package — re-exports the public surface previously defined in
``agent_server/environment_catalog.py`` so existing imports keep working.
"""

from __future__ import annotations

from agent_server.environment_catalog.core_packages import CORE_PACKAGE_NAMES
from agent_server.environment_catalog.groups import MANAGEABLE_GROUPS, PackageGroup
from agent_server.environment_catalog.helpers import (
    is_core_package,
    is_manageable_package,
    manageable_package_names,
    normalize_package_name,
)

__all__ = [
    "CORE_PACKAGE_NAMES",
    "PackageGroup",
    "MANAGEABLE_GROUPS",
    "normalize_package_name",
    "manageable_package_names",
    "is_core_package",
    "is_manageable_package",
]
