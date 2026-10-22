# Working in this repo (humans and agents)

Sandwalk is a monorepo: `cli/` (Python agent API + CLI), `apps/local-web/`
(React dashboard, Tauri shell), `apps/sandwalk-mac/` (Swift menubar server),
`apps/packaging/` (DMG / signing). Two skills in `.agents/skills/` carry the
day-to-day workflow — read them before running or testing anything:

- **`sandwalk-dev-loop`** — run the API (`scripts/dev-api.sh`, :8787) and the UI
  (`scripts/dev-ui.sh`, :1420) from this checkout; what hot-reloads; how to get
  the packaged app off :8787.
- **`sandwalk-testing`** — what to run per change (`scripts/verify.sh` mirrors
  the required CI gate), the Playwright e2e + perf harness in
  `apps/local-web/e2e/`, baseline/compare, and the live multi-agent grid bench.

## Ground rules

- Run `scripts/verify.sh` before every commit; grid/terminal/PTY changes also
  need `scripts/verify.sh e2e`; perf-sensitive UI changes need a bench
  baseline → compare table in the PR.
- User-facing strings are English. Code comments may be anything readable,
  but new comments should be English too.
- Never print or commit API keys / tokens (`~/.sandwalk/config.json`,
  `settings.json`, `token=` in URLs). Redact when quoting logs.
- Do not start/restart the packaged "Sandwalk Server" menubar app to test
  checkout code — it runs the bundled API.
- Keep `perfCount()` / `data-pane-*` hooks: the harness depends on them.
- Commit style: `type(scope): imperative summary` (`fix(fas-107): …`,
  `perf(grid): …`, `test(e2e): …`); explain the *why* in the body.
- Coverage thresholds in `apps/local-web/vitest.config.ts` and
  `cli/pyproject.toml` are floors — raise, never lower, to make a test pass.

More: [CONTRIBUTING.md](CONTRIBUTING.md), [.github/TESTING.md](.github/TESTING.md),
[apps/local-web/DESKTOP.md](apps/local-web/DESKTOP.md).
