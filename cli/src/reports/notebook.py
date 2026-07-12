"""Convert agent trace JSONL files to Jupyter notebooks."""

from __future__ import annotations

import json
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook, new_output


def _load_events(trace_path: Path) -> list[dict]:
    events: list[dict] = []
    text = trace_path.read_text(encoding="utf-8").strip()
    if not text:
        return events
    for line in text.splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def _header_cell(query: str, *, query_index: int) -> str:
    if query_index <= 1:
        return f"# Fastfold Agent Session\n\n**Query:** {query}\n"
    return f"---\n\n## Query {query_index}: {query}\n"


def _tool_markdown(tool: str, result_text: str, is_error: bool) -> str:
    status = "Error" if is_error else "Result"
    return f"### Tool: `{tool}`\n\n**{status}:**\n\n{result_text}\n"


def _code_outputs(event: dict) -> list:
    outputs = []
    stdout = event.get("stdout") or ""
    if stdout:
        text = stdout if isinstance(stdout, list) else stdout.splitlines(keepends=True)
        outputs.append(new_output(output_type="stream", name="stdout", text=text))

    if event.get("is_error"):
        error = event.get("error") or event.get("result_text") or "Execution failed"
        lines = str(error).splitlines()
        outputs.append(
            new_output(
                output_type="error",
                ename="ExecutionError",
                evalue=lines[-1] if lines else "Execution failed",
                traceback=lines,
            )
        )

    for plot in event.get("plots_base64") or []:
        data = plot.get("data", "")
        mime = plot.get("mime", "image/png")
        outputs.append(new_output(output_type="display_data", data={mime: data}, metadata={}))

    return outputs


def trace_to_notebook(trace_path: Path | str) -> nbformat.NotebookNode:
    """Convert a trace JSONL file into a Jupyter notebook."""
    trace_path = Path(trace_path)
    if not trace_path.exists():
        raise FileNotFoundError(str(trace_path))

    events = _load_events(trace_path)
    if not events:
        nb = new_notebook()
        nb.cells.append(new_markdown_cell("No agent activity recorded in this trace."))
        nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
        return nb

    cells = []
    query_index = 0
    pending_code: dict[str, dict] = {}

    for event in events:
        etype = event.get("type")

        if etype == "query_start":
            query_index += 1
            cells.append(new_markdown_cell(_header_cell(event.get("query", ""), query_index=query_index)))

        elif etype == "text":
            content = event.get("content", "").strip()
            if content:
                cells.append(new_markdown_cell(content))

        elif etype == "tool_start":
            tool_use_id = event.get("tool_use_id")
            if tool_use_id:
                pending_code[tool_use_id] = event

        elif etype == "tool_result":
            tool = event.get("tool", "tool")
            tool_use_id = event.get("tool_use_id")
            start = pending_code.pop(tool_use_id, {}) if tool_use_id else {}
            code = event.get("code") or (start.get("input") or {}).get("code", "")

            if tool in {"run_python", "run_r"} and code:
                source = f"%%R\n{code}" if tool == "run_r" else code
                cell = new_code_cell(source)
                cell.outputs = _code_outputs(event)
                cells.append(cell)
            else:
                cells.append(
                    new_markdown_cell(
                        _tool_markdown(tool, event.get("result_text", ""), bool(event.get("is_error")))
                    )
                )

    nb = new_notebook(cells=cells)
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    return nb


def save_notebook(nb: nbformat.NotebookNode, out_path: Path | str) -> Path:
    """Write a notebook to disk, creating parent directories as needed."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, str(out_path))
    return out_path
