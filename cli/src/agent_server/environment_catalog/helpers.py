"""Name normalization helpers for the Environment page package catalog."""

from __future__ import annotations

from agent_server.environment_catalog.core_packages import CORE_PACKAGE_NAMES
from agent_server.environment_catalog.groups import MANAGEABLE_GROUPS


def normalize_package_name(name: str) -> str:
    """Normalize a PyPI name for comparison (PEP 503-ish)."""
    return name.strip().lower().replace("_", "-")


def manageable_package_names() -> frozenset[str]:
    names: set[str] = set()
    for group in MANAGEABLE_GROUPS:
        for pkg in group.packages:
            names.add(normalize_package_name(pkg))
    return frozenset(names)


def is_core_package(name: str) -> bool:
    return normalize_package_name(name) in {
        normalize_package_name(item) for item in CORE_PACKAGE_NAMES
    }


def is_manageable_package(name: str) -> bool:
    return normalize_package_name(name) in manageable_package_names()
