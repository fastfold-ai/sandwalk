"""
Interactive terminal for ct.

Provides a REPL-style interface for continuous research sessions.

This package is split by responsibility:
    slash_commands.py  — SLASH_COMMANDS registry
    mentions.py         — @ mention parsing, dataset candidates, LLM-output helpers
    completion.py        — prompt_toolkit completers (slash + mention)
    key_bindings.py      — custom prompt_toolkit key bindings
    plan_preview.py       — Rich rendering of a plan for approval
    interactive.py       — the InteractiveTerminal REPL itself

A handful of third-party names (``Console``, ``PromptSession``,
``patch_stdout``) and stdlib modules (``threading``, ``time``, ``urllib``,
``Path``) are re-exported here — and looked up through this package's
namespace at call time in ``interactive.py`` — so that existing tests can
keep monkeypatching them as ``ui.terminal.<name>``.
"""

import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

from .completion import MentionCompleter, MergedCompleter, PT_STYLE, SlashCompleter
from .interactive import (
    AVAILABLE_MODELS,
    DEFAULT_SUGGESTIONS,
    InteractiveTerminal,
)
from .key_bindings import _build_key_bindings
from .mentions import (
    DATASET_CANDIDATES,
    KNOWN_DATASETS,
    MentionCandidate,
    _extract_llm_suggestions,
    _get_workflow_names,
    _is_openai_managed_base_url,
    build_mention_context,
    extract_mentions,
)
from .plan_preview import render_plan_preview
from .slash_commands import SLASH_COMMANDS

__all__ = [
    "AVAILABLE_MODELS",
    "Console",
    "DATASET_CANDIDATES",
    "DEFAULT_SUGGESTIONS",
    "InteractiveTerminal",
    "KNOWN_DATASETS",
    "MentionCandidate",
    "MentionCompleter",
    "MergedCompleter",
    "PT_STYLE",
    "Path",
    "PromptSession",
    "SLASH_COMMANDS",
    "SlashCompleter",
    "_build_key_bindings",
    "_extract_llm_suggestions",
    "_get_workflow_names",
    "_is_openai_managed_base_url",
    "build_mention_context",
    "extract_mentions",
    "patch_stdout",
    "render_plan_preview",
    "threading",
    "time",
    "urllib",
]
