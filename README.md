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

Agents run on your machine or in the cloud: OpenRouter, frontier APIs, or local models. Science is a starter toolkit, not a ceiling. Chat, CLI, and the Mac app share one session list.

### Capy

Capy is the overlay agent. It is not a chat in the sidebar. It starts and steers other chats, and it can open Bench, skills, MCP servers, and projects.

- Open it from the sidebar, or press **Ctrl + Ctrl** to show the minimized icon and talk hands-free.
- Spawn chats, `#` mention them, seed context, and open a split when you start two or more.
- New chats follow the sidebar scope (All, or the project you have selected). Capy can create projects and move chats.
- Minimize it and keep talking. A red badge counts replies you have not opened.

<!-- screenshot: images/capy.png — Capy overlay or minimized icon -->
<p align="center"><em>Placeholder: Capy overlay. Save as <code>images/capy.png</code></em></p>

### Split view and chats

Session tabs work like a browser. Split the focused pane right or down (**⌘D**, **⇧⌘D**) so two or more chats sit side by side, including chats from different projects. Each pane has its own composer and stream. Files, the terminal, and previews stay in that pane. Pin a chat to keep it at the front of the list.

### CLI

The same sessions, from a terminal. `sandwalk` opens the interactive TUI. `sandwalk serve` runs the local API the Mac app talks to. One-shot prompts, `sandwalk setup`, and the slash commands (`/model`, `/plan`, `/sandbox`) use the sessions you already have in the app.

<!-- screenshot: images/cli.png — Interactive sandwalk TUI -->
<p align="center"><em>Placeholder: Interactive CLI (TUI). Save as <code>images/cli.png</code></em></p>

### Plan mode

Plan mode drafts before it edits. Shift-Tab, or the Plan chip, switches the composer. The agent writes `plans/*.md` with todos and a Mermaid flowchart. **Build** runs that plan. In the CLI, `/plan` does the same thing.

<!-- screenshot: images/plan-mode.png — Plan toggle, plan markdown, Build -->
<p align="center"><em>Placeholder: Plan mode (toggle + Build). Save as <code>images/plan-mode.png</code></em></p>

### Skills and MCPs

Skills are instructions and scripts the agent loads on demand. Install them from GitHub or [skills.sh](https://skills.sh), or ask the agent to find one, try it once, or write one. Type `/` in the composer to attach a skill or an MCP server. MCP config is `~/.sandwalk/mcp.json`, the same shape Cursor uses. Specialists are saved profiles that pin a set of skills, MCPs, and extra instructions for a kind of session.

<!-- screenshot: images/skills.png — Composer / picker with a skill open -->
<p align="center"><em>Placeholder: Skills / MCP picker. Save as <code>images/skills.png</code></em></p>

### Benchmarking

Bench runs question suites through real Sandwalk sessions. Pick a suite, a model, and an optional specialist, set the sample size and how many runs go out in parallel, then read scores on the Results tab. Compare models on the same suite. Runs stay off the chat list. From the CLI: `sandwalk eval`.

<!-- screenshot: images/bench.png — Bench results with scores / judges -->
<p align="center"><em>Placeholder: Bench results. Save as <code>images/bench.png</code></em></p>

### Projects and widgets

Projects group chats. Project Home and Dashboard Overview are boards you can rearrange: usage, library size, a description, agent context. The Library lists files in the project folder next to files the chats produced.

### Artifacts

Structures, plots, and reports open beside the chat instead of as a raw download. That includes CIF and PDB, PAE and pLDDT, plus JSON and SVG.

<!-- screenshot: images/artifacts.png — Structure or plot beside chat -->
<p align="center"><em>Placeholder: Artifacts / structure viewer. Save as <code>images/artifacts.png</code></em></p>

### Remote sessions

Run the agent on a Mac Mini or a cluster and open it from another machine. The Mac app and the CLI both take a URL and an API key. The session list is the one on that server, not a copy on your laptop.

<!-- screenshot: images/remote.png — Remote connect (URL + key) or a remote session -->
<p align="center"><em>Placeholder: Remote session. Save as <code>images/remote.png</code></em></p>

### Models and compute

`sandwalk setup`, or Dashboard → Models, stores keys for Anthropic, OpenAI, Gemini, OpenRouter, and local endpoints (Ollama, Unsloth, oMLX, llama.cpp, LM Studio). The composer shows the model, effort, and how much of the context window the turn is using. Sandbox runs stay on this machine, or go to Modal, Lambda, or Fastfold Cloud when you want a clean GPU box.

### Science toolkit

Live databases (PubChem, ChEMBL, UniProt, PDB, Open Targets, ClinicalTrials.gov, and others) are available as tools. Optional local corpora install with `sandwalk data pull-all`. Add tools for another domain with `sandwalk tool list`.

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
