"""Pure helpers that assemble the Environment report from installed-package data."""

from __future__ import annotations

from agent_server.environment_catalog import (
    MANAGEABLE_GROUPS,
    is_core_package,
    normalize_package_name,
)
from agent_server.models import EnvironmentCorePackage, EnvironmentPackage, EnvironmentPackageGroup


def build_groups(installed: dict[str, str]) -> list[EnvironmentPackageGroup]:
    groups: list[EnvironmentPackageGroup] = []
    for group in MANAGEABLE_GROUPS:
        packages: list[EnvironmentPackage] = []
        for pkg in group.packages:
            key = normalize_package_name(pkg)
            version = installed.get(key)
            packages.append(
                EnvironmentPackage(
                    name=pkg,
                    version=version,
                    installed=version is not None,
                    removable=True,
                )
            )
        groups.append(
            EnvironmentPackageGroup(
                id=group.id,
                label=group.label,
                description=group.description,
                packages=packages,
            )
        )
    return groups


def build_core(installed: dict[str, str]) -> list[EnvironmentCorePackage]:
    core: list[EnvironmentCorePackage] = []
    for name, version in sorted(installed.items(), key=lambda item: item[0]):
        if not is_core_package(name):
            continue
        core.append(EnvironmentCorePackage(name=name, version=version))
    return core
