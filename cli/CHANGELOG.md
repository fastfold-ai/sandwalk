# Changelog

All notable changes to `fastfold-agent-cli` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Suggested cloud MCP catalog (Tamarind, Latch, Neurosnap, Linear) with Connect /
  enable / disable / validate flows in the agent server, CLI (`fastfold mcp`),
  and interactive `/mcp`.
- MCP credentials under Integrations / `/keys` (`mcp.*` config keys) with runtime
  auth headers for enabled catalog servers.
- Custom MCP servers: description, OAuth metadata fields, static custom headers
  (secret values in config), and optional headers-helper command; helper wins
  over static headers at runtime.
- Storage reports the agent sandbox Python environment size and installed
  package list (name + version) under Disk usage.
- Environment dashboard page to install/remove allowlisted skill/tool Python
  packages (chemistry, single-cell, ML, etc.) while core deps stay locked.
- Doctor checks in the `mcp` category that live-probe enabled catalog MCPs.
- Docs for the shortlist under `docs/mcp-defaults/`.

### Changed

- Dashboard MCP catalog listing uses cached health (tool counts / last status)
  so `/dashboard/mcp` loads quickly; live probes remain on connect, enable, and
  doctor.
- Tamarind Bio Connect is API-key-only (no OAuth client registration path).

### Fixed

- Reconnect now persists a new API key before probing, and clears stale OAuth
  tokens so the saved key is what runtime and doctor use.
- Toggle enable/disable no longer disconnects or wipes credentials.

## [0.0.70] - 2026-07-10

### Changed

- Skill upgrades now group skills by repository, clone each repository once, and
  process independent repositories concurrently with bounded parallelism.
- Git-backed skill installs now disable interactive authentication prompts so
  failures fall back promptly to GitHub archive downloads instead of hanging.
- Dataset status now reports actual on-disk sizes when available and corrected
  estimates for DepMap, L1000, MSigDB, and STRING.
- L1000 preparation now identifies the 978 landmark genes from GEO metadata
  before extracting the Level-5 matrix.

### Fixed

- Live data-source smoke checks now distinguish OpenAlex provider quota
  exhaustion from API schema regressions.
- Expanded regression coverage for skill synchronization, MCP execution
  handlers, and system-prompt assembly to keep the CI coverage gate reliable.

## [0.0.69] - 2026-06-23

### Changed

- Removed the CLI system-prompt diagram guardrails added in 0.0.67 (node limits,
  HTML/label restrictions, topology rules). The terminal renderer handles
  diagrams well now, so the agent is no longer constrained in how it authors
  Mermaid. The renderer-side `<br/>`/HTML label cleanup is retained.

## [0.0.68] - 2026-06-23

### Changed

- Mermaid diagrams now always attempt to render in the terminal. The 0.0.67
  complexity guard that fell back to raw fenced source for larger flowcharts and
  sequence diagrams was removed because it hid diagrams users wanted to see. The
  `<br/>`/HTML label cleanup from 0.0.67 is retained.

## [0.0.67] - 2026-06-23

### Fixed

- Mermaid diagrams now render more cleanly in the terminal: HTML in node labels
  (`<br/>`, tags, entities) is stripped/decoded before rendering, so labels no
  longer leak literal `<br/>` markup or blow out the layout.
- Overly complex diagrams (dense sequence lifelines, or wide/branchy flowcharts
  with many nodes or multiple subgraphs) now fall back to clean, copyable fenced
  Mermaid source instead of unreadable ASCII sprawl.

### Changed

- The agent system prompt now instructs the model to produce terminal-friendly
  diagrams by default (short single-line labels, no HTML, few nodes, mostly
  linear topology), keeping CLI-specific guidance out of shared skills.

## [0.0.65] - 2026-06-23

### Added

- New `fastfold agent fork <share_id>` command to import a shared cloud thread
  into local CLI session history, including transcript reconstruction and optional
  shared-file restore.
- Phase-based progress loaders for fork import (metadata fetch, trajectory build,
  file manifest, and downloads) to make long imports easier to track.

### Changed

- `FASTFOLD_AGENTS_API_URL` now defaults to production
  (`https://agents-api.fastfold.ai/v1`) when not configured.
- CLI entrypoint routing now treats `fastfold agent ...` as a first-class
  subcommand while preserving backward compatibility for `fastfold run <subcommand>`.

### Fixed

- Fork command failures now print friendly actionable messages for missing shares
  and access-denied cases instead of raw tracebacks.
- Fork completion output now reports imported message count, shared file/folder
  totals, restored file count, restore path, and a clear `--resume` hint.
- Local development runs (`uv run fastfold ...`) now prefer live source execution
  from `src/cli.py` when invoked inside the repo.

## [0.0.64] - 2026-06-22

### Added

- Plan preview now renders an automatic Mermaid flowchart in interactive plan mode
  (respecting existing `ui.mermaid.*` settings) to make execution plans easier
  to review before approval.

### Fixed

- Startup and `/new` banners now use the active in-memory config/session model so
  the displayed model/provider stays consistent with the live status bar.
- Setup wizard regression tests now stub optional Boltz key prompts in non-TTY
  runs, and runner interrupt/plan-preview tests were expanded to keep the 80%
  coverage gate stable.

## [0.0.63] - 2026-06-22

### Fixed

- GitHub archive skill downloads now use `httpx` with certifi-backed TLS instead
  of stdlib `urllib`, fixing `CERTIFICATE_VERIFY_FAILED` failures on Windows
  when `npx` and `git` are unavailable.

## [0.0.62] - 2026-06-21

### Fixed

- Skills install now works without `npx` or `git` by falling back to GitHub
  archive download during setup, upgrade, and `/skills-upgrade` catalog sync.
- Setup/upgrade skill install messaging now reports the actual install method
  used instead of always labeling failures as `git`.

## [0.0.61] - 2026-06-21

### Changed

- `/upgrade` now runs a full skills sync automatically after the CLI package
  upgrade (same behavior as `/skills-upgrade`), including catalog refresh and
  tracked skill source updates.

## [0.0.60] - 2026-06-21

### Fixed

- `/upgrade` now targets Python `3.11` (matching the CLI runtime requirement)
  instead of an outdated `3.10` tool install target.

## [0.0.59] - 2026-06-21

### Changed

- Interactive boot now avoids blocking startup work in the initial banner path:
  upgrade checks use a local cache plus background refresh, and tool counts use a
  lightweight hint when the registry is not loaded yet.
- `@` mention autocomplete now uses a lightweight initial candidate set and lazy
  loads heavy tool/file candidates on first mention use, with file-scan caps to
  avoid startup stalls in large workspaces.

### Fixed

- Reduced first-run cold-start latency after `fastfold upgrade` by removing
  synchronous tool-loading and network calls from pre-prompt startup.

## [0.0.58] - 2026-06-21

### Added

- Native Boltz provider onboarding in both interactive (`/keys set-boltz`) and
  setup flows, including optional installation of the Fastfold `boltz` skill and
  `boltz-api` CLI with health checks in `fastfold doctor`.
- Provider integration docs updates in CLI and docs pages, including direct key
  setup links and provider matrix guidance.
- Regression coverage for Boltz setup/doctor/config flows and OpenAI-compatible
  profile prompts.

### Changed

- Startup news banner now promotes the unified Boltz API skill with rotating use
  cases instead of the legacy BoltzGen-only message.
- OpenAI-compatible profile handling now heals cloud-model/local-backend mismatch
  states (for example GPT-5 model ids with Ollama endpoints) by aligning to the
  active profile default model.

### Fixed

- OpenAI-compatible provider failures (including model-not-found and unavailable
  local endpoints) now show concise, actionable errors instead of deep tracebacks.
- Session startup now mirrors configured tool credentials (`BOLTZ_API_KEY`,
  `FASTFOLD_API_KEY`) into process env when missing so shell/skill subprocesses
  authenticate consistently.

## [0.0.57] - 2026-06-20

### Added

- **Deep Agents (LangGraph) runtime** as the agent engine, with native
  progressive skill discovery so many installed skills no longer bloat the
  system prompt.
- Unit-test coverage for the Deep Agents runtime (`deepagents_runtime` model
  factory, tool adapter, and `process_events` event stream), the
  `_run_async_deepagents` dispatch, and the trace renderer.
- **Programmatic Tool Calling (PTC)** tool mode (`agent.tool_mode=ptc`, now the
  default): domain tools are exposed as Python callables inside the sandbox and
  discovered via a compact catalog plus a `search_tools` helper, significantly
  reducing per-turn input tokens and removing the OpenAI tool-count ceiling.
  `agent.tool_mode=native` restores per-tool schemas.
- **Data management commands**: `fastfold data list` (catalog) and
  `fastfold data pull-all` (download every auto-downloadable dataset), plus a
  `/data` interactive command (`/data list | status | pull <name> | pull-all`).
- **Dataset step in `fastfold setup`**: optionally download datasets during the
  wizard with a multi-select (all auto-downloadable datasets preselected).
  Non-interactive via `--datasets depmap,msigdb` / `--datasets all` /
  `--skip-datasets`.
- Configurable tool-trace rendering: `agent.group_tool_traces` and
  `agent.tool_trace_detail_limit` keep the current/last tool call in full detail
  and progressively collapse older ones to compact, still-named lines.
- `shell.run` gains a `working_dir` parameter and auto-extracts a leading
  `cd <dir> &&` so chained-directory commands are no longer blocked.

### Changed

- Minimum Python version is now **3.11** (required by deepagents); install and
  docs updated accordingly.
- Token usage display in the footer/toolbar now shows fresh (non-cached) input
  tokens, subtracting Anthropic prompt-cache reads.
- Tool-call durations under a second now render in milliseconds (e.g. `42ms`)
  instead of `0.0s`.
- `write_todos` renders as a checklist in the interactive trace output.
- README and CLI docs rewritten around the Deep Agents / PTC stack, with an
  Acknowledgements section (CellType, BixBench, Deep Agents, open-ptc-agent) and
  a Benchmarks (coming soon) section.

### Removed

- **Legacy Claude Agent SDK runtime** and the redundant non-deepagents OpenAI
  loop. Deep Agents is now the only runtime, so the `agent.runtime` setting and
  the `claude-agent-sdk` dependency are gone.
- **In-process `local` / `gluelm` providers**, which only ran on the old SDK
  path. Use `anthropic` or `openai` (OpenAI-compatible local servers such as
  Ollama/LM Studio/vLLM/llama.cpp still work via `provider=openai` +
  `llm.openai_base_url`).
- The `/autofix` command, the `fastfold autofix` CLI command, and the Windows
  Claude Code launcher safeguards (they only repaired the SDK CLI).

### Fixed

- Auth, rate-limit, and connection failures now show a concise, actionable
  message instead of dumping a LangGraph/Anthropic traceback.
- Tests no longer clobber the real `~/.fastfold-cli/config.json`: an autouse
  fixture redirects the CLI config directory to a temp path for every test.
- Resolved an `OSError: [Errno 7] Argument list too long` when many/long-named
  skills were installed, by moving skill discovery onto the deepagents runtime.
