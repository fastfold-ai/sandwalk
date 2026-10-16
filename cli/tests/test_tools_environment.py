"""The agent-facing environment tools wrap the sandbox package service."""

from __future__ import annotations

from unittest.mock import patch

from agent_server.models import EnvironmentPackageMutationResult
from tools import ensure_loaded, registry


def test_environment_tools_are_registered_and_core():
    from agent.tool_tiers import is_core_tool

    ensure_loaded()
    install = registry.get_tool("environment.install_package")
    listing = registry.get_tool("environment.list_packages")
    assert install is not None and listing is not None
    assert is_core_tool("environment.install_package")
    assert is_core_tool("environment.list_packages")


def test_install_tool_allows_unlisted_and_reports_import():
    ensure_loaded()
    tool = registry.get_tool("environment.install_package")
    fake = EnvironmentPackageMutationResult(
        ok=True,
        action="install",
        name="pyfiglet",
        version="1.0.2",
        installed=True,
        message="Installed pyfiglet 1.0.2",
        import_module="pyfiglet",
    )
    with patch(
        "agent_server.environment_service.EnvironmentService.install",
        return_value=fake,
    ) as install:
        result = tool.function(name="pyfiglet")
    assert install.call_args.kwargs["allow_unlisted"] is True
    assert result["ok"] is True
    assert result["import_module"] == "pyfiglet"


def test_install_tool_refuses_core_dependency():
    ensure_loaded()
    tool = registry.get_tool("environment.install_package")
    result = tool.function(name="fastapi")
    assert result["ok"] is False
    assert "core" in result["error"].lower()


def test_ptc_mode_exposes_install_tool_directly():
    """In PTC mode the model must see install_package as a real tool call."""
    from types import SimpleNamespace

    from agent.deepagents_runtime.langchain_tools_setup import (
        build_ptc_domain_tools,
        make_unique_namer,
    )

    ensure_loaded()
    used: set[str] = set()
    display: dict[str, str] = {}
    session = SimpleNamespace(config={}, registry=registry)
    tools, _namespace = build_ptc_domain_tools(
        session,
        exclude_categories=set(),
        exclude_tools=set(),
        display_name_map=display,
        used_names=used,
        unique_name=make_unique_namer(used),
    )
    exposed = set(display.values())
    assert "shell.run" in exposed
    assert "environment.install_package" in exposed
    assert "environment.list_packages" in exposed
    assert len(tools) >= 4  # search_tools + the three direct tools


def test_list_tool_filters_by_substring():
    ensure_loaded()
    tool = registry.get_tool("environment.list_packages")
    with patch(
        "agent_server.storage_service.list_installed_packages",
        return_value=[("numpy", "2.0"), ("pandas", "2.2"), ("pyfiglet", "1.0")],
    ):
        result = tool.function(contains="py")
    names = [row["name"] for row in result["packages"]]
    assert names == ["numpy", "pyfiglet"]
    assert result["ok"] is True
