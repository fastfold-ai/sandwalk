"""The InteractiveTerminal REPL: prompt loop, slash-command routing, and
session/agent orchestration for the interactive terminal.
"""

import random
import threading
from collections import deque

from prompt_toolkit.history import FileHistory

from agent.config import CONFIG_DIR
from ui.suggestions import DEFAULT_SUGGESTIONS

from .completion import MentionCompleter, MergedCompleter, PT_STYLE, SlashCompleter
from .key_bindings import _build_key_bindings
from .model_ids import AVAILABLE_MODELS  # noqa: F401 — re-exported via ui.terminal
from .slash_commands import SLASH_COMMANDS
# Staged mixins — method bodies live in sibling modules.
from .agent_bootstrap import _AgentBootstrapMixin
from .agents_and_case_study import _AgentsAndCaseStudyMixin
from .boltz_setup import _BoltzSetupMixin
from .bottom_toolbar import _BottomToolbarMixin
from .compatible_backend_info import _CompatibleBackendInfoMixin
from .compatible_backend_prompt import _CompatibleBackendPromptMixin
from .compatible_model_legacy import _CompatibleModelLegacyMixin
from .compatible_profile_activate import _CompatibleProfileActivateMixin
from .compatible_profile_edit import _CompatibleProfileEditMixin
from .data_and_help import _DataAndHelpMixin
from .discovery_helpers import _DiscoveryHelpersMixin
from .export_helpers import _ExportHelpersMixin
from .export_session import _ExportSessionMixin
from .export_share_and_misc import _ExportShareAndMiscMixin
from .fetch_compatible_models import _FetchCompatibleModelsMixin
from .fetch_openai_models import _FetchOpenaiModelsMixin
from .llm_ready_check import _LlmReadyCheckMixin
from .mention_and_activity import _MentionAndActivityMixin
from .model_discovery_choice import _ModelDiscoveryChoiceMixin
from .model_manager_command import _ModelManagerCommandMixin
from .openai_profiles_settings import _OpenaiProfilesSettingsMixin
from .profile_probe import _ProfileProbeMixin
from .profile_prompts import _ProfilePromptsMixin
from .profile_template_backend import _ProfileTemplateBackendMixin
from .provider_status import _ProviderStatusMixin
from .query_worker import _QueryWorkerMixin
from .resumed_history import _ResumedHistoryMixin
from .run_clarification import _RunClarificationMixin
from .sandbox_keys_commands import _SandboxKeysCommandsMixin
from .session_lifecycle import _SessionLifecycleMixin
from .session_upgrade_sync import _SessionUpgradeSyncMixin
from .settings_menu import _SettingsMenuMixin
from .skills_commands import _SkillsCommandsMixin
from .skills_upgrade_remove import _SkillsUpgradeRemoveMixin
from .switch_model import _SwitchModelMixin
from .trace_replay import _TraceReplayMixin
from .usage_persistence import _UsagePersistenceMixin
from .usage_tasks_display import _UsageTasksDisplayMixin
from .usage_tracking import _UsageTrackingMixin

class InteractiveTerminal(
    _SwitchModelMixin,
    _AgentBootstrapMixin,
    _AgentsAndCaseStudyMixin,
    _BoltzSetupMixin,
    _BottomToolbarMixin,
    _CompatibleBackendInfoMixin,
    _CompatibleBackendPromptMixin,
    _CompatibleModelLegacyMixin,
    _CompatibleProfileActivateMixin,
    _CompatibleProfileEditMixin,
    _DataAndHelpMixin,
    _DiscoveryHelpersMixin,
    _ExportHelpersMixin,
    _ExportSessionMixin,
    _ExportShareAndMiscMixin,
    _FetchCompatibleModelsMixin,
    _FetchOpenaiModelsMixin,
    _LlmReadyCheckMixin,
    _MentionAndActivityMixin,
    _ModelDiscoveryChoiceMixin,
    _ModelManagerCommandMixin,
    _OpenaiProfilesSettingsMixin,
    _ProfileProbeMixin,
    _ProfilePromptsMixin,
    _ProfileTemplateBackendMixin,
    _ProviderStatusMixin,
    _QueryWorkerMixin,
    _ResumedHistoryMixin,
    _RunClarificationMixin,
    _SandboxKeysCommandsMixin,
    _SessionLifecycleMixin,
    _SessionUpgradeSyncMixin,
    _SettingsMenuMixin,
    _SkillsCommandsMixin,
    _SkillsUpgradeRemoveMixin,
    _TraceReplayMixin,
    _UsagePersistenceMixin,
    _UsageTasksDisplayMixin,
    _UsageTrackingMixin,
):
    """Interactive research session terminal."""
    def __init__(self, config=None, verbose=False):
        from agent.session import Session
        # Imported from the package namespace (rather than at module level)
        # so tests can monkeypatch `ui.terminal.Console` / `ui.terminal.PromptSession`.
        from ui.terminal import Console, PromptSession

        self.session = Session(config=config, verbose=verbose, mode="interactive")
        # CLI sessions always start in agent mode (plan mode off). Toggle with /plan.
        # In-memory only so we don't overwrite the web dashboard preference on disk.
        try:
            self.session.config.set("agent.plan_preview", False)
        except Exception:
            pass
        self.console = Console()
        self.history_file = CONFIG_DIR / "history"
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self._last_interrupt = 0.0
        self._show_exit_hint = False
        self._show_interrupt_hint = False
        self._verbose_hint = None
        self._cli_specialist_label: str | None = None
        self._cli_sandbox_label: str = "Local Sandbox"
        self._refresh_cli_specialist_label()
        self._refresh_cli_sandbox_label()
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

    def run(self, initial_context: dict = None, resume_id: str = None):
        """Run the interactive session."""
        # Imported from the package namespace so tests can monkeypatch
        # `ui.terminal.patch_stdout`.
        from ui.terminal import patch_stdout

        context = initial_context or {}
        term_width = self.console.width
        self._bootstrap_agent_loop(resume_id)

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
            except KeyboardInterrupt:
                # Ctrl+C at idle prompt — keep session alive (double-tap exits via binding).
                self.console.print("  [dim]Interrupted.[/dim]")
                continue

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
                from tools import ensure_loaded, registry, tool_load_errors
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
            if cmd_head in ("specialist", "/specialist"):
                self._handle_specialist_command(query)
                self._advance_suggestion()
                continue
            if cmd_head in ("sandbox", "/sandbox"):
                self._handle_sandbox_command(query)
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
                    self.console.print("  [cyan]Continuing synthesis...[/cyan]\n")
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
