"""
Code generation and execution tool for ct.

Generates Python code from natural language goals and executes it
in a sandboxed environment with access to loaded datasets and
scientific Python libraries.

Split across tools/code_prompts.py (small prompt templates + run_python tool
schema), tools/code_prompts_bio.py (bioinformatics prompt), tools/code_script.py
(standalone script authoring), tools/code_agentic.py (multi-turn run_python
loop), and tools/code_exec.py (sandbox orchestration + the registered
``code.execute`` tool); re-exported here for backward compatibility. This
module is the canonical patch target for tests (e.g.
``patch("tools.code._generate_and_execute_code")``); submodules access this
helper indirectly via ``from tools import code as _code`` so that such
patches take effect regardless of which submodule performs the call.
"""

from tools.code_agentic import _agentic_code_loop
from tools.code_exec import _describe_data_files, _generate_and_execute_code, execute
from tools.code_prompts import (
    AGENTIC_CODE_ADDENDUM,
    CODE_GEN_SYSTEM_PROMPT,
    ERROR_RETRY_PROMPT,
    REFLECTION_PROMPT,
    RUN_PYTHON_TOOL,
    SCRIPT_GEN_SYSTEM_PROMPT,
    SCRIPT_RETRY_PROMPT,
)
from tools.code_prompts_bio import BIOINFORMATICS_CODE_GEN_PROMPT
from tools.code_script import (
    _extract_code,
    _extract_script_filename,
    _generate_and_save_script,
    _is_script_authoring_goal,
    _resolve_script_path,
)

__all__ = [
    "CODE_GEN_SYSTEM_PROMPT",
    "BIOINFORMATICS_CODE_GEN_PROMPT",
    "RUN_PYTHON_TOOL",
    "AGENTIC_CODE_ADDENDUM",
    "SCRIPT_GEN_SYSTEM_PROMPT",
    "ERROR_RETRY_PROMPT",
    "REFLECTION_PROMPT",
    "SCRIPT_RETRY_PROMPT",
    "_extract_code",
    "_is_script_authoring_goal",
    "_extract_script_filename",
    "_resolve_script_path",
    "_generate_and_save_script",
    "_agentic_code_loop",
    "_generate_and_execute_code",
    "_describe_data_files",
    "execute",
]
