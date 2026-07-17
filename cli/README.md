# CLI (`sandwalk`)

Python package for the Sandwalk agent and local server.

```bash
cd cli
uv sync --extra dev --extra all --extra api
uv run sandwalk serve
uv run sandwalk --version
uv run pytest tests/ -q
```

## Interactive terminal

```bash
uv run sandwalk
```

Type a research question, or `/` for slash-command autocomplete. Shared sessions with the Web UI live under `~/.sandwalk/`.

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

During a run the bar shows elapsed time, live token counts, and activity text.

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

### Models & context

- `/model` — interactive model picker  
- Cloud context windows are curated in `agent/model_catalog/context_windows.py` (e.g. 1M for modern Claude / GPT-5.6 / Gemini).  
- Local Ollama: context from `/api/tags`, with `/api/show` fallback when tags omit it.  
- Usage popover / status bar show the known limit; the model picker shows a **1M** badge only for ≥1M windows.

### Useful slash commands

| Slash | Description |
|-------|-------------|
| `/help` | Full command reference |
| `/model` | Switch model / provider |
| `/sandbox` | Pick Local / Modal compute (+ edit base image) |
| `/plan` | Toggle Plan mode |
| `/specialist` | Set / clear specialist |
| `/usage` | Session token / cost table |
| `/doctor` | Readiness checks |
| `/keys` | API key status |
| `/interrupt` | Stop the active generation (`!` to force) |

Shortcuts: `Ctrl+J` / `Alt+Enter` newline · `Tab` accept suggestion · `Ctrl+C` interrupt (double-tap at idle to exit).

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
