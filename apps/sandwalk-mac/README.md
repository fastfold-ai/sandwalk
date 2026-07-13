# Sandwalk macOS menubar

Menubar app that owns **both** the agent API (`sandwalk serve`) and the web
dashboard (Vite) — Start / Stop / Quit together, like oMLX’s unified control.

| Service | Default | Health |
|---------|---------|--------|
| Agent API | `127.0.0.1:8787` | `GET /v1/health` |
| Web UI | `127.0.0.1:8969` | HTTP GET `/` |

## Run (from monorepo root)

```bash
pnpm install   # once — web dashboard deps
cd apps/sandwalk-mac && swift run
```

On launch (default auto-start) the menu bar starts API + web.
Use **Start Sandwalk** / **Stop Sandwalk**, **Open Web Dashboard** (⌘O), or **Quit**.

**Settings…** opens a real Settings window (Server + Security). Clicking the Dock
icon (while Settings is open) or Launchpad / Applications relaunches into Settings.

## Install as a Mac app (Launchpad / Applications)

```bash
cd apps/sandwalk-mac
./scripts/package-app.sh
open ~/Applications/Sandwalk.app
```

This builds `Sandwalk.app`, installs it to `~/Applications`, and gives it the
Sandwalk mark icon. Prefer this over bare `swift run` so the app shows up in
Finder / Launchpad like a normal Mac app.

Persisted under `~/Library/Application Support/Sandwalk/settings.json` (`server` + `auth` sections).

**Settings…** (menubar) manages:

- **Server** — API / dashboard ports, allow remote connections (`0.0.0.0`), start on launch. Apply restarts both services.
- **Security** — API key generate / show / copy / reset, enable auth. Same `settings.json` as `sandwalk auth`.

Do **not** run a standalone `pnpm dev` in another terminal while the menubar is
supervising — it will fight over the dashboard port.

## Env (optional overrides)

Env wins over `settings.json` when set at launch:

| Variable | Default | Meaning |
|----------|---------|---------|
| `SANDWALK_HOST` / `SANDWALK_PORT` | from settings / `127.0.0.1` / `8787` | API bind |
| `SANDWALK_DASHBOARD_HOST` / `SANDWALK_DASHBOARD_PORT` | from settings / `127.0.0.1` / `8969` | Web bind |
| `SANDWALK_DASHBOARD_URL` | — | Override host/port from a full URL |
| `SANDWALK_AUTO_START` | from settings / `1` | Start both on launch (`0` to wait) |
| `SANDWALK_REPO_ROOT` | auto | Monorepo root (`package.json` + `cli/`) |
| `SANDWALK_AGENT_CLI` | `./cli` | Python package root |
| `SANDWALK_SERVE_BIN` | — | Absolute path to `sandwalk` binary |

Logs: `~/Library/Application Support/Sandwalk/logs/{server,web}.log`

## Tests & coverage

Requires full **Xcode** (not Command Line Tools alone) so `XCTest` is available.
`scripts/test.sh` sets `DEVELOPER_DIR` to Xcode.app when needed, runs unit tests
with coverage, and **fails if scoped line coverage is below 80%**.

```bash
cd apps/sandwalk-mac
./scripts/test.sh
```

The gate matches **local-web**: only pure, unit-testable modules count toward
coverage (SwiftUI views and process supervisors are excluded):

- `PathSupport.swift`
- `SettingsSection.swift`
- `AppConfig.swift` (includes `ServerSettingsStore`)
- `AuthSettingsStore.swift`
- `AgentAPI/AgentAPIModels.swift`

Override the threshold with `COVERAGE_THRESHOLD=85 ./scripts/test.sh`.

Run tests without the gate:

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift test --enable-code-coverage
```

Outputs after a successful `./scripts/test.sh`:

- `coverage-report.txt` — llvm-cov text summary
- `coverage.lcov` — uploaded to Codecov as flag `mac-app` in CI

Scoped HTML report (after `./scripts/test.sh` or a coverage-enabled test run):

```bash
BIN="$(swift build --show-bin-path)"
xcrun llvm-cov show \
  "$BIN/SandwalkPackageTests.xctest/Contents/MacOS/SandwalkPackageTests" \
  -instr-profile="$BIN/codecov/default.profdata" \
  -format=html -output-dir coverage-html \
  Sources/SandwalkCore/PathSupport.swift \
  Sources/SandwalkCore/SettingsSection.swift \
  Sources/SandwalkCore/AppConfig.swift \
  Sources/SandwalkCore/AuthSettingsStore.swift \
  Sources/SandwalkCore/AgentAPI/AgentAPIModels.swift
open coverage-html/index.html
```

Full monorepo testing guide: [docs/TESTING.md](../../docs/TESTING.md).

Pure helpers live in the `SandwalkCore` library target so XCTest can
`@testable import` them. The `Sandwalk` executable is a thin `@main` entry only.

