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
uv sync --extra dev --extra all --extra api   # or: python -m venv .venv && pip install -e ".[dev,all,api]"
.venv/bin/python -m pytest tests/ -q

# With coverage (matches CI)
.venv/bin/python -m pytest tests/ -q \
  --cov=agent --cov=agent_server --cov=api --cov=cli --cov=data --cov=kb --cov=models \
  --cov=reports --cov=skills --cov=tools --cov=ui \
  --cov-report=term-missing:skip-covered \
  --cov-report=xml:coverage-full.xml \
  --cov-fail-under=80
```

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

Coverage include set (Vitest `vitest.config.ts`):

- `src/components/agents/transcript.ts`
- `src/components/agents/composer-parts.ts`
- `src/components/agents/skill-examples.ts`
- `src/lib/**`

Reports:

- Terminal summary
- `apps/local-web/coverage/lcov.info` (Codecov)
- `apps/local-web/coverage/index.html` (open in browser; generated when `html` reporter is enabled)

```bash
open apps/local-web/coverage/index.html
```

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
