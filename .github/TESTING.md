# Testing & coverage

Each Sandwalk component uploads its own coverage report with a Codecov **flag**,
and the monorepo dashboard shows them side-by-side.

| Component | Flag | Tooling | Gate |
|-----------|------|---------|------|
| Agent CLI | `agent-cli` | pytest + pytest-cov | ≥80% (scoped omit list) |
| Agent Server | `agent-server` | pytest + pytest-cov | ≥80% (scoped omit list) |
| Local Web UI | `local-web` | Vitest + v8 | ≥80% on included modules |
| Mac App | `mac-app` | XCTest + llvm-cov | ≥80% on pure modules |

Codecov config: [`codecov.yml`](../codecov.yml) · CI: [`workflows/ci.yml`](./workflows/ci.yml)  
Dashboard (after first upload): https://app.codecov.io/gh/fastfold-ai/sandwalk

---

## Quick start (from monorepo root)

```bash
# Local Web UI
pnpm install
pnpm test                 # unit tests
pnpm test:coverage        # unit tests + coverage (writes apps/local-web/coverage/)
pnpm e2e                  # Playwright grid/terminal e2e (needs sandwalk serve on :8787)
pnpm e2e:bench            # grid perf benchmarks → apps/local-web/e2e/results/
pnpm e2e:compare a.json b.json

# Agent CLI + Agent Server
pnpm test:cli             # unit + functional CLI (excludes live/network/pexpect)
pnpm test:cli:functional  # real sandwalk subprocess + temp HOME only
pnpm test:cli:network     # GitHub skill installs (RUN_CLI_NETWORK=1)
pnpm test:cli:e2e         # one-shot chat (RUN_CLI_E2E=1 + LLM API key)
pnpm test:cli:live        # network + e2e together
pnpm test:cli:coverage    # unit/functional + 80% gate (needs cli/.venv)

# Mac App (requires full Xcode)
pnpm test:mac             # XCTest + 80% scoped gate + coverage.lcov
```

Or run everything that is available on this machine:

```bash
pnpm test:coverage && pnpm test:cli:coverage && pnpm test:mac
```

---

## Agent CLI & Agent Server

Working directory: `cli/`

```bash
cd cli
uv sync --extra all   # or: python -m venv .venv && pip install -e ".[dev,all]"
.venv/bin/python -m pytest tests/ -q

# With coverage (matches CI)
.venv/bin/python -m pytest tests/ -q \
  --cov=agent --cov=agent_server --cov=api --cov=cli --cov=data --cov=kb --cov=models \
  --cov=reports --cov=skills --cov=tools --cov=ui \
  --cov-report=term-missing:skip-covered \
  --cov-report=xml:coverage-full.xml \
  --cov-fail-under=80
```

`--extra all` is **required**, not optional: tests import `rdkit` and `duckdb`
directly, so a plain `uv sync` leaves ~79 tests failing on `ModuleNotFoundError`
rather than on anything real.

Opt-in lanes (`cli_network`, `cli_e2e`, `modal_e2e`, `data_smoke`, `integration`) are
**auto-deselected** in `tests/conftest.py` unless their env gate is set — no
`-m "not … and not …"` expression needed.

### CLI test layers

| Layer | What it is | How to run | Size |
|-------|------------|------------|------|
| **Functional smoke** | Real `sandwalk` + temp `HOME` | `pnpm test:cli:functional` | ~10–20 tests, ~10s |
| **Unit** | Mocked helpers / CliRunner | `pnpm test:cli:unit` | ~2400 tests, several minutes |
| **CI CLI** | Unit + offline functional | `pnpm test:cli` | same as unit + a bit |
| **Full integration** | Functional + network + live chat | `pnpm test:cli:all` | minutes |
| Interactive REPL | pexpect TTY | `RUN_INTEGRATION=1` | opt-in |
| Live Modal / data | Real APIs / Modal | `RUN_MODAL_E2E=1` / `RUN_DATA_SMOKE=1` | credentials |

```bash
pnpm test:cli:functional   # quick smoke
pnpm test:cli:unit         # full unit suite — expect several minutes
pnpm test:cli              # CI mix
pnpm test:cli:all          # full CLI integration (keys from ~/.sandwalk)
```

Cases: [`cli/tests/integration_cli/`](../cli/tests/integration_cli/) · [CASES.md](../cli/tests/integration_cli/CASES.md).

### Modal sandbox E2E

Live Modal verification is **opt-in** (creates a short-lived sandbox):

```bash
export RUN_MODAL_E2E=1
export MODAL_TOKEN_ID=...
export MODAL_TOKEN_SECRET=...
pip install -e ".[modal]"   # from cli/
sandwalk sandbox probe
.venv/bin/python -m pytest tests/test_modal_sandbox_e2e.py -m modal_e2e -v
```

# Agent Server–only gate (reuses .coverage from a coverage run above)
```bash
.venv/bin/coverage report --include='*/agent_server/*' \
  --omit='*/agent_server/pty_manager.py,*/agent_server/app.py,*/agent_server/main.py,*/agent_server/mcp_service.py,*/agent_server/service.py,*/agent_server/default_specialists.py' \
  --skip-covered --fail-under=80

# Split XML for Codecov flags (optional locally)
.venv/bin/coverage xml -o coverage-agent-cli.xml --omit='*/agent_server/*'
.venv/bin/coverage xml -o coverage-agent-server.xml --include='*/agent_server/*' \
  --omit='*/agent_server/pty_manager.py,*/agent_server/app.py,*/agent_server/main.py,*/agent_server/mcp_service.py,*/agent_server/service.py,*/agent_server/default_specialists.py'
```

**What counts toward 80%:** statement coverage with an omit list in
`cli/pyproject.toml` (`[tool.coverage.run] omit`). Interactive REPL (`ui/terminal.py`),
Typer entry (`cli.py`), PTY, FastAPI/WebSocket surface, MCP process glue, and the
streaming agent loop are omitted — same “pure modules” idea as local-web / Mac.

Open HTML locally:

```bash
cd cli
.venv/bin/coverage html -d coverage-html
open coverage-html/index.html
```

---

## Local Web UI

Working directory: `apps/local-web/` (or use root `pnpm` scripts)

```bash
pnpm --filter @sandwalk/agent-local-web test
pnpm --filter @sandwalk/agent-local-web test:coverage
```

Coverage include set (Vitest `vitest.config.ts`) and gates:

| Glob | Lines | Functions | Notes |
|------|-------|-----------|-------|
| `src/lib/**` | 80% | 80% | Pure helpers — the strict gate (branches 70%) |
| `src/components/agents/{transcript,composer-parts,skill-examples}.ts` | 75% | 70% | Pure agent helpers |
| `src/hooks/**` | 25% | 30% | Floor; raise as hook tests land |
| `src/components/app/**` | 40% | 50% | App-shell model (`app-display`, `build-*-props`) |
| `src/components/agents/terminal-layer/**` | 10% | 15% | Registry is unit-tested; xterm/WS code is covered by the e2e harness |
| *global* | 55% | 60% | Over everything above (branches 50%, statements 52%) |

Reports:

- Terminal summary
- `apps/local-web/coverage/lcov.info` (Codecov)
- `apps/local-web/coverage/index.html` (open in browser; generated when `html` reporter is enabled)

```bash
open apps/local-web/coverage/index.html
```

### E2E + performance harness (Playwright)

Drives the real SPA against a real `sandwalk serve`. Cases live in
[`apps/local-web/e2e/`](../apps/local-web/e2e/): `tests/` are functional
(split grid renders every chat/terminal pane, terminal hosts track their
placeholders, PTY round-trip, **FAS-121** scrollback survives pane switches,
no PTY resize spam), `bench/` writes timing + counter reports.

```bash
# 1. API (checkout Python, auth on) — the harness never starts this for you
cd cli && .venv/bin/sandwalk serve --host 127.0.0.1 --port 8787

# 2. From the monorepo root (Vite is started on :1420 if not already running,
#    so `pnpm tauri:dev` can stay up)
pnpm --filter @sandwalk/agent-local-web e2e:install   # once: Chromium
pnpm e2e                                              # functional specs
pnpm e2e:bench                                        # → apps/local-web/e2e/results/grid-latest.json
pnpm e2e:compare apps/local-web/e2e/results/grid-baseline.json apps/local-web/e2e/results/grid-latest.json
```

How it works:

- `fixtures/seed.ts` creates N chats + T terminals through the REST API,
  writes the same localStorage keys `app-storage.ts` reads (tab group, open
  tabs, remembered API key) and boots `/agents/<grp>?perf=1`.
- `?perf=1` (always on in dev) exposes `window.__sandwalkPerf`: counters from
  `perfCount()` in hot paths (`terminal.applyPosition`, `terminal.fit`,
  `terminal.ptyResizeRpc`, `render.<Component>`, `props.SidebarSessionList.<prop>`)
  and live xterm instances for buffer assertions. Increments are one property
  write; safe to leave in production code.
- `fixtures/perf.ts` measures long tasks (`PerformanceObserver`), frames and
  counter deltas around an interaction; each measurement is upserted into
  `e2e/results/<suite>-latest.json` and archived with a timestamp.
- `compare.mjs` diffs two reports and exits 1 on regressions past the
  threshold (`--threshold=0.25` default, with absolute floors so sub-second
  timings do not flap). Copy a good `*-latest.json` to `*-baseline.json`
  before a perf change to get a before/after table.

Env knobs: `SANDWALK_WEB_URL` (default `http://127.0.0.1:1420`),
`SANDWALK_API_URL` (default `http://127.0.0.1:8787`), `SANDWALK_API_KEY`
(else read from the Sandwalk `settings.json`), `SANDWALK_E2E_PANES` /
`SANDWALK_E2E_TERMINALS` (bench grid size, default 6 / 2). Failures keep a
Playwright trace under `apps/local-web/e2e/.artifacts/`.

#### Live multi-agent grid bench (real messages)

`e2e/bench/grid-live.bench.spec.ts` opens R×C grids of chats, sends one tiny
prompt to every pane at once, and records per grid the API `POST /messages`
latency (p50/p95), time until each reply is painted in its pane, time until
each run is idle, failures split by layer (`stillRunning` / `emptyReply` /
`replyNotVisible`), and the UI render counters under N concurrent streams.
It costs tokens, so it is opt-in:

```bash
SANDWALK_E2E_LIVE=1 SANDWALK_E2E_GRIDS=2x2,4x2,4x4 \
SANDWALK_E2E_PROVIDER=anthropic SANDWALK_E2E_MODEL=claude-sonnet-5 \
pnpm --filter @sandwalk/agent-local-web exec playwright test --project=bench --grep 'live agent grid'
# → apps/local-web/e2e/results/grid-live-latest.json
```

Pin a model that answers the agent prompt: Fable 5 / 5.1 currently return
`stop_reason=refusal` for Sandwalk's tool set, which the transcript now reports
as "(Agent produced no text output — model returned stop_reason=refusal)".

---

## Mac App

Requires **Xcode** (not Command Line Tools alone) so XCTest is available.

```bash
cd apps/sandwalk-mac
./scripts/test.sh
```

Scoped modules (≥80% line coverage):

- `PathSupport.swift`
- `SettingsSection.swift`
- `AppConfig.swift`
- `AuthSettingsStore.swift`
- `AgentAPI/AgentAPIModels.swift`

Outputs:

- `coverage-report.txt` — llvm-cov text report
- `coverage.lcov` — Codecov upload
- Optional HTML:

```bash
# printed by test.sh after a successful run
open coverage-html/index.html   # after generating with the command test.sh prints
```

Override threshold: `COVERAGE_THRESHOLD=85 ./scripts/test.sh`

---

## Codecov (CI)

On every push/PR, `.github/workflows/ci.yml` runs three jobs and uploads:

| Job | Flag | File |
|-----|------|------|
| Agent CLI & Server | `agent-cli` | `cli/coverage-agent-cli.xml` |
| Agent CLI & Server | `agent-server` | `cli/coverage-agent-server.xml` |
| Local Web UI | `local-web` | `apps/local-web/coverage/lcov.info` |
| Mac App | `mac-app` | `apps/sandwalk-mac/coverage.lcov` |

**One-time setup:** add a `CODECOV_TOKEN` repository secret for
[fastfold-ai/sandwalk](https://github.com/fastfold-ai/sandwalk) (Codecov → repo → upload token).

PR comments show **flags** and **components** (Agent CLI, Agent Server, Local Web UI, Mac App).

---

## Troubleshooting

- **CLI `python` not found:** use `cli/.venv/bin/python` or `uv run pytest`.
- **Mac tests fail with missing XCTest:** `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`
- **Coverage below 80% after adding glue code:** prefer adding unit tests for pure logic, or extend the documented omit/include sets deliberately — do not silently drop the gate.
- **Codecov upload skipped locally:** uploads only run in GitHub Actions; local runs still enforce the ≥80% gates.
