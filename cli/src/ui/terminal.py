"""
Interactive terminal for ct.

Provides a REPL-style interface for continuous research sessions.
"""

import random
import re
import shlex
import shutil
import subprocess
import time
import threading
import json
import os
from collections import deque
from dataclasses import dataclass
import urllib.error
import urllib.request
from urllib.parse import urlparse, urlunparse
from typing import Any, Callable

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown as RichMarkdown
from ui.markdown import LeftMarkdown, print_markdown_with_mermaid
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.filters import has_completions
from prompt_toolkit.formatted_text import HTML, ANSI
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from pathlib import Path


@dataclass
class MentionCandidate:
    """A candidate item for the @ mention autocomplete."""
    name: str          # e.g., "target.coessentiality" or "depmap"
    kind: str          # "tool", "database", or "file"
    category: str      # e.g., "target", "dataset", "file"
    description: str   # truncated for display


# Slash commands available in the interactive terminal
SLASH_COMMANDS = {
    "/help": "Show command reference with examples",
    "/tools": "List all tools with status (stable/experimental)",
    "/data": "Manage local datasets (/data list | status | pull <name> | pull-all)",
    "/skills": "List currently loaded skills",
    "/skills-add": "Install a skill from GitHub/local path/name",
    "/skills-find": "Discover installable skills from the catalog",
    "/skills-upgrade": "Sync the Fastfold catalog and update installed skills",
    "/skills-remove": "Remove a globally-installed skill",
    "/model": "Switch LLM model/provider interactively",
    "/settings": "Configure UI and agent preferences",
    "/config": "Show active runtime configuration",
    "/keys": "Show API key status (/keys profile | /keys set-compatible | /keys set-boltz)",
    "/mcp": "List and manage MCP servers (/mcp connect|enable|validate|add|remove)",
    "/model-manager": "Manage OpenAI-compatible profiles (add/edit/delete)",
    "/upgrade": "Upgrade fastfold-agent-cli via uv",
    "/doctor": "Run readiness diagnostics and fix hints",
    "/usage": "Show session token/cost usage",
    "/tasks": "Show background task watcher status (/tasks refresh for live probe)",
    "/interrupt": "Interrupt the active generation (add ! to force)",
    "/copy": "Copy the last answer to clipboard",
    "/export": "Export current session transcript to markdown",
    "/export-share": "Export session, send to Slack, and save to library",
    "/notebook": "Export current session as Jupyter notebook (.ipynb)",
    "/compact": "Compress session context for longer runs",
    "/agents": "Run a query with N parallel research agents",
    "/new": "Start a new empty session",
    "/sessions": "List saved sessions (or delete: /sessions delete <id>)",
    "/sync": "Import legacy CLI sessions into the shared UI database",
    "/resume": "Resume a previous session by id/index",
    "/case-study": "Run/list curated case studies (/case-study list)",
    "/plan": "Toggle plan mode — preview & approve before executing",
    "/clear": "Clear the screen",
    "/exit": "Exit the terminal",
}

# Models available for switching, grouped by provider
from agent.model_catalog import terminal_available_models

AVAILABLE_MODELS = terminal_available_models()

from ui.suggestions import DEFAULT_SUGGESTIONS

_ANTHROPIC_MODEL_IDS = {m[0] for m in AVAILABLE_MODELS.get("anthropic", [])}
_BOLTZ_SKILL_SOURCE = "fastfold-ai/skills@skills/boltz"
_BOLTZ_INSTALL_SCRIPT = "set -euo pipefail; curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"


def _is_openai_managed_base_url(base_url: str | None) -> bool:
    """Return True for OpenAI-managed API hosts."""
    value = str(base_url or "").strip()
    if not value:
        return True
    try:
        host = (urlparse(value).hostname or "").strip().lower()
    except Exception:
        return False
    if not host:
        return False
    return host == "api.openai.com" or host.endswith(".openai.com")


# ---------------------------------------------------------------------------
# @ Mention: datasets and completer
# ---------------------------------------------------------------------------

DATASET_CANDIDATES = [
    ("depmap", "dataset", "DepMap CRISPR/model data"),
    ("prism", "dataset", "PRISM drug sensitivity"),
    ("l1000", "dataset", "L1000 gene expression signatures"),
    ("proteomics", "dataset", "Proteomics log2FC matrix"),
    ("msigdb", "dataset", "MSigDB gene sets"),
    ("string", "dataset", "STRING protein interaction network"),
]

KNOWN_DATASETS = frozenset(d[0] for d in DATASET_CANDIDATES)


def _get_workflow_names() -> frozenset[str]:
    """Lazily load workflow names."""
    try:
        from agent.workflows import WORKFLOWS
        return frozenset(WORKFLOWS.keys())
    except Exception:
        return frozenset()


def extract_mentions(text: str):
    """Parse @mentions from input text.

    Returns:
        tuple of (cleaned_query, tool_names, dataset_names, workflow_names)
    """
    dataset_names_set = {d[0] for d in DATASET_CANDIDATES}
    workflow_names_set = _get_workflow_names()
    tool_pattern = re.compile(r"@(\w+\.\w+)")
    word_pattern = re.compile(r"@(\w+)")

    tools = []
    datasets = []
    workflows = []

    # Find @category.tool_name mentions first
    for m in tool_pattern.finditer(text):
        tools.append(m.group(1))

    # Find @dataset and @workflow mentions (single word, no dot)
    cleaned = tool_pattern.sub("", text)
    for m in word_pattern.finditer(cleaned):
        name = m.group(1)
        if name in dataset_names_set:
            datasets.append(name)
        elif name in workflow_names_set:
            workflows.append(name)

    # Strip all recognized @mentions from query
    query = re.sub(r"@\w+(?:\.\w+)?", "", text).strip()
    # Collapse multiple spaces
    query = re.sub(r"\s{2,}", " ", query)

    return query, tools, datasets, workflows


def build_mention_context(tools: list[str], datasets: list[str], workflows: list[str] | None = None) -> str:
    """Build context string from extracted mentions for planner injection."""
    parts = []
    if tools:
        tool_list = ", ".join(tools)
        parts.append(
            f"User specifically requested these tools: {tool_list}. "
            f"You MUST include these tools in your plan."
        )
    if datasets:
        for ds in datasets:
            desc = next(
                (d[2] for d in DATASET_CANDIDATES if d[0] == ds), ds
            )
            parts.append(f"User requested dataset: {ds} ({desc}).")
    if workflows:
        try:
            from agent.workflows import WORKFLOWS
            for wf_name in workflows:
                wf = WORKFLOWS.get(wf_name)
                if wf:
                    steps = ", ".join(s["tool"] for s in wf.get("steps", []))
                    parts.append(
                        f"User requested workflow '{wf_name}': {wf['description']}. "
                        f"Follow this tool sequence: {steps}"
                    )
        except Exception:
            pass
    return "\n".join(parts)



def _extract_llm_suggestions(synthesis_text: str) -> list[str]:
    """Extract follow-up suggestions from the LLM synthesis output.

    Looks for a 'Suggested Next Steps' section and extracts bullet/numbered items.
    Handles various formats: **"quoted text"**, plain bullets, numbered lists.
    """
    suggestions = []
    in_section = False

    for line in synthesis_text.split("\n"):
        stripped = line.strip()

        # Detect the suggested next steps section
        if "suggested next" in stripped.lower() or "follow-up" in stripped.lower():
            if stripped.startswith("#") or stripped.startswith("**"):
                in_section = True
                continue

        if in_section:
            # Stop at next heading (not related to suggestions)
            if stripped.startswith("#") and "suggested" not in stripped.lower() and "follow" not in stripped.lower():
                break
            # Extract bullet items (-, *, 1., 2., etc.)
            if stripped and (stripped[0] in "-*" or (len(stripped) > 1 and stripped[0].isdigit() and stripped[1] in ".)")):
                # Remove bullet prefix
                text = stripped.lstrip("-*0123456789.) ").strip()
                # Extract quoted text from **"..."** or "..." patterns
                quoted = re.findall(r'["\u201c]([^"\u201d]+)["\u201d]', text)
                if quoted:
                    # Use the longest quoted string (the actual query)
                    text = max(quoted, key=len)
                else:
                    # Remove markdown formatting
                    text = text.strip("`").strip("*").strip("_")
                # Skip if it's a header or too short
                if len(text) > 10 and not text.startswith("#"):
                    suggestions.append(text)

    return suggestions[:5]





# prompt_toolkit style — dim ghost text, colored prompt, dark completion menu
PT_STYLE = Style.from_dict({
    "prompt": "bold #50fa7b",
    "placeholder": "#555555",
    # Force plain, non-reversed toolbar text so no default
    # prompt_toolkit badge/background styling bleeds through.
    "bottom-toolbar": "noinherit noreverse #8a8f98 bg:default",
    "bottom-toolbar.text": "noinherit noreverse #8a8f98 bg:default",
    # Completion menu — dark background so mention colors stay readable
    "completion-menu": "bg:#1a1a2e #cccccc",
    "completion-menu.completion": "bg:#1a1a2e #cccccc",
    "completion-menu.completion.current": "bg:#333355 #ffffff bold",
    "completion-menu.meta.completion": "bg:#1a1a2e #888888",
    "completion-menu.meta.completion.current": "bg:#333355 #aaaaaa",
    "scrollbar.background": "bg:#1a1a2e",
    "scrollbar.button": "bg:#333355",
    # Mention kind colors
    "mention-tool": "#00d7ff",     # cyan for tool mentions
    "mention-dataset": "#50fa7b",  # green for dataset mentions
    "mention-file": "#ffd700",     # yellow for file mentions
    "mention-workflow": "#ff79c6",  # pink for workflow mentions
})


class SlashCompleter(Completer):
    """Autocomplete slash commands when input starts with /."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            for cmd, desc in SLASH_COMMANDS.items():
                if cmd.startswith(text):
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display_meta=desc,
                    )


class MentionCompleter(Completer):
    """Autocomplete tools, datasets, and files when input contains @.

    Supports tabbed filtering via TABS (All / Tools / DB / Files).
    Candidates are ``(name, category, description, kind)`` tuples where
    *kind* is ``"tool"``, ``"dataset"``, or ``"file"``.
    """

    TABS = ["All", "Tools", "DB", "Files", "Flows"]
    _TAB_FILTERS = {
        0: None,          # All
        1: "tool",        # Tools
        2: "dataset",     # DB
        3: "file",        # Files
        4: "workflow",    # Flows
    }

    def __init__(
        self,
        candidates: list[tuple[str, str, str, str]] | None = None,
        *,
        lazy_loader: Callable[[], list[tuple[str, str, str, str]]] | None = None,
    ):
        self.candidates = candidates or []
        self._active_tab = 0
        self._lazy_loader = lazy_loader
        self._lazy_loaded = lazy_loader is None

    def set_candidates(self, candidates: list[tuple[str, str, str, str]]) -> None:
        self.candidates = candidates

    def _ensure_lazy_loaded(self) -> None:
        if self._lazy_loaded:
            return
        self._lazy_loaded = True
        if self._lazy_loader is None:
            return
        try:
            loaded = self._lazy_loader()
            if loaded:
                self.set_candidates(loaded)
        except Exception:
            # Keep initial lightweight candidates if background loading fails.
            pass

    def get_completions(self, document, complete_event):
        self._ensure_lazy_loaded()
        text = document.text_before_cursor
        # Find the last @ in the text
        at_pos = text.rfind("@")
        if at_pos < 0:
            return

        partial = text[at_pos + 1:].lower()
        replace_len = len(text) - at_pos  # replace from @ onwards

        # Filter by active tab
        kind_filter = self._TAB_FILTERS.get(self._active_tab)

        # Group by category for ordering
        by_category: dict[str, list[tuple]] = {}
        for name, category, description, kind in self.candidates:
            if kind_filter and kind != kind_filter:
                continue
            # Case-insensitive substring match against name, category, description
            if (partial in name.lower()
                    or partial in category.lower()
                    or partial in description.lower()):
                by_category.setdefault(category, []).append(
                    (name, description, kind)
                )

        # Style mapping per kind
        styles = {
            "tool": "class:mention-tool",
            "dataset": "class:mention-dataset",
            "file": "class:mention-file",
            "workflow": "class:mention-workflow",
        }

        for category in sorted(by_category):
            for name, description, kind in sorted(by_category[category]):
                yield Completion(
                    f"@{name}",
                    start_position=-replace_len,
                    display_meta=description,
                    style=styles.get(kind, ""),
                )


class MergedCompleter(Completer):
    """Delegates to SlashCompleter for / and MentionCompleter for @."""

    def __init__(self, slash: Completer, mention: MentionCompleter):
        self._slash = slash
        self._mention = mention

    @property
    def mention_completer(self) -> MentionCompleter:
        return self._mention

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.lstrip().startswith("/"):
            yield from self._slash.get_completions(document, complete_event)
        elif "@" in text:
            yield from self._mention.get_completions(document, complete_event)


# ---------------------------------------------------------------------------
# Plan preview rendering
# ---------------------------------------------------------------------------

def render_plan_preview(plan, console=None):
    """Render a plan as a Rich Panel for user approval.

    Args:
        plan: A Plan object with .steps (each having id, tool, description,
              tool_args, depends_on).
        console: Optional Rich Console. Defaults to a new Console().

    Returns:
        The rendered Text (for testing) or prints to console.
    """
    from rich.text import Text
    from ui.traces import format_args

    if console is None:
        console = Console()

    lines = Text()
    lines.append("Research Plan\n\n", style="bold")

    for step in plan.steps:
        # Dependency indicator
        deps = getattr(step, "depends_on", []) or []
        dep_str = ""
        if deps:
            dep_str = f" (after step {', '.join(str(d) for d in deps)})"

        lines.append(f"  {step.id}. ", style="bold cyan")
        lines.append(step.tool or "", style="cyan")
        if dep_str:
            lines.append(dep_str, style="dim")
        lines.append("\n")

        # Description
        desc = getattr(step, "description", "") or ""
        if desc:
            lines.append(f"     {desc}\n", style="")

        # Key args
        args = getattr(step, "tool_args", {}) or {}
        args_str = format_args(args)
        if args_str:
            lines.append(f"     {args_str}\n", style="dim")

    console.print(Panel(lines, border_style="cyan", title="Plan Preview", width=80))
    return lines


def _build_key_bindings(terminal):
    """Key bindings: Tab accepts ghost suggestion, Ctrl+C double-tap to exit,
    Ctrl+O toggle verbose, Ctrl+J insert newline."""
    kb = KeyBindings()

    @kb.add("tab")
    def _accept_suggestion(event):
        buf = event.app.current_buffer
        if not buf.text:
            idx = terminal._suggestion_idx % len(terminal._suggestions)
            buf.insert_text(terminal._suggestions[idx])
        else:
            buf.start_completion()

    @kb.add("c-c")
    def _handle_ctrl_c(event):
        buf = event.app.current_buffer
        now = time.time()
        if terminal._has_active_query():
            force = (now - terminal._last_interrupt) < 0.7
            terminal._last_interrupt = now
            terminal._show_interrupt_hint = True
            terminal._request_interrupt(force=force)
            buf.reset()
            event.app.invalidate()

            def _clear_interrupt_hint():
                time.sleep(1.0)
                terminal._show_interrupt_hint = False
                try:
                    if event.app.is_running:
                        event.app.invalidate()
                except Exception:
                    pass

            threading.Thread(target=_clear_interrupt_hint, daemon=True).start()
            return

        if now - terminal._last_interrupt < 0.5:
            # Double Ctrl+C — signal exit
            event.app.exit(result="__EXIT__")
        else:
            terminal._last_interrupt = now
            terminal._show_exit_hint = True
            buf.reset()
            event.app.invalidate()

            def _clear_hint():
                time.sleep(0.5)
                terminal._show_exit_hint = False
                try:
                    if event.app.is_running:
                        event.app.invalidate()
                except Exception:
                    pass

            threading.Thread(target=_clear_hint, daemon=True).start()

    @kb.add("c-o")
    def _toggle_verbose(event):
        """Toggle verbose mode mid-session."""
        terminal.session.verbose = not terminal.session.verbose
        state = "ON" if terminal.session.verbose else "OFF"
        terminal._verbose_hint = f"Verbose {state}"
        event.app.invalidate()

        def _clear_hint():
            time.sleep(2.0)
            terminal._verbose_hint = None
            try:
                if event.app.is_running:
                    event.app.invalidate()
            except Exception:
                pass

        threading.Thread(target=_clear_hint, daemon=True).start()

    @kb.add("c-j")
    def _insert_newline(event):
        """Insert a newline for multi-line input."""
        event.app.current_buffer.insert_text("\n")

    @kb.add("escape", "enter")
    def _insert_newline_alt(event):
        """Option+Enter / Alt+Enter inserts newline."""
        event.app.current_buffer.insert_text("\n")

    @kb.add("enter", filter=has_completions)
    def _accept_first_completion(event):
        """When completions are visible on a / command, accept the current
        (or first) completion and submit."""
        buf = event.app.current_buffer
        cs = buf.complete_state
        if buf.text.lstrip().startswith("/") and cs and cs.completions:
            # If nothing is selected yet, jump to the first completion
            if cs.complete_index is None:
                buf.go_to_completion(0)
                cs = buf.complete_state  # refresh after navigation
            if cs and cs.current_completion:
                buf.apply_completion(cs.current_completion)
            buf.validate_and_handle()
        else:
            # Non-slash: just submit normally
            buf.cancel_completion()
            buf.validate_and_handle()

    @kb.add("right", filter=has_completions)
    def _mention_tab_right(event):
        """Switch to next mention tab while completions are visible."""
        completer = terminal._merged_completer
        if completer is None:
            return
        mc = completer.mention_completer
        mc._active_tab = (mc._active_tab + 1) % len(mc.TABS)
        buf = event.app.current_buffer
        buf.cancel_completion()
        buf.start_completion()

    @kb.add("left", filter=has_completions)
    def _mention_tab_left(event):
        """Switch to previous mention tab while completions are visible."""
        completer = terminal._merged_completer
        if completer is None:
            return
        mc = completer.mention_completer
        mc._active_tab = (mc._active_tab - 1) % len(mc.TABS)
        buf = event.app.current_buffer
        buf.cancel_completion()
        buf.start_completion()

    return kb


class InteractiveTerminal:
    """Interactive research session terminal."""

    def __init__(self, config=None, verbose=False):
        from agent.session import Session
        self.session = Session(config=config, verbose=verbose, mode="interactive")
        self.console = Console()
        self.history_file = Path.home() / ".fastfold-cli" / "history"
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self._last_interrupt = 0.0
        self._show_exit_hint = False
        self._show_interrupt_hint = False
        self._verbose_hint = None
        self._last_response = None  # Last synthesis text for /copy
        self._suggestions = list(DEFAULT_SUGGESTIONS)
        random.shuffle(self._suggestions)
        self._suggestion_idx = 0
        self._run_lock = threading.Lock()
        self._worker_thread: threading.Thread | None = None
        self._active_query: str | None = None
        self._active_query_started_at: float = 0.0
        self._active_activity: str = ""
        self._active_activity_updated_at: float = 0.0
        self._active_input_tokens: int = 0
        self._active_output_tokens: int = 0
        self._active_streamed_chars: int = 0
        self._session_sdk_calls: int = 0
        self._session_sdk_input_tokens: int = 0
        self._session_sdk_output_tokens: int = 0
        self._session_sdk_cache_read_tokens: int = 0
        self._session_sdk_cache_creation_tokens: int = 0
        self._session_sdk_cost_usd: float = 0.0
        self._session_sdk_total_cost_usd: float = 0.0
        self._session_sdk_extra_server_tool_cost_usd: float = 0.0
        self._session_sdk_models: set[str] = set()
        self._session_sdk_turn_rows: list[dict] = []
        self._queued_queries: deque[tuple[str, dict]] = deque()
        self._live_refresh_thread: threading.Thread | None = None
        self._toolbar_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._toolbar_frame_interval_s = 0.25
        self._toolbar_words = ["Thinking", "Planning", "Evaluating"]
        self._toolbar_word_interval_s = 3.0
        self._toolbar_spinner_palette = ["#50fa7b", "#8be9fd", "#7aa2f7", "#ffb86c"]
        self._init_toolbar_animation_profile()
        # Build @ mention completer with tool + dataset + file candidates
        mention_candidates = self._build_mention_candidates(include_tools=False, include_files=False)
        mention_completer = MentionCompleter(
            mention_candidates,
            lazy_loader=lambda: self._build_mention_candidates(
                include_tools=True,
                include_files=True,
                max_file_candidates=500,
            ),
        )
        self._merged_completer = MergedCompleter(
            slash=SlashCompleter(),
            mention=mention_completer,
        )
        self._prompt_session = PromptSession(
            history=FileHistory(str(self.history_file)),
            completer=self._merged_completer,
            complete_while_typing=True,
            style=PT_STYLE,
            key_bindings=_build_key_bindings(self),
            multiline=False,  # Ctrl+J / Alt+Enter for newlines
        )
        # Separate session for secret entry prompts (API keys, etc.).
        # Avoids re-entrancy issues with the main interactive app session.
        self._secret_prompt_session = PromptSession(
            style=PT_STYLE,
            multiline=False,
        )
        # Plain session for setup/config prompts that should not use completions
        # and must never be masked like password inputs.
        self._plain_prompt_session = PromptSession(
            style=PT_STYLE,
            multiline=False,
        )
        # Auto-highlight (not apply) the first completion for slash commands
        # so the dropdown shows which item will be accepted on Enter.
        def _auto_highlight_first(buf):
            if (buf.text.lstrip().startswith("/")
                    and buf.complete_state
                    and buf.complete_state.complete_index is None
                    and buf.complete_state.completions):
                # Set the index directly — this highlights without changing text
                buf.complete_state.go_to_index(0)

        self._prompt_session.default_buffer.on_completions_changed += _auto_highlight_first

    def _init_toolbar_animation_profile(self) -> None:
        """Load spinner/word profile for prompt-owned live animation."""
        try:
            from ui.status import SPINNERS, THINKING_WORDS
            style = str(self.session.config.get("ui.spinner", "benzene_breathing"))
            spinner_conf = SPINNERS.get(style, SPINNERS["benzene_breathing"])
            frames = [str(f) for f in spinner_conf.get("frames", []) if str(f)]
            if frames:
                self._toolbar_frames = frames
            interval_ms = int(spinner_conf.get("interval_ms", 125))
            self._toolbar_frame_interval_s = max(0.12, min(interval_ms / 1000.0, 0.6))
            words = list(THINKING_WORDS.get("planning", []))
            random.shuffle(words)
            if words:
                self._toolbar_words = words
        except Exception:
            pass

    def _build_mention_candidates(
        self,
        *,
        include_tools: bool = True,
        include_workflows: bool = True,
        include_files: bool = True,
        max_file_candidates: int = 500,
    ) -> list[tuple[str, str, str, str]]:
        """Build the candidate list for @ mention completion.

        Returns (name, category, description, kind) tuples.
        """
        candidates = []
        # Add datasets
        for name, category, description in DATASET_CANDIDATES:
            candidates.append((name, category, description, "dataset"))
        # Add tools from registry (lazy load)
        if include_tools:
            try:
                from tools import registry, ensure_loaded

                ensure_loaded()
                for tool in registry.list_tools():
                    candidates.append(
                        (tool.name, tool.category, tool.description[:80], "tool")
                    )
            except Exception:
                pass  # Registry not available — datasets still work
        # Add workflow candidates
        if include_workflows:
            try:
                from agent.workflows import WORKFLOWS

                for wf_name, wf in WORKFLOWS.items():
                    n_steps = len(wf.get("steps", []))
                    candidates.append(
                        (wf_name, "workflow", f"{wf['description']} ({n_steps} steps)", "workflow")
                    )
            except Exception:
                pass  # Workflows not available
        # Add file candidates from configured data directory
        if include_files:
            try:
                data_base = self.session.config.get("data.base", "")
                if data_base:
                    data_path = Path(data_base)
                    if data_path.is_dir():
                        file_count = 0
                        for f in data_path.rglob("*"):
                            if not f.is_file() or f.name.startswith("."):
                                continue
                            candidates.append(
                                (f.name, "file", str(f.relative_to(data_path)), "file")
                            )
                            file_count += 1
                            if file_count >= max(0, int(max_file_candidates)):
                                break
            except Exception:
                pass  # Best-effort file scanning
        return candidates

    def _has_active_query(self) -> bool:
        with self._run_lock:
            worker = self._worker_thread
            return bool(worker and worker.is_alive())

    def _queued_query_count(self) -> int:
        with self._run_lock:
            return len(self._queued_queries)

    def _request_interrupt(self, force: bool = False) -> bool:
        runner = getattr(getattr(self, "agent", None), "_runner", None)
        if runner is None or not hasattr(runner, "request_interrupt"):
            self.console.print("  [dim]No active runner to interrupt.[/dim]")
            return False
        ok = bool(runner.request_interrupt(force=force))
        if ok:
            if force:
                self.console.print("  [yellow]Force stop requested.[/yellow]")
            else:
                self.console.print("  [dim]Interrupt requested…[/dim]")
        else:
            self.console.print("  [dim]No active generation to interrupt.[/dim]")
        return ok

    def _ensure_live_refresh_thread(self) -> None:
        """Keep toolbar status live while generation runs."""
        with self._run_lock:
            t = self._live_refresh_thread
            if t and t.is_alive():
                return
            t = threading.Thread(
                target=self._live_refresh_loop,
                daemon=True,
                name="ct-live-toolbar-refresh",
            )
            self._live_refresh_thread = t
            t.start()

    def _live_refresh_loop(self) -> None:
        while True:
            try:
                if self._has_active_query():
                    app = self._prompt_session.app
                    if app and app.is_running:
                        app.invalidate()
            except Exception:
                pass
            time.sleep(0.25)

    def _set_active_activity(self, text: str) -> None:
        clean = str(text or "").replace("\n", " ").strip()
        if len(clean) > 80:
            clean = clean[:77] + "..."
        with self._run_lock:
            self._active_activity = clean
            self._active_activity_updated_at = time.time()

    @staticmethod
    def _coerce_token_count(value) -> int:
        try:
            if value is None:
                return 0
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, int):
                return max(0, value)
            if isinstance(value, float):
                return max(0, int(value))
            text = str(value).strip()
            if not text:
                return 0
            return max(0, int(float(text)))
        except Exception:
            return 0

    def _set_active_usage(self, input_tokens=None, output_tokens=None,
                          cache_read_tokens=None) -> None:
        # Track fresh (non-cached) input only — subtract prompt-cache reads so the
        # live counter doesn't balloon when a large cached prefix is re-sent on
        # every model call of a long agentic turn.
        cache_read = self._coerce_token_count(cache_read_tokens)
        in_tokens = max(0, self._coerce_token_count(input_tokens) - cache_read)
        out_tokens = self._coerce_token_count(output_tokens)
        with self._run_lock:
            if in_tokens > self._active_input_tokens:
                self._active_input_tokens = in_tokens
            if out_tokens > self._active_output_tokens:
                self._active_output_tokens = out_tokens

    def _set_active_streamed_chars(self, streamed_chars=None) -> None:
        chars = self._coerce_token_count(streamed_chars)
        with self._run_lock:
            if chars > self._active_streamed_chars:
                self._active_streamed_chars = chars

    @staticmethod
    def _estimate_output_tokens_from_chars(char_count: int) -> int:
        # Rough fallback while SDK usage counters are not yet emitted.
        return max(0, int(round(char_count / 4.0)))

    @staticmethod
    def _coerce_cost(value) -> float:
        try:
            if value is None:
                return 0.0
            if isinstance(value, bool):
                return float(int(value))
            if isinstance(value, (int, float)):
                return max(0.0, float(value))
            text = str(value).strip()
            if not text:
                return 0.0
            return max(0.0, float(text))
        except Exception:
            return 0.0

    def _record_sdk_usage(self, result) -> None:
        metadata = getattr(result, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            return

        input_tokens = self._coerce_token_count(metadata.get("sdk_input_tokens"))
        output_tokens = self._coerce_token_count(metadata.get("sdk_output_tokens"))
        cache_read_tokens = self._coerce_token_count(metadata.get("sdk_cache_read_input_tokens"))
        cache_creation_tokens = self._coerce_token_count(metadata.get("sdk_cache_creation_input_tokens"))
        sdk_turns = self._coerce_token_count(metadata.get("sdk_turns"))
        cost_split_known = bool(metadata.get("sdk_cost_split_known", False))
        total_cost_usd = self._coerce_cost(metadata.get("sdk_total_cost_usd"))
        model_usage_cost_usd = self._coerce_cost(metadata.get("sdk_model_usage_cost_usd"))
        if total_cost_usd <= 0.0:
            total_cost_usd = self._coerce_cost(metadata.get("sdk_cost_usd"))
        # Main display cost aligns with token rows when split is known.
        if cost_split_known and model_usage_cost_usd > 0.0:
            cost_usd = model_usage_cost_usd
            extra_server_tool_cost_usd = self._coerce_cost(
                metadata.get("sdk_server_tool_cost_usd")
            )
            if extra_server_tool_cost_usd <= 0.0 and total_cost_usd > cost_usd:
                extra_server_tool_cost_usd = total_cost_usd - cost_usd
        else:
            # SDK didn't provide model-usage cost; avoid double-reporting.
            cost_usd = total_cost_usd
            extra_server_tool_cost_usd = 0.0
        models_raw = metadata.get("sdk_models") or []
        if isinstance(models_raw, str):
            models = [models_raw]
        elif isinstance(models_raw, (list, tuple, set)):
            models = [str(m).strip() for m in models_raw if str(m).strip()]
        else:
            models = []
        if not models:
            fallback_model = str(metadata.get("sdk_model") or self.session.current_model or "").strip()
            if fallback_model:
                models = [fallback_model]

        has_usage = any((
            input_tokens > 0,
            output_tokens > 0,
            cache_read_tokens > 0,
            cache_creation_tokens > 0,
            cost_usd > 0.0,
            sdk_turns > 0,
        ))
        if not has_usage:
            return

        with self._run_lock:
            self._session_sdk_calls += 1
            turn_idx = self._session_sdk_calls
            self._session_sdk_input_tokens += input_tokens
            self._session_sdk_output_tokens += output_tokens
            self._session_sdk_cache_read_tokens += cache_read_tokens
            self._session_sdk_cache_creation_tokens += cache_creation_tokens
            self._session_sdk_cost_usd += cost_usd
            self._session_sdk_total_cost_usd += total_cost_usd
            self._session_sdk_extra_server_tool_cost_usd += extra_server_tool_cost_usd
            for model in models:
                if model:
                    self._session_sdk_models.add(model)
            self._session_sdk_turn_rows.append(
                {
                    "turn": turn_idx,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cache_read_tokens": cache_read_tokens,
                    "cache_creation_tokens": cache_creation_tokens,
                    "cost_usd": cost_usd,
                    "total_cost_usd": total_cost_usd,
                    "extra_server_tool_cost_usd": extra_server_tool_cost_usd,
                    "models": list(models),
                    "timestamp": time.time(),
                }
            )
        self._persist_usage_to_trajectory()

    def _usage_snapshot(self) -> dict:
        """Create a serializable snapshot of current session usage counters."""
        with self._run_lock:
            return {
                "sdk_calls": int(self._session_sdk_calls),
                "sdk_input_tokens": int(self._session_sdk_input_tokens),
                "sdk_output_tokens": int(self._session_sdk_output_tokens),
                "sdk_cache_read_tokens": int(self._session_sdk_cache_read_tokens),
                "sdk_cache_creation_tokens": int(self._session_sdk_cache_creation_tokens),
                "sdk_cost_usd": float(self._session_sdk_cost_usd),
                "sdk_total_cost_usd": float(self._session_sdk_total_cost_usd),
                "sdk_extra_server_tool_cost_usd": float(self._session_sdk_extra_server_tool_cost_usd),
                "sdk_models": sorted(self._session_sdk_models),
                "sdk_turn_rows": list(self._session_sdk_turn_rows),
            }

    def _persist_usage_to_trajectory(self) -> None:
        """Persist usage snapshot alongside trajectory metadata for resume."""
        trajectory = getattr(getattr(self, "agent", None), "trajectory", None)
        if trajectory is None:
            return
        snapshot = self._usage_snapshot()
        if hasattr(trajectory, "set_usage_data"):
            trajectory.set_usage_data(snapshot)
            trajectory.save()

    def _restore_usage_from_trajectory(self) -> None:
        """Restore usage counters from persisted session metadata."""
        trajectory = getattr(getattr(self, "agent", None), "trajectory", None)
        if trajectory is None or not hasattr(trajectory, "get_usage_data"):
            return
        raw = trajectory.get_usage_data()
        if not isinstance(raw, dict) or not raw:
            return

        rows_raw = raw.get("sdk_turn_rows")
        rows: list[dict] = rows_raw if isinstance(rows_raw, list) else []
        models_raw = raw.get("sdk_models")
        if isinstance(models_raw, str):
            models = {models_raw} if models_raw else set()
        elif isinstance(models_raw, (list, tuple, set)):
            models = {str(m).strip() for m in models_raw if str(m).strip()}
        else:
            models = set()

        with self._run_lock:
            self._session_sdk_calls = self._coerce_token_count(raw.get("sdk_calls"))
            self._session_sdk_input_tokens = self._coerce_token_count(raw.get("sdk_input_tokens"))
            self._session_sdk_output_tokens = self._coerce_token_count(raw.get("sdk_output_tokens"))
            self._session_sdk_cache_read_tokens = self._coerce_token_count(raw.get("sdk_cache_read_tokens"))
            self._session_sdk_cache_creation_tokens = self._coerce_token_count(raw.get("sdk_cache_creation_tokens"))
            self._session_sdk_cost_usd = self._coerce_cost(raw.get("sdk_cost_usd"))
            self._session_sdk_total_cost_usd = self._coerce_cost(raw.get("sdk_total_cost_usd"))
            self._session_sdk_extra_server_tool_cost_usd = self._coerce_cost(
                raw.get("sdk_extra_server_tool_cost_usd")
            )
            self._session_sdk_models = models
            self._session_sdk_turn_rows = [r for r in rows if isinstance(r, dict)]

    def _toolbar_spinner_markup(self) -> str:
        """Render spinner frame with subtle cycling color."""
        frames = self._toolbar_frames or ["⠋"]
        frame_idx = int(time.time() / self._toolbar_frame_interval_s) % len(frames)
        palette = self._toolbar_spinner_palette or ["#8be9fd"]
        color_idx = int(time.time() * 4) % len(palette)
        frame = str(frames[frame_idx])
        color = str(palette[color_idx])
        return f'<style fg="{color}" bg="default">{frame}</style>'

    def _submit_query(self, query: str, context: dict) -> None:
        payload = (query, dict(context))
        start_refresh = False
        with self._run_lock:
            worker = self._worker_thread
            if worker and worker.is_alive():
                self._queued_queries.append(payload)
                # Do not print queue notices immediately; users found it
                # confusing when this appears before the prior response.
                # The worker prints a "running queued message" notice right
                # before execution, which naturally appears below the
                # previous response.
                return

            worker = threading.Thread(
                target=self._run_query_worker,
                args=(payload,),
                daemon=True,
                name="ct-query-worker",
            )
            self._worker_thread = worker
            self._active_query = query
            self._active_query_started_at = time.time()
            self._active_activity = "Running..."
            self._active_activity_updated_at = time.time()
            self._active_input_tokens = 0
            self._active_output_tokens = 0
            self._active_streamed_chars = 0
            start_refresh = True
            worker.start()
        if start_refresh:
            self._ensure_live_refresh_thread()

    def _run_query_worker(self, first_payload: tuple[str, dict]) -> None:
        current = first_payload
        try:
            while True:
                query, ctx = current
                with self._run_lock:
                    self._active_query = query
                    self._active_query_started_at = time.time()
                    self._active_activity = "Running..."
                    self._active_activity_updated_at = time.time()
                    self._active_input_tokens = 0
                    self._active_output_tokens = 0
                    self._active_streamed_chars = 0

                def _progress_update(event="activity", **payload) -> None:
                    # New callback shape: (event, **payload); keep legacy text-only support.
                    if isinstance(event, dict):
                        merged = dict(event)
                        merged.update(payload)
                        payload = merged
                        event = str(payload.pop("event", "activity"))
                    elif not isinstance(event, str):
                        event = str(event or "")

                    if payload:
                        if "input_tokens" in payload or "output_tokens" in payload:
                            self._set_active_usage(
                                payload.get("input_tokens"),
                                payload.get("output_tokens"),
                                payload.get("cache_read_input_tokens"),
                            )
                        if "streamed_chars" in payload:
                            self._set_active_streamed_chars(payload.get("streamed_chars"))
                        text = payload.get("text") or payload.get("activity")
                        if text:
                            self._set_active_activity(str(text))
                        return

                    # Legacy: callback invoked with a plain status string.
                    if event and event not in {"activity", "usage"}:
                        self._set_active_activity(event)

                try:
                    self.console.print()
                    result = self._run_with_clarification(
                        query,
                        ctx,
                        progress_callback=_progress_update,
                    )
                    self.console.print()
                except KeyboardInterrupt:
                    self.console.print("\n  [yellow]Interrupted.[/yellow]")
                    result = None
                except Exception as e:
                    self.console.print(f"\n  [red]Execution error:[/red] {e}")
                    result = None

                if result is not None:
                    self._record_sdk_usage(result)
                    self._last_response = result.summary
                    self._update_suggestions(query, result.plan, result)

                with self._run_lock:
                    if self._queued_queries:
                        current = self._queued_queries.popleft()
                    else:
                        self._worker_thread = None
                        self._active_query = None
                        self._active_query_started_at = 0.0
                        self._active_activity = ""
                        self._active_activity_updated_at = 0.0
                        self._active_input_tokens = 0
                        self._active_output_tokens = 0
                        self._active_streamed_chars = 0
                        break
        finally:
            with self._run_lock:
                self._worker_thread = None
                self._active_query = None
                self._active_query_started_at = 0.0
                self._active_activity = ""
                self._active_activity_updated_at = 0.0
                self._active_input_tokens = 0
                self._active_output_tokens = 0
                self._active_streamed_chars = 0

    def _current_placeholder(self):
        """Return the current ghost suggestion as dim placeholder text."""
        text = self._suggestions[self._suggestion_idx % len(self._suggestions)]
        return HTML(f'<style fg="#555555">{text}</style>')

    def _advance_suggestion(self):
        """Move to next ghost suggestion."""
        self._suggestion_idx = (self._suggestion_idx + 1) % len(self._suggestions)

    def _update_suggestions(self, query: str, plan=None, result=None):
        """Replace suggestions with contextual follow-ups based on last query.

        Uses LLM-suggested follow-ups extracted from the synthesis output.
        """
        suggestions = []

        # Extract LLM-suggested follow-ups from synthesis
        if result and hasattr(result, 'summary') and result.summary:
            llm_suggestions = _extract_llm_suggestions(result.summary)
            suggestions.extend(llm_suggestions)

        if suggestions:
            self._suggestions = suggestions[:5]
            self._suggestion_idx = 0
        else:
            self._advance_suggestion()

    def _model_display_name(self, model_id: str = None) -> str:
        """Get a short display name for a model ID."""
        model_id = model_id or self.session.current_model
        names = {
            "claude-sonnet-4-5-20250929": "Sonnet 4.5",
            "claude-haiku-4-5-20251001": "Haiku 4.5",
            "claude-opus-4-6": "Opus 4.6",
            "gpt-5.5": "GPT-5.5",
            "gpt-5.5-pro": "GPT-5.5 Pro",
            "gpt-5.4": "GPT-5.4",
            "gpt-5.4-pro": "GPT-5.4 Pro",
            "gpt-5.4-mini": "GPT-5.4 Mini",
            "gpt-5.4-nano": "GPT-5.4 Nano",
            "gpt-5-mini": "GPT-5 Mini",
            "gpt-5-nano": "GPT-5 Nano",
            "gpt-4o": "GPT-4o",
            "gpt-4o-mini": "GPT-4o Mini",
        }
        return names.get(model_id, model_id)

    def _prompt_select_compatible_profile_id(
        self,
        *,
        cfg=None,
        allow_create: bool = False,
        create_label: str = "Create new profile",
    ) -> str | None:
        """Prompt user to pick a compatible profile id."""
        profile_cfg = cfg or self.session.config
        profiles = profile_cfg.openai_profiles(include_cloud=False)
        if not profiles:
            self.console.print("  [dim]No compatible profiles configured yet.[/dim]")
            return "__create__" if allow_create else None

        rows = sorted(
            profiles.items(),
            key=lambda item: str(item[1].get("label") or item[0]).strip().lower(),
        )
        active_profile_id = profile_cfg.active_openai_profile_id()
        self.console.print("  [cyan]Compatible profiles[/cyan]")
        for idx, (profile_id, profile) in enumerate(rows, 1):
            marker = " [green]*[/green]" if profile_id == active_profile_id else "  "
            label = str(profile.get("label") or profile_id).strip()
            backend = str(profile.get("backend") or "other").strip().lower()
            endpoint = str(profile.get("base_url") or "—").strip()
            self.console.print(
                f"{marker} [{idx}] {label} [dim]({backend}, {endpoint})[/dim]"
            )
        create_idx = len(rows) + 1
        if allow_create:
            self.console.print(f"   [{create_idx}] {create_label}")

        default_idx = 1
        for idx, (profile_id, _) in enumerate(rows, 1):
            if profile_id == active_profile_id:
                default_idx = idx
                break
        if allow_create and not rows:
            default_idx = create_idx

        try:
            raw_choice = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Select profile [{default_idx}]: ")]
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        selected = raw_choice or str(default_idx)
        if allow_create and selected in {str(create_idx), "new", "n", "create"}:
            return "__create__"
        if selected.isdigit():
            selected_idx = int(selected)
            if 1 <= selected_idx <= len(rows):
                return rows[selected_idx - 1][0]
        selected_lower = selected.lower()
        for profile_id, profile in rows:
            profile_label = str(profile.get("label") or "").strip().lower()
            if selected_lower in {profile_id.lower(), profile_label}:
                return profile_id
        self.console.print("  [dim]Invalid selection.[/dim]")
        return None

    def _prompt_profile_label(self, default_label: str) -> str | None:
        """Prompt for a profile label with a default value."""
        try:
            entered = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Profile label [{default_label}]: ")]
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        label = entered or default_label
        return label.strip() or None

    def _prompt_profile_template_backend(self, default_backend: str = "ollama") -> str | None:
        """Prompt for compatible profile template backend."""
        normalized_default = str(default_backend or "").strip().lower()
        if normalized_default not in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}:
            normalized_default = "ollama"
        self.console.print("  [cyan]Profile template[/cyan]")
        self.console.print(
            f"    [1] Ollama - {self._compatible_install_url('ollama')}"
        )
        self.console.print(
            f"    [2] Unsloth - {self._compatible_install_url('unsloth')}"
        )
        self.console.print(
            f"    [3] oMLX - {self._compatible_install_url('omlx')}"
        )
        self.console.print(
            f"    [4] DS4 (DeepSeek v4) - {self._compatible_install_url('ds4')}"
        )
        self.console.print(
            f"    [5] llama.cpp - {self._compatible_install_url('llama_cpp')}"
        )
        self.console.print(
            f"    [6] LM Studio - {self._compatible_install_url('lm_studio')}"
        )
        self.console.print(
            "    [7] Other compatible endpoint"
        )
        default_num = {
            "ollama": "1",
            "unsloth": "2",
            "omlx": "3",
            "ds4": "4",
            "llama_cpp": "5",
            "lm_studio": "6",
            "other": "7",
        }[normalized_default]
        try:
            raw = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Select template [{default_num}]: ")]
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        selected = raw or default_num
        if selected in {"1", "ollama", "o"}:
            return "ollama"
        if selected in {"2", "unsloth", "u"}:
            return "unsloth"
        if selected in {"3", "omlx", "m"}:
            return "omlx"
        if selected in {"4", "ds4", "deepseek", "deepseek-v4"}:
            return "ds4"
        if selected in {"5", "llama.cpp", "llama_cpp", "llamacpp", "llama-cpp"}:
            return "llama_cpp"
        if selected in {"6", "lmstudio", "lm_studio", "lm-studio", "lm studio"}:
            return "lm_studio"
        if selected in {"7", "other", "custom", "k"}:
            return "other"
        self.console.print("  [dim]Invalid selection.[/dim]")
        return None

    def _current_provider_status(self) -> tuple[str, str, str | None]:
        """Return effective provider id, user-facing label, and endpoint (if any)."""
        raw_provider = str(self.session.config.get("llm.provider", "anthropic") or "anthropic").strip().lower()
        current_model = str(self.session.current_model or "").strip()
        profile = None
        if hasattr(self.session.config, "get_openai_profile"):
            try:
                profile = self.session.config.get_openai_profile()
            except Exception:
                profile = None
        if not isinstance(profile, dict):
            profile = None
        if not profile:
            legacy_base_url = str(self.session.config.get("llm.openai_base_url") or "").strip()
            legacy_backend = str(self.session.config.get("llm.openai_compatible_backend") or "").strip().lower()
            if legacy_base_url and not _is_openai_managed_base_url(legacy_base_url):
                if legacy_backend not in {
                    "ollama",
                    "unsloth",
                    "omlx",
                    "ds4",
                    "llama_cpp",
                    "lm_studio",
                    "other",
                }:
                    legacy_backend = "other"
                profile = {
                    "id": "legacy_compatible",
                    "label": "OpenAI-compatible endpoint",
                    "backend": legacy_backend,
                    "base_url": legacy_base_url,
                    "api_key": str(self.session.config.get("llm.openai_compatible_api_key") or "").strip(),
                }
            else:
                profile = {
                    "id": "openai_cloud",
                    "label": "OpenAI Cloud",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": str(self.session.config.get("llm.openai_api_key") or "").strip(),
                }
        profile_backend = str((profile or {}).get("backend") or "").strip().lower()
        profile_label = str((profile or {}).get("label") or "").strip()
        openai_base_url = ""
        if hasattr(self.session.config, "llm_openai_base_url"):
            try:
                candidate_base_url = self.session.config.llm_openai_base_url()
                if isinstance(candidate_base_url, str):
                    openai_base_url = candidate_base_url.strip()
            except Exception:
                openai_base_url = ""
        if not openai_base_url:
            openai_base_url = str(self.session.config.get("llm.openai_base_url") or "").strip()
        is_compat_endpoint = bool(openai_base_url) and (
            profile_backend != "openai" or not _is_openai_managed_base_url(openai_base_url)
        )

        if raw_provider == "openai":
            if is_compat_endpoint:
                label = profile_label or "OpenAI-compatible profile"
                if label.lower() in {"openai-compatible endpoint", "openai-compatible profile"}:
                    return "openai", "OpenAI-compatible custom endpoint", openai_base_url
                return "openai", f"OpenAI-compatible custom endpoint ({label})", openai_base_url
            return "openai", "OpenAI", None
        if raw_provider == "anthropic":
            # If a custom OpenAI-compatible endpoint is configured and the active
            # model is not an Anthropic id, treat this as OpenAI-compatible mode.
            if (
                is_compat_endpoint
                and current_model
                and current_model not in _ANTHROPIC_MODEL_IDS
            ):
                label = profile_label or "OpenAI-compatible profile"
                if label.lower() in {"openai-compatible endpoint", "openai-compatible profile"}:
                    return "openai", "OpenAI-compatible custom endpoint", openai_base_url
                return "openai", f"OpenAI-compatible custom endpoint ({label})", openai_base_url
            return "anthropic", "Anthropic", None
        from agent.config import OPENAI_COMPATIBLE_PROVIDERS

        if raw_provider in OPENAI_COMPATIBLE_PROVIDERS:
            meta = OPENAI_COMPATIBLE_PROVIDERS[raw_provider]
            return (
                raw_provider,
                str(meta.get("label") or raw_provider),
                str(meta.get("base_url") or "") or None,
            )
        return raw_provider or "anthropic", (raw_provider or "anthropic"), None

    @staticmethod
    def _compatible_backend_display_name(backend: str) -> str:
        """Return user-facing backend label."""
        backend_type = str(backend or "").strip().lower()
        if backend_type == "omlx":
            return "oMLX"
        if backend_type == "ollama":
            return "Ollama"
        if backend_type == "unsloth":
            return "Unsloth"
        if backend_type == "ds4":
            return "DS4"
        if backend_type == "llama_cpp":
            return "llama.cpp"
        if backend_type == "lm_studio":
            return "LM Studio"
        return "Custom"

    @staticmethod
    def _compatible_default_base_url(backend: str, fallback: str = "http://localhost:11434/v1") -> str:
        """Return default endpoint for a compatible backend."""
        backend_type = str(backend or "").strip().lower()
        defaults = {
            "ollama": "http://localhost:11434/v1",
            "unsloth": "http://localhost:8888/v1",
            "omlx": "http://localhost:8000/v1",
            "ds4": "http://localhost:8000/v1",
            "llama_cpp": "http://localhost:8080/v1",
            "lm_studio": "http://localhost:1234/v1",
        }
        return defaults.get(backend_type, fallback)

    @staticmethod
    def _compatible_install_url(backend: str) -> str:
        """Return install/reference URL for a compatible backend template."""
        try:
            from agent.config import Config

            return Config.compatible_backend_install_url(backend)
        except Exception:
            backend_type = str(backend or "").strip().lower()
            fallback = ""
            urls = {
                "ollama": "https://github.com/ollama/ollama",
                "unsloth": "https://github.com/unslothai/unsloth",
                "omlx": "https://github.com/jundot/omlx",
                "ds4": "https://github.com/antirez/ds4",
                "llama_cpp": "https://github.com/ggml-org/llama.cpp",
                "lm_studio": "https://lmstudio.ai/docs/developer/openai-compat",
                "other": fallback,
            }
            return urls.get(backend_type, fallback)

    @staticmethod
    def _resolve_optional_api_key_input(
        raw_input: str,
        *,
        existing_key: str = "",
        default_key: str = "",
    ) -> str | None:
        """Resolve optional key input where blank means unset/clear."""
        normalized = str(raw_input or "").strip()
        lowered = normalized.lower()
        if lowered in {":keep", "keep"}:
            kept = str(existing_key or default_key or "").strip()
            return kept or None
        if lowered in {":default", "default"}:
            chosen = str(default_key or "").strip()
            return chosen or None
        if not normalized:
            return None
        return normalized

    def _current_compatible_backend_label(self) -> str | None:
        """Return compatible backend label for status line, when applicable."""
        _, provider_label, endpoint = self._current_provider_status()
        profile = None
        if hasattr(self.session.config, "get_openai_profile"):
            try:
                profile = self.session.config.get_openai_profile()
            except Exception:
                profile = None
        if not isinstance(profile, dict):
            profile = None
        backend = str((profile or {}).get("backend") or "").strip().lower()
        if backend not in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other", "custom"}:
            backend = str(
                self.session.config.get("llm.openai_compatible_backend") or ""
            ).strip().lower()
        if not endpoint or "OpenAI-compatible" not in provider_label:
            return None

        if backend in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio"}:
            return self._compatible_backend_display_name(backend)
        if backend in {"other", "custom"}:
            return "Custom"

        # Fallback heuristics for older configs that predate backend selection.
        key = str((profile or {}).get("api_key") or self.session.config.get("llm.openai_compatible_api_key") or "").strip().lower()
        endpoint_text = str(endpoint).strip().lower()
        if key.startswith("sk-unsloth-") or "8888" in endpoint_text:
            return "Unsloth"
        if (
            key.startswith("dsv4-")
            or key.startswith("sk-ds4-")
            or "ds4" in endpoint_text
            or "deepseek-v4" in endpoint_text
        ):
            return "DS4"
        if "1234" in endpoint_text or "lmstudio" in endpoint_text or "lm-studio" in endpoint_text:
            return "LM Studio"
        if (
            "8080" in endpoint_text
            or "llama.cpp" in endpoint_text
            or "llama-cpp" in endpoint_text
            or "llamacpp" in endpoint_text
        ):
            return "llama.cpp"
        if "8000" in endpoint_text or "omlx" in endpoint_text:
            return "oMLX"
        if "11434" in endpoint_text:
            return "Ollama"
        return "Custom"

    def _mention_completing(self) -> bool:
        """Check if @ mention completions are currently active."""
        try:
            buf = self._prompt_session.app.current_buffer
            if buf.complete_state and "@" in buf.text:
                return True
        except Exception:
            pass
        return False

    def _bottom_toolbar(self):
        if self._show_exit_hint:
            return HTML('<style fg="#888888" bg="default">Press Ctrl+C again to exit</style>')
        if self._show_interrupt_hint:
            return HTML('<style fg="#ffb86c" bg="default">Interrupt requested · press Ctrl+C again to force stop</style>')
        if self._verbose_hint:
            return HTML(f'<style fg="#50fa7b" bg="default">{self._verbose_hint}</style>')

        # Show tab bar when @ mention completions are active
        if self._mention_completing():
            mc = self._merged_completer.mention_completer
            tabs = []
            for i, label in enumerate(mc.TABS):
                if i == mc._active_tab:
                    tabs.append(f'<style fg="#50fa7b" bg="default"><b>[{label}]</b></style>')
                else:
                    tabs.append(f'<style fg="#555555" bg="default"> {label} </style>')
            tab_bar = "  ".join(tabs)
            return HTML(f'{tab_bar}  <style fg="#555555" bg="default">·  ←/→ switch tab</style>')

        model = self._model_display_name()
        compat_backend = self._current_compatible_backend_label()
        if compat_backend:
            model = f"{model} · {compat_backend}"
        if self._has_active_query():
            with self._run_lock:
                queued = len(self._queued_queries)
                status = self._active_activity or "thinking..."
                status_updated_at = self._active_activity_updated_at
                started_at = self._active_query_started_at
                in_tokens = self._active_input_tokens
                out_tokens = self._active_output_tokens
                streamed_chars = self._active_streamed_chars
            elapsed_s = max(0, int(time.time() - started_at)) if started_at else 0
            if elapsed_s < 60:
                elapsed = f"{elapsed_s}s"
            else:
                elapsed = f"{elapsed_s // 60}m{elapsed_s % 60:02d}s"
            stale_status = (time.time() - status_updated_at) > 2.5
            if stale_status or status in {"thinking...", "starting..."}:
                word_idx = int(time.time() / self._toolbar_word_interval_s) % max(1, len(self._toolbar_words))
                status = f"{self._toolbar_words[word_idx]}..."
            fallback_out = self._estimate_output_tokens_from_chars(streamed_chars)
            shown_out = out_tokens if out_tokens > 0 else fallback_out
            usage_label = ""
            if in_tokens > 0 or shown_out > 0:
                in_label = f"↑ {in_tokens}" if in_tokens > 0 else "↑ …"
                usage_label = f" · {in_label} · ↓ {shown_out} tokens"
            queued_label = f" · queued {queued}" if queued else ""
            spinner = self._toolbar_spinner_markup()
            return HTML(
                f"{spinner}"
                f'<style fg="#8be9fd" bg="default"> running {elapsed}</style>'
                f'<style fg="#7f8790" bg="default">{usage_label}</style>'
                f'<style fg="#8be9fd" bg="default">{queued_label}</style>'
                f'<style fg="#50fa7b" bg="default"> {status}</style>'
                '<style fg="#555555" bg="default"> · /interrupt · Ctrl+C interrupt</style>'
            )
        verbose = ' <style fg="#50fa7b" bg="default">verbose</style>' if self.session.verbose else ""
        plan = ' <style fg="#ff79c6" bg="default">plan mode</style>' if self.session.config.get("agent.plan_preview", False) else ""
        return HTML(
            f'<style fg="#8be9fd" bg="default">{model}</style>{verbose}{plan}'
            '<style fg="#555555" bg="default"> · ? for commands · Ctrl+O verbose</style>'
        )

    def run(self, initial_context: dict = None, resume_id: str = None):
        """Run the interactive session."""
        from agent.loop import AgentLoop

        context = initial_context or {}
        term_width = self.console.width

        # AgentLoop persists across queries — holds trajectory for multi-turn memory
        if resume_id:
            try:
                if resume_id == "last":
                    self.agent = AgentLoop.resume_latest(self.session)
                else:
                    self.agent = AgentLoop.resume(self.session, resume_id)
                self._restore_usage_from_trajectory()
                n = len(self.agent.trajectory.turns)
                title = self.agent.trajectory.title or "untitled"
                self.console.print(f"  [green]Resumed session[/green] [bold]{self.agent.trajectory.session_id}[/bold] — {title} ({n} turns)")
                self._render_resumed_history(term_width, turns=self.agent.trajectory.turns)
                self.console.print()
            except FileNotFoundError as e:
                self.console.print(f"  [yellow]{e}[/yellow]")
                self.console.print("  [dim]Use /sessions to list available session IDs.[/dim]")
                self.agent = AgentLoop(self.session)
        else:
            self.agent = AgentLoop(self.session)

        while True:
            try:
                # Separator line above prompt
                self.console.print(f"[#333333]{'─' * term_width}[/]")

                with patch_stdout(raw=True):
                    query = self._prompt_session.prompt(
                        [("class:prompt", "❯ ")],
                        bottom_toolbar=self._bottom_toolbar,
                        placeholder=self._current_placeholder(),
                    ).strip()
                self._show_exit_hint = False
                self._show_interrupt_hint = False
            except EOFError:
                if self._has_active_query():
                    self._request_interrupt(force=True)
                self._print_exit_with_resume_hint()
                break

            # Handle double Ctrl+C exit signal from key binding
            if query == "__EXIT__":
                if self._has_active_query():
                    self._request_interrupt(force=True)
                self._print_exit_with_resume_hint()
                break

            if not query:
                self._advance_suggestion()
                continue

            # Handle slash commands and plain commands
            cmd = query.lower()
            # Normalize accidental "/ command" spacing to "/command"
            if cmd.startswith("/ "):
                cmd = "/" + cmd[2:].lstrip()
                query = "/" + query[2:].lstrip()

            # Auto-resolve partial slash commands — first match wins
            # (e.g. "/mod" → "/model", "/co" → "/config")
            if cmd.startswith("/") and cmd not in SLASH_COMMANDS:
                prefix = cmd.split()[0]  # handle "/export file.md" → "/export"
                matches = [c for c in SLASH_COMMANDS if c.startswith(prefix)]
                if matches:
                    cmd = matches[0] + cmd[len(prefix):]
                    query = matches[0] + query[len(prefix):]

            busy = self._has_active_query()
            if cmd in ("exit", "quit", "q", "/exit", "/quit"):
                if busy:
                    self._request_interrupt(force=True)
                self._print_exit_with_resume_hint()
                break
            if cmd.startswith("/interrupt") or cmd == "interrupt":
                force = cmd.endswith("!") or "--force" in cmd or " force" in cmd
                self._request_interrupt(force=force)
                self._advance_suggestion()
                continue
            if busy and (
                cmd.startswith("/model")
                or cmd.startswith("/settings")
                or cmd.startswith("/model-manager")
                or cmd.startswith("/plan")
                or cmd.startswith("/new")
                or cmd.startswith("/sessions")
                or cmd.startswith("/sync")
                or cmd.startswith("/resume")
                or cmd.startswith("/agents")
                or cmd.startswith("/case-study")
                or cmd.startswith("/compact")
                or cmd.startswith("/export")
                or cmd.startswith("/notebook")
                or cmd.startswith("/upgrade")
            ):
                self.console.print("  [dim]Command unavailable while a generation is running.[/dim]")
                self.console.print("  [dim]Use /interrupt, or wait for queued messages to run.[/dim]")
                self._advance_suggestion()
                continue
            if cmd in ("help", "/help", "?"):
                self._show_help()
                self._advance_suggestion()
                continue
            if cmd in ("tools", "/tools"):
                from tools import registry, ensure_loaded, tool_load_errors
                ensure_loaded()
                self.console.print(registry.list_tools_table())
                errors = tool_load_errors()
                if errors:
                    names = ", ".join(sorted(errors.keys())[:8])
                    extra = "" if len(errors) <= 8 else f" (+{len(errors) - 8} more)"
                    self.console.print(
                        f"[yellow]Warning:[/yellow] {len(errors)} tool module(s) failed to load: "
                        f"{names}{extra}"
                    )
                self._advance_suggestion()
                continue
            cmd_head = cmd.split(maxsplit=1)[0]
            cmd_rest = query.split(maxsplit=1)[1] if len(query.split(maxsplit=1)) > 1 else ""
            if cmd_head in ("skills-add", "/skills-add", "skill-add", "/skill-add"):
                self._add_skill(cmd_rest)
                self._advance_suggestion()
                continue
            if cmd_head in ("skills-find", "/skills-find", "skill-find", "/skill-find"):
                self._find_skills(cmd_rest)
                self._advance_suggestion()
                continue
            if cmd_head in ("skills-upgrade", "/skills-upgrade", "skill-upgrade", "/skill-upgrade"):
                self._upgrade_skills()
                self._advance_suggestion()
                continue
            if cmd_head in ("skills-remove", "/skills-remove", "skill-remove", "/skill-remove"):
                self._remove_skill(cmd_rest)
                self._advance_suggestion()
                continue
            if cmd in ("skill", "/skill", "skills", "/skills"):
                self._show_skills()
                self._advance_suggestion()
                continue
            if cmd_head in ("data", "/data"):
                self._handle_data_command(query)
                self._advance_suggestion()
                continue
            if cmd in ("model", "/model"):
                self._switch_model()
                self._advance_suggestion()
                continue
            if cmd in ("settings", "/settings"):
                self._change_settings()
                self._advance_suggestion()
                continue
            if (
                cmd == "model-manager"
                or cmd.startswith("/model-manager")
                or cmd == "model-details"
                or cmd.startswith("/model-details")
                or cmd == "compatible"
                or cmd.startswith("/compatible")
            ):
                self._handle_model_manager_command(query)
                self._advance_suggestion()
                continue
            if cmd in ("plan", "/plan"):
                self._toggle_plan_mode()
                self._advance_suggestion()
                continue
            if cmd in ("usage", "/usage"):
                self._show_usage()
                self._advance_suggestion()
                continue
            if cmd == "tasks" or cmd.startswith("/tasks"):
                parts = query.strip().lower().split()
                force_refresh = len(parts) > 1 and parts[1] in {"refresh", "-r", "--refresh", "force"}
                self._show_tasks(force_refresh=force_refresh)
                self._advance_suggestion()
                continue
            if cmd in ("config", "/config"):
                from agent.config import Config
                self.console.print(Config.load().to_table())
                self._advance_suggestion()
                continue
            if cmd == "keys" or cmd.startswith("/keys"):
                self._handle_keys_command(query)
                self._advance_suggestion()
                continue
            if cmd == "mcp" or cmd.startswith("/mcp"):
                self._handle_mcp_command(query)
                self._advance_suggestion()
                continue
            if cmd in ("upgrade", "/upgrade"):
                self._run_upgrade()
                self._advance_suggestion()
                continue
            if cmd in ("doctor", "/doctor"):
                from agent.doctor import has_errors, has_warnings, run_checks, to_table
                checks = run_checks(self.session.config, session=self.session)
                self.console.print(to_table(checks))
                if has_errors(checks):
                    self.console.print("  [red]Blocking issues found.[/red]")
                elif has_warnings(checks):
                    self.console.print("  [yellow]No blocking errors; warnings remain.[/yellow]")
                else:
                    self.console.print("  [green]No blocking issues found.[/green]")
                self._advance_suggestion()
                continue
            if cmd in ("clear", "/clear"):
                self.console.clear()
                self._advance_suggestion()
                continue
            if cmd in ("copy", "/copy"):
                self._copy_last_response()
                continue
            if cmd.startswith("/export-share"):
                parts = query.split(maxsplit=1)
                filename = parts[1] if len(parts) > 1 else None
                self._export_share(filename)
                continue
            if cmd.startswith("/export"):
                parts = query.split(maxsplit=1)
                filename = parts[1] if len(parts) > 1 else None
                self._export_session(filename)
                continue
            if cmd.startswith("/notebook"):
                parts = query.split(maxsplit=1)
                filename = parts[1] if len(parts) > 1 else None
                self._export_notebook(filename)
                continue
            if cmd.startswith("/compact"):
                parts = query.split(maxsplit=1)
                instructions = parts[1] if len(parts) > 1 else None
                self._compact_context(instructions)
                continue
            if cmd in ("new", "/new"):
                self._new_session()
                continue
            if cmd.startswith("/sessions") or cmd == "sessions":
                parts = query.split(maxsplit=2)
                action = parts[1].strip().lower() if len(parts) > 1 else ""
                if action in {"delete", "del", "rm", "remove"}:
                    target = parts[2].strip() if len(parts) > 2 else None
                    self._delete_session(target)
                else:
                    self._list_sessions()
                continue
            if cmd.startswith("/sync") or cmd == "sync":
                parts = query.split()
                force = any(part in {"--force", "-f", "force"} for part in parts[1:])
                self._sync_sessions(force=force)
                continue
            if cmd.startswith("/resume"):
                parts = query.split(maxsplit=1)
                sid = parts[1].strip() if len(parts) > 1 else None
                self._resume_session(sid)
                continue
            if cmd.startswith("/agents"):
                self._handle_agents_command(query, context)
                continue
            if cmd.startswith("/case-study"):
                self._handle_case_study_command(query, context)
                continue

            # ! prefix — shell command
            if query.startswith("!"):
                self._run_shell(query[1:].strip())
                continue

            # "continue" — resume interrupted synthesis or continue conversation
            if cmd in ("continue", "go on", "keep going"):
                if self.agent._last_plan is not None:
                    self.console.print(f"  [cyan]Continuing synthesis...[/cyan]\n")
                    try:
                        result = self.agent.continue_synthesis()
                        self.console.print()
                    except KeyboardInterrupt:
                        self.console.print("\n  [dim]Interrupted.[/dim]")
                        continue
                    if result is not None:
                        self._last_response = result.summary
                        self._update_suggestions(
                            self.agent._last_query or query, result.plan, result,
                        )
                    continue
                # No interrupted state — fall through to normal query
                # (planner will use session history to understand context)

            # Keep prompt available while one generation runs; extra user messages
            # are queued and executed serially by the worker.
            self._submit_query(query, context)
            self._advance_suggestion()

    def _run_with_clarification(
        self,
        query: str,
        context: dict,
        progress_callback=None,
    ):
        """Run a query, handling clarification requests interactively."""
        from agent.loop import ClarificationNeeded

        if not self._ensure_llm_ready_for_query():
            return None

        run_context = dict(context)

        # Extract @mentions and inject into context
        cleaned_query, mention_tools, mention_datasets, mention_workflows = extract_mentions(query)
        if mention_tools or mention_datasets or mention_workflows:
            mention_ctx = build_mention_context(mention_tools, mention_datasets, mention_workflows)
            run_context["mention_context"] = mention_ctx
            query = cleaned_query

        max_clarifications = 3  # Prevent infinite clarification loops

        for _ in range(max_clarifications):
            try:
                return self.agent.run(
                    query,
                    run_context,
                    progress_callback=progress_callback,
                )
            except ClarificationNeeded as e:
                clar = e.clarification
                self.console.print(f"  [cyan]{clar.question}[/cyan]")
                if clar.suggestions:
                    self.console.print(f"  [dim]e.g. {', '.join(clar.suggestions[:3])}[/dim]")

                try:
                    answer = self._prompt_session.prompt(
                        [("class:prompt", "  ❯ ")],
                    ).strip()
                except (EOFError, KeyboardInterrupt):
                    self.console.print("  [dim]Cancelled.[/dim]")
                    return None

                if not answer:
                    self.console.print("  [dim]Cancelled.[/dim]")
                    return None

                # Add the answer to context using the missing parameter name
                if clar.missing:
                    run_context[clar.missing[0]] = answer
                # Also append to the query so the planner gets full context
                query = f"{query} — {answer}"

        return self.agent.run(
            query,
            run_context,
            progress_callback=progress_callback,
        )

    def _print_exit_with_resume_hint(self) -> None:
        """Print exit message with a copyable resume command."""
        self.console.print("\nGoodbye!\n")
        session_id = None
        has_messages = False
        if hasattr(self, "agent") and getattr(self.agent, "trajectory", None):
            trajectory = self.agent.trajectory
            session_id = getattr(trajectory, "session_id", None)
            has_messages = bool(getattr(trajectory, "turns", None))
        if session_id and has_messages:
            self.console.print("Resume this session with:")
            self.console.print(f"[cyan]fastfold --resume {session_id}[/cyan]")

    def _ensure_llm_ready_for_query(self) -> bool:
        """Ensure required provider API key is present; prompt interactively if missing."""
        issue = self.session.config.llm_preflight_issue()
        if not issue:
            return True

        provider = str(self.session.config.get("llm.provider", "anthropic") or "anthropic").strip().lower()

        from agent.config import OPENAI_COMPATIBLE_PROVIDERS

        if provider in OPENAI_COMPATIBLE_PROVIDERS:
            meta = OPENAI_COMPATIBLE_PROVIDERS[provider]
            label = meta["label"]
            self.console.print(f"  [yellow]{issue}[/yellow]")
            self.console.print(
                f"  [dim]Set {meta['env_var']} or enter it now to continue.[/dim]"
            )
            try:
                api_key = self._secret_prompt_session.prompt(
                    [("class:prompt", f"  Enter {label} API key (or press Enter to cancel): ")],
                    is_password=True,
                ).strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("  [dim]Cancelled.[/dim]")
                return False
            if not api_key:
                self.console.print("  [dim]Cancelled.[/dim]")
                return False
            self.session.config.set(meta["config_key"], api_key)
            self.session.config.save()
            return self.session.config.llm_preflight_issue() is None

        if provider not in {"anthropic", "openai"}:
            self.console.print(f"  [red]{issue}[/red]")
            return False

        self.console.print(f"  [yellow]{issue}[/yellow]")
        if provider == "openai":
            profile = None
            if hasattr(self.session.config, "get_openai_profile"):
                try:
                    profile = self.session.config.get_openai_profile()
                except Exception:
                    profile = None
            if not isinstance(profile, dict):
                profile = None
            profile_id = str((profile or {}).get("id") or "").strip() or None
            profile_label = str((profile or {}).get("label") or "").strip() or "Compatible endpoint"
            profile_backend = str((profile or {}).get("backend") or "").strip().lower()
            openai_base_url = ""
            if hasattr(self.session.config, "llm_openai_base_url"):
                try:
                    base_url_candidate = self.session.config.llm_openai_base_url()
                    if isinstance(base_url_candidate, str):
                        openai_base_url = base_url_candidate.strip()
                except Exception:
                    openai_base_url = ""
            if not openai_base_url:
                openai_base_url = str(self.session.config.get("llm.openai_base_url") or "").strip()
            if not profile_backend and openai_base_url and not _is_openai_managed_base_url(openai_base_url):
                profile_backend = str(
                    self.session.config.get("llm.openai_compatible_backend", "other") or "other"
                ).strip().lower()
            is_compat = bool(openai_base_url) and profile_backend not in {"", "openai"}
            self.console.print(
                "  [dim]Set OPENAI_COMPATIBLE_API_KEY (or OPENAI_API_KEY) or enter it now to continue.[/dim]"
                if is_compat
                else "  [dim]Set OPENAI_API_KEY or enter it now to continue.[/dim]"
            )
            prompt = (
                f"  Enter OpenAI-compatible API key for '{profile_label}' (or press Enter to cancel): "
                if is_compat
                else "  Enter OpenAI API key (or press Enter to cancel): "
            )
            cfg_key = None if is_compat else "llm.openai_api_key"
        else:
            self.console.print(
                "  [dim]Set ANTHROPIC_API_KEY or enter it now to continue.[/dim]"
            )
            prompt = "  Enter Anthropic API key (or press Enter to cancel): "
            cfg_key = "llm.anthropic_api_key"

        try:
            api_key = self._secret_prompt_session.prompt(
                [("class:prompt", prompt)],
                is_password=True,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return False

        if not api_key:
            self.console.print("  [dim]Cancelled.[/dim]")
            return False

        try:
            from agent.config import Config
            if (
                provider == "openai"
                and cfg_key is None
                and isinstance(self.session.config, Config)
            ):
                self.session.config.upsert_openai_profile(
                    profile_id=profile_id,
                    label=profile_label,
                    backend=profile_backend or "other",
                    base_url=openai_base_url or "http://localhost:11434/v1",
                    api_key=api_key,
                    set_active=True,
                )
            else:
                target_key = cfg_key or "llm.openai_compatible_api_key"
                self.session.config.set(target_key, api_key)
        except ValueError as exc:
            self.console.print(f"  [red]{exc}[/red]")
            return False
        self.session.config.save()
        return self.session.config.llm_preflight_issue() is None

    def _replay_trace_events(self, events: list[dict]) -> bool:
        """Replay persisted trace events using the same renderer as live runs.

        Returns True when at least one assistant text block was rendered.
        """
        if not events:
            return False

        from ui.traces import TraceRenderer

        trace_renderer = TraceRenderer(
            self.console,
            config=getattr(self.session, "config", None),
        )
        tool_inputs: dict[str, dict] = {}
        tool_names: dict[str, str] = {}
        rendered_text = False

        for event in events:
            etype = str(event.get("type") or "")
            if etype == "text":
                content = str(event.get("content") or "")
                if content.strip():
                    trace_renderer.render_reasoning(content)
                    rendered_text = True
                continue

            if etype == "tool_start":
                tool = str(event.get("tool") or "unknown_tool")
                tool_use_id = str(event.get("tool_use_id") or "")
                tool_input = event.get("input") if isinstance(event.get("input"), dict) else {}
                if tool_use_id:
                    tool_inputs[tool_use_id] = tool_input
                    tool_names[tool_use_id] = tool
                trace_renderer.render_tool_start(tool, tool_input)
                continue

            if etype == "tool_result":
                tool_use_id = str(event.get("tool_use_id") or "")
                tool = str(event.get("tool") or "")
                if not tool and tool_use_id:
                    tool = str(tool_names.get(tool_use_id) or "")
                if not tool:
                    tool = "unknown_tool"
                tool_input = tool_inputs.get(tool_use_id, {})
                result_text = str(event.get("result_text") or "")
                is_error = bool(event.get("is_error"))
                duration_s = float(event.get("duration_s") or 0.0)
                if is_error:
                    trace_renderer.render_tool_error(tool, result_text)
                else:
                    trace_renderer.render_tool_complete(tool, tool_input, result_text, duration_s)
                continue

            if etype == "task_started":
                trace_renderer.render_task_started(
                    str(event.get("task_id") or ""),
                    str(event.get("description") or ""),
                    str(event.get("task_type") or "") or None,
                )
                continue

            if etype == "task_progress":
                usage = event.get("usage") if isinstance(event.get("usage"), dict) else None
                trace_renderer.render_task_progress(
                    str(event.get("task_id") or ""),
                    str(event.get("description") or ""),
                    usage,
                    str(event.get("last_tool_name") or "") or None,
                )
                continue

            if etype == "task_notification":
                trace_renderer.render_task_notification(
                    str(event.get("task_id") or ""),
                    str(event.get("status") or ""),
                    str(event.get("summary") or ""),
                    str(event.get("output_file") or ""),
                )

        return rendered_text

    @staticmethod
    def _format_duration_label(duration_s: float) -> str:
        """Format generation duration like live footer (e.g., 24s, 1m 05s)."""
        duration = max(0.0, float(duration_s))
        if duration >= 60:
            mins = int(duration // 60)
            secs = int(duration % 60)
            return f"{mins}m {secs}s"
        return f"{int(round(duration))}s"

    @staticmethod
    def _coerce_int(value) -> int:
        try:
            if value is None:
                return 0
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, (int, float)):
                return max(0, int(value))
            return max(0, int(float(str(value).strip() or "0")))
        except Exception:
            return 0

    def _render_turn_usage_footer(
        self,
        *,
        term_width: int,
        duration_s: float | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        verb: str = "Generated",
    ) -> None:
        """Render one-line turn footer with duration and per-turn token arrows."""
        left = f"✻ {verb}"
        if duration_s is not None:
            left = f"{left} for {self._format_duration_label(duration_s)}"

        in_tokens = self._coerce_int(input_tokens)
        out_tokens = self._coerce_int(output_tokens)
        right = f"↑ {in_tokens:,} ↓ {out_tokens:,}"

        width = max(40, int(term_width or self.console.width or 100))
        inner_width = max(10, width - 2)
        if len(left) + len(right) + 1 <= inner_width:
            spaces = max(1, inner_width - len(left) - len(right))
            self.console.print(
                f"  [#7f8790]{left}{' ' * spaces}[/][dim #7f8790]{right}[/]"
            )
        else:
            self.console.print(
                f"  [#7f8790]{left} · [/][dim #7f8790]{right}[/]"
            )

    def _render_resumed_history(self, term_width: int, turns: list) -> None:
        """Render saved turns so resumed sessions reopen with full context."""
        if not turns:
            return

        trace_blocks = self._load_trace_blocks()
        self.console.print()
        self.console.print("  [cyan]Session History[/cyan]")
        for idx, turn in enumerate(turns):
            query = str(getattr(turn, "query", "") or "").strip()
            answer = str(getattr(turn, "answer", "") or "").strip()
            self.console.print(f"[#333333]{'─' * term_width}[/]")
            if query:
                self.console.print(f"❯ {query}", markup=False)
            rendered_from_trace = False
            duration_s = None
            input_tokens = None
            output_tokens = None
            if idx < len(trace_blocks):
                end = trace_blocks[idx].get("end", {})
                if isinstance(end, dict):
                    raw_duration = end.get("duration_s")
                    if isinstance(raw_duration, (int, float)):
                        duration_s = float(raw_duration)
                events = trace_blocks[idx].get("events", [])
                if isinstance(events, list) and events:
                    rendered_from_trace = self._replay_trace_events(events)
            rows_snapshot = list(getattr(self, "_session_sdk_turn_rows", []))
            run_lock = getattr(self, "_run_lock", None)
            if run_lock is not None and hasattr(run_lock, "__enter__"):
                with run_lock:
                    rows_snapshot = list(getattr(self, "_session_sdk_turn_rows", []))
            if idx < len(rows_snapshot):
                row = rows_snapshot[idx]
                if isinstance(row, dict):
                    # Show fresh (non-cached) input only, matching the live footer.
                    input_tokens = max(
                        0,
                        self._coerce_int(row.get("input_tokens"))
                        - self._coerce_int(row.get("cache_read_tokens")),
                    )
                    output_tokens = self._coerce_int(row.get("output_tokens"))
            if answer and not rendered_from_trace:
                print_markdown_with_mermaid(
                    self.console,
                    answer,
                    config=getattr(self.session, "config", None),
                    markdown_factory=RichMarkdown,
                )
            if duration_s is not None or input_tokens is not None or output_tokens is not None:
                self._render_turn_usage_footer(
                    term_width=term_width,
                    duration_s=duration_s,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    verb="Generated",
                )

    def _switch_model(self):
        """Interactive model switcher."""
        from agent.config import Config

        provider, provider_label, provider_endpoint = self._current_provider_status()
        cfg = self.session.config
        # Match the web UI: only show models enabled in Dashboard → Models
        # (hidden ones are managed there and re-enabled from the same place).
        hidden_models: set[str] = set()
        if isinstance(cfg, Config):
            try:
                hidden_models = set(cfg.hidden_models())
            except Exception:
                hidden_models = set()

        models_with_provider: list[dict[str, str | None]] = []
        profile_discovery_warnings: list[str] = []
        for prov, models in AVAILABLE_MODELS.items():
            for model_id, display, desc in models:
                if model_id == "__custom_openai_compatible__":
                    # Profile management moved to /model-manager.
                    continue
                if model_id in hidden_models:
                    continue
                models_with_provider.append(
                    {
                    "provider": prov,
                    "model_id": model_id,
                    "display": display,
                    "desc": desc,
                    "profile_id": None,
                    }
                )

        # Discover live catalogs for first-party proxy providers (OpenCode Go)
        # when an API key is configured — same behavior as the Models dashboard.
        if isinstance(cfg, Config):
            from agent.config import OPENAI_COMPATIBLE_PROVIDERS
            from agent.model_catalog import format_discovered_model_label
            from agent.model_discovery import probe_compatible_profile

            existing_ids = {
                str(item.get("model_id") or "") for item in models_with_provider
            }
            for prov, meta in OPENAI_COMPATIBLE_PROVIDERS.items():
                if str(meta.get("discover_models") or "").strip().lower() not in {
                    "1",
                    "true",
                    "yes",
                }:
                    continue
                api_key = cfg.llm_api_key(prov)
                if not api_key:
                    continue
                base_url = str(meta.get("base_url") or "").strip()
                if not base_url:
                    continue
                label = str(meta.get("label") or prov)
                probe = probe_compatible_profile(
                    base_url=base_url,
                    backend="other",
                    api_key=api_key,
                )
                discovered_models = list(probe.get("models") or [])
                if not discovered_models:
                    fallback = str(meta.get("default_model") or "").strip()
                    if fallback:
                        discovered_models = [fallback]
                for model_id in discovered_models:
                    if model_id in hidden_models or model_id in existing_ids:
                        continue
                    existing_ids.add(model_id)
                    models_with_provider.append(
                        {
                            "provider": prov,
                            "model_id": model_id,
                            "display": format_discovered_model_label(model_id),
                            "desc": f"{label} (discovered)",
                            "profile_id": None,
                        }
                    )

        if isinstance(cfg, Config):
            compatible_profiles = cfg.openai_profiles(include_cloud=False)
            for profile_id, profile in sorted(
                compatible_profiles.items(),
                key=lambda item: str(item[1].get("label") or item[0]).strip().lower(),
            ):
                backend = str(profile.get("backend") or "other").strip().lower()
                base_url = str(profile.get("base_url") or "").strip()
                if not base_url:
                    continue
                profile_label = str(profile.get("label") or profile_id).strip()
                api_key = str(profile.get("api_key") or "").strip() or None
                discovered_models = self._fetch_compatible_models(
                    base_url,
                    backend=backend,
                    api_key=api_key,
                    quiet=True,
                )
                if not discovered_models:
                    backend_label = self._compatible_backend_display_name(backend)
                    issue = ""
                    probe = self._probe_compatible_profile(
                        base_url=base_url,
                        backend=backend,
                        api_key=api_key,
                    )
                    if isinstance(probe, dict):
                        issue = str(probe.get("error") or "").strip()
                    if issue:
                        profile_discovery_warnings.append(
                            f"{profile_label} ({backend_label}): {issue}"
                        )
                    else:
                        profile_discovery_warnings.append(
                            f"{profile_label} ({backend_label}): no models discovered"
                        )
                if not discovered_models and profile_id == cfg.active_openai_profile_id():
                    fallback_model = str(profile.get("default_model") or "").strip()
                    if fallback_model:
                        discovered_models = [fallback_model]
                for discovered_model in discovered_models:
                    models_with_provider.append(
                        {
                            "provider": "local",
                            "model_id": discovered_model,
                            "display": f"{profile_label}: {discovered_model}",
                            "desc": f"{backend} profile model",
                            "profile_id": profile_id,
                            "backend": backend,
                        }
                    )

        current = self.session.current_model
        active_profile_id = None
        active_openai_profile = None
        if isinstance(cfg, Config):
            active_profile_id = cfg.active_openai_profile_id()
            active_openai_profile = cfg.get_openai_profile(active_profile_id)
        active_backend = str((active_openai_profile or {}).get("backend") or "").strip().lower()

        compat_backend = self._current_compatible_backend_label()
        backend_suffix = f" ({compat_backend})" if compat_backend else ""
        self.console.print(
            f"\n  [cyan]Current model:[/cyan] {self._model_display_name()}{backend_suffix} ({current})"
        )
        self.console.print(f"  [cyan]Provider:[/cyan] {provider_label}{backend_suffix}\n")
        if provider_endpoint:
            self.console.print(f"  [cyan]Endpoint:[/cyan] {provider_endpoint}\n")

        if not models_with_provider:
            self.console.print("  [yellow]No model options configured[/yellow]")
            return

        for i, option in enumerate(models_with_provider, 1):
            prov = str(option.get("provider") or "")
            model_id = str(option.get("model_id") or "")
            display = str(option.get("display") or model_id)
            desc = str(option.get("desc") or "")
            profile_id = str(option.get("profile_id") or "").strip() or None
            backend = str(option.get("backend") or "").strip().lower()
            is_current = False
            if model_id == current and str(provider).strip().lower() == prov:
                if profile_id:
                    is_current = profile_id == (active_profile_id or "")
                elif prov == "openai":
                    is_current = active_backend in {"", "openai"}
                else:
                    is_current = True
            marker = " [green]*[/green]" if is_current else "  "
            if profile_id:
                provider_hint = self._compatible_backend_display_name(backend)
            else:
                provider_hint = prov
            self.console.print(
                f"  {marker} [{i}] {display} [dim]({provider_hint})[/dim] — [dim]{desc}[/dim]"
            )

        if profile_discovery_warnings:
            self.console.print(
                "  Warning: some compatible providers are unhealthy or returned no models.",
                style="yellow",
            )
            for warning in profile_discovery_warnings[:3]:
                self.console.print(
                    f"    - {self._truncate_discovery_detail(warning, max_chars=160)}",
                    style="dim",
                    markup=False,
                )
            remaining = len(profile_discovery_warnings) - 3
            if remaining > 0:
                self.console.print(
                    f"    - (+{remaining} more profiles)",
                    style="dim",
                    markup=False,
                )
            self.console.print(
                "    Run /model-manager to inspect health and provider config.",
                style="dim",
                markup=False,
            )

        self.console.print()

        try:
            choice = self._prompt_session.prompt(
                [("class:prompt", "  Select model (number): ")],
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return

        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(models_with_provider):
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        idx = int(choice) - 1
        selected = models_with_provider[idx]
        selected_provider = str(selected.get("provider") or "")
        model_id = str(selected.get("model_id") or "")
        display = str(selected.get("display") or model_id)
        selected_profile_id = str(selected.get("profile_id") or "").strip() or None
        # Catalog labels local profile models as "local"; runtime still uses openai.
        runtime_provider = "openai" if selected_provider == "local" else selected_provider

        same_model = model_id == current and str(provider).strip().lower() == runtime_provider
        same_profile = True
        if selected_profile_id and isinstance(cfg, Config):
            same_profile = selected_profile_id == (active_profile_id or "")
        if same_model and same_profile:
            self.console.print(f"  [dim]Already using {display}.[/dim]")
            return

        self.session.set_model(model_id, provider=runtime_provider)
        if runtime_provider == "openai":
            # Built-in OpenAI models should use the cloud profile by default.
            if isinstance(cfg, Config):
                if selected_profile_id:
                    cfg.set_openai_active_profile(selected_profile_id)
                    cfg.upsert_openai_profile(
                        profile_id=selected_profile_id,
                        default_model=model_id,
                    )
                else:
                    cfg.set_openai_active_profile("openai_cloud")
            else:
                self.session.config.unset("llm.openai_base_url")
                self.session.config.unset("llm.openai_compatible_backend")
        self.session.config.save()  # Persist to ~/.fastfold-cli/config.json
        self.console.print(
            f"  [green]Switched to {display}[/green] ({model_id}) [dim]provider={selected_provider}[/dim]"
        )

    def _configure_openai_compatible_model(self) -> None:
        """Manage compatible profiles and switch model using selected profile."""
        from agent.config import Config

        if not isinstance(self.session.config, Config):
            self._configure_openai_compatible_model_legacy()
            return

        cfg = self.session.config
        self.console.print("\n  [cyan]OpenAI-compatible profile setup[/cyan]")
        self.console.print("  [dim]Switch, add, or edit Ollama/Unsloth/oMLX/custom profiles.[/dim]")

        profiles = cfg.openai_profiles(include_cloud=False)
        has_profiles = bool(profiles)
        default_choice = "1" if has_profiles else "2"
        self.console.print("    [1] Use existing profile")
        self.console.print("    [2] Add new profile")
        self.console.print("    [3] Edit existing profile")
        self.console.print("    [4] Cancel")
        try:
            raw_choice = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Select action [{default_choice}]: ")]
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return
        selected_action = raw_choice or default_choice
        if selected_action in {"4", "cancel", "c", "q"}:
            self.console.print("  [dim]Cancelled.[/dim]")
            return
        if selected_action in {"2", "new", "add", "a"}:
            profile_id = self._create_or_edit_compatible_profile()
            if not profile_id:
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            self._activate_compatible_profile(profile_id)
            return
        if selected_action in {"3", "edit", "e"}:
            profile_id = self._prompt_select_compatible_profile_id(cfg=cfg, allow_create=False)
            if not profile_id:
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            updated_profile_id = self._create_or_edit_compatible_profile(profile_id=profile_id)
            if not updated_profile_id:
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            self._activate_compatible_profile(updated_profile_id)
            return

        profile_id = self._prompt_select_compatible_profile_id(
            cfg=cfg,
            allow_create=True,
            create_label="Add new profile",
        )
        if profile_id == "__create__":
            created_profile_id = self._create_or_edit_compatible_profile()
            if not created_profile_id:
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            self._activate_compatible_profile(created_profile_id)
            return
        if not profile_id:
            self.console.print("  [dim]Cancelled.[/dim]")
            return
        self._activate_compatible_profile(profile_id)

    def _configure_openai_compatible_model_legacy(self) -> None:
        """Legacy single-endpoint OpenAI-compatible setup for backward compatibility."""
        existing_base_url = (
            str(self.session.config.get("llm.openai_base_url") or "").strip()
            or "http://localhost:11434/v1"
        )
        default_base_url = existing_base_url
        default_model = str(self.session.current_model or "").strip()
        if default_model in {"", "__custom_openai_compatible__"}:
            default_model = "llama3.1"
        current_key = str(self.session.config.get("llm.openai_compatible_api_key") or "").strip()

        self.console.print("\n  [cyan]OpenAI-compatible endpoint setup[/cyan]")
        self.console.print(
            "  [dim]Examples: Ollama, Unsloth, oMLX, DS4, llama.cpp, LM Studio, vLLM, gateway proxies[/dim]"
        )

        backend = self._prompt_openai_compatible_backend(default_base_url)
        if not backend:
            self.console.print("  [dim]Cancelled.[/dim]")
            return
        if backend == "other":
            default_base_url = existing_base_url
        else:
            default_base_url = self._compatible_default_base_url(
                backend,
                fallback=existing_base_url,
            )

        try:
            endpoint_input = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Endpoint base URL [{default_base_url}]: ")],
            ).strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return
        base_url = (endpoint_input or default_base_url).rstrip("/")
        if not base_url:
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        if backend == "ollama":
            default_key = "ollama"
            key_hint = (
                "  API key [(optional) Enter leaves blank; :default uses ollama; :keep keeps existing]: "
            )
        elif backend == "unsloth":
            default_key = current_key or ""
            key_hint = "  API key [Unsloth sk-unsloth-...; Enter leaves blank; :keep keeps existing]: "
        elif backend == "omlx":
            default_key = current_key or ""
            key_hint = "  API key [oMLX; Enter leaves blank; :keep keeps existing]: "
        elif backend == "ds4":
            default_key = current_key or ""
            key_hint = "  API key [DS4 token (optional); Enter leaves blank; :keep keeps existing]: "
        elif backend == "llama_cpp":
            default_key = current_key or ""
            key_hint = "  API key [llama.cpp key (optional); Enter leaves blank; :keep keeps existing]: "
        elif backend == "lm_studio":
            default_key = current_key or ""
            key_hint = "  API key [LM Studio key (optional); Enter leaves blank; :keep keeps existing]: "
        else:
            default_key = current_key or ""
            key_hint = "  API key [optional; Enter leaves blank; :keep keeps existing]: "
        try:
            api_key_input = self._secret_prompt_session.prompt(
                [("class:prompt", key_hint)],
                is_password=True,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        effective_key = self._resolve_optional_api_key_input(
            api_key_input,
            existing_key=current_key,
            default_key=default_key,
        )
        discovered_models = self._fetch_compatible_models(
            base_url,
            backend=backend,
            api_key=effective_key or None,
        )
        while not discovered_models:
            action = self._prompt_discovery_followup_action()
            if action is None or action == "cancel":
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            if action == "manual":
                break

            try:
                retry_key = self._secret_prompt_session.prompt(
                    [("class:prompt", "  New API key [Enter to skip retry]: ")],
                    is_password=True,
                ).strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            if not retry_key:
                self.console.print("  [dim]Retry skipped; keeping current key.[/dim]")
                continue
            effective_key = retry_key
            discovered_models = self._fetch_compatible_models(
                base_url,
                backend=backend,
                api_key=effective_key or None,
            )
        model_id = self._choose_model_from_discovered_tags(discovered_models, default_model)
        if not model_id:
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        self.session.set_model(model_id, provider="openai")
        self.session.config.set("llm.openai_base_url", base_url)
        self.session.config.set("llm.openai_compatible_backend", backend)
        if effective_key:
            self.session.config.set("llm.openai_compatible_api_key", effective_key)
        else:
            self.session.config.unset("llm.openai_compatible_api_key")
        self.session.config.save()

        key_state = "configured" if self.session.config.get("llm.openai_compatible_api_key") else "not set"
        self.console.print(
            "  [green]Switched to OpenAI-compatible endpoint[/green] "
            f"[dim]model={model_id} endpoint={base_url} api_key={key_state}[/dim]"
        )

    def _create_or_edit_compatible_profile(self, profile_id: str | None = None) -> str | None:
        """Create or edit an OpenAI-compatible profile and return profile id."""
        cfg = self.session.config
        existing_profile = cfg.get_openai_profile(profile_id) if profile_id else None
        existing_backend = str((existing_profile or {}).get("backend") or "").strip().lower()
        existing_base_url = str((existing_profile or {}).get("base_url") or "").strip()
        existing_key = str((existing_profile or {}).get("api_key") or "").strip()
        existing_default_model = str((existing_profile or {}).get("default_model") or "").strip()

        default_base_url = existing_base_url or "http://localhost:11434/v1"
        backend = self._prompt_openai_compatible_backend(default_base_url)
        if not backend:
            return None
        if backend != "other":
            default_base_url = self._compatible_default_base_url(
                backend,
                fallback=default_base_url,
            )

        label_defaults = {
            "ollama": "Ollama Local",
            "unsloth": "Unsloth Local",
            "omlx": "oMLX Local",
            "ds4": "DS4 Local",
            "llama_cpp": "llama.cpp Local",
            "lm_studio": "LM Studio Local",
            "other": "Custom Compatible Endpoint",
        }
        default_label = str((existing_profile or {}).get("label") or "").strip() or label_defaults.get(
            backend, "Compatible Endpoint"
        )
        label = self._prompt_profile_label(default_label)
        if not label:
            return None

        try:
            endpoint_input = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Endpoint base URL [{default_base_url}]: ")]
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        base_url = (endpoint_input or default_base_url).rstrip("/")
        if not base_url:
            return None

        if backend == "ollama":
            default_key = existing_key or "ollama"
            key_hint = (
                "  API key [(optional) Enter leaves blank; :default uses ollama; :keep keeps existing]: "
            )
        elif backend == "unsloth":
            default_key = existing_key or ""
            key_hint = "  API key [Unsloth sk-unsloth-...; Enter leaves blank; :keep keeps existing]: "
        elif backend == "omlx":
            default_key = existing_key or ""
            key_hint = "  API key [oMLX; Enter leaves blank; :keep keeps existing]: "
        elif backend == "ds4":
            default_key = existing_key or ""
            key_hint = "  API key [DS4 token (optional); Enter leaves blank; :keep keeps existing]: "
        elif backend == "llama_cpp":
            default_key = existing_key or ""
            key_hint = "  API key [llama.cpp key (optional); Enter leaves blank; :keep keeps existing]: "
        elif backend == "lm_studio":
            default_key = existing_key or ""
            key_hint = "  API key [LM Studio key (optional); Enter leaves blank; :keep keeps existing]: "
        else:
            default_key = existing_key or ""
            key_hint = "  API key [optional; Enter leaves blank; :keep keeps existing]: "
        try:
            api_key_input = self._secret_prompt_session.prompt(
                [("class:prompt", key_hint)],
                is_password=True,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        effective_key = self._resolve_optional_api_key_input(
            api_key_input,
            existing_key=existing_key,
            default_key=default_key,
        )

        profile_default_model = existing_default_model or str(self.session.current_model or "").strip() or "llama3.1"
        if profile_default_model == "__custom_openai_compatible__":
            profile_default_model = "llama3.1"

        saved_profile_id = cfg.upsert_openai_profile(
            profile_id=profile_id,
            label=label,
            backend=backend,
            base_url=base_url,
            api_key=effective_key,
            default_model=profile_default_model,
            set_active=(existing_backend != "openai"),
        )
        cfg.save()
        return saved_profile_id

    def _activate_compatible_profile(self, profile_id: str) -> None:
        """Activate a compatible profile and select a model for it."""
        profile = self.session.config.get_openai_profile(profile_id)
        if not profile:
            self.console.print("  [dim]Profile not found.[/dim]")
            return

        backend = str(profile.get("backend") or "").strip().lower() or "other"
        base_url = str(profile.get("base_url") or "").strip()
        current_key = str(profile.get("api_key") or "").strip()
        default_model = str(profile.get("default_model") or "").strip() or "llama3.1"
        profile_label = str(profile.get("label") or profile_id).strip()

        discovered_models = self._fetch_compatible_models(
            base_url,
            backend=backend,
            api_key=current_key or None,
        )
        effective_key = current_key
        while not discovered_models:
            action = self._prompt_discovery_followup_action()
            if action is None or action == "cancel":
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            if action == "manual":
                break
            try:
                retry_key = self._secret_prompt_session.prompt(
                    [("class:prompt", "  New API key [Enter to skip retry]: ")],
                    is_password=True,
                ).strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            if not retry_key:
                self.console.print("  [dim]Retry skipped; keeping current key.[/dim]")
                continue
            effective_key = retry_key
            discovered_models = self._fetch_compatible_models(
                base_url,
                backend=backend,
                api_key=effective_key or None,
            )

        model_id = self._choose_model_from_discovered_tags(discovered_models, default_model)
        if not model_id:
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        self.session.config.upsert_openai_profile(
            profile_id=profile_id,
            api_key=effective_key or None,
            default_model=model_id,
            set_active=True,
        )
        self.session.set_model(model_id, provider="openai")
        self.session.config.set("llm.provider", "openai")
        self.session.config.save()
        key_state = "configured" if (effective_key or "").strip() else "not set"
        self.console.print(
            f"  [green]Switched to {profile_label}[/green] "
            f"[dim]model={model_id} endpoint={base_url} api_key={key_state}[/dim]"
        )

    def _prompt_openai_compatible_backend(self, base_url: str) -> str | None:
        """Prompt for compatible backend type to avoid endpoint guessing."""
        default_choice = "other"
        current_profile = None
        if hasattr(self.session.config, "get_openai_profile"):
            try:
                current_profile = self.session.config.get_openai_profile()
            except Exception:
                current_profile = None
        if not isinstance(current_profile, dict):
            current_profile = None
        current_key = str(
            (current_profile or {}).get("api_key")
            or self.session.config.get("llm.openai_compatible_api_key")
            or ""
        ).strip()
        current_backend = str(
            (current_profile or {}).get("backend")
            or self.session.config.get("llm.openai_compatible_backend")
            or ""
        ).strip().lower()
        if current_backend in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}:
            default_choice = current_backend
        if current_key.startswith("sk-unsloth-"):
            default_choice = "unsloth"
        elif (
            current_key.lower().startswith("dsv4-")
            or current_key.lower().startswith("sk-ds4-")
            or "ds4" in str(base_url).lower()
            or "deepseek-v4" in str(base_url).lower()
        ):
            default_choice = "ds4"
        elif "1234" in str(base_url) or "lmstudio" in str(base_url).lower() or "lm-studio" in str(base_url).lower():
            default_choice = "lm_studio"
        elif (
            "8080" in str(base_url)
            or "llama.cpp" in str(base_url).lower()
            or "llama-cpp" in str(base_url).lower()
            or "llamacpp" in str(base_url).lower()
        ):
            default_choice = "llama_cpp"
        elif "8000" in str(base_url) or "omlx" in str(base_url).lower():
            default_choice = "omlx"
        elif "11434" in str(base_url):
            default_choice = "ollama"

        self.console.print("  [cyan]Endpoint type[/cyan]")
        self.console.print(
            f"    [1] Ollama (/api/tags) - {self._compatible_install_url('ollama')}"
        )
        self.console.print(
            f"    [2] Unsloth (/v1/models, auth) - {self._compatible_install_url('unsloth')}"
        )
        self.console.print(
            f"    [3] oMLX (/v1/models, auth) - {self._compatible_install_url('omlx')}"
        )
        self.console.print(
            f"    [4] DS4 (DeepSeek v4, /v1/models) - {self._compatible_install_url('ds4')}"
        )
        self.console.print(
            f"    [5] llama.cpp (/v1/models) - {self._compatible_install_url('llama_cpp')}"
        )
        self.console.print(
            f"    [6] LM Studio (/v1/models) - {self._compatible_install_url('lm_studio')}"
        )
        self.console.print("    [7] Other OpenAI-compatible (/v1/models then /api/tags)")
        default_num = {
            "ollama": "1",
            "unsloth": "2",
            "omlx": "3",
            "ds4": "4",
            "llama_cpp": "5",
            "lm_studio": "6",
            "other": "7",
        }[default_choice]
        try:
            raw = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Select endpoint type [{default_num}]: ")],
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        selected = (raw or default_num).strip().lower()
        if selected in {"1", "ollama", "o"}:
            return "ollama"
        if selected in {"2", "unsloth", "u"}:
            return "unsloth"
        if selected in {"3", "omlx", "m"}:
            return "omlx"
        if selected in {"4", "ds4", "deepseek", "deepseek-v4"}:
            return "ds4"
        if selected in {"5", "llama.cpp", "llama_cpp", "llamacpp", "llama-cpp"}:
            return "llama_cpp"
        if selected in {"6", "lmstudio", "lm_studio", "lm-studio", "lm studio"}:
            return "lm_studio"
        if selected in {"7", "other", "custom", "k"}:
            return "other"
        self.console.print("  [dim]Invalid selection; using generic compatible mode.[/dim]")
        return "other"

    @staticmethod
    def _ollama_tags_url_from_base(base_url: str) -> str:
        """Build an Ollama /api/tags URL from an OpenAI-compatible base URL."""
        parsed = urlparse(str(base_url or "").strip())
        path = (parsed.path or "").rstrip("/")
        if path.endswith("/v1"):
            path = path[:-3]
        tags_path = f"{path}/api/tags" if path else "/api/tags"
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                tags_path,
                "",
                "",
                "",
            )
        )

    @staticmethod
    def _openai_models_url_from_base(base_url: str) -> str:
        """Build an OpenAI-compatible /v1/models URL from base URL."""
        parsed = urlparse(str(base_url or "").strip())
        path = (parsed.path or "").rstrip("/")
        if path.endswith("/v1"):
            models_path = f"{path}/models"
        elif path:
            models_path = f"{path}/v1/models"
        else:
            models_path = "/v1/models"
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                models_path,
                "",
                "",
                "",
            )
        )

    @staticmethod
    def _truncate_discovery_detail(text: str, max_chars: int = 320) -> str:
        value = str(text or "").strip()
        if len(value) <= max_chars:
            return value
        return value[:max_chars] + f"... [{len(value)} chars total]"

    @staticmethod
    def _extract_discovery_error_message(raw: str) -> str:
        """Extract a compact human-readable message from API error payloads."""
        value = str(raw or "").strip()
        if not value:
            return ""
        try:
            payload = json.loads(value)
        except Exception:
            return value

        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict):
                msg = str(err.get("message") or err.get("detail") or "").strip()
                code = str(err.get("code") or "").strip()
                if msg:
                    return f"{msg} (code={code})" if code else msg
            for key in ("message", "detail", "description", "error_description"):
                msg = payload.get(key)
                if isinstance(msg, str) and msg.strip():
                    return msg.strip()
        return value

    @staticmethod
    def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
        """Best-effort read of HTTPError response body."""
        try:
            body = exc.read()
        except Exception:
            return ""
        if not body:
            return ""
        return body.decode("utf-8", errors="replace").strip()

    def _report_discovery_http_error(self, endpoint: str, url: str, exc: urllib.error.HTTPError) -> None:
        status = int(getattr(exc, "code", 0) or 0)
        reason = str(getattr(exc, "reason", "") or getattr(exc, "msg", "")).strip()
        body_raw = self._read_http_error_body(exc)
        body_msg = self._extract_discovery_error_message(body_raw)

        self.console.print(
            f"  [yellow]{endpoint} request failed[/yellow] "
            f"[dim](status={status or 'unknown'}, url={url})[/dim]"
        )
        if reason:
            self.console.print(f"  [dim]Reason:[/dim] {reason}")
        if body_msg:
            self.console.print(
                f"  [dim]Response:[/dim] {self._truncate_discovery_detail(body_msg)}",
                markup=False,
            )

    def _report_discovery_exception(self, endpoint: str, url: str, exc: Exception) -> None:
        self.console.print(
            f"  [yellow]{endpoint} request failed[/yellow] [dim](url={url})[/dim]"
        )
        self.console.print(
            f"  [dim]Error:[/dim] {self._truncate_discovery_detail(str(exc))}",
            markup=False,
        )

    def _fetch_openai_models(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        quiet: bool = False,
        return_error: bool = False,
    ) -> list[str] | tuple[list[str], str | None]:
        """Fetch model ids from OpenAI-compatible /v1/models."""
        auth_headers = {"Accept": "application/json"}
        if api_key:
            auth_headers["Authorization"] = f"Bearer {api_key}"
        models_url = self._openai_models_url_from_base(base_url)
        req_models = urllib.request.Request(
            url=models_url,
            headers=auth_headers,
            method="GET",
        )
        error_message: str | None = None
        try:
            if quiet:
                with urllib.request.urlopen(req_models, timeout=5.0) as resp:
                    payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
            else:
                with self.console.status("[green]Discovering models from /v1/models...[/green]", spinner="dots"):
                    with urllib.request.urlopen(req_models, timeout=5.0) as resp:
                        payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
            data = payload.get("data") if isinstance(payload, dict) else None
        except urllib.error.HTTPError as exc:
            if not quiet:
                self._report_discovery_http_error("/v1/models", models_url, exc)
                if exc.code in {401, 403}:
                    self.console.print(
                        "  [yellow]/v1/models requires endpoint auth.[/yellow] "
                        "[dim]Check API key if model list is empty.[/dim]"
                    )
            body_raw = self._read_http_error_body(exc)
            body_msg = self._extract_discovery_error_message(body_raw) if body_raw else ""
            reason = str(getattr(exc, "reason", "") or getattr(exc, "msg", "")).strip()
            parts = [f"status={int(getattr(exc, 'code', 0) or 0)}", f"url={models_url}"]
            if reason:
                parts.append(reason)
            if body_msg:
                parts.append(body_msg)
            error_message = " | ".join(parts)
            if return_error:
                return [], error_message
            return []
        except (urllib.error.URLError, TimeoutError) as exc:
            if not quiet:
                self._report_discovery_exception("/v1/models", models_url, exc)
            error_message = str(exc)
            if return_error:
                return [], error_message
            return []
        except Exception as exc:
            if not quiet:
                self._report_discovery_exception("/v1/models", models_url, exc)
            error_message = str(exc)
            if return_error:
                return [], error_message
            return []

        names: list[str] = []
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or "").strip()
            if model_id and model_id not in names:
                names.append(model_id)
        if names and not quiet:
            self.console.print(f"  [green]Found {len(names)} model(s) from /v1/models.[/green]")
        if return_error:
            return names, error_message
        return names

    def _fetch_ollama_tags(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        quiet: bool = False,
        return_error: bool = False,
    ) -> list[str] | tuple[list[str], str | None]:
        """Fetch model names from Ollama /api/tags."""
        auth_headers = {"Accept": "application/json"}
        if api_key:
            auth_headers["Authorization"] = f"Bearer {api_key}"
        tags_url = self._ollama_tags_url_from_base(base_url)
        req_tags = urllib.request.Request(
            url=tags_url,
            headers=auth_headers,
            method="GET",
        )
        error_message: str | None = None
        try:
            if quiet:
                with urllib.request.urlopen(req_tags, timeout=5.0) as resp:
                    payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
            else:
                with self.console.status("[green]Discovering models from /api/tags...[/green]", spinner="dots"):
                    with urllib.request.urlopen(req_tags, timeout=5.0) as resp:
                        payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
        except urllib.error.HTTPError as exc:
            if not quiet:
                self._report_discovery_http_error("/api/tags", tags_url, exc)
            body_raw = self._read_http_error_body(exc)
            body_msg = self._extract_discovery_error_message(body_raw) if body_raw else ""
            reason = str(getattr(exc, "reason", "") or getattr(exc, "msg", "")).strip()
            parts = [f"status={int(getattr(exc, 'code', 0) or 0)}", f"url={tags_url}"]
            if reason:
                parts.append(reason)
            if body_msg:
                parts.append(body_msg)
            error_message = " | ".join(parts)
            if return_error:
                return [], error_message
            return []
        except (urllib.error.URLError, TimeoutError) as exc:
            if not quiet:
                self._report_discovery_exception("/api/tags", tags_url, exc)
            error_message = str(exc)
            if return_error:
                return [], error_message
            return []
        except Exception as exc:
            if not quiet:
                self._report_discovery_exception("/api/tags", tags_url, exc)
            error_message = str(exc)
            if return_error:
                return [], error_message
            return []

        models = payload.get("models") if isinstance(payload, dict) else None
        names: list[str] = []
        for item in models if isinstance(models, list) else []:
            if not isinstance(item, dict):
                continue
            raw = item.get("name") or item.get("model")
            name = str(raw or "").strip()
            if name and name not in names:
                names.append(name)
        if names and not quiet:
            self.console.print(f"  [green]Found {len(names)} model(s) from /api/tags.[/green]")
        if return_error:
            return names, error_message
        return names

    def _fetch_compatible_models(
        self,
        base_url: str,
        backend: str,
        api_key: str | None = None,
        *,
        quiet: bool = False,
    ) -> list[str]:
        """Discover models based on selected endpoint type."""
        backend_type = str(backend or "").strip().lower()
        if backend_type in {"unsloth", "omlx", "ds4", "llama_cpp", "lm_studio"}:
            names = self._fetch_openai_models(base_url, api_key=api_key, quiet=quiet)
        elif backend_type == "ollama":
            names = self._fetch_ollama_tags(base_url, api_key=api_key, quiet=quiet)
            if not names:
                names = self._fetch_openai_models(base_url, api_key=api_key, quiet=quiet)
        else:
            names = self._fetch_openai_models(base_url, api_key=api_key, quiet=quiet)
            if not names:
                names = self._fetch_ollama_tags(base_url, api_key=api_key, quiet=quiet)

        if names:
            return names
        if not quiet:
            self.console.print(
                "  [yellow]No models found from discovery endpoint(s).[/yellow] "
                "[dim]You can still enter a model manually.[/dim]"
            )
        return []

    def _prompt_discovery_followup_action(self) -> str | None:
        """Prompt next step after model discovery returns no results."""
        self.console.print("  [cyan]Model discovery options[/cyan]")
        self.console.print("    [1] Retry discovery with a new API key")
        self.console.print("    [2] Enter model ID manually")
        self.console.print("    [3] Cancel")
        try:
            raw = self._plain_prompt_session.prompt(
                [("class:prompt", "  Select option [2]: ")],
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        if raw in {"1", "retry", "r"}:
            return "retry"
        if raw in {"3", "cancel", "c", "q"}:
            return "cancel"
        if raw in {"", "2", "manual", "m"}:
            return "manual"
        self.console.print("  [dim]Invalid selection; switching to manual model entry.[/dim]")
        return "manual"

    def _choose_model_from_discovered_tags(self, discovered_models: list[str], default_model: str) -> str | None:
        """Choose a model from discovered tags or enter one manually."""
        if discovered_models:
            self.console.print("  [cyan]Available models[/cyan]")
            for i, model_name in enumerate(discovered_models, 1):
                self.console.print(f"    [{i}] {model_name}")
            manual_idx = len(discovered_models) + 1
            self.console.print(f"    [{manual_idx}] Enter custom model name")
            try:
                choice = self._plain_prompt_session.prompt(
                    [("class:prompt", "  Select model (number): ")],
                ).strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if choice.isdigit():
                selected = int(choice)
                if 1 <= selected <= len(discovered_models):
                    return discovered_models[selected - 1]
                if selected == manual_idx:
                    pass
                else:
                    self.console.print("  [dim]Invalid selection; switching to manual entry.[/dim]")
            elif choice:
                self.console.print("  [dim]Invalid selection; switching to manual entry.[/dim]")

        try:
            model_input = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Model ID [{default_model}]: ")],
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        model_id = model_input or default_model
        return model_id or None

    def _getch(self):
        """Read a single character from standard input without requiring Enter."""
        import os
        import sys

        if os.name == "nt":
            import msvcrt

            chb = msvcrt.getch()
            if chb in (b"\x03", b"\x04"):
                raise KeyboardInterrupt
            return chb.decode("latin-1", errors="replace")

        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        # Handle ctrl-c (x03) and ctrl-d (x04)
        if ch in ('\x03', '\x04'):
            raise KeyboardInterrupt
        return ch

    def _change_settings(self):
        """Interactive settings configuration menu."""
        from agent.config import Config, AGENT_PROFILE_PRESETS
        from ui.status import SPINNERS
        
        cfg = Config.load()
        self.session.config = cfg
        
        while True:
            self.console.print("\n  [cyan]Settings Menu[/cyan]")
            self.console.print("  [1] UI Loading Spinner")
            self.console.print("  [2] Agent Profile (Research/Pharma/Enterprise)")
            self.console.print("  [3] Auto-publish HTML Reports")
            self.console.print("  [4] OpenAI-compatible Profiles")
            self.console.print("  [0] Done")
            self.console.print("\n  Select option: ", end="")
            
            import sys
            sys.stdout.flush()
            
            try:
                choice = self._getch()
            except KeyboardInterrupt:
                self.console.print()
                return
                
            self.console.print(choice)
            
            if choice == "0":
                break
            elif choice == "1":
                spinners = list(SPINNERS.keys())
                current_spinner = cfg.get("ui.spinner", "dna_helix")
                self.console.print(f"\n  [cyan]UI Loading Spinner[/cyan]")
                for i, spinner_id in enumerate(spinners, 1):
                    marker = " [green]*[/green]" if spinner_id == current_spinner else "  "
                    self.console.print(f"  {marker} [{i}] {spinner_id}")
                self.console.print("\n  Select spinner: ", end="")
                sys.stdout.flush()
                
                try:
                    s_choice = self._getch()
                except KeyboardInterrupt:
                    self.console.print()
                    return
                    
                self.console.print(s_choice)
                
                if s_choice.isdigit() and 1 <= int(s_choice) <= len(spinners):
                    new_spinner = spinners[int(s_choice) - 1]
                    if new_spinner != current_spinner:
                        cfg.set("ui.spinner", new_spinner)
                        cfg.save()
                        self.console.print(f"  [green]Spinner updated to:[/green] {new_spinner}")
                else:
                    self.console.print("  [dim]Cancelled.[/dim]")

            elif choice == "2":
                profiles = list(AGENT_PROFILE_PRESETS.keys())
                current_profile = cfg.get("agent.profile", "research")
                self.console.print(f"\n  [cyan]Agent Profile[/cyan]")
                for i, profile_id in enumerate(profiles, 1):
                    marker = " [green]*[/green]" if profile_id == current_profile else "  "
                    self.console.print(f"  {marker} [{i}] {profile_id}")
                self.console.print("\n  Select profile: ", end="")
                sys.stdout.flush()
                
                try:
                    p_choice = self._getch()
                except KeyboardInterrupt:
                    self.console.print()
                    return
                    
                self.console.print(p_choice)
                
                if p_choice.isdigit() and 1 <= int(p_choice) <= len(profiles):
                    new_profile = profiles[int(p_choice) - 1]
                    if new_profile != current_profile:
                        cfg.set("agent.profile", new_profile)
                        cfg.save()
                        self.console.print(f"  [green]Profile updated to:[/green] {new_profile}")
                else:
                    self.console.print("  [dim]Cancelled.[/dim]")
                    
            elif choice == "3":
                current_html = cfg.get("output.auto_publish_html_interactive", True)
                self.console.print(f"\n  [cyan]Auto-publish HTML Reports[/cyan]")
                self.console.print(f"  Current: [bold]{'Yes' if current_html else 'No'}[/bold]")
                self.console.print("\n  Enable? (y/n): ", end="")
                sys.stdout.flush()
                
                try:
                    h_choice = self._getch().lower()
                except KeyboardInterrupt:
                    self.console.print()
                    return
                    
                self.console.print(h_choice)
                
                if h_choice == "y":
                    cfg.set("output.auto_publish_html_interactive", True)
                    cfg.save()
                    self.console.print(f"  [green]Auto-publish HTML enabled.[/green]")
                elif h_choice == "n":
                    cfg.set("output.auto_publish_html_interactive", False)
                    cfg.save()
                    self.console.print(f"  [green]Auto-publish HTML disabled.[/green]")
                else:
                    self.console.print("  [dim]Cancelled.[/dim]")
            elif choice == "4":
                self._manage_openai_profiles_settings(cfg)
            else:
                self.console.print("  [dim]Invalid choice.[/dim]")

    def _manage_openai_profiles_settings(self, cfg) -> None:
        """Manage OpenAI-compatible profiles from /settings (add/edit/delete)."""
        import sys

        while True:
            profiles = cfg.openai_profiles(include_cloud=True)

            self.console.print("\n  [cyan]OpenAI Profile Manager[/cyan]")
            for profile_id, profile in sorted(
                profiles.items(),
                key=lambda item: str(item[1].get("label") or item[0]).strip().lower(),
            ):
                label = str(profile.get("label") or profile_id).strip()
                backend = str(profile.get("backend") or "other").strip().lower()
                endpoint = str(profile.get("base_url") or "—").strip()
                self.console.print(
                    f"  - [bold]{profile_id}[/bold] · {label} [dim]({backend}, {endpoint})[/dim]"
                )

            self.console.print("\n  [1] Add compatible profile")
            self.console.print("  [2] Edit compatible profile")
            self.console.print("  [3] Delete compatible profile")
            self.console.print("  [0] Back")
            self.console.print("\n  Select option: ", end="")
            sys.stdout.flush()

            try:
                choice = self._getch()
            except KeyboardInterrupt:
                self.console.print()
                return
            self.console.print(choice)

            if choice == "0":
                return
            if choice == "1":
                profile_id = self._create_or_edit_compatible_profile()
                if profile_id:
                    self.session.config = cfg
                    self.console.print(f"  [green]Profile saved:[/green] {profile_id}")
                else:
                    self.console.print("  [dim]Cancelled.[/dim]")
                continue
            if choice == "2":
                profile_id = self._prompt_select_compatible_profile_id(
                    cfg=cfg,
                    allow_create=False,
                )
                if not profile_id:
                    self.console.print("  [dim]Cancelled.[/dim]")
                    continue
                updated_profile_id = self._create_or_edit_compatible_profile(profile_id=profile_id)
                if updated_profile_id:
                    self.session.config = cfg
                    self.console.print(f"  [green]Profile updated:[/green] {updated_profile_id}")
                else:
                    self.console.print("  [dim]Cancelled.[/dim]")
                continue
            if choice == "3":
                profile_id = self._prompt_select_compatible_profile_id(
                    cfg=cfg,
                    allow_create=False,
                )
                if not profile_id:
                    self.console.print("  [dim]Cancelled.[/dim]")
                    continue
                if not cfg.remove_openai_profile(profile_id):
                    self.console.print("  [yellow]Profile could not be deleted.[/yellow]")
                    continue
                cfg.save()
                self.session.config = cfg
                self.console.print(f"  [green]Deleted profile:[/green] {profile_id}")
                continue
            self.console.print("  [dim]Invalid choice.[/dim]")

    def _prompt_yes_no(self, prompt: str, *, default: bool = True) -> bool:
        """Prompt a yes/no question with a sensible default."""
        suffix = "[Y/n]" if default else "[y/N]"
        try:
            prompt_session = getattr(self, "_plain_prompt_session", None)
            if prompt_session is not None and hasattr(prompt_session, "prompt"):
                raw = prompt_session.prompt([("class:prompt", f"  {prompt} {suffix} ")]).strip().lower()
            else:
                raw = input(f"  {prompt} {suffix} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return False

        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        return default

    @staticmethod
    def _resolve_boltz_cli_path() -> Path | None:
        """Return the first available boltz-api executable path."""
        candidates: list[str] = []
        in_path = shutil.which("boltz-api")
        if in_path:
            candidates.append(in_path)
        candidates.extend(
            [
                str(Path.home() / ".local" / "bin" / "boltz-api"),
                str(Path.home() / ".boltz" / "bin" / "boltz-api"),
            ]
        )
        for candidate in candidates:
            p = Path(candidate).expanduser()
            if p.exists() and p.is_file() and os.access(str(p), os.X_OK):
                return p
        return None

    @staticmethod
    def _boltz_cli_version(executable: Path) -> str:
        """Return a compact boltz-api version string when callable."""
        try:
            proc = subprocess.run(
                [str(executable), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:  # noqa: BLE001
            return "unknown version"
        output = (proc.stdout or proc.stderr or "").strip()
        if not output:
            return "unknown version"
        return output.splitlines()[0].strip()

    def _install_boltz_skill(self) -> bool:
        """Install the official Fastfold boltz skill if missing."""
        from agent.skills import install_skill, installed_skill_names

        installed = set(installed_skill_names())
        if "boltz" in installed:
            self.console.print("  [green]Boltz skill already installed.[/green]")
            return True

        with self.console.status("[green]Installing Fastfold Boltz skill...[/green]", spinner="dots"):
            result = install_skill(_BOLTZ_SKILL_SOURCE, prefer_npx=True)
        if result.get("ok"):
            self.console.print(f"  [green]{result.get('summary', 'Installed boltz skill.')}[/green]")
            self.console.print("  [dim]Skill will be available on your next message.[/dim]")
            return True

        self.console.print(
            "  [yellow]Could not auto-install Boltz skill.[/yellow] "
            f"[dim]{result.get('summary', '')}[/dim]"
        )
        self.console.print(
            f"  [dim]Install manually with:[/dim] /skills-add {_BOLTZ_SKILL_SOURCE}"
        )
        return False

    def _ensure_boltz_cli_ready(self) -> bool:
        """Ensure boltz-api CLI is installed locally."""
        existing = self._resolve_boltz_cli_path()
        if existing:
            version = self._boltz_cli_version(existing)
            self.console.print(f"  [green]boltz-api ready:[/green] {existing} [dim]({version})[/dim]")
            if shutil.which("boltz-api") is None:
                self.console.print(
                    "  [dim]Tip: add ~/.local/bin to PATH if you want `boltz-api` by name in shell.[/dim]"
                )
            return True

        if not shutil.which("curl") or not shutil.which("sh"):
            self.console.print(
                "  [yellow]Could not install boltz-api automatically (missing curl/sh).[/yellow]"
            )
            self.console.print(
                "  [dim]Install manually:[/dim] curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
            )
            return False

        with self.console.status("[green]Installing boltz-api CLI...[/green]", spinner="dots"):
            proc = subprocess.run(
                ["sh", "-lc", _BOLTZ_INSTALL_SCRIPT],
                capture_output=True,
                text=True,
                timeout=180,
            )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            detail = detail.splitlines()[-1] if detail else "installer exited with a non-zero code"
            self.console.print(f"  [yellow]boltz-api install failed:[/yellow] {detail}")
            self.console.print(
                "  [dim]Retry manually:[/dim] curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
            )
            return False

        installed_path = self._resolve_boltz_cli_path()
        if not installed_path:
            self.console.print(
                "  [yellow]boltz-api installer completed, but executable was not found on disk.[/yellow]"
            )
            return False

        version = self._boltz_cli_version(installed_path)
        self.console.print(f"  [green]Installed boltz-api:[/green] {installed_path} [dim]({version})[/dim]")
        if shutil.which("boltz-api") is None:
            self.console.print(
                "  [dim]Tip: add ~/.local/bin to PATH if you want `boltz-api` by name in shell.[/dim]"
            )
        return True

    def _handle_set_boltz_key(self, cfg) -> None:
        """Prompt/update BOLTZ_API_KEY and offer skill/CLI setup."""
        existing_value = str(cfg.get("api.boltz_api_key") or os.environ.get("BOLTZ_API_KEY") or "").strip()
        current_state = "configured" if existing_value else "not set"
        self.console.print(
            f"  [cyan]Update BOLTZ_API_KEY[/cyan] [dim](currently {current_state})[/dim]"
        )
        try:
            api_key_input = self._secret_prompt_session.prompt(
                [("class:prompt", "  New BOLTZ_API_KEY [Enter clears key; :keep keeps existing]: ")],
                is_password=True,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        api_key = self._resolve_optional_api_key_input(
            api_key_input,
            existing_key=existing_value,
            default_key=existing_value,
        )

        if api_key:
            cfg.set("api.boltz_api_key", api_key)
            os.environ["BOLTZ_API_KEY"] = api_key
            self.console.print("  [green]BOLTZ_API_KEY updated.[/green]")
        else:
            cfg.unset("api.boltz_api_key")
            os.environ.pop("BOLTZ_API_KEY", None)
            self.console.print("  [green]BOLTZ_API_KEY cleared.[/green]")

        cfg.save()
        self.session.config = cfg
        self.console.print(cfg.keys_table())

        if not api_key:
            return

        if self._prompt_yes_no("Install Fastfold Boltz skill now?", default=True):
            self._install_boltz_skill()
        else:
            self.console.print("  [dim]Skipped Boltz skill install.[/dim]")

        if self._prompt_yes_no("Install boltz-api CLI now?", default=True):
            self._ensure_boltz_cli_ready()
        else:
            self.console.print("  [dim]Skipped boltz-api install.[/dim]")

    def _handle_mcp_command(self, query: str) -> None:
        """Handle /mcp — list and manage MCP servers (Deep Agents–style)."""
        from agent.mcp_manage import handle_mcp_argv

        parts = query.strip().split()
        # Drop leading /mcp or mcp
        if parts and parts[0].lstrip("/").lower() == "mcp":
            parts = parts[1:]
        handle_mcp_argv(parts or ["list"], self.console)

    def _handle_keys_command(self, query: str) -> None:
        """Handle /keys with optional compatible-profile actions."""
        from agent.config import Config

        cfg = getattr(self.session, "config", None) or Config.load()
        parts = query.strip().split()
        if len(parts) <= 1:
            self.console.print(cfg.keys_table())
            return

        action = str(parts[1] or "").strip().lower()
        if action in {"profile", "use", "select"}:
            profile_id = self._prompt_select_compatible_profile_id(
                cfg=cfg,
                allow_create=False,
            )
            if not profile_id:
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            try:
                cfg.set_openai_active_profile(profile_id)
            except ValueError as exc:
                self.console.print(f"  [red]{exc}[/red]")
                return
            cfg.save()
            self.session.config = cfg
            self.console.print(f"  [green]Active compatible profile:[/green] {profile_id}")
            self.console.print(cfg.keys_table())
            return

        if action in {"set-compatible", "set", "update"}:
            profile_id_arg = str(parts[2] or "").strip() if len(parts) > 2 else ""
            if profile_id_arg:
                profile_id = profile_id_arg
            else:
                active_profile = cfg.get_openai_profile()
                active_backend = str((active_profile or {}).get("backend") or "").strip().lower()
                if active_backend and active_backend != "openai":
                    profile_id = str((active_profile or {}).get("id") or "").strip()
                else:
                    profile_id = self._prompt_select_compatible_profile_id(
                        cfg=cfg,
                        allow_create=False,
                    )
            if not profile_id:
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            profile = cfg.get_openai_profile(profile_id)
            if not profile or str(profile.get("backend") or "").strip().lower() == "openai":
                self.console.print("  [yellow]Select a compatible profile (not OpenAI Cloud).[/yellow]")
                return
            label = str(profile.get("label") or profile_id).strip()
            current_preview = str(profile.get("api_key") or "").strip()
            current_state = "configured" if current_preview else "not set"
            self.console.print(
                f"  [cyan]Update API key for {label}[/cyan] [dim](currently {current_state})[/dim]"
            )
            try:
                api_key_input = self._secret_prompt_session.prompt(
                    [("class:prompt", "  New API key [Enter clears key; :keep keeps existing]: ")],
                    is_password=True,
                ).strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            api_key = self._resolve_optional_api_key_input(
                api_key_input,
                existing_key=current_preview,
                default_key=current_preview,
            )
            cfg.upsert_openai_profile(
                profile_id=profile_id,
                api_key=api_key,
                set_active=True,
            )
            cfg.save()
            self.session.config = cfg
            if api_key:
                self.console.print(f"  [green]Updated key for profile:[/green] {label}")
            else:
                self.console.print(f"  [green]Cleared key for profile:[/green] {label}")
            self.console.print(cfg.keys_table())
            return

        if action in {"set-boltz", "boltz", "set-boltz-key"}:
            self._handle_set_boltz_key(cfg)
            return

        self.console.print(
            "  [dim]Usage:[/dim] /keys  |  /keys profile  |  /keys set-compatible [profile_id]  |  /keys set-boltz"
        )
        self.console.print(cfg.keys_table())

    @staticmethod
    def _compatible_models_path_label(backend: str) -> str:
        """Return discovery path(s) used for a compatible backend."""
        backend_type = str(backend or "").strip().lower()
        if backend_type in {"unsloth", "omlx", "ds4", "llama_cpp", "lm_studio"}:
            return "/v1/models"
        if backend_type == "ollama":
            return "/api/tags -> /v1/models"
        return "/v1/models -> /api/tags"

    def _probe_compatible_profile(
        self,
        *,
        base_url: str,
        backend: str,
        api_key: str | None,
    ) -> dict[str, Any]:
        """Probe one compatible profile and return health/model diagnostics."""
        backend_type = str(backend or "").strip().lower() or "other"
        models_path = self._compatible_models_path_label(backend_type)
        discovered: list[str] = []
        errors: list[str] = []
        source = ""

        if backend_type in {"unsloth", "omlx", "ds4", "llama_cpp", "lm_studio"}:
            models, err = self._fetch_openai_models(
                base_url,
                api_key=api_key,
                quiet=True,
                return_error=True,
            )
            discovered = list(models)
            source = "/v1/models"
            if err:
                errors.append(str(err))
        elif backend_type == "ollama":
            models, err = self._fetch_ollama_tags(
                base_url,
                api_key=api_key,
                quiet=True,
                return_error=True,
            )
            discovered = list(models)
            source = "/api/tags"
            if err:
                errors.append(str(err))
            if not discovered:
                models_fallback, err_fallback = self._fetch_openai_models(
                    base_url,
                    api_key=api_key,
                    quiet=True,
                    return_error=True,
                )
                discovered = list(models_fallback)
                source = "/v1/models"
                if err_fallback:
                    errors.append(str(err_fallback))
        else:
            models, err = self._fetch_openai_models(
                base_url,
                api_key=api_key,
                quiet=True,
                return_error=True,
            )
            discovered = list(models)
            source = "/v1/models"
            if err:
                errors.append(str(err))
            if not discovered:
                models_fallback, err_fallback = self._fetch_ollama_tags(
                    base_url,
                    api_key=api_key,
                    quiet=True,
                    return_error=True,
                )
                discovered = list(models_fallback)
                source = "/api/tags"
                if err_fallback:
                    errors.append(str(err_fallback))

        health = "[green]healthy[/green]" if discovered else "[yellow]no models[/yellow]"
        if not discovered and errors:
            health = "[red]error[/red]"
        error_text = ""
        if errors:
            joined_error = "; ".join(dict.fromkeys(errors))
            error_text = self._truncate_discovery_detail(joined_error, max_chars=120)

        return {
            "health": health,
            "models": discovered,
            "models_source": source,
            "models_path": models_path,
            "error": error_text,
        }

    def _handle_model_manager_command(self, query: str) -> None:
        """Show and manage OpenAI-compatible profiles (add/edit/delete)."""
        from agent.config import Config
        from rich.table import Table
        import sys

        cfg = Config.load()
        self.session.config = cfg

        while True:
            profiles = cfg.openai_profiles(include_cloud=False)
            if not profiles:
                self.console.print("  [yellow]No OpenAI-compatible profiles configured yet.[/yellow]")
                self.console.print("  [dim]Use [1] below to add your first profile.[/dim]")
            else:
                table = Table(title="OpenAI-compatible Profiles")
                table.add_column("Profile", style="bold")
                table.add_column("Backend")
                table.add_column("Endpoint", style="dim")
                table.add_column("Models Path", style="dim")
                table.add_column("Health")
                table.add_column("API Key", style="magenta dim")
                table.add_column("Models", style="dim")

                for profile_id, profile in sorted(
                    profiles.items(),
                    key=lambda item: str(item[1].get("label") or item[0]).strip().lower(),
                ):
                    backend = str(profile.get("backend") or "other").strip().lower() or "other"
                    endpoint = str(profile.get("base_url") or "").strip() or "—"
                    profile_label = str(profile.get("label") or profile_id).strip()
                    api_key = str(profile.get("api_key") or "").strip() or None

                    probe = self._probe_compatible_profile(
                        base_url=endpoint,
                        backend=backend,
                        api_key=api_key,
                    )
                    model_names = list(probe.get("models") or [])
                    models_display = "—"
                    if model_names:
                        shown = model_names[:4]
                        models_display = ", ".join(shown)
                        if len(model_names) > 4:
                            models_display += f" (+{len(model_names) - 4})"
                    elif probe.get("error"):
                        models_display = f"[dim]{probe.get('error')}[/dim]"

                    backend_label = self._compatible_backend_display_name(backend)
                    key_preview = Config._secret_preview(api_key)
                    table.add_row(
                        profile_label,
                        backend_label,
                        endpoint,
                        str(probe.get("models_path") or "—"),
                        str(probe.get("health") or "—"),
                        key_preview,
                        models_display,
                    )

                self.console.print(table)

            self.console.print("  [cyan]Model Manager options[/cyan]")
            self.console.print("  [1] Add compatible profile")
            self.console.print("  [2] Edit compatible profile")
            self.console.print("  [3] Delete compatible profile")
            self.console.print("  [0] Back")
            self.console.print("\n  Select option: ", end="")
            sys.stdout.flush()

            try:
                choice = self._getch()
            except KeyboardInterrupt:
                self.console.print()
                return
            self.console.print(choice)

            if choice == "0":
                return
            if choice == "1":
                profile_id = self._create_or_edit_compatible_profile()
                if profile_id:
                    self.session.config = cfg
                    self.console.print(f"  [green]Profile saved:[/green] {profile_id}")
                else:
                    self.console.print("  [dim]Cancelled.[/dim]")
                continue
            if choice == "2":
                profile_id = self._prompt_select_compatible_profile_id(
                    cfg=cfg,
                    allow_create=False,
                )
                if not profile_id:
                    self.console.print("  [dim]Cancelled.[/dim]")
                    continue
                updated_profile_id = self._create_or_edit_compatible_profile(profile_id=profile_id)
                if updated_profile_id:
                    self.session.config = cfg
                    self.console.print(f"  [green]Profile updated:[/green] {updated_profile_id}")
                else:
                    self.console.print("  [dim]Cancelled.[/dim]")
                continue
            if choice == "3":
                profile_id = self._prompt_select_compatible_profile_id(
                    cfg=cfg,
                    allow_create=False,
                )
                if not profile_id:
                    self.console.print("  [dim]Cancelled.[/dim]")
                    continue
                if not cfg.remove_openai_profile(profile_id):
                    self.console.print("  [yellow]Profile could not be deleted.[/yellow]")
                    continue
                cfg.save()
                self.session.config = cfg
                self.console.print(f"  [green]Deleted profile:[/green] {profile_id}")
                continue
            self.console.print("  [dim]Invalid choice.[/dim]")

    # Backward-compatible alias for older command wiring/tests.
    def _handle_compatible_profiles_command(self, query: str) -> None:
        self._handle_model_manager_command(query)

    def _toggle_plan_mode(self):
        """Toggle plan mode — agent shows plan for approval before executing."""
        cfg = self.session.config
        current = bool(cfg.get("agent.plan_preview", False))
        cfg.set("agent.plan_preview", not current)
        if not current:
            self.console.print("  [#ff79c6]Plan mode ON[/] — agent will preview its plan before executing")
        else:
            self.console.print("  [dim]Plan mode OFF[/dim] — agent will execute directly")

    def _show_usage(self):
        """Show token usage and cost for this session."""
        with self._run_lock:
            sdk_calls = int(self._session_sdk_calls)
            sdk_in = int(self._session_sdk_input_tokens)
            sdk_out = int(self._session_sdk_output_tokens)
            sdk_cache_read = int(self._session_sdk_cache_read_tokens)
            sdk_cache_create = int(self._session_sdk_cache_creation_tokens)
            sdk_models = sorted(self._session_sdk_models)
            sdk_rows = list(self._session_sdk_turn_rows)

        if sdk_calls > 0:
            from rich.table import Table

            table = Table(title="Session SDK Usage", show_lines=False)
            table.add_column("Turn", style="cyan", no_wrap=True)
            table.add_column("Input", justify="right", style="green")
            table.add_column("Output", justify="right", style="green")
            table.add_column("Cache Read", justify="right", style="dim")
            table.add_column("Cache Create", justify="right", style="dim")
            table.add_column("Models", style="dim")

            for row in sdk_rows:
                models = ", ".join(row.get("models", [])) or "-"
                table.add_row(
                    str(row.get("turn", "")),
                    f"{int(row.get('input_tokens', 0)):,}",
                    f"{int(row.get('output_tokens', 0)):,}",
                    f"{int(row.get('cache_read_tokens', 0)):,}",
                    f"{int(row.get('cache_creation_tokens', 0)):,}",
                    models,
                )

            total_models = ", ".join(sdk_models) if sdk_models else "-"
            table.add_row(
                "TOTAL",
                f"{sdk_in:,}",
                f"{sdk_out:,}",
                f"{sdk_cache_read:,}",
                f"{sdk_cache_create:,}",
                total_models,
                style="bold",
            )
            self.console.print(table)
            return

        # Fallback for legacy non-SDK flows.
        llm = self.session.get_llm()
        if hasattr(llm, "usage") and llm.usage.calls:
            self.console.print(f"  {llm.usage.summary()}")
            return
        self.console.print("  [dim]No LLM calls made yet.[/dim]")

    def _show_tasks(self, force_refresh: bool = False):
        """Show current background task watcher state from the SDK runner."""
        runner = None
        if hasattr(self, "agent"):
            runner = getattr(self.agent, "_runner", None)
        if runner is None or not hasattr(runner, "get_background_watch_status"):
            self.console.print("  [dim]No background watcher available in this session.[/dim]")
            return

        # Reconcile pending tasks before rendering so /tasks reflects
        # any just-completed tasks detected by the local output-file probe.
        if hasattr(runner, "refresh_background_watch_status"):
            runner.refresh_background_watch_status(force=force_refresh)

        statuses = runner.get_background_watch_status(include_inactive=True)
        if not statuses:
            self.console.print("  [dim]No background tasks tracked yet.[/dim]")
            return

        from rich.table import Table
        table = Table(title="Background Task Watchers", show_lines=False)
        table.add_column("Session", style="cyan", no_wrap=True)
        table.add_column("Status", style="bold")
        table.add_column("Watcher", style="dim")
        table.add_column("Attempts", style="dim")
        table.add_column("Pending", style="yellow")
        table.add_column("Completed", style="green")
        table.add_column("Updated", style="dim")

        for item in statuses:
            session_id = str(item.get("session_id") or "")
            session_short = session_id[:8] + "…" if len(session_id) > 8 else session_id
            status = str(item.get("status") or "unknown")
            if status == "running":
                status_markup = "[cyan]running[/cyan]"
            elif status == "completed":
                status_markup = "[green]completed[/green]"
            elif status == "timeout":
                status_markup = "[yellow]timeout[/yellow]"
            else:
                status_markup = f"[red]{status}[/red]"

            watcher_alive = bool(item.get("watcher_alive"))
            watcher_text = "alive" if watcher_alive else "stopped"
            attempts_text = str(int(item.get("connection_attempts") or 0))
            disconnect_reason = str(item.get("last_disconnect_reason") or "").strip()
            if disconnect_reason and disconnect_reason != "unknown":
                watcher_text = f"{watcher_text} ({disconnect_reason})"

            pending_ids = [str(x) for x in (item.get("pending_task_ids") or []) if str(x)]
            completed_ids = [str(x) for x in (item.get("completed_task_ids") or []) if str(x)]

            def _compact_ids(ids: list[str]) -> str:
                if not ids:
                    return "—"
                shown = [i[:8] + "…" if len(i) > 8 else i for i in ids[:3]]
                suffix = f" (+{len(ids) - 3})" if len(ids) > 3 else ""
                return ", ".join(shown) + suffix

            updated_at = item.get("last_update_at")
            if isinstance(updated_at, (int, float)) and updated_at > 0:
                age_s = max(0, int(time.time() - updated_at))
                if age_s < 60:
                    updated_text = f"{age_s}s ago"
                elif age_s < 3600:
                    updated_text = f"{age_s // 60}m ago"
                else:
                    updated_text = f"{age_s // 3600}h ago"
            else:
                updated_text = "—"

            table.add_row(
                session_short or "—",
                status_markup,
                watcher_text,
                attempts_text,
                _compact_ids(pending_ids),
                _compact_ids(completed_ids),
                updated_text,
            )

        self.console.print(table)

    def _copy_last_response(self):
        """Copy the last synthesis response to the system clipboard."""
        if not self._last_response:
            self.console.print("  [dim]No response to copy yet.[/dim]")
            return

        try:
            proc = subprocess.run(
                ["pbcopy"], input=self._last_response.encode(),
                capture_output=True, timeout=5,
            )
            if proc.returncode == 0:
                preview = self._last_response[:80].replace("\n", " ")
                self.console.print(f"  [green]Copied to clipboard.[/green] [dim]{preview}...[/dim]")
            else:
                # Fallback for non-macOS
                self.console.print(f"  [yellow]Clipboard not available. Use /export instead.[/yellow]")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.console.print(f"  [yellow]Clipboard not available. Use /export instead.[/yellow]")

    def _truncate_for_export(self, text: str, max_chars: int = 800) -> str:
        """Trim long text fields for readable markdown export."""
        if not text:
            return ""
        value = text.strip()
        if len(value) <= max_chars:
            return value
        return value[:max_chars] + f"... [{len(value)} chars total]"

    def _format_tool_args_for_export(self, args: dict | None) -> str:
        """Compactly render tool args in export timeline."""
        if not isinstance(args, dict) or not args:
            return ""
        parts = []
        for key, value in args.items():
            if str(key).startswith("_"):
                continue
            raw = str(value).replace("\n", " ")
            if len(raw) > 120:
                raw = raw[:120] + "..."
            parts.append(f"{key}={raw}")
        return ", ".join(parts)

    def _load_trace_blocks(self) -> list[dict]:
        """Load and group trace events into query blocks."""
        if not hasattr(self, "agent") or not hasattr(self.agent, "trace_store"):
            return []
        trace_path = getattr(self.agent.trace_store, "path", None)
        if trace_path is None or not Path(trace_path).exists():
            return []

        try:
            from agent.trace_store import TraceStore
            events = TraceStore.load(trace_path)
        except Exception:
            return []

        blocks: list[dict] = []
        current: dict | None = None
        for event in events:
            etype = event.get("type")
            if etype == "query_start":
                if current is not None:
                    blocks.append(current)
                current = {"start": event, "events": [], "end": None}
                continue
            if etype == "query_end":
                if current is None:
                    current = {"start": None, "events": [], "end": event}
                else:
                    current["end"] = event
                blocks.append(current)
                current = None
                continue

            if current is None:
                current = {"start": None, "events": [], "end": None}
            current["events"].append(event)

        if current is not None:
            blocks.append(current)

        return blocks

    def _render_trace_timeline_markdown(self, block: dict) -> list[str]:
        """Render detailed chronological timeline for one query block."""
        events = block.get("events", [])
        if not isinstance(events, list) or not events:
            return ["### Timeline", "", "_No detailed trace events captured for this query._", ""]

        lines: list[str] = ["### Timeline", ""]
        attempts_by_tool: dict[str, int] = {}
        attempts_by_tool_use_id: dict[str, int] = {}

        for event in events:
            etype = str(event.get("type") or "")

            if etype == "text":
                snippet = self._truncate_for_export(str(event.get("content") or ""), max_chars=260)
                if snippet:
                    lines.append(f"- assistant: {snippet}")
                continue

            if etype == "tool_start":
                tool = str(event.get("tool") or "unknown_tool")
                tool_use_id = str(event.get("tool_use_id") or "")
                attempts_by_tool[tool] = attempts_by_tool.get(tool, 0) + 1
                attempt = attempts_by_tool[tool]
                if tool_use_id:
                    attempts_by_tool_use_id[tool_use_id] = attempt
                arg_text = self._format_tool_args_for_export(event.get("input"))
                if arg_text:
                    lines.append(
                        f"- tool start: `{tool}` (attempt {attempt})"
                        f" — args: `{arg_text}`"
                    )
                else:
                    lines.append(f"- tool start: `{tool}` (attempt {attempt})")
                continue

            if etype == "tool_result":
                tool = str(event.get("tool") or "unknown_tool")
                tool_use_id = str(event.get("tool_use_id") or "")
                attempt = attempts_by_tool_use_id.get(tool_use_id, attempts_by_tool.get(tool, 1))
                status = "error" if bool(event.get("is_error")) else "ok"
                duration = event.get("duration_s")
                duration_text = ""
                if isinstance(duration, (int, float)):
                    duration_text = f", duration={duration:.2f}s"
                lines.append(
                    f"- tool result: `{tool}` (attempt {attempt})"
                    f" — status={status}{duration_text}"
                )
                output = self._truncate_for_export(str(event.get("result_text") or ""), max_chars=400)
                if output:
                    lines.append(f"  - output: `{output}`")
                continue

            # Keep unknown event types visible for debugging.
            lines.append(f"- event: `{etype or 'unknown'}`")

        lines.append("")
        return lines

    def _export_session(self, filename: str = None):
        """Export the session transcript to a markdown file and return the path."""
        if not hasattr(self, 'agent') or not self.agent.trajectory.turns:
            self.console.print("  [dim]No session data to export yet.[/dim]")
            return None

        output_dir = Path.cwd() / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)

        if filename:
            path = output_dir / filename
        else:
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = output_dir / f"session_{ts}.md"

        lines = ["# FastFold Agent CLI Session Export\n"]
        lines.append(f"*Model: {self._model_display_name()}*\n\n---\n")
        trace_blocks = self._load_trace_blocks()

        for i, turn in enumerate(self.agent.trajectory.turns, 1):
            lines.append(f"## Query {i}\n")
            lines.append(f"**Q:** {turn.query}\n")
            lines.append(f"**A:** {turn.answer}\n")
            if turn.entities:
                lines.append(f"*Entities: {', '.join(turn.entities)}*\n")
            if turn.tools_used:
                lines.append(f"*Tools: {', '.join(turn.tools_used)}*\n")
            if i <= len(trace_blocks):
                block = trace_blocks[i - 1]
                start = block.get("start") or {}
                end = block.get("end") or {}
                if start:
                    query_model = start.get("model")
                    if query_model:
                        lines.append(f"*Trace model: {query_model}*\n")
                if end:
                    duration = end.get("duration_s")
                    cost = end.get("cost_usd")
                    if isinstance(duration, (int, float)):
                        lines.append(f"*Trace duration: {duration:.2f}s*\n")
                    if isinstance(cost, (int, float)):
                        lines.append(f"*Trace cost (USD): {cost:.6f}*\n")
                lines.extend(self._render_trace_timeline_markdown(block))
            lines.append("\n---\n")

        if len(trace_blocks) > len(self.agent.trajectory.turns):
            lines.append("## Additional Trace Blocks\n")
            for j in range(len(self.agent.trajectory.turns), len(trace_blocks)):
                block_num = j + 1
                lines.append(f"### Trace Block {block_num}\n")
                start = trace_blocks[j].get("start") or {}
                if start:
                    raw_query = start.get("query")
                    if raw_query:
                        lines.append(f"**Q:** {raw_query}\n")
                lines.extend(self._render_trace_timeline_markdown(trace_blocks[j]))
                lines.append("\n---\n")

        path.write_text("\n".join(lines))
        self.console.print(f"  [green]Exported to[/green] {path}")
        return path

    def _send_export_to_slack(self, markdown: str, report_name: str) -> dict:
        """Send markdown report to Fastfold Slack report endpoint."""
        from agent.config import Config

        cfg = Config.load()
        api_key = os.environ.get("FASTFOLD_API_KEY") or cfg.get("api.fastfold_cloud_key")
        if not api_key:
            return {
                "ok": False,
                "message": (
                    "Fastfold API key not configured. Run `fastfold setup` or "
                    "`fastfold config set api.fastfold_cloud_key <key>`."
                ),
            }

        base_url = os.environ.get("FASTFOLD_API_BASE_URL", "https://api.fastfold.ai").strip() or "https://api.fastfold.ai"
        url = f"{base_url.rstrip('/')}/v1/slack/messages/agent-cli-report"
        body = json.dumps(
            {
                "markdown": markdown,
                "report_name": report_name,
                "save_to_library": True,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self.console.status("[green]Sending report to Slack...[/green]", spinner="dots"):
                with urllib.request.urlopen(req, timeout=30) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(text) if text else {}
            except Exception:
                data = {}
            return {"ok": False, "message": data.get("message") or f"API error ({e.code})"}
        except urllib.error.URLError as e:
            return {"ok": False, "message": f"Network error: {e.reason}"}

        try:
            data = json.loads(text) if text else {}
        except Exception:
            return {"ok": False, "message": "Invalid JSON response from Fastfold API."}
        if not isinstance(data, dict):
            return {"ok": False, "message": "Unexpected response from Fastfold API."}
        return data

    def _export_share(self, filename: str = None):
        """Export transcript and share to configured Slack report channel."""
        path = self._export_session(filename)
        if path is None:
            return

        try:
            markdown = path.read_text(encoding="utf-8")
        except Exception as exc:
            self.console.print(f"  [red]Could not read export file:[/red] {exc}")
            return

        self.console.print("  [cyan]Sending report to Slack...[/cyan]")
        payload = self._send_export_to_slack(markdown, path.name)
        if bool(payload.get("ok")):
            channel_id = payload.get("channel_id") or "(unknown)"
            library_item_id = payload.get("library_item_id")
            self.console.print(f"  [green]Shared to Slack channel[/green] {channel_id}")
            if library_item_id:
                self.console.print(f"  [green]Saved to library item[/green] {library_item_id}")
            return

        self.console.print(f"  [yellow]{payload.get('message') or 'Failed to share report.'}[/yellow]")
        if bool(payload.get("needs_slack_setup")):
            setup = payload.get("setup_instructions") or (
                "Configure Slack at https://cloud.fastfold.ai/integrations/slack "
                "and set a channel for the agent_cli_report mode."
            )
            self.console.print(f"  [dim]{setup}[/dim]")

    def _export_notebook(self, filename: str = None):
        """Export the current session trace as a Jupyter notebook."""
        if not hasattr(self, 'agent') or not hasattr(self.agent, 'trace_store'):
            self.console.print("  [dim]No trace data available.[/dim]")
            return

        trace_store = self.agent.trace_store
        if not trace_store.path.exists():
            self.console.print("  [dim]No trace data yet. Run a query first.[/dim]")
            return

        try:
            from reports.notebook import trace_to_notebook, save_notebook
        except ImportError:
            self.console.print("  [red]nbformat required.[/red] pip install nbformat")
            return

        nb = trace_to_notebook(trace_store.path)

        output_dir = Path.cwd() / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)

        if filename:
            path = output_dir / filename
        else:
            import re
            slug = re.sub(r"[^a-zA-Z0-9]+", "_", trace_store.session_id).strip("_")
            path = output_dir / f"session_{slug}.ipynb"

        save_notebook(nb, path)
        self.console.print(f"  [green]Notebook exported to[/green] {path}")
        self.console.print(f"  [dim]Open with: jupyter lab {path}[/dim]")

    def _compact_context(self, instructions: str = None):
        """Summarize session trajectory to free context window space."""
        if not hasattr(self, 'agent') or not self.agent.trajectory.turns:
            self.console.print("  [dim]Nothing to compact yet.[/dim]")
            return

        n_turns = len(self.agent.trajectory.turns)
        if n_turns <= 2:
            self.console.print("  [dim]Session too short to compact.[/dim]")
            return

        # Build a summary of the session using the LLM
        context = self.agent.trajectory.context_for_planner()
        focus = f"\nFocus: {instructions}" if instructions else ""
        prompt = (
            f"Summarize this research session into a brief paragraph that preserves "
            f"key findings, entities, and conclusions. Be specific about results and numbers.{focus}\n\n"
            f"{context}"
        )

        try:
            llm = self.session.get_llm()
            response = llm.chat(
                system="You are a research session summarizer. Be concise but preserve specific results.",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1200,
            )
            summary = response.content if hasattr(response, "content") else str(response)
            if not summary.strip():
                raise ValueError("Summarizer returned empty output")

            # Replace all turns except the last one with a single summary turn
            from agent.trajectory import Turn
            last_turn = self.agent.trajectory.turns[-1]
            summary_turn = Turn(
                query="[session summary]",
                answer=summary,
                entities=list(self.agent.trajectory.entities()),
                tools_used=[],
                timestamp=time.time(),
            )
            self.agent.trajectory.turns = [summary_turn, last_turn]
            self.console.print(f"  [green]Compacted[/green] {n_turns} turns → 2 (summary + last)")
        except Exception as e:
            self.console.print(f"  [red]Compact failed:[/red] {e}")

    def _run_shell(self, cmd: str):
        """Execute a shell command and display output."""
        if not cmd:
            self.console.print("  [dim]Usage: !<command>  (e.g., !ls .)[/dim]")
            return

        from tools.shell import _is_blocked
        blocked_reason = _is_blocked(cmd)
        if blocked_reason:
            self.console.print(f"  [yellow]Command blocked:[/yellow] {blocked_reason}")
            return

        try:
            args = shlex.split(cmd, posix=True)
        except ValueError as e:
            self.console.print(f"  [red]Invalid command syntax:[/red] {e}")
            return

        # Expand user-home shorthand for convenience when not using a shell.
        args = [str(Path(arg).expanduser()) if arg.startswith("~") else arg for arg in args]

        try:
            result = subprocess.run(
                args,
                shell=False,
                cwd=str(Path.cwd()),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.stdout:
                self.console.print(result.stdout.rstrip())
            if result.stderr:
                self.console.print(f"[red]{result.stderr.rstrip()}[/red]")
            if result.returncode != 0 and not result.stderr:
                self.console.print(f"  [dim]Exit code: {result.returncode}[/dim]")
        except subprocess.TimeoutExpired:
            self.console.print("  [yellow]Command timed out (30s limit).[/yellow]")
        except Exception as e:
            self.console.print(f"  [red]Error: {e}[/red]")

    def _run_upgrade(self) -> None:
        """Upgrade CLI installation using the shared uv install flow."""
        try:
            from cli import execute_upgrade
        except Exception as exc:
            self.console.print(f"  [red]Could not load upgrade command:[/red] {exc}")
            return

        ok = execute_upgrade(console_obj=self.console, cfg=self.session.config)
        if ok:
            self.console.print("  [dim]Tip: restart fastfold to confirm the new version.[/dim]")

    def _list_sessions(self):
        """Show recent saved sessions."""
        from agent.trajectory import Trajectory
        from rich.table import Table

        sessions = Trajectory.list_sessions()
        if not sessions:
            self.console.print("  [dim]No saved sessions.[/dim]")
            return

        def _relative_time(ts: float | int | None) -> str:
            if not isinstance(ts, (int, float)) or ts <= 0:
                return "—"
            age_s = max(0, int(time.time() - float(ts)))
            if age_s < 5:
                return "just now"
            if age_s < 60:
                return f"{age_s}s ago"
            if age_s < 3600:
                return f"{age_s // 60}m ago"
            if age_s < 86400:
                return f"{age_s // 3600}h ago"
            return f"{age_s // 86400}d ago"

        table = Table(title="/sessions", show_lines=False)
        table.add_column("", style="green", no_wrap=True)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Preview")
        table.add_column("Messages", justify="right", style="magenta")
        table.add_column("Model", style="yellow")
        table.add_column("Last Used", style="dim", no_wrap=True)

        current_session_id = (
            self.agent.trajectory.session_id
            if hasattr(self, "agent") and getattr(self.agent, "trajectory", None)
            else None
        )

        def _preview_text(value: object, max_len: int = 70) -> str:
            # Keep preview strictly single-line so long multiline prompts
            # don't break row layout in the sessions table.
            normalized = " ".join(str(value or "untitled").split())
            return normalized[:max_len] if normalized else "untitled"

        for s in sessions[:20]:
            sid = str(s.get("session_id", "?"))
            title = _preview_text(s.get("title"))
            model = str(s.get("model") or "—")
            n_turns = int(s.get("n_turns") or 0)
            updated_at = s.get("updated_at", s.get("created_at"))
            marker = "*" if current_session_id == sid else ""
            table.add_row(
                marker,
                sid,
                title,
                str(n_turns),
                model,
                _relative_time(updated_at),
            )

        self.console.print()
        self.console.print(table)
        self.console.print(
            "\n  [dim]/resume <id-or-prefix> to continue · /resume <number> from table · /sessions delete <id|number|last> to remove · /sync to share with UI[/dim]"
        )

    def _sync_sessions(self, *, force: bool = False) -> None:
        """Import legacy JSONL CLI sessions into the shared SQLite store for the UI."""
        from agent_server.session_sync import sync_jsonl_sessions

        self.console.print(
            "  [cyan]Syncing legacy CLI sessions into the shared UI database…[/cyan]"
            + (" [dim](force)[/dim]" if force else "")
        )
        result = sync_jsonl_sessions(force=force)
        self.console.print(
            "  [green]Sync complete.[/green] "
            f"scanned={result.scanned} imported={result.imported} "
            f"updated={result.updated} skipped={result.skipped} failed={result.failed}"
        )
        if result.failed and result.details:
            for line in result.details:
                if "failed" in line:
                    self.console.print(f"  [yellow]{line}[/yellow]")
        self.console.print(
            "  [dim]Start the UI with `fastfold serve` + local-web to continue these chats there.[/dim]"
        )

    def _resolve_session_identifier(self, identifier: str, sessions: list[dict]) -> str | None:
        """Resolve number/id/prefix/last into a concrete session id."""
        token = str(identifier or "").strip()
        if not token:
            self.console.print("  [dim]No session selected.[/dim]")
            return None

        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(sessions):
                return str(sessions[idx]["session_id"])
            self.console.print("  [dim]Invalid number.[/dim]")
            return None

        if token == "last":
            return str(sessions[0]["session_id"])

        matches = [s for s in sessions if str(s.get("session_id", "")).startswith(token)]
        if not matches:
            self.console.print(f"  [yellow]Session '{token}' not found.[/yellow]")
            return None
        if len(matches) > 1:
            options = ", ".join(str(s.get("session_id", "")) for s in matches[:5])
            self.console.print(
                f"  [yellow]Session prefix '{token}' is ambiguous.[/yellow] Matches: {options}"
            )
            return None
        return str(matches[0]["session_id"])

    def _resume_session(self, identifier: str = None):
        """Resume a previous session."""
        from agent.loop import AgentLoop
        from agent.trajectory import Trajectory

        sessions = Trajectory.list_sessions()
        if not sessions:
            self.console.print("  [dim]No saved sessions.[/dim]")
            return

        if identifier is None:
            # Show picker
            self._list_sessions()
            try:
                choice = self._prompt_session.prompt(
                    [("class:prompt", "  Select session: ")],
                ).strip()
            except (EOFError, KeyboardInterrupt):
                return
            if not choice:
                return
            identifier = choice

        session_id = self._resolve_session_identifier(identifier, sessions)
        if not session_id:
            return

        try:
            self.agent = AgentLoop.resume(self.session, session_id)
            self._restore_usage_from_trajectory()
            n = len(self.agent.trajectory.turns)
            title = self.agent.trajectory.title or "untitled"
            self.console.print(f"  [green]Resumed[/green] [bold]{session_id}[/bold] — {title} ({n} turns)")
            self._render_resumed_history(self.console.width, turns=self.agent.trajectory.turns)
        except FileNotFoundError:
            self.console.print(f"  [yellow]Session '{session_id}' not found.[/yellow]")

    def _reset_usage_counters(self) -> None:
        """Reset per-session usage counters for a fresh session."""
        with self._run_lock:
            self._session_sdk_calls = 0
            self._session_sdk_input_tokens = 0
            self._session_sdk_output_tokens = 0
            self._session_sdk_cache_read_tokens = 0
            self._session_sdk_cache_creation_tokens = 0
            self._session_sdk_cost_usd = 0.0
            self._session_sdk_total_cost_usd = 0.0
            self._session_sdk_extra_server_tool_cost_usd = 0.0
            self._session_sdk_models = set()
            self._session_sdk_turn_rows = []

    def _new_session(self) -> None:
        """Start a brand-new local session."""
        from agent.loop import AgentLoop

        # Clear visible transcript so /new feels like a blank chat start.
        self.console.clear()
        try:
            # Mirror startup UX when beginning a fresh session.
            from cli import print_banner
            # Add slight top margin so content isn't pinned to row 1.
            self.console.print()
            self.console.print()
            self.console.print()
            self.console.print()
            self.console.print()
            self.console.print()
            print_banner(self.session.config)
            self.console.print()
        except Exception:
            pass
        self.agent = AgentLoop(self.session)
        self._reset_usage_counters()
        self._last_response = None
        self.console.print(
            f"  [green]Started new session[/green] [bold]{self.agent.trajectory.session_id}[/bold]."
        )

    def _delete_session(self, identifier: str | None = None) -> None:
        """Delete a saved session (and trace file) by id, prefix, number, or 'last'."""
        from agent.trajectory import Trajectory

        sessions = Trajectory.list_sessions()
        if not sessions:
            self.console.print("  [dim]No saved sessions.[/dim]")
            return

        if identifier is None:
            self._list_sessions()
            try:
                choice = self._prompt_session.prompt(
                    [("class:prompt", "  Delete session: ")],
                ).strip()
            except (EOFError, KeyboardInterrupt):
                return
            if not choice:
                return
            identifier = choice

        session_id = self._resolve_session_identifier(identifier, sessions)
        if not session_id:
            return

        try:
            result = Trajectory.delete_session(session_id)
        except FileNotFoundError:
            self.console.print(f"  [yellow]Session '{session_id}' not found.[/yellow]")
            return

        trace_note = " and trace" if result.get("trace_deleted") else ""
        self.console.print(
            f"  [green]Deleted[/green] [bold]{session_id}[/bold]{trace_note}."
        )

        current_session_id = (
            self.agent.trajectory.session_id
            if hasattr(self, "agent") and getattr(self.agent, "trajectory", None)
            else None
        )
        if current_session_id == session_id:
            self._new_session()
            self.console.print(
                f"  [dim]Current session was deleted; switched to new session {self.agent.trajectory.session_id}.[/dim]"
            )

    def _handle_agents_command(self, query: str, context: dict):
        """Handle /agents N [query] command."""
        parts = query.split(maxsplit=2)
        # /agents N query  or  /agents N
        if len(parts) < 2 or not parts[1].isdigit():
            self.console.print(
                "  [dim]Usage: /agents N [query]  "
                "(e.g., /agents 3 profile lenalidomide)[/dim]"
            )
            return

        n_threads = int(parts[1])
        if n_threads < 1:
            self.console.print("  [dim]Need at least 1 agent.[/dim]")
            return

        if len(parts) > 2:
            agent_query = parts[2]
        else:
            # Prompt for query
            try:
                agent_query = self._prompt_session.prompt(
                    [("class:prompt", "  Research question: ")],
                ).strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            if not agent_query:
                self.console.print("  [dim]Cancelled.[/dim]")
                return

        self._run_orchestrated(agent_query, context, n_threads)

    def _run_orchestrated(self, query: str, context: dict, n_threads: int):
        """Run a query using the multi-agent orchestrator."""
        from agent.orchestrator import ResearchOrchestrator

        orchestrator = ResearchOrchestrator(
            self.session,
            n_threads=n_threads,
            trajectory=self.agent.trajectory if hasattr(self, 'agent') else None,
        )

        try:
            self.console.print()
            result = orchestrator.run(query, context)
            self.console.print()

            if result is not None:
                self._last_response = result.summary
                self._update_suggestions(query, result.merged_plan, result)
        except KeyboardInterrupt:
            self.console.print("\n  [yellow]Interrupted.[/yellow]")
        except Exception as e:
            self.console.print(f"\n  [red]Orchestrator error:[/red] {e}")

    def _handle_case_study_command(self, query: str, context: dict):
        """Handle /case-study <id> or /case-study list."""
        from agent.case_studies import CASE_STUDIES, run_case_study

        parts = query.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""

        if not arg or arg == "list":
            from rich.table import Table

            table = Table(title="Case Studies")
            table.add_column("ID", style="cyan")
            table.add_column("Drug")
            table.add_column("Threads", style="dim")
            table.add_column("Description")
            for case_id, case in CASE_STUDIES.items():
                table.add_row(
                    case_id,
                    case.name,
                    str(len(case.thread_goals)),
                    case.description[:80] + ("..." if len(case.description) > 80 else ""),
                )
            self.console.print(table)
            self.console.print(
                "\n  [dim]Usage: /case-study <id>  (e.g., /case-study revlimid)[/dim]"
            )
            return

        case_id = arg.split()[0].lower()
        if case_id not in CASE_STUDIES:
            available = ", ".join(sorted(CASE_STUDIES.keys()))
            self.console.print(
                f"  [red]Unknown case study '{case_id}'.[/red] Available: {available}"
            )
            return

        case = CASE_STUDIES[case_id]
        self.console.print(
            f"\n  [cyan]Case Study:[/cyan] [bold]{case.name}[/bold]"
            f"\n  [dim]{case.description}[/dim]\n"
        )

        try:
            result = run_case_study(self.session, case_id)
            self.console.print()

            if result is not None:
                self._last_response = result.summary
                self._update_suggestions(case.compound, result.merged_plan, result)
        except KeyboardInterrupt:
            self.console.print("\n  [yellow]Interrupted.[/yellow]")
        except Exception as e:
            self.console.print(f"\n  [red]Case study error:[/red] {e}")

    def _handle_data_command(self, query: str) -> None:
        """Interactive dataset management: /data [list | status | pull <name> | pull-all]."""
        try:
            from data.downloader import (
                DATASETS,
                dataset_catalog,
                dataset_status,
                download_all,
                download_dataset,
            )
        except Exception as e:  # noqa: BLE001
            self.console.print(f"  [red]Data module unavailable:[/red] {e}")
            return

        parts = query.strip().split()
        sub = parts[1].lower() if len(parts) > 1 else "status"
        args = parts[2:]

        if sub in ("list", "ls", "catalog"):
            self.console.print(dataset_catalog())
            return
        if sub in ("status", "st"):
            self.console.print(dataset_status())
            return
        if sub in ("pull-all", "pullall", "all"):
            auto = [n for n, ds in DATASETS.items() if ds.get("auto_download")]
            self.console.print(
                f"  [cyan]Downloading all auto-downloadable datasets:[/cyan] {', '.join(auto)}"
            )
            self.console.print("  [dim]This can be large (depmap alone is ~580MB). Ctrl+C to stop.[/dim]")
            try:
                download_all()
            except KeyboardInterrupt:
                self.console.print("\n  [yellow]Download interrupted.[/yellow]")
            return
        if sub == "pull":
            if not args:
                self.console.print("  [yellow]Usage:[/yellow] /data pull <name|all>")
                self.console.print(f"  [dim]Available:[/dim] {', '.join(DATASETS.keys())}")
                return
            name = args[0].lower()
            if name not in DATASETS and name not in ("all",):
                self.console.print(f"  [red]Unknown dataset:[/red] {name}")
                self.console.print(f"  [dim]Available:[/dim] {', '.join(DATASETS.keys())} (or 'all')")
                return
            try:
                download_dataset(name)
            except KeyboardInterrupt:
                self.console.print("\n  [yellow]Download interrupted.[/yellow]")
            return

        self.console.print(f"  [yellow]Unknown /data subcommand:[/yellow] {sub}")
        self.console.print(r"  [dim]Usage:[/dim] /data \[list | status | pull <name> | pull-all]")

    def _show_help(self):
        command_lines = ["**Slash Commands:**"]
        for command in sorted(SLASH_COMMANDS.keys()):
            command_lines.append(f"- `{command}` — {SLASH_COMMANDS[command]}")

        help_text = (
            "**Usage:**\n"
            "- Type any research question to investigate.\n"
            "- `!command` — run one shell command safely (no pipes/chaining; e.g., `!ls .`).\n"
            + "\n".join(command_lines)
            + "\n\n"
            "**Shortcuts:**\n"
            "- `Ctrl+O` — toggle verbose mode\n"
            "- `Ctrl+J` or `Alt+Enter` — insert newline (multi-line input)\n"
            "- `Tab` — accept ghost suggestion\n"
            "- `Ctrl+C` — interrupt active generation (double-tap forces stop)\n"
            "- `Ctrl+C` × 2 at idle prompt — exit\n"
            "\n"
            "**Examples:**\n"
            '- `find top genetically supported Parkinson targets`\n'
            '- `/agents 3 find repurposing hypotheses for ulcerative colitis`\n'
            '- `/case-study list` then `/case-study revlimid`\n'
            '- `fastfold report publish` (from shell) to convert latest markdown report to HTML.'
        )
        self.console.print(Panel(
            LeftMarkdown(help_text),
            title="fastfold Help",
            border_style="cyan",
        ))

    def _show_skills(self):
        """List currently loaded skills in interactive mode."""
        from rich.table import Table
        from agent.skills import list_skills, display_author, display_updated, display_version

        skills = list_skills()
        if not skills:
            self.console.print("  [yellow]No skills loaded.[/yellow]")
            self.console.print(
                "  [dim]Add one with[/dim] /skills-add <github url or owner/repo@path>"
            )
            return

        enabled_count = len([info for info in skills if getattr(info, "enabled", True)])
        table = Table(
            title=f"Loaded Skills ({len(skills)} total, {enabled_count} enabled)",
            show_lines=False,
        )
        table.add_column("Skill", style="bold cyan", no_wrap=True)
        table.add_column("Enabled", style="dim", no_wrap=True)
        table.add_column("Source", style="dim")
        table.add_column("Author", style="dim")
        table.add_column("Updated", style="dim")
        table.add_column("Version", style="dim")
        table.add_column("Description", style="white")

        for info in skills:
            table.add_row(
                info.name,
                "yes" if getattr(info, "enabled", True) else "no",
                info.source,
                display_author(info),
                display_updated(info),
                display_version(info),
                info.description,
            )

        self.console.print(table)

    def _add_skill(self, source: str):
        """Install a skill from a GitHub URL / shorthand / local path / name."""
        from agent.skills import install_skill

        source = (source or "").strip()
        if not source:
            self.console.print(
                "  [yellow]Usage:[/yellow] /skills-add <github url | owner/repo@path | local path | name>"
            )
            return
        with self.console.status(
            f"[green]Installing skill from {source}...[/green]", spinner="dots"
        ):
            result = install_skill(source)
        if result.get("ok"):
            self.console.print(f"  [green]{result['summary']}[/green]")
            self.console.print(
                "  [dim]Available on your next message (the system prompt reloads each turn).[/dim]"
            )
        else:
            self.console.print(f"  [red]{result['summary']}[/red]")

    def _find_skills(self, query: str = ""):
        """Discover installable skills from the catalog."""
        from rich.table import Table
        from agent.skills import discover_skills

        with self.console.status("[green]Searching skill catalog...[/green]", spinner="dots"):
            results = discover_skills(query.strip() or None)
        if not results:
            self.console.print(
                "  [yellow]No matching skills found.[/yellow] "
                "[dim](Requires git; check network/catalog access.)[/dim]"
            )
            return
        table = Table(title=f"Available Skills ({len(results)})", show_lines=False)
        table.add_column("Skill", style="bold cyan", no_wrap=True)
        table.add_column("Install source", style="dim")
        table.add_column("Description", style="white")
        for r in results:
            table.add_row(r["name"], r["install_source"], r["description"])
        self.console.print(table)
        self.console.print("  [dim]Install with:[/dim] /skills-add <install source>")

    def _upgrade_skills(self):
        """Sync the Fastfold catalog and update installed skills."""
        from agent.skills import upgrade_skills, GLOBAL_SKILLS_DIR

        with self.console.status("[green]Syncing agent skills...[/green]", spinner="dots") as status:
            result = upgrade_skills(
                progress=lambda msg: status.update(f"[green]{msg}[/green]")
            )
        if result.get("added"):
            self.console.print(f"  [green]Added:[/green] {', '.join(result['added'])}")
        if result.get("updated"):
            self.console.print(f"  [green]Updated:[/green] {', '.join(result['updated'])}")
        if result.get("npx_synced"):
            self.console.print(
                f"  [green]npx-synced:[/green] {result['npx_synced']} project-local source(s)"
            )
        for source, reason in result.get("failed", []):
            self.console.print(f"  [yellow]Failed:[/yellow] {source} — {reason}")
        self.console.print(f"  [dim]{result['summary']}[/dim]")
        self.console.print(f"  [dim]Location: {GLOBAL_SKILLS_DIR}[/dim]")
        self.console.print(
            "  [dim]Available on your next message (the system prompt reloads each turn).[/dim]"
        )

    def _remove_skill(self, name: str):
        """Remove a globally-installed skill by name."""
        from agent.skills import remove_skill

        name = (name or "").strip()
        if not name:
            self.console.print("  [yellow]Usage:[/yellow] /skills-remove <name>")
            return
        result = remove_skill(name)
        style = "green" if result.get("ok") else "yellow"
        self.console.print(f"  [{style}]{result['summary']}[/{style}]")
