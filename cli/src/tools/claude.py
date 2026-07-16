"""
Claude reasoning tools and Claude Code integration for ct.

Uses Claude as a reasoning engine for open-ended questions that don't fit
pre-built tools, and delegates complex coding/editing tasks to Claude Code CLI.

Split across claude_reason.py, claude_summarize.py, and claude_code.py
(+ claude_prompts.py for shared prompts/context helper); re-exported here
for backward compatibility.
"""

from tools.claude_code import code
from tools.claude_prompts import _build_context_section
from tools.claude_reason import compare, reason
from tools.claude_summarize import summarize

__all__ = ["reason", "compare", "summarize", "code", "_build_context_section"]
