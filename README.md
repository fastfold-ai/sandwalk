<p align="center">
  <a href="https://github.com/fastfold-ai/sandwalk"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/sandwalk-logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="images/sandwalk-logo-light.svg">
    <img alt="sandwalk" src="images/sandwalk-logo-light.svg" height="64" style="max-width:100%;">
  </picture></a>
</p>
<p align="center">
  <small>An agent harness for ambitious work.</small>
</p>

<p align="center">
  <a href="#get-started">Get started</a> ·
  <a href="#quickstart">Quickstart</a> ·
  <a href="#features">Features</a> ·
  <a href="#capy">Capy</a> ·
  <a href="#cli">CLI</a> ·
  <a href="#documentation">Docs</a>
</p>

<p align="center">
  <img alt="Sandwalk desktop: chat, files, and terminal" src="images/showcase.png" style="max-width:100%; border-radius:8px;">
</p>

> Sandwalk is an open, self-hosted agent you run on your own compute. Direct it toward hard scientific research, or any ambitious work. Chat, CLI, and the macOS app share the same sessions. Leave one running on a Mac Mini or a cluster and open it from wherever you are.

## Get started

Download the native Sandwalk app for your operating system:

| Platform | Link |
|----------|------|
| macOS (Apple Silicon) | [Download](https://github.com/fastfold-ai/sandwalk/releases/latest/download/Sandwalk-macos-arm64.dmg) |

Download from [GitHub Releases](https://github.com/fastfold-ai/sandwalk/releases).

Or if you prefer to install the CLI:

```bash
curl -fsSL https://sandwalk.sh/install | bash
```

## Quickstart

### macOS App

Launch Sandwalk from Applications. Pick **Local** or **Remote**, then start a session.

<!-- screenshot: images/welcome.png — Welcome: Local vs Remote -->
<p align="center"><em>Placeholder: Welcome (Local vs Remote). Save as <code>images/welcome.png</code></em></p>

<!-- screenshot: images/menubar.png — Sandwalk Server menubar -->
<p align="center"><em>Placeholder: Menubar helper. Save as <code>images/menubar.png</code></em></p>

### CLI

```bash
sandwalk setup
sandwalk
sandwalk "What is known about KRAS G12C inhibitors?"
```

## Features

Agents run 24/7 on your machine or in the cloud: OpenRouter, frontier APIs, or local models. Science is a starter toolkit, not a ceiling.

### Capy

Capy is the overlay meta-agent. It stays out of the chat list and orchestrates worker chats, Bench, Doctor, skills, MCP, and projects.

- Open it from the sidebar, or **Ctrl + Ctrl** anywhere to show the minimized icon and talk hands-free.
- Spawn chats, `#` mention them, seed context, and open a split when you start two or more.
- New chats follow the current sidebar scope (All vs a selected project). Capy can create projects and move chats.
- Minimize to keep talking. A macOS-style red badge counts new replies.

<!-- screenshot: images/capy.png — Capy overlay or minimized icon -->
<p align="center"><em>Placeholder: Capy overlay. Save as <code>images/capy.png</code></em></p>

### Split view and chats

Chrome-style session tabs. Group 2–3 chats side by side — including chats from different projects. Each panel is a full session (own composer and stream). Files, terminal, and preview sit in the workspace panel under the tab strip. CLI, Mac, and iOS share one session.

### CLI

A fully featured CLI for people who love a TUI. Same sessions as the Mac app.

<!-- screenshot: images/cli.png — Interactive sandwalk TUI -->
<p align="center"><em>Placeholder: Interactive CLI (TUI). Save as <code>images/cli.png</code></em></p>

### Plan mode

Draft `plans/*.md` with todos and a Mermaid flowchart, then **Build** when ready. CLI: `/plan`.

<!-- screenshot: images/plan-mode.png — Plan toggle, plan markdown, Build -->
<p align="center"><em>Placeholder: Plan mode (toggle + Build). Save as <code>images/plan-mode.png</code></em></p>

### Skills and MCPs

Install from GitHub or [skills.sh](https://skills.sh). Type `/` in chat to browse. Ask the agent to find, try once, or create a skill. Config is Cursor-compatible `~/.sandwalk/mcp.json`.

<!-- screenshot: images/skills.png — Composer / picker with a skill open -->
<p align="center"><em>Placeholder: Skills / MCP picker. Save as <code>images/skills.png</code></em></p>

### Benchmarking and Doctor

Automate evals, score results, and run LLM judges. Dashboard → Bench, or `sandwalk eval`. Live suites stay off your chat list. Doctor reports diagnostics from the Dashboard or via Capy.

<!-- screenshot: images/bench.png — Bench results with scores / judges -->
<p align="center"><em>Placeholder: Bench results. Save as <code>images/bench.png</code></em></p>

### Human-in-the-loop

Skill install and remove pause for **Approve / Edit / Reject** in the desktop chat or interactive CLI.

<!-- screenshot: images/hitl.png — Approval card in chat -->
<p align="center"><em>Placeholder: Approval card. Save as <code>images/hitl.png</code></em></p>

### Projects and widgets

Projects group chats. Project Home and Dashboard Overview use configurable widget boards (usage, library size, description, agent context). Library lists project-folder files next to chat artifacts.

### Artifacts

Structures, plots, and reports open beside the chat (CIF/PDB, PAE, pLDDT, JSON, SVG).

<!-- screenshot: images/artifacts.png — Structure or plot beside chat -->
<p align="center"><em>Placeholder: Artifacts / structure viewer. Save as <code>images/artifacts.png</code></em></p>

### Remote sessions

Run the agent on a Mac Mini or a university cluster. Open it from the Mac app or CLI wherever you are.

<!-- screenshot: images/remote.png — Remote connect (URL + key) or a remote session -->
<p align="center"><em>Placeholder: Remote session. Save as <code>images/remote.png</code></em></p>

### Models and compute

`sandwalk setup` (or Dashboard → Models) for Anthropic, OpenAI, Gemini, OpenRouter, and local endpoints (Ollama, Unsloth, oMLX, llama.cpp, LM Studio). Local Sandbox on your machine, or Modal / Lambda / Fastfold Cloud for GPU jobs.

### Science toolkit

Live databases (PubChem, ChEMBL, UniProt, PDB, Open Targets, ClinicalTrials.gov, …) and optional local corpora (`sandwalk data pull-all`). Install more tools for any domain: `sandwalk tool list`.

## CLI

A fully featured TUI for people who prefer the terminal. Same sessions as the Mac app.

```bash
sandwalk setup
sandwalk
sandwalk serve
sandwalk eval
sandwalk skills add fastfold-ai/skills
sandwalk --help
```

Interactive: `/model`, `/sandbox`, `/plan`, `/usage`. Full reference: [`cli/README.md`](cli/README.md).

Config lives under `~/.sandwalk/`.

## Documentation

Product docs: [`docs/`](docs/) (`pnpm dev:docs`). Site: [sandwalk.sh](https://sandwalk.sh).

## Contributing

Monorepo: `cli/`, `apps/local-web/`, `apps/sandwalk-mac/`, `apps/packaging/`. See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
git clone https://github.com/fastfold-ai/sandwalk.git
cd sandwalk
pnpm install
cd cli && uv sync --extra dev && cd ..
scripts/dev-api.sh        # agent API from this checkout on :8787
scripts/dev-ui.sh         # another terminal: Tauri window + Vite :1420 (`web` for browser only)
```

Testing mirrors CI in one command, plus a Playwright harness for the split
grid / terminals and perf benchmarks with before/after comparison:

```bash
scripts/verify.sh         # typecheck, lint, build, unit tests + coverage gates (web + cli)
pnpm e2e                  # grid + terminal e2e against your running API
pnpm e2e:bench            # perf report → apps/local-web/e2e/results/grid-latest.json
pnpm e2e:compare apps/local-web/e2e/results/grid-baseline.json apps/local-web/e2e/results/grid-latest.json
```

Working with an AI agent? [AGENTS.md](AGENTS.md) and the project skills in
`.cursor/skills/` (`sandwalk-dev-loop`, `sandwalk-testing`) encode the dev and
test cycle; [.github/TESTING.md](.github/TESTING.md) has the details.

## License

[Apache License 2.0](LICENSE). Copyright © 2026 Fastfold AI Labs.
