"""Pure helpers for resolving/reporting package install & uninstall mutations."""

from __future__ import annotations

from agent_server.environment_catalog import MANAGEABLE_GROUPS, normalize_package_name
from agent_server.models import EnvironmentPackageMutationResult


def resolve_canonical_display(raw: str) -> str:
    """Prefer catalog spelling for a package name when present."""
    canonical = normalize_package_name(raw)
    for group in MANAGEABLE_GROUPS:
        for pkg in group.packages:
            if normalize_package_name(pkg) == canonical:
                return pkg
    return raw


def build_mutation_result(
    action: str,
    canonical_display: str,
    installed: dict[str, str],
) -> EnvironmentPackageMutationResult:
    key = normalize_package_name(canonical_display)
    version = installed.get(key)
    return EnvironmentPackageMutationResult(
        ok=True,
        action=action,  # type: ignore[arg-type]
        name=canonical_display,
        version=version,
        installed=version is not None,
        message=(
            f"{'Installed' if action == 'install' else 'Removed'} {canonical_display}"
            + (f" {version}" if version and action == "install" else "")
        ),
    )
