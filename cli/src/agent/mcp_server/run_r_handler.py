"""The run_r MCP tool handler — first-class R execution via rpy2."""

from __future__ import annotations

import asyncio
from typing import Any


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
