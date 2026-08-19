"""
Tool registry for ct.

Each tool is a Python function decorated with @tool that the agent can invoke.
Tools are organized by category (target, structure, chemistry, etc.).
"""

import importlib
import logging
import threading

from tools.registry import EXPERIMENTAL_CATEGORIES, Tool, ToolRegistry, registry

__all__ = [
    "EXPERIMENTAL_CATEGORIES",
    "Tool",
    "ToolRegistry",
    "registry",
    "ensure_loaded",
    "tool_load_errors",
]

_TOOL_MODULES = (
    "target",
    "structure",
    "chemistry",
    "expression",
    "viability",
    "biomarker",
    "combination",
    "clinical",
    "intel",
    "translational",
    "regulatory",
    "pk",
    "report",
    "literature",
    "safety",
    "cro",
    "compute",
    "experiment",
    "notification",
    "slack",
    "code",
    "files",
    "claude",
    "network",
    "genomics",
    "statistics",
    "repurposing",
    "design",
    "singlecell",
    "protein",
    "imaging",
    "data_api",
    "parity",
    "ops",
    "skills",
    "sites",
    "dna",
    "omics",
    "shell",
    "cellxgene",
    "clue",
    "remote_data",
)


# Import tool modules to trigger registration
def _load_tools():
    """Import all tool modules to register them."""
    logger = logging.getLogger("tools")
    errors = {}

    for module_name in _TOOL_MODULES:
        import_name = f"tools.{module_name}"
        try:
            importlib.import_module(import_name)
        except Exception as exc:
            errors[module_name] = str(exc)
            logger.warning("Failed to load tool module %s: %s", import_name, exc)

    return errors


# Lazy loading — tools are registered on first access
_loaded = False
_load_errors: dict[str, str] = {}
_load_lock = threading.Lock()


def ensure_loaded():
    global _loaded
    global _load_errors
    if _loaded:
        return
    with _load_lock:
        if _loaded:
            return
        _load_errors = _load_tools()
        _loaded = True


def tool_load_errors() -> dict[str, str]:
    """Return module import failures from tool loading."""
    return dict(_load_errors)
