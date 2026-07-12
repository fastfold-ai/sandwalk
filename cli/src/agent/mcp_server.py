"""
Shared tool handlers for the deepagents runtime.

Wraps the ct ToolRegistry so each registered tool can be invoked as a handler,
and provides the persistent ``run_python`` / ``run_r`` sandbox handlers used by
the deepagents LangChain tool layer.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("mcp_server")


# ---------------------------------------------------------------------------
# Tool result formatting
# ---------------------------------------------------------------------------

def _format_tool_result(result: Any, max_chars: int = 8000) -> str:
    """Format a ct tool result dict into text for the Agent SDK."""
    if not isinstance(result, dict):
        text = str(result)
        return text[:max_chars] if len(text) > max_chars else text

    parts = []

    # Summary first (most important)
    summary = result.get("summary", "")
    if summary:
        parts.append(summary)

    # Include key data fields
    skip = {"summary"}
    compact = {"top_hits", "top_terms"}
    for key, val in result.items():
        if key in skip:
            continue
        if key in compact and isinstance(val, (dict, list)):
            count = len(val)
            parts.append(f"{key}: {type(val).__name__} with {count} entries")
            continue
        val_str = str(val)
        if len(val_str) > 1500:
            val_str = val_str[:1500] + f"... [{len(val_str)} chars total]"
        parts.append(f"{key}: {val_str}")

    text = "\n".join(parts)
    return text[:max_chars] if len(text) > max_chars else text


# ---------------------------------------------------------------------------
# Convert ct Tool.parameters to JSON Schema
# ---------------------------------------------------------------------------

_PY_TYPE_MAP = {
    "str": "string",
    "string": "string",
    "int": "integer",
    "integer": "integer",
    "float": "number",
    "number": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "list": "array",
    "dict": "object",
}


def _params_to_json_schema(parameters: dict) -> dict:
    """Convert a ct tool parameters dict to a JSON Schema object.

    ct tools describe parameters as ``{param_name: description_string}``.
    We map these to string-typed JSON Schema properties since the LLM
    produces string values that tools coerce internally.
    """
    if not parameters:
        return {"type": "object", "properties": {}}

    properties = {}
    for name, desc in parameters.items():
        # Extract type hint from description if present (e.g., "gene name (str)")
        prop = {"type": "string", "description": str(desc)}
        properties[name] = prop

    return {
        "type": "object",
        "properties": properties,
    }


# ---------------------------------------------------------------------------
# Create MCP tools from registry
# ---------------------------------------------------------------------------

def _make_tool_handler(tool_obj, session):
    """Create an async handler for a registry tool.

    The handler runs the synchronous tool function in a thread to avoid
    blocking the event loop.
    """

    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        # Inject session and prior results (empty for SDK mode)
        call_args = dict(args)
        call_args["_session"] = session
        call_args["_prior_results"] = {}

        # Coerce string values to numeric types when they look like numbers.
        # MCP sends all parameters as strings, but tools often expect int/float.
        for key, val in list(call_args.items()):
            if key.startswith("_"):
                continue
            if isinstance(val, str):
                # Try int first, then float
                try:
                    call_args[key] = int(val)
                    continue
                except ValueError:
                    pass
                try:
                    call_args[key] = float(val)
                    continue
                except ValueError:
                    pass
                # Boolean coercion
                if val.lower() in ("true", "false"):
                    call_args[key] = val.lower() == "true"

        try:
            result = await asyncio.to_thread(tool_obj.run, **call_args)
            text = _format_tool_result(result)
        except Exception as e:
            logger.warning("Tool %s raised: %s", tool_obj.name, e)
            text = f"Error: {e}"
            return {
                "content": [{"type": "text", "text": text}],
                "is_error": True,
            }

        return {"content": [{"type": "text", "text": text}]}

    return handler


# ---------------------------------------------------------------------------
# run_python sandbox tool
# ---------------------------------------------------------------------------

def _make_run_python_handler(session, code_trace_buffer: list | None = None,
                             tools_namespace=None):
    """Create the run_python MCP tool handler with a persistent Sandbox.

    The sandbox is created lazily on first invocation and persists across
    tool calls within one query (variables carry over). A new MCP server
    (and thus a new sandbox) is created for each query, so state resets
    between queries automatically.

    Args:
        session: Active ct Session.
        code_trace_buffer: Optional shared list. When provided, the handler
            appends structured execution metadata after each call. This
            bypasses the SDK message stream (which may truncate tool results)
            so the trace collector gets full code, stdout, and plot data.
        tools_namespace: Optional Programmatic Tool Calling (PTC) namespace of
            domain-tool callables to bind as ``tools`` in the sandbox. See
            :mod:`agent.ptc_tools`.
    """
    from agent.sandbox import Sandbox

    config = session.config
    timeout = int(config.get("sandbox.timeout", 300))
    output_dir = config.get("sandbox.output_dir")
    max_retries = int(config.get("sandbox.max_retries", 2))

    extra_read_dirs = []
    extra_read_str = config.get("sandbox.extra_read_dirs")
    if extra_read_str:
        for d in str(extra_read_str).split(","):
            d = d.strip()
            if d and Path(d).exists():
                extra_read_dirs.append(Path(d))

    sandbox = Sandbox(
        timeout=timeout,
        output_dir=output_dir,
        max_retries=max_retries,
        extra_read_dirs=extra_read_dirs or None,
    )
    sandbox.load_datasets()
    if tools_namespace is not None:
        sandbox.inject_tools(tools_namespace)

    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        code = args.get("code", "")
        if not code.strip():
            return {
                "content": [{"type": "text", "text": "Error: no code provided"}],
                "is_error": True,
            }

        exec_result = await asyncio.to_thread(sandbox.execute, code)

        # Build output text
        parts = []
        if exec_result.get("stdout"):
            parts.append(exec_result["stdout"])
        if exec_result.get("error"):
            parts.append(f"Error:\n{exec_result['error']}")
        if exec_result.get("plots"):
            parts.append(f"Plots saved: {exec_result['plots']}")
        if exec_result.get("exports"):
            parts.append(f"Exports saved: {exec_result['exports']}")

        # Check if the code set a `result` variable
        result_var = sandbox.get_variable("result")
        if result_var and isinstance(result_var, dict):
            summary = result_var.get("summary", "")
            answer = result_var.get("answer", "")
            if summary:
                parts.append(f"\nResult summary: {summary}")
            if answer:
                parts.append(f"Result answer: {answer}")

        text = "\n".join(parts) if parts else "(no output)"
        # Cap output to keep context manageable
        text = text[:6000]

        # Buffer structured execution metadata for trace capture.
        # This bypasses the SDK stream which may truncate tool results.
        if code_trace_buffer is not None:
            code_trace_buffer.append({
                "tool": "run_python",
                "code": code,
                "stdout": exec_result.get("stdout", ""),
                "plots": exec_result.get("plots", []),
                "exports": exec_result.get("exports", []),
                "error": exec_result.get("error"),
            })

        is_error = bool(exec_result.get("error"))
        return {
            "content": [{"type": "text", "text": text}],
            "is_error": is_error,
        }

    return handler, sandbox


# ---------------------------------------------------------------------------
# run_r tool — first-class R execution via rpy2
# ---------------------------------------------------------------------------

def _make_run_r_handler(code_trace_buffer: list | None = None):
    """Create the run_r MCP tool handler for R code execution.

    Uses rpy2 to execute R code. The global R session persists across calls
    (packages stay loaded, variables carry over within a query).
    """

    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        code = args.get("code", "")
        if not code.strip():
            return {
                "content": [{"type": "text", "text": "Error: no R code provided"}],
                "is_error": True,
            }

        def _exec_r(code: str) -> str:
            try:
                import rpy2.robjects as ro
                from rpy2.robjects import numpy2ri, pandas2ri

                # Use capture.output to grab all printed/cat output
                # Wrap user code in braces so multi-line code works
                wrapper = f"paste(capture.output({{ {code} }}), collapse='\\n')"

                try:
                    captured = ro.r(wrapper)
                    output_text = str(captured[0]) if captured else ""
                except Exception:
                    # If capture.output fails (syntax error etc), run directly
                    # to get the actual R error message
                    try:
                        result = ro.r(code)
                        output_text = str(result)[:3000]
                    except Exception as e2:
                        return f"R Error: {e2}"

                # Also get the return value of the last expression
                # by running the code directly (capture.output eats return values)
                result_text = ""
                try:
                    result = ro.r(code)
                    if result is not None and result != ro.NULL:
                        numpy2ri.activate()
                        pandas2ri.activate()
                        try:
                            if hasattr(result, '__len__') and len(result) == 1:
                                result_text = f"\nReturn value: {float(result[0])}"
                            elif hasattr(result, '__len__') and len(result) <= 50:
                                vals = [str(x) for x in result]
                                result_text = f"\nReturn value: [{', '.join(vals)}]"
                            else:
                                result_text = f"\nReturn value: {str(result)[:2000]}"
                        except Exception:
                            result_text = f"\nReturn value: {str(result)[:2000]}"
                        finally:
                            numpy2ri.deactivate()
                            pandas2ri.deactivate()
                except Exception:
                    pass  # Already captured output above

                return (output_text + result_text).strip() or "(no output)"

            except Exception as e:
                return f"R Error: {e}"

        text = await asyncio.to_thread(_exec_r, code)
        text = text[:6000]
        is_error = text.startswith("R Error:")

        # Buffer structured execution metadata for trace capture.
        if code_trace_buffer is not None:
            code_trace_buffer.append({
                "tool": "run_r",
                "code": code,
                "stdout": text,
                "error": text if is_error else None,
            })

        return {
            "content": [{"type": "text", "text": text}],
            "is_error": is_error,
        }

    return handler

