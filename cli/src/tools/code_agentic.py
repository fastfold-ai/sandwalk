"""
code.execute multi-turn agentic run_python loop.

Split from tools/code.py. Reads prompt templates from tools/code_prompts.py.
"""

from tools.code_prompts import REFLECTION_PROMPT, RUN_PYTHON_TOOL
from tools.code_script import _extract_code

__all__ = ["_agentic_code_loop"]


def _agentic_code_loop(
    *,
    goal: str,
    system_prompt: str,
    llm,
    sandbox,
    session,
    max_turns: int,
) -> dict:
    """Multi-turn agentic code execution loop.

    The LLM calls ``run_python`` repeatedly, seeing output after each
    execution, and stops when it has no more tool calls (``end_turn``).
    """
    messages = [{"role": "user", "content": f"Goal: {goal}"}]
    all_code: list[str] = []
    all_stdout: list[str] = []
    last_exec_result: dict | None = None

    for turn in range(max_turns):
        with session.console.status(
            f"[green]Agent turn {turn + 1}/{max_turns}...[/green]",
            spinner="dots",
        ):
            response = llm.chat(
                system=system_prompt,
                messages=messages,
                tools=[RUN_PYTHON_TOOL],
                temperature=0.2,
            )

        # Check for tool calls in the content blocks
        content_blocks = response.content_blocks or []
        tool_calls = [b for b in content_blocks if getattr(b, "type", None) == "tool_use"]

        if not tool_calls:
            # LLM is done (end_turn) — no more tool calls
            break

        # Process the first tool call
        tool_call = tool_calls[0]
        code = (tool_call.input or {}).get("code", "")
        all_code.append(code)

        exec_result = sandbox.execute(code)
        last_exec_result = exec_result

        # Collect stdout
        if exec_result.get("stdout"):
            all_stdout.append(exec_result["stdout"])

        # Build tool result content
        tool_output_parts = []
        if exec_result.get("stdout"):
            tool_output_parts.append(exec_result["stdout"])
        if exec_result.get("error"):
            tool_output_parts.append(f"Error:\n{exec_result['error']}")
        tool_output = "\n".join(tool_output_parts) if tool_output_parts else "(no output)"

        # Truncate to avoid blowing up context
        tool_output = tool_output[:5000]

        # Append assistant message (full content blocks) and tool result
        messages.append({"role": "assistant", "content": content_blocks})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": tool_output,
                    }
                ],
            }
        )

    # Extract result from sandbox namespace
    result_obj = sandbox.get_variable("result")
    combined_code = "\n\n# --- next turn ---\n\n".join(all_code)
    combined_stdout = "\n".join(all_stdout)

    # Reflection pass for multi-turn mode (parity with single-shot path):
    # when execution succeeds but constraints may be violated, ask the model
    # to self-check and optionally provide corrected code.
    max_reflect = int(session.config.get("sandbox.max_reflect", 2))
    for _ in range(max_reflect):
        if not combined_code:
            break
        result_preview = str(result_obj)[:1000] if result_obj else "(no result dict)"
        reflect_msg = REFLECTION_PROMPT.format(
            goal=goal,
            code=combined_code,
            stdout=combined_stdout[:3000],
            result=result_preview,
        )
        with session.console.status(
            "[cyan]Reviewing output...[/cyan]",
            spinner="dots",
        ):
            reflect_response = llm.chat(
                system=system_prompt,
                messages=[{"role": "user", "content": reflect_msg}],
                temperature=0.2,
            )
        reflect_text = (reflect_response.content or "").strip()
        if reflect_text.upper().startswith("LGTM"):
            break

        fixed_code = _extract_code(reflect_text)
        if not fixed_code:
            break

        exec_result = sandbox.execute(fixed_code)
        last_exec_result = exec_result
        all_code.append(fixed_code)
        if exec_result.get("stdout"):
            all_stdout.append(exec_result["stdout"])

        combined_code = "\n\n# --- next turn ---\n\n".join(all_code)
        combined_stdout = "\n".join(all_stdout)
        if exec_result.get("error"):
            break
        result_obj = sandbox.get_variable("result")

    # Collect plots/exports from the last execution (sandbox output dir)
    plots = []
    exports = []
    if last_exec_result:
        plots = last_exec_result.get("plots", [])
        exports = last_exec_result.get("exports", [])

    if result_obj and isinstance(result_obj, dict):
        summary = result_obj.get("summary", "")
    elif combined_stdout:
        summary = combined_stdout[-500:]
    else:
        summary = "Code executed successfully."

    if not result_obj and not combined_stdout and not all_code:
        return {
            "summary": "Agent loop completed but no code was executed.",
            "error": "LLM did not call run_python tool.",
            "code": "",
            "stdout": "",
        }

    return {
        "summary": summary,
        "code": combined_code,
        "stdout": combined_stdout,
        "result": result_obj,
        "plots": plots,
        "exports": exports,
    }
