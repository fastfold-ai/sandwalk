"""Let the agent add Python packages to the sandbox it runs code in.

``run_python`` executes in the server process. These tools go through the same
service the Dashboard's sandbox catalog uses, so an install lands where that
interpreter can import it: the venv itself in a dev checkout, or the per-user
package folder when the runtime is sealed (the Mac app bundle).
"""

from __future__ import annotations

from tools import registry


@registry.register(
    name="environment.install_package",
    description=(
        "Install a Python package into the sandbox that run_python uses, then "
        "verify it imports. Works in the Mac app, where plain pip cannot write "
        "into the bundled interpreter. Core Sandwalk dependencies are refused."
    ),
    category="environment",
    parameters={
        "name": "PyPI distribution name, optionally with a version spec (e.g. 'biopython' or 'pyfiglet>=1.0')",
    },
    usage_guide=(
        "Call this before run_python when an import fails with ModuleNotFoundError. "
        "Do not use shell.run with pip or uv for this; it fails in the packaged app. "
        "The result includes import_module, the top-level name to import."
    ),
)
def environment_install_package(name: str = "", **kwargs) -> dict:
    from agent_server.environment_service import EnvironmentError, EnvironmentService

    spec = str(name or "").strip()
    if not spec:
        return {"ok": False, "error": "Package name is required."}
    try:
        result = EnvironmentService().install(spec, allow_unlisted=True)
    except EnvironmentError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": result.ok,
        "name": result.name,
        "version": result.version,
        "installed": result.installed,
        "import_module": result.import_module,
        "message": result.message,
    }


@registry.register(
    name="environment.list_packages",
    description=(
        "List Python packages the sandbox can import right now, with versions. "
        "Optionally filter by a substring of the name."
    ),
    category="environment",
    parameters={
        "contains": "Only return packages whose name contains this text (optional)",
    },
    usage_guide="Use to check whether a library is already available before installing it.",
)
def environment_list_packages(contains: str = "", **kwargs) -> dict:
    from agent_server.environment_service import active_user_site
    from agent_server.storage_service import list_installed_packages

    needle = str(contains or "").strip().lower()
    rows = [
        {"name": name, "version": version}
        for name, version in list_installed_packages()
        if not needle or needle in name.lower()
    ]
    site = active_user_site()
    return {
        "ok": True,
        "count": len(rows),
        "packages": rows[:300],
        "user_site": str(site) if site else None,
    }
