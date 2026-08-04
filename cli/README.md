# CLI (`sandwalk`)

Python package for the Sandwalk agent and local server.

```bash
cd cli

# CLI + local agent server (default; FastAPI serve is included)
uv sync

# Everything — chemistry, biology, single-cell, ML, DuckDB/Arrow
uv sync --extra all

uv run sandwalk serve
uv run sandwalk --version
uv run pytest tests/ -q
```

`uv sync` already pulls the `dev` group (pytest, ruff, mypy). Use `--extra all` only when you need the optional science stacks.

## Interactive terminal

```bash
uv run sandwalk
```

Type a research question, or `/` for slash-command autocomplete. Shared sessions with the Web UI live under `~/.sandwalk/`.

### Compose box

| Shortcut | Action |
|----------|--------|
| `Enter` | Submit |
| `Ctrl+J` / `Alt+Enter` | Insert newline |
| `Cmd+V` / `Ctrl+V` | Paste clipboard image or image path → orange `[Image N]` chip (saved under session `uploads/`) |
| Path paste / drop | Same as paste: leading image path becomes `[Image N]` |
| Mouse select / copy | Host terminal selection (Warp/iTerm). App mouse mode is off on purpose so drag-select works. |

On submit, chips expand to `@uploads/…` for the vision pipeline (same as the Web UI). Use a vision-capable model.

### Status bar

Idle footer (left → right):

| Segment | Meaning |
|---------|---------|
| Model | Active model id (cyan) |
| Specialist | Active specialist, if any |
| Sandbox | Local Sandbox or Modal Sandbox |
| Path | Current working directory (muted gray) |
| Plan mode | Shown only when Plan mode is on |
| Context | `context: N% (used/limit)` when the window is known |

During a run the bar shows a compact comet scanner and `ctrl+c interrupt` (plus a queued count if messages are waiting).

### Plan mode

- Interactive sessions **start with Plan mode off** (Agent mode).
- `/plan` toggles Plan ↔ Agent and **persists** the choice for the session.
- In Plan mode the agent writes `plans/<slug>.md` (steps + Mermaid) without executing heavy tools until you switch back.

See also [docs: Plan mode](../docs/content/cli/plan.mdx) and the Web UI Plan mode docs.

### Sandbox (`/sandbox`)

Bare `/sandbox` opens a numbered picker (same idea as `/model`):

1. **Local Sandbox** — this machine  
2. **Modal CPU** presets (2·8, 4·16, …) — matches the Web UI  
3. **Modal GPU** presets (T4, L4, A10, A100, H100, …)

After a Modal pick you can **edit the base image inline** (prefilled; Enter keeps the default):

- CPU default: `python:3.12-slim`  
- GPU default: `pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime` (CUDA comes from this image)

Other forms:

```text
/sandbox status     # backend + compute + base image
/sandbox builtin    # Local Sandbox
/sandbox modal      # Modal (current compute settings)
/sandbox toggle
/sandbox help
```

CLI preference key: `agent.cli_sandbox` (`builtin` | `modal`).  
Compute/image keys: `sandbox.compute_type`, `sandbox.gpu_class`, `sandbox.cpu_cores`, `sandbox.ram_gb`, `sandbox.cpu_image`, `sandbox.gpu_image`.

### Models (`/model`)

Bare `/model` opens a numbered picker of **enabled** catalog models (same list as Dashboard → Models). Pick a cloud or local entry to switch the active session model.

- Hidden / disabled models are omitted (toggle them in the Web UI Models view).
- Status bar shows the active model id; `/usage` shows tokens for the session.
- Cloud context windows are curated in `agent/model_catalog/context_windows.py` (e.g. 1M for modern Claude / GPT-5.6 / Gemini / Kimi K3).
- Local Ollama: context from `/api/tags`, with `/api/show` fallback when tags omit it.
- The picker shows a **1M** badge only for ≥1M windows; the status bar shows `context: N% (used/limit)` when known.
- After switching to a model that supports thinking controls (Kimi K2.5/K2.6, Unsloth profiles, GPT/Claude effort models, …), the CLI prompts for **Effort** (Low / Medium / High / Fast). Use `/effort` to change it later. Values persist in `llm.model_reasoning` (shared with the Web UI).

**Kimi:** set `MOONSHOT_API_KEY` via `/keys set-moonshot`, `sandwalk config set llm.moonshot_api_key …`, or `sandwalk setup`. Catalog models include `kimi-k3`, `kimi-k2.6`, `kimi-k2.7-code` (+ highspeed); `kimi-k2.5` is disabled by default.

Config keys: `llm.provider`, `llm.model`, `llm.moonshot_api_key`, `llm.model_reasoning`. Cloud keys: `/keys` or `sandwalk config set`.

### Model Manager (`/model-manager`)

Manage **OpenAI-compatible** endpoints (local / proxy). Profile CRUD lives here — not under `/model`.

```text
/model-manager
```

Interactive menu:

1. **Add** compatible profile  
2. **Edit** compatible profile  
3. **Delete** compatible profile  
0. Back  

For each profile you set endpoint type, base URL, optional API key, and default model. Endpoint types:

| # | Backend | Typical discovery |
|---|---------|-------------------|
| 1 | Ollama | `/api/tags` |
| 2 | Unsloth | `/v1/models` (auth) |
| 3 | oMLX | `/v1/models` (auth) |
| 4 | DS4 (DeepSeek v4) | `/v1/models` |
| 5 | llama.cpp | `/v1/models` |
| 6 | LM Studio | `/v1/models` |
| 7 | Other OpenAI-compatible | `/v1/models`, then `/api/tags` |

The table probes each profile (health, models path, key preview, discovered model ids). After adding a profile, use `/model` to select one of its models.

### Slash commands

| Slash | Description |
|-------|-------------|
| `/help` | Show command reference with examples |
| `/model` | Switch LLM model / provider interactively |
| `/effort` | Set Effort / Fast (thinking) for the active model |
| `/model-manager` | Manage OpenAI-compatible profiles (add / edit / delete) |
| `/keys` | API key status (`profile`, `set-compatible`, `set-moonshot`, `set-boltz`) |
| `/sandbox` | Pick Local / Modal compute presets (+ edit base image) |
| `/plan` | Toggle Plan mode (starts off; writes `plans/*.md` until Agent mode) |
| `/specialist` | Set / list specialists (`<slug>` \| `use` \| `clear` \| `list` \| `show`) |
| `/mcp` | MCP servers (`connect` \| `enable` \| `validate` \| `add` \| `remove`) |
| `/tools` | List tools with status (stable / experimental) |
| `/skills` | List loaded skills (filtered to active specialist if set) |
| `/skills-add` | Install a skill from GitHub / local path / name |
| `/skills-find` | Discover installable skills from the catalog |
| `/skills-upgrade` | Sync the Fastfold catalog and update installed skills |
| `/skills-remove` | Remove a globally installed skill |
| `/data` | Local datasets (`list` \| `status` \| `pull <name>` \| `pull-all`) |
| `/config` | Show active runtime configuration |
| `/settings` | Configure UI and agent preferences |
| `/usage` | Show session token / cost usage |
| `/tasks` | Background task watcher status (`/tasks refresh` for live probe) |
| `/compact` | Compress session context for longer runs |
| `/new` | Start a new empty session |
| `/sessions` | List saved sessions (`/sessions delete <id>`) |
| `/resume` | Resume a previous session by id / index |
| `/sync` | Import legacy CLI sessions into the shared UI database |
| `/export` | Export current session transcript to markdown |
| `/export-share` | Export session, send to Slack, and save to library |
| `/notebook` | Export current session as Jupyter notebook (`.ipynb`) |
| `/copy` | Copy the last answer to clipboard |
| `/agents` | Run a query with N parallel research agents |
| `/case-study` | Run / list curated case studies (`/case-study list`) |
| `/doctor` | Run readiness diagnostics and fix hints |
| `/upgrade` | Upgrade sandwalk via uv |
| `/interrupt` | Interrupt the active generation (add `!` to force) |
| `/clear` | Clear the screen |
| `/exit` | Exit the terminal |

Shortcuts: `Enter` submit · `Ctrl+J` / `Alt+Enter` newline · paste image → `[Image N]` · `Tab` completions · `Ctrl+C` interrupt (double-tap at idle to exit).

## Tests & coverage

| Command | What | Size / time |
|---------|------|-------------|
| `pnpm test:cli:functional` | Offline real-process smoke | ~10–20 tests, ~10s |
| `pnpm test:cli:all` | Full CLI integration (network + chat) | minutes; uses `~/.sandwalk` keys |
| `pnpm test:cli:unit` | **Full** mocked unit suite (not a smoke) | ~2400 tests, several minutes |
| `pnpm test:cli` | CI mix: unit + offline functional | same as unit + a bit |

```bash
pnpm test:cli:functional   # quick smoke
pnpm test:cli:unit         # full unit suite (~2400)
pnpm test:cli:all          # integration only
pnpm test:cli:coverage     # CI coverage gate
```

Or from `cli/`:

```bash
.venv/bin/python -m pytest tests/ -q \
  --cov=agent --cov=agent_server --cov=api --cov=cli --cov=data --cov=kb --cov=models \
  --cov=reports --cov=skills --cov=tools --cov=ui \
  --cov-report=term-missing:skip-covered --cov-fail-under=80
```

Coverage is uploaded to Codecov under flags `agent-cli` and `agent-server`.
See [.github/TESTING.md](../.github/TESTING.md).

Package name: `sandwalk` · version: see repo root `VERSION` / `pyproject.toml`.
