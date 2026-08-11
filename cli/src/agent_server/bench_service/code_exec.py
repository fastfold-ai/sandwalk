"""Sandboxed code execution graders for MBPP / LiveCodeBench."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from typing import Any

EXEC_TIMEOUT_MBPP = 15
EXEC_TIMEOUT_LCB = 30
EXEC_MEMORY_LIMIT_BYTES = 256 * 1024 * 1024


def extract_python_code(response: str) -> str:
    """Prefer the last fenced code block (skip drafts), else heuristic scrape."""
    text = response or ""
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, flags=re.DOTALL | re.I)
    if blocks:
        return blocks[-1].strip()

    lines = text.strip().split("\n")
    code_lines: list[str] = []
    in_code = False
    for line in lines:
        if not in_code and (
            line.startswith("def ")
            or line.startswith("class ")
            or line.startswith("import ")
            or line.startswith("from ")
            or line.startswith("#")
        ):
            in_code = True
        if in_code:
            code_lines.append(line)
    return "\n".join(code_lines) if code_lines else text.strip()


def grade_code_exec(*, suite_id: str, source: dict[str, Any], predicted: str) -> bool:
    code = extract_python_code(predicted)
    if not code.strip():
        return False
    if suite_id == "mbpp":
        return _run_mbpp(code, source)
    if suite_id == "livecodebench":
        return _run_livecodebench(code, source)
    return False


def _run_mbpp(code: str, source: dict[str, Any]) -> bool:
    tests = list(source.get("test_list") or [])
    if not tests:
        return False
    setup = str(source.get("test_setup_code") or "")
    script = f"{setup}\n{code}\n" + "\n".join(tests) + "\n"
    ok, _ = _execute(script, stdin="", timeout=EXEC_TIMEOUT_MBPP)
    return ok


def _run_livecodebench(code: str, source: dict[str, Any]) -> bool:
    inputs = list(source.get("inputs") or [])[:3]
    outputs = list(source.get("outputs") or [])[:3]
    if not inputs or not outputs:
        return False
    for inp, expected_out in zip(inputs, outputs, strict=False):
        stdin = inp if isinstance(inp, str) else str(inp)
        expected = (
            expected_out.strip()
            if isinstance(expected_out, str)
            else str(expected_out).strip()
        )
        stdout, ok, _ = _execute_capture(code, stdin=stdin, timeout=EXEC_TIMEOUT_LCB)
        if not ok or stdout.strip() != expected:
            return False
    return True


def _execute(script: str, *, stdin: str, timeout: int) -> tuple[bool, str]:
    stdout, ok, err = _execute_capture(script, stdin=stdin, timeout=timeout)
    return ok, err or stdout


def _execute_capture(script: str, *, stdin: str, timeout: int) -> tuple[str, bool, str]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as fh:
        fh.write(script)
        tmp_path = fh.name
    try:
        kwargs: dict[str, Any] = {
            "args": ["python3", tmp_path],
            "input": stdin,
            "capture_output": True,
            "text": True,
            "timeout": timeout,
            "env": {
                "PATH": os.environ.get("PATH", "/usr/bin:/usr/local/bin"),
                "HOME": os.environ.get("HOME", "/tmp"),
                "LANG": "en_US.UTF-8",
            },
        }
        if os.name == "posix":
            kwargs["preexec_fn"] = _set_resource_limits
        result = subprocess.run(**kwargs)
        if result.returncode == 0:
            return result.stdout, True, ""
        return result.stdout, False, (result.stderr or "")[:500]
    except subprocess.TimeoutExpired:
        return "", False, "Execution timed out"
    except Exception as exc:  # noqa: BLE001
        return "", False, str(exc)[:500]
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _set_resource_limits() -> None:
    try:
        import resource

        resource.setrlimit(
            resource.RLIMIT_AS, (EXEC_MEMORY_LIMIT_BYTES, EXEC_MEMORY_LIMIT_BYTES)
        )
    except Exception:
        pass
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (35, 35))
    except Exception:
        pass


def parse_lcb_public_tests(raw: Any) -> tuple[list[str], list[str]]:
    if isinstance(raw, str):
        try:
            cases = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            cases = []
    else:
        cases = raw or []
    if not isinstance(cases, list):
        return [], []
    inputs = [tc.get("input", "") for tc in cases if isinstance(tc, dict)]
    outputs = [tc.get("output", "") for tc in cases if isinstance(tc, dict)]
    return inputs, outputs
