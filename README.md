# Sandwalk

**A thinking path for open science.**

Local science agents you can run on your machine — ask research questions in natural language, use computational biology tools, and explore results in a web dashboard. Includes a CLI, local agent server, dashboard, and (on macOS) a menubar app that starts everything for you.

## Install

### CLI (recommended)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv tool install "sandwalk[all]"
sandwalk --version
```

Lighter installs are available if you do not need every optional stack (chemistry, single-cell, etc.):

```bash
uv tool install sandwalk
# or: uv tool install "sandwalk[chemistry]"
```

Upgrade later with:

```bash
sandwalk upgrade
```

### macOS app

Package and install the menubar app (API + dashboard supervised together):

```bash
cd apps/sandwalk-mac
./scripts/package-app.sh
open ~/Applications/Sandwalk.app
```

Or download a release from [GitHub Releases](https://github.com/fastfold-ai/sandwalk/releases) when published.

## First-time setup

```bash
sandwalk setup          # interactive wizard (models, keys, skills)
sandwalk doctor         # health check
```

Set an API key for your model provider (Anthropic, OpenAI, or an OpenAI-compatible endpoint) when prompted, or later with `sandwalk config`.

Optional:

```bash
sandwalk auth generate  # protect the local server / web UI
sandwalk auth enable
sandwalk skills add fastfold-ai/skills
sandwalk data pull-all  # optional local datasets
```

## Usage

### Ask a question (CLI)

```bash
sandwalk "What is known about KRAS G12C inhibitors?"
sandwalk --smiles "CCO" "Profile this compound"
```

Interactive mode:

```bash
sandwalk
```

### Local server + dashboard

```bash
sandwalk serve
```

Then open the dashboard (defaults):

| Service    | URL                         |
|------------|-----------------------------|
| Agent API  | http://127.0.0.1:8787       |
| Dashboard  | http://127.0.0.1:8969       |

On macOS, use **Sandwalk.app** instead: Start / Stop from the menu bar, **Open Web Dashboard**, and **Settings…** for ports, remote bind, API key, models, tools, skills, and more.

### Common commands

```bash
sandwalk config show
sandwalk tool list
sandwalk skills list
sandwalk mcp list
sandwalk data list
sandwalk doctor
sandwalk --help
```

## Configuration

Config and local data live under your user home (typically `~/.sandwalk` / Application Support on macOS). Use:

```bash
sandwalk config show
sandwalk config set <key> <value>
```

For the menubar app, server and auth settings are also editable in **Settings…** and stored in Application Support.

## License

MIT — Copyright © 2026 Fastfold AI Labs. See [LICENSE](LICENSE).

## Contributing / from source

This is a monorepo (`cli/`, `apps/local-web/`, `apps/sandwalk-mac/`). For day-to-day science work, prefer the install options above. To hack on the repo:

```bash
pnpm install
cd cli && uv sync && uv run sandwalk serve
# another terminal: pnpm dev
# or on macOS: cd apps/sandwalk-mac && swift run
```

### Unit tests & coverage

Each component has unit tests with an **≥80%** scoped coverage gate. CI uploads
reports to [Codecov](https://app.codecov.io/gh/fastfold-ai/sandwalk)
with flags `agent-cli`, `agent-server`, `local-web`, and `mac-app`.

```bash
pnpm test:coverage       # Local Web UI
pnpm test:cli:coverage   # Agent CLI + Agent Server
pnpm test:mac            # Mac app (Xcode required)
```

Full guide: [docs/TESTING.md](docs/TESTING.md).

See `apps/sandwalk-mac/README.md` and `cli/README.md` for package-specific notes.
