"""
code.execute helpers for standalone Python script authoring.

Split from tools/code.py. Reads prompt templates from tools/code_prompts.py.
"""

import re
from pathlib import Path

from tools.code_prompts import SCRIPT_GEN_SYSTEM_PROMPT, SCRIPT_RETRY_PROMPT


def _extract_code(text: str) -> str:
    """Strip markdown code fences from LLM response if present."""
    text = text.strip()
    # Remove ```python ... ``` fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```python or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)
    return text


def _is_script_authoring_goal(goal: str) -> bool:
    """Return True when the goal is about writing/saving a standalone script file."""
    g = (goal or "").lower()
    if not g:
        return False
    explicit_script = any(
        phrase in g
        for phrase in (
            "write a python script",
            "create a python script",
            "save the script",
            "standalone file",
            "standalone script",
        )
    )
    has_py_target = ".py" in g and any(
        word in g for word in ("script", "save", "write", "create", "generate")
    )
    return explicit_script or has_py_target


def _extract_script_filename(goal: str) -> str:
    """Extract target script filename from the goal, defaulting safely."""
    text = goal or ""

    quoted = re.findall(r"""['"]([^'"]+\.py)['"]""", text, flags=re.IGNORECASE)
    for candidate in quoted:
        c = candidate.strip().rstrip(".,;:)")
        if c and not c.lower().startswith(("http://", "https://")):
            return c

    bare = re.findall(r"""\b([A-Za-z0-9_\-./]+\.py)\b""", text, flags=re.IGNORECASE)
    for candidate in bare:
        c = candidate.strip().rstrip(".,;:)")
        if c and not c.lower().startswith(("http://", "https://")):
            return c

    return "generated_script.py"


def _resolve_script_path(path_str: str) -> tuple[Path | None, str | None]:
    """Resolve a script path and enforce CWD containment."""
    p = Path(path_str).expanduser()
    if p.is_absolute():
        return None, "Absolute paths are not allowed for generated scripts."
    resolved = (Path.cwd() / p).resolve()
    try:
        resolved.relative_to(Path.cwd().resolve())
    except ValueError:
        return None, "Path traversal detected for generated script path."
    if resolved.suffix.lower() != ".py":
        return None, "Generated script path must end with .py."
    return resolved, None


def _generate_and_save_script(
    *,
    goal: str,
    llm,
    max_retries: int,
    session,
) -> dict:
    """Generate a standalone Python script and save it in the working directory."""
    filename = _extract_script_filename(goal)
    script_path, path_error = _resolve_script_path(filename)
    if path_error:
        return {
            "summary": f"Script generation failed: {path_error}",
            "error": path_error,
        }

    script_text = ""
    last_error = None
    for attempt in range(1, max_retries + 2):
        if attempt == 1:
            user_msg = (
                f"User request:\n{goal}\n\n"
                f"Write a complete standalone Python script for this request.\n"
                f"Target filename: {script_path.name}\n"
                f"The script must be directly runnable with `python {script_path.name}`."
            )
        else:
            user_msg = SCRIPT_RETRY_PROMPT.format(
                code=script_text, error=last_error or "Unknown syntax error"
            )

        with session.console.status(
            f"[green]{'Generating' if attempt == 1 else 'Fixing'} script...[/green]",
            spinner="dots",
        ):
            response = llm.chat(
                system=SCRIPT_GEN_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.2,
            )

        script_text = _extract_code(response.content)

        # Validate syntax before writing to disk.
        try:
            compile(script_text, str(script_path), "exec")
        except SyntaxError as e:
            last_error = f"{e.msg} (line {e.lineno})"
            if attempt > max_retries:
                break
            continue
        except Exception as e:
            last_error = str(e)
            if attempt > max_retries:
                break
            continue

        try:
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(script_text, encoding="utf-8")
        except Exception as e:
            return {
                "summary": f"Script generation failed while writing {script_path}: {e}",
                "error": str(e),
                "path": str(script_path),
            }

        lines = script_text.count("\n") + 1
        return {
            "summary": f"Generated standalone Python script: {script_path.name} ({lines} lines).",
            "path": str(script_path),
            "script": script_text,
            "lines": lines,
            "size": len(script_text),
            "exports": [str(script_path)],
            "result": {
                "summary": f"Script saved to {script_path}",
                "path": str(script_path),
            },
        }

    return {
        "summary": f"Script generation failed after {max_retries + 1} attempts: {last_error}",
        "error": last_error or "unknown_script_generation_error",
        "path": str(script_path),
        "script": script_text,
    }
