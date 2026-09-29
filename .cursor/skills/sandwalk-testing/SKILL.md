---
name: sandwalk-testing
description: >-
  Test and benchmark Sandwalk changes the way CI does: which checks to run per
  change type (web unit + coverage gate, CLI pytest/ruff/mypy, Playwright grid
  and terminal e2e, perf bench with baseline/compare, live multi-agent grid
  bench), how to read the perf counters, and how to add tests. Use before
  committing, when asked to test/verify/benchmark, when CI fails, or when
  adding a spec, a perf counter, or a benchmark.
---

# Sandwalk testing

## Which checks for which change

| You changed | Run | Time |
|-------------|-----|------|
| Anything, before commit | `scripts/verify.sh` (= required CI gate) | ~2 min |
| `apps/local-web/src` | `scripts/verify.sh web` | ~40 s |
| `cli/src` | `scripts/verify.sh cli` | ~50 s |
| Split grid, terminals, sidebar/strip, PTY, tiling | `scripts/verify.sh` **and** `scripts/verify.sh e2e` | +30 s |
| Perf-sensitive UI (rendering, scroll, terminal layer, stores) | e2e + `pnpm e2e:bench` vs. a baseline (below) | +1 min |
| Agent runtime, streaming, LLM params, API latency | live bench (below; costs tokens) | +1–5 min |

`verify.sh` stops at the first failing step. Fix, re-run only that target, then
run the full script once before committing. CI additionally runs the Mac app
tests (`pnpm test:mac`, needs Xcode).

## Unit tests

- Web (Vitest, jsdom): `pnpm --filter @sandwalk/agent-local-web test` —
  colocated `*.test.ts(x)`. Coverage gate in `apps/local-web/vitest.config.ts`
  is per-glob: `src/lib/**` 80 %, hooks 25 %, app model 40 %, terminal layer
  10 % (floors — raise them when you add tests, never lower).
- CLI (pytest + xdist): `cd cli && .venv/bin/python -m pytest tests/ -q -n auto --ignore=tests/integration_cli`.
  Coverage omits in `cli/pyproject.toml [tool.coverage.run]`; PTY pure pieces
  (`osc_parser`, `snapshot_store`, `shell_env`) are measured, the TTY loop is not.
- Opt-in lanes need env gates: `RUN_CLI_NETWORK=1`, `RUN_CLI_E2E=1`,
  `RUN_LIVE_MODELS=1` (`cli/tests/integration_cli/live_model_matrix_run.py`
  pings each provider's default model).
- Tests must not touch the network or the developer's real config: `conftest.py`
  redirects `~/.sandwalk` and blanks provider keys; monkeypatch functions where
  they are *used* (`cli.setup.model_prompt._fetch_…`), not where they are defined.

## E2E harness (Playwright) — `apps/local-web/e2e/`

Needs the API on :8787 (`scripts/dev-api.sh`); Vite is started on :1420 if not
already running, so `scripts/dev-ui.sh` may stay up.

```bash
pnpm --filter @sandwalk/agent-local-web e2e:install   # once
pnpm e2e                    # tests/: grid renders, hosts track placeholders, PTY round-trip,
                            #         FAS-121 scrollback across pane switches, no resize spam,
                            #         UI re-bootstraps after an API outage (route-aborted /v1)
pnpm e2e:bench              # bench/: gridReady, scrollTranscript, paneSwitch, terminalBurst
pnpm e2e:compare apps/local-web/e2e/results/grid-baseline.json apps/local-web/e2e/results/grid-latest.json
```

How it works: `fixtures/seed.ts` creates chats/terminals via REST, writes the
localStorage keys the SPA reads (`fastfold.tab-groups`, open tabs, remembered
API key) and boots `/agents/<grp>?perf=1`. Use `createGridFixture` +
`openGrid` (layout `{rows, cols}` for real R×C grids), `focusPane` (terminal
panes must be clicked through their xterm), `readTerminalText` (stitches
soft-wrapped rows), `measure()` for long tasks / fps / counter deltas.
Failures leave a trace in `apps/local-web/e2e/.artifacts/` —
`npx playwright show-trace <zip>`.

### Perf counters (`window.__sandwalkPerf`, `?perf=1` or dev)

| Counter | Meaning | Healthy |
|---------|---------|---------|
| `terminal.applyPosition` | portal host followed its placeholder | ≈ #terminals per layout change; **0** while scrolling a chat |
| `terminal.fit` / `terminal.ptyResizeRpc` | xterm refit / SIGWINCH sent | 0 on pane focus change |
| `terminal.scrollIgnored` | scroll events filtered per terminal | > 0 when other panes scroll (informational) |
| `render.App`, `render.SidebarSessionList`, `render.SessionTabs`, `render.ChatSplitPanelHeader` | React renders | App ≈ 8/click today; sidebar ≪ App |
| `props.SidebarSessionList.<prop>` | which prop broke the sidebar memo | only `sessionId`, `sections`, `orderedVisibleSessionIds`, `activeGroupChildId` on focus change |
| `terminal.wsOpen`, `terminal.inputQueued` | PTY socket opened / keystrokes held until open | informational |

Add a counter with `perfCount('area.event')` from `@/lib/perf-probe`; add a
render counter as the first line of a component body. Then read it in a spec via
`page.evaluate(() => window.__sandwalkPerf?.snapshot())`.

### Baseline / compare workflow

1. On the branch **before** your perf change: `pnpm e2e:bench` then
   `cp apps/local-web/e2e/results/grid-latest.json apps/local-web/e2e/results/grid-baseline.json`.
2. Make the change, `pnpm e2e:bench`, `pnpm e2e:compare …baseline.json …latest.json`.
3. `compare.mjs` exits 1 on > 25 % regressions (absolute floors: 250 ms, 3 long
   tasks, 2 counter events). `terminal.*Ignored`, `*.wsOpen`, `live.panes` are informational.
   Results are git-ignored; paste the table in the PR.

## Live multi-agent grid bench (real messages, costs tokens)

```bash
SANDWALK_E2E_LIVE=1 SANDWALK_E2E_GRIDS=2x2,4x2,4x4 \
SANDWALK_E2E_PROVIDER=anthropic SANDWALK_E2E_MODEL=claude-sonnet-5 \
pnpm --filter @sandwalk/agent-local-web exec playwright test --project=bench --grep 'live agent grid'
```

Opens an R×C grid, sends one tiny prompt to every pane at once and records per
grid: `live.postLatencyP50/P95Ms` (API `POST /messages`), `live.firstVisibleP50/P95Ms`
(reply painted in its pane), `live.completeP50/P95/MaxMs` (run idle),
`live.failures` split into `stillRunning` / `emptyReply` / `replyNotVisible`,
plus the UI counters under N concurrent streams. Report → `e2e/results/grid-live-latest.json`.

Reading the live numbers: `live.postLatency*` is the API accepting the
message (should be tens of ms; hundreds under 16 concurrent runs = GIL
contention from graph compiles); `first-visible` − server `total run` (from
`[perf]` log lines) is UI/API delivery lag. Agent turns run in worker threads
of the API process, so heavy CPU per turn slows every request — keep per-turn
work cached (`skills_sources` cache, tool memo, MCP tool lists are shared
across concurrent runs and served stale-while-revalidating) and never block
the loop with network I/O (the MCP OAuth refresh did; it now backs off after
a failure). CPU-bound builds (tools + graph compile) go through
`agent/runner/build_slots.py` — `SANDWALK_BUILD_CONCURRENCY` (default 2)
bounds how many run at once so the loop stays responsive. The server `[perf]`
lines to read per run: `tools n=… +Xs`, `create_deep_agent +Xs`,
`first_stream +Xs` (LLM latency). The offline bench also prints
`props.<Component>.<prop>=N` memo-miss counters — that is the prop that
forced a re-render; chase the largest one.

Known: Fable 5 / 5.1 refuse the agent prompt (`stop_reason=refusal`, shows in
the transcript as "(Agent produced no text output — model returned
stop_reason=refusal)") — pin Sonnet 5 or GPT-5.6 Sol for this bench.
Sizes above 4x4 are expensive; ask before running them.

## Adding tests

- **Pure logic** → colocated Vitest/pytest test; it counts toward the coverage gate.
- **Grid/terminal behaviour** → new spec in `apps/local-web/e2e/tests/` using the
  fixtures; assert on DOM (`[data-pane-id]`, `[data-pane-kind]`,
  `[data-pane-focused]`, `[data-terminal-placeholder]`,
  `[data-terminal-portal-host]`, `[data-transcript]`, `[data-tab-id]`) and counters.
- **Perf** → add a `measure()` block to `bench/grid.bench.spec.ts` and `record()` it;
  keep assertions to loose sanity bounds, let `compare` judge deltas.
- Bench/e2e code is typechecked by `tsc -b` (`tsconfig.e2e.json`) and linted; run
  `scripts/verify.sh web` after editing it.

Details: [.github/TESTING.md](../../../.github/TESTING.md).
