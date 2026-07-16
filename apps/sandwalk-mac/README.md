<h1 align="center">Sandwalk macOS</h1>

<p align="center">
  <img src="Resources/AppIcon-1024.png" alt="Sandwalk macOS app icon" width="160" height="160" />
</p>

<p align="center">
Native macOS app that supervises the local <strong>agent API</strong> (<code>sandwalk serve</code>) and the
<strong>web dashboard</strong> together — start, stop, restart, open the dashboard, and manage
settings from one place.
</p>

<p align="center">
  <img src="../../images/showcase-mac-app-1.png" alt="Sandwalk macOS menu bar" width="280" />
  &nbsp;&nbsp;
  <img src="../../images/showcase-mac-app-2.png" alt="Sandwalk macOS Settings" width="420" />
</p>

| Mode | API | Dashboard |
|------|-----|-----------|
| **Production** (default) | `127.0.0.1:8787` | Built UI served from the same API port |
| **Development** | `127.0.0.1:8787` | Vite on `127.0.0.1:8969` |

Toggle under **Settings → Server → Advanced**.

## What it does

- **Menu bar** — running status, pinned / recent agents, New Agent (⌘N), Open Web Dashboard (⌘O), Settings (⌘,), Stop / Restart (⌘R), Quit (⌘Q)
- **Settings window** — Server (Status, Network, Advanced, Security, Logs), Agent (Runtime, Sandbox, Prompts), Capabilities (Models, Tools, Datasets, Skills, Specialists, Integrations, MCPs), Workspace, About
- **Supervises both processes** — API + dashboard share Start / Stop / Quit; Apply on network settings restarts both
- **Persists config** under `~/Library/Application Support/Sandwalk/settings.json` (`server` + `auth`), same auth story as `sandwalk auth`

Clicking the Dock icon (while Settings is open) or Launchpad / Applications relaunches into Settings.

## Prerequisites

- macOS 14+
- Full **Xcode** (not Command Line Tools alone) for `swift build` / XCTest
- From the monorepo root: `pnpm install` once (web dashboard deps for Development mode and packaging)

## Run (development)

From the monorepo root:

```bash
pnpm install   # once — web dashboard deps
cd apps/sandwalk-mac && swift run
```

On launch (default auto-start) the app starts API + web.
Use **Start Sandwalk** / **Stop Sandwalk**, **Open Web Dashboard** (⌘O), or **Quit**.

Do **not** run a standalone `pnpm dev` in another terminal while the app is
supervising Development mode — it will fight over the dashboard port.

## Install as a Mac app (Launchpad / Applications)

```bash
cd apps/sandwalk-mac
./scripts/package-app.sh
open ~/Applications/Sandwalk.app
```

This builds `Sandwalk.app`, installs it to `~/Applications`, and applies the
Sandwalk mark icon. Prefer this over bare `swift run` so the app shows up in
Finder / Launchpad like a normal Mac app.

Or download a release from [GitHub Releases](https://github.com/fastfold-ai/sandwalk/releases) when published.

## Settings

**Settings…** manages:

- **Server → Status** — running state, hardware / RAM / load, cache, health probes, endpoints
- **Server → Network** — API / dashboard ports, allow remote connections (`0.0.0.0`), start on launch. Apply restarts both services
- **Server → Advanced** — Production (built UI on API) vs Development (Vite HMR). Default is Production
- **Security** — API key generate / show / copy / reset, enable auth. Same `settings.json` as `sandwalk auth`
- **Agent / Capabilities / Workspace** — runtime, sandbox, models, tools, skills, specialists, MCPs, doctor, storage, and more

Logs: `~/Library/Application Support/Sandwalk/logs/{server,web}.log`

## Env (optional overrides)

Env wins over `settings.json` when set at launch:

| Variable | Default | Meaning |
|----------|---------|---------|
| `SANDWALK_HOST` / `SANDWALK_PORT` | from settings / `127.0.0.1` / `8787` | API bind |
| `SANDWALK_DASHBOARD_HOST` / `SANDWALK_DASHBOARD_PORT` | from settings / `127.0.0.1` / `8969` | Web bind (Development mode) |
| `SANDWALK_DASHBOARD_URL` | — | Override host/port from a full URL |
| `SANDWALK_DASHBOARD_MODE` | from settings / `production` | `production` or `development` |
| `SANDWALK_AUTO_START` | from settings / `1` | Start both on launch (`0` to wait) |
| `SANDWALK_REPO_ROOT` | auto | Monorepo root (`package.json` + `cli/`) |
| `SANDWALK_AGENT_CLI` | `./cli` | Python package root |
| `SANDWALK_SERVE_BIN` | — | Absolute path to `sandwalk` binary |

## Project layout

```
apps/sandwalk-mac/
├── Package.swift              # SandwalkCore library + Sandwalk executable + tests
├── Sources/
│   ├── SandwalkApp/           # Thin @main entry
│   └── SandwalkCore/          # App logic, Settings UI, process supervision, Agent API client
├── Tests/SandwalkTests/       # XCTest (@testable import SandwalkCore)
├── scripts/
│   ├── package-app.sh         # Build + install ~/Applications/Sandwalk.app
│   ├── lint.sh                # SwiftLint (pinned)
│   ├── install-swiftlint.sh   # Portable SwiftLint into .tools/
│   └── test.sh                # Lint → XCTest → coverage gate
├── .swiftlint.yml
└── .swiftlint-version         # Pinned SwiftLint release (e.g. 0.65.0)
```

`SandwalkCore` holds the real app so XCTest can `@testable import` it. The
`Sandwalk` executable is a thin entry only.

## Module size guidance

Prefer cohesive types and views. SwiftLint may warn around ~300 lines under
`Sources/` (comment-only lines ignored); that is advisory, not a hard gate.
Extract helpers, sections, and actions when a file mixes unrelated responsibilities.

SwiftLint is **pinned** in `.swiftlint-version` (portable binary under `.tools/`,
gitignored):

```bash
cd apps/sandwalk-mac
./scripts/lint.sh
# or from repo root:
pnpm lint:mac
```

`./scripts/test.sh` runs lint before XCTest.

## Build

```bash
cd apps/sandwalk-mac
swift build
# release / app bundle:
./scripts/package-app.sh
```

If `swift` cannot find XCTest or SourceKit, point at full Xcode:

```bash
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
```

`scripts/lint.sh` and `scripts/test.sh` set this when needed.

## Tests & coverage

Requires full **Xcode**. `scripts/test.sh` runs SwiftLint, unit tests with
coverage, and **fails if scoped line coverage is below 80%**.

```bash
cd apps/sandwalk-mac
./scripts/test.sh
# or from repo root:
pnpm test:mac
```

Only pure, unit-testable modules count toward
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

## Contributing

This package lives in the [sandwalk](https://github.com/fastfold-ai/sandwalk) monorepo
(`cli/`, `apps/local-web/`, `apps/sandwalk-mac/`). See [CONTRIBUTING.md](../../CONTRIBUTING.md)
for repo-wide setup.

When changing the Mac app:

1. Prefer cohesive modules; extract when a file mixes unrelated responsibilities
2. Prefer logic in `SandwalkCore` (testable) over the thin `SandwalkApp` entry
3. Add / update XCTest coverage for pure helpers you touch; keep the scoped gate ≥80%
4. Run before opening a PR:

```bash
pnpm lint:mac
pnpm test:mac
# or: cd apps/sandwalk-mac && ./scripts/lint.sh && ./scripts/test.sh
```

5. Keep PRs focused; do not commit `.build/`, `.tools/`, secrets, or local settings
6. CI runs Mac lint + tests on macOS runners (`pnpm test:mac` / Codecov flag `mac-app`)

Handy scripts from this directory:

| Script | Purpose |
|--------|---------|
| `./scripts/lint.sh` | Install pinned SwiftLint if needed + advisory lint |
| `./scripts/test.sh` | Lint → XCTest → coverage gate + `coverage.lcov` |
| `./scripts/package-app.sh` | Release-style `Sandwalk.app` into `~/Applications` |
