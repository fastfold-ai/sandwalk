"""Persistent run_python / optional run_r sandbox tool attachment."""

from __future__ import annotations

import logging
import os
from typing import Any

from agent.deepagents_runtime.tool_adapter import _args_schema_for, _make_lc_tool

logger = logging.getLogger("deepagents_runtime")


def _r_support_enabled() -> bool:
    """R/rpy2 is opt-in — probing rpy2 every session boot is expensive and noisy."""
    return os.environ.get("SANDWALK_ENABLE_R", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def attach_sandbox_tools(
    tools: list[Any],
    session,
    *,
    code_trace_buffer: list[dict],
    tools_namespace,
    session_id: str | None,
    display_name_map: dict[str, str],
    used_names: set[str],
    ptc: bool,
) -> Any:
    """Append run_python (+ run_r only when ``SANDWALK_ENABLE_R`` is set)."""
    from agent.mcp_server import _make_run_python_handler, _make_run_r_handler

    rp_handler, sandbox = _make_run_python_handler(
        session,
        code_trace_buffer,
        tools_namespace=tools_namespace,
        session_id=session_id,
    )
    display_name_map["run_python"] = "run_python"
    used_names.add("run_python")
    rp_description = (
        "Execute Python code in a persistent sandbox. Variables persist "
        "between calls on the host CT sandbox. Pre-imported on host: pd, np, "
        "plt, sns, scipy_stats, sklearn, json, re, math, Path, "
        "safe_subprocess_run. Save plots to OUTPUT_DIR. When done, assign "
        "result = {'summary': '...', 'answer': '...'}. "
        "IMPORTANT: when a Modal sandbox is attached for this chat, general "
        "Python (no tools.* calls) is executed inside Modal under /workspace "
        "(remote Linux). Code that calls tools.<category>.<name>(...) stays "
        "on the host. Prefer /workspace paths for Modal runs; do not mkdir "
        "/workspace on the host."
    )
    if ptc:
        rp_description += (
            " The full domain-tool library is pre-bound as `tools` — call "
            "tools.<category>.<name>(**kwargs) -> dict and process results here; "
            "only what you print returns. Use tools.search('...') or the "
            "search_tools tool to find signatures. Domain-tool calls always "
            "run on the host even when Modal is attached."
        )
    tools.append(
        _make_lc_tool(
            name="run_python",
            description=rp_description,
            args_schema=_args_schema_for("run_python", None, required_code=True),
            handler=rp_handler,
            strip_none=False,
        )
    )

    if _r_support_enabled():
        try:
            import importlib.util

            if importlib.util.find_spec("rpy2.robjects") is None:
                raise ImportError("rpy2 unavailable")
            # find_spec succeeds even when R_HOME is missing — probe a real import.
            import rpy2.robjects  # noqa: F401

            rr_handler = _make_run_r_handler(code_trace_buffer)
            display_name_map["run_r"] = "run_r"
            used_names.add("run_r")
            tools.append(
                _make_lc_tool(
                    name="run_r",
                    description=(
                        "Execute R code via rpy2 for statistical workflows (splines, "
                        "p.adjust, wilcox.test, fisher.test, lm/predict, KEGGREST)."
                    ),
                    args_schema=_args_schema_for("run_r", None, required_code=True),
                    handler=rr_handler,
                    strip_none=False,
                )
            )
        except Exception as exc:
            logger.info("rpy2 not available — run_r tool disabled (%s)", exc)

    return sandbox
