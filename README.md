<h1 align="center" style="margin:0;">
  <a href="https://github.com/fastfold-ai/sandwalk"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/sandwalk-logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="images/sandwalk-logo-light.svg">
    <img alt="sandwalk" src="images/sandwalk-logo-light.svg" height="64" style="max-width:100%;">
  </picture></a>
</h1>
<h3 align="center" style="margin: 0; margin-top: 0.5rem;">
A thinking path for open science.
</h3>

<p align="center">
  <a href="https://github.com/fastfold-ai/sandwalk/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/fastfold-ai/sandwalk/ci.yml?branch=main&label=CI&logo=github" alt="CI status" /></a>
  <a href="https://codecov.io/gh/fastfold-ai/sandwalk"><img src="https://img.shields.io/codecov/c/github/fastfold-ai/sandwalk?branch=main&logo=codecov&label=coverage" alt="Codecov coverage" /></a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#install">Install</a> •
  <a href="#first-time-setup">Setup</a> •
  <a href="#usage">Usage</a> •
  <a href="#contributing--from-source">Contributing</a>
</p>
<br>
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/showcase-dark.jpg">
    <source media="(prefers-color-scheme: light)" srcset="images/showcase-light.jpg">
    <img alt="sandwalk dashboard: chat, structure viewers, skills, and terminal" src="images/showcase-light.jpg" style="max-width:100%; border-radius:8px;">
  </picture>
</p>
<br>

**sandwalk** is a local science agent for open research: ask questions in natural language and it plans multi-step workflows across 190+ tools, database APIs, skills, MCPs, and sandboxes. Think of it as a coding agent, but for biology and drug discovery.

Includes a CLI, local agent server, web dashboard with viewers, and a Mac app that starts everything for you. Run fully on your machine, or reach cloud GPUs when the work needs it.

## Features

- **CLI ↔ web sessions**: start a chat in the terminal or the dashboard; both share the same agent sessions, workspace, and history (bidirectional).
- **190+ science tools**: chemistry, targets, structures, expression, genomics, clinical, literature, single-cell, and more (`sandwalk tool list`).
- **Database APIs**: live lookups across PubChem, ChEMBL, UniProt, PDB, Open Targets, ClinicalTrials.gov, GTEx, STRING, Ensembl, NCBI, and related sources.
- **Local datasets**: optional offline corpora such as DepMap, PRISM, L1000, proteomics, MSigDB, and STRING (`sandwalk data pull-all`).
- **Local**: run the agent, tools, and dashboard on your machine with a local sandbox for code and plots.
- **Cloud GPU sandboxing**: run heavy compute in an isolated GPU sandbox, or send serverless jobs to Modal, Lambda, or Fastfold Cloud (folding, design, MD, and more).
- **MCPs**: connect remote tool servers (catalog + custom) so the agent can use external apps and data sources.
- **Skills**: discover and install guided workflows (`sandwalk skills find` / `sandwalk skills add`).
- **Specialist profiles**: save skill + MCP + instruction packs for repeatable research modes (`sandwalk specialists`).
- **Viewers**: explore structures, plots, and results in the web dashboard alongside the chat transcript.

### Tools and databases

Built for tool-heavy research, not generic chat. The agent can search tools on demand, call them in a sandbox, and chain results into a report.

**Tool areas**

- Targets and genetics
- Chemistry and compounds
- Protein structure and design
- Expression, omics, and single-cell
- Clinical and translational
- Literature and competitive intel
- Safety, PK, biomarkers, and statistics

**Database APIs (examples)**

- PubChem, ChEMBL, DrugBank
- UniProt, PDB / RCSB, AlphaFold DB
- Open Targets, ClinicalTrials.gov
- GTEx, STRING, Ensembl, NCBI

**Local datasets**

- DepMap (CRISPR / models)
- PRISM (drug sensitivity)
- L1000 (expression signatures)
- Proteomics, MSigDB, STRING

List everything with `sandwalk tool list` and `sandwalk data list`.

### Models

Configure providers during `sandwalk setup`, in the dashboard, or with `sandwalk config`.

**Frontier / cloud**

- Anthropic (Claude)
- OpenAI
- Google Gemini
- xAI (Grok)
- NVIDIA
- OpenCode Zen

**Local models**

Point sandwalk at an OpenAI-compatible endpoint on your machine:

- Ollama
- Unsloth
- oMLX
- DS4
- llama.cpp
- LM Studio

### Integrations

Built-in keys and connectors (Dashboard → Integrations / `sandwalk keys`):

- Modal
- LangSmith
- Tavily
- Slack
- Vercel
- NVIDIA
- OpenCode Zen
- Custom webhook

### MCP catalog

Featured remote MCPs you can connect from setup or Dashboard → MCP:

- Tamarind Bio (protein design, structure, docking, MD)
- Paperclip (papers, trials, biology databases)
- Latch Bio (bioinformatics workflows and compute)
- Neurosnap (folding, docking, design jobs)

Also available: Linear. Add any custom MCP URL as well.

## Install

### CLI (recommended)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv tool install sandwalk
sandwalk --version
```

That installs all **core** dependencies (agent server, Local Sandbox plotting stack,
Modal runtime client, etc.). Optional science stacks are separate extras:

```bash
uv tool install "sandwalk[all]"          # chemistry, single-cell, ML, …
# or: uv tool install "sandwalk[chemistry]"
```

Upgrade later with:

```bash
sandwalk upgrade
```

### macOS app

Package and install the Mac app (API + dashboard supervised together):

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

On macOS, use **Sandwalk.app** instead: Start / Stop, **Open Web Dashboard**, and **Settings…** for ports, remote bind, API key, models, tools, skills, and more.

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

Config and local data live under `~/.sandwalk/` (legacy `~/.fastfold-cli/` and
`~/.ct/` are copied once on first run if present). Use:

```bash
sandwalk config show
sandwalk config set <key> <value>
```

For the Mac app, server and auth settings are also editable in **Settings…** and stored in Application Support.

## License

MIT. Copyright © 2026 Fastfold AI Labs. See [LICENSE](LICENSE).

## Contributing / from source

This is a monorepo (`cli/`, `apps/local-web/`, `apps/sandwalk-mac/`). For day-to-day science work, prefer the install options above. To hack on the repo, see [CONTRIBUTING.md](CONTRIBUTING.md). Quick start:

```bash
pnpm install
cd cli && uv sync --extra dev --extra all --extra api && uv run sandwalk serve
# another terminal: pnpm dev
# or on macOS: cd apps/sandwalk-mac && swift run
```

`uv sync` (no extras) already installs core deps including the Local Sandbox stack.
`--extra all` adds optional chemistry / single-cell / ML packages for full science tooling.

### Lint

```bash
cd cli && uv run ruff check src && uv run mypy
pnpm --filter @sandwalk/agent-local-web lint:check
pnpm --filter @sandwalk/agent-local-web build
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
