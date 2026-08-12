<h1 align="center" style="margin:0;">
  <a href="https://github.com/fastfold-ai/sandwalk"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/sandwalk-logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="images/sandwalk-logo-light.svg">
    <img alt="sandwalk" src="images/sandwalk-logo-light.svg" height="64" style="max-width:100%;">
  </picture></a>
</h1>
<h3 align="center" style="margin: 0; margin-top: 0;">
Great ideas need a path. This one is yours.
</h3>

<p align="center">
  <a href="#-get-started">Get started</a> •
  <a href="#features">Features</a> •
  <a href="#quickstart">Quickstart</a> •
  <a href="#documentation">Documentation</a>
</p>

## ⚡ Get started

Download the native Sandwalk Desktop app for your operating system:

| Platform | Link |
|----------|------|
| macOS (Apple Silicon) | [Download](https://github.com/fastfold-ai/sandwalk/releases/latest/download/Sandwalk-macos-arm64.dmg) |

Download from [GitHub Releases](https://github.com/fastfold-ai/sandwalk/releases).

Open **Sandwalk.app**. The nested menubar helper starts the agent and installs a `sandwalk` command into `~/.local/bin` (open a new terminal, then `sandwalk --version`). Same sessions as the CLI and web dashboard.

If you already installed the CLI via curl/uv, that install is left alone (the app does not overwrite it).

### Or if you prefer to install the CLI manually

#### macOS, Linux

```bash
curl -fsSL https://sandwalk.sh/install | bash
sandwalk --version
```

This installs the **Python CLI only** (via uv / pipx / pip). It does **not** download or install `Sandwalk.app`. Use the Desktop DMG above for the native Mac app.

Tracks the latest **stable** [GitHub Release](https://github.com/fastfold-ai/sandwalk/releases). For pre-releases:

```bash
curl -fsSL https://sandwalk.sh/install | bash -s -- --pre
```

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/) (or pipx / pip).

## Features

**sandwalk** runs agents 24/7 on your compute or in the cloud: OpenRouter, frontier APIs, or local models. You decide what they work on: a hard scientific question, a company, a craft, a line of inquiry nobody has funded yet.

Leave a session on a Mac Mini at home or a university cluster, and control it remotely from the CLI, the Mac app, and iOS.

Invention, not just automation. Novel ideas come from people with better tools. As those tools get more powerful, each person becomes more able to shape the work. Sandwalk is open source and self-hosted, so you keep the keys.

- **CLI ↔ Mac ↔ iOS**: one agent session across terminal, desktop, and phone.
- **Remote sessions**: run the agent on a Mac Mini or a university cluster; open it from wherever you are.
- **Benchmarking**: automate evals, score results, and run LLM judges. Dashboard → Bench, or `sandwalk eval`.
- **Split view and chats**: several sessions in tabs. Chat, files, and terminal side by side in one working UI.
- **Working terminal**: a real shell next to the chat. Use Codex, Claude, OpenCode, Pi, or any other CLI you already run.
- **Plan mode**: draft `plans/*.md` with todos and a Mermaid flowchart, then **Build** when ready.
- **Multimodal**: `@`-attach images, PDFs, audio, and video (Gemini takes the full set).
- **Tools you can grow**: install as many as you want. We ship a deep science starter set (chemistry, targets, structures, omics, clinical, literature) and you add whatever your field needs.
- **Live databases**: PubChem, ChEMBL, UniProt, PDB, Open Targets, ClinicalTrials.gov, GTEx, STRING, Ensembl, NCBI, …
- **Local datasets**: optional DepMap, PRISM, L1000, proteomics, MSigDB, STRING (`sandwalk data pull-all`).
- **Local + cloud compute**: Local Sandbox on your machine, or Modal / Lambda / Fastfold Cloud for GPU jobs.
- **Skills & MCPs**: install from GitHub or [skills.sh](https://skills.sh); connect remote MCPs via Cursor-compatible `~/.sandwalk/mcp.json`.
- **Find skills**: ask the agent to search the Fastfold catalog and the [skills.sh](https://skills.sh) ecosystem (`skill-find` / `skills.manage find`), try a skill once without installing, or install what you pick.
- **Create skills with the agent**: scaffold, author, validate, and install new skills via `skill-creator`. They land under **Created by Me** and show up in the composer `/` menu.
- **Human-in-the-loop approvals**: skill install/remove (and related lifecycle actions) pause for **Approve / Edit / Reject** in the desktop chat or interactive CLI; one approve can cover the rest of a run.
- **Specialists**: reusable skill + MCP + instruction packs for focused modes.
- **Voice input (desktop)**: dictate into the composer with on-device Whisper.
- **Slack**: talk to Sandwalk from Slack DMs or `@mentions`. One-click via Fastfold Cloud, or manual Socket Mode with your own app tokens.
- **Viewers**: structures, plots, and artifacts beside the chat.

### Tools, data, and models

We ship a deep science toolkit out of the box (targets and genetics, chemistry, protein structure and design, expression / single-cell, clinical and translational, literature, safety / PK / stats). That is a starting point, not a ceiling. Install more for any domain. Browse what you have with `sandwalk tool list` and `sandwalk data list`.

**Models** (via `sandwalk setup`, the dashboard, or `sandwalk config`): Anthropic, OpenAI, Google Gemini, xAI (Grok), Kimi (Moonshot), NVIDIA, OpenCode Zen, DeepSeek, MiniMax, Mistral, Qwen Cloud, Together AI, OpenRouter, plus local OpenAI-compatible endpoints like Ollama, Unsloth, oMLX, DS4, llama.cpp, and LM Studio.

**Integrations** (`sandwalk keys` / Dashboard → Integrations): Modal, LangSmith, Tavily, Slack (one-click or Socket Mode), Vercel, NVIDIA, OpenCode Zen.

**MCP catalog** (seeded in Dashboard → MCPs): Tamarind Bio, Paperclip, Latch Bio, Neurosnap, plus Linear, Lucid, and any custom URL.

## Quickstart

```bash
sandwalk setup          # models, keys, skills
sandwalk doctor

sandwalk                # interactive (shares sessions with the dashboard)
sandwalk "What is known about KRAS G12C inhibitors?"

sandwalk serve          # API + dashboard (or use Sandwalk.app)
```

| Service   | Default URL             |
|-----------|-------------------------|
| Agent API | http://127.0.0.1:8787   |
| Dashboard | http://127.0.0.1:8969   |

```bash
sandwalk auth generate && sandwalk auth enable   # optional API key
sandwalk skills add fastfold-ai/skills
sandwalk data pull-all                           # optional local corpora
```

## Web Dashboard

Open the Vite UI (`pnpm --filter @sandwalk/agent-local-web dev`), `http://127.0.0.1:8969` after `sandwalk serve`, or **Open Sandwalk** from the Mac menubar. Chat, files, viewers, and a terminal share the same sessions as the CLI.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/showcase-web-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="images/showcase-web-light.png">
    <img alt="sandwalk web dashboard overview" src="images/showcase-web-light.png" width="820" style="max-width:100%; border-radius:8px;">
  </picture>
</p>

### Overview and projects

Overview shows a year-long session heatmap plus featured skills, MCPs, and integrations. **Projects** scope sessions and files to a campaign; each project can set **Agent Context** that every agent in that project inherits.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/showcase-projects-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="images/showcase-projects-light.png">
    <img alt="Create a project with name, description, and agent context" src="images/showcase-projects-light.png" width="520" style="max-width:100%; border-radius:8px;">
  </picture>
</p>

### Composer

The composer drives every turn: model and effort, specialist, sandbox, plus `@` files and `/` skills & MCPs.

**Model.** Pick a frontier or local model, set Low / Medium / High effort, and optionally enable Fast.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/showcase-composer-models-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="images/showcase-composer-models-light.png">
    <img alt="Model picker with effort and fast mode" src="images/showcase-composer-models-light.png" width="640" style="max-width:100%; border-radius:8px;">
  </picture>
</p>

**Specialist.** Load a skill + MCP + instruction pack (genomics, MD, protein design, …) or define your own.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/showcase-composer-specialist-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="images/showcase-composer-specialist-light.png">
    <img alt="Specialist profile picker in the composer" src="images/showcase-composer-specialist-light.png" width="640" style="max-width:100%; border-radius:8px;">
  </picture>
</p>

**Sandbox.** Stay on Local Sandbox (live chip / RAM / GPU specs) or switch to Modal for cloud CPU/GPU.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/showcase-composer-sandbox-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="images/showcase-composer-sandbox-light.png">
    <img alt="Sandbox picker: Local or Modal with machine specs" src="images/showcase-composer-sandbox-light.png" width="640" style="max-width:100%; border-radius:8px;">
  </picture>
</p>

**Plan mode.** Switch the composer from **Agent** to **Plan** when you want a campaign design first. The agent writes `plans/<slug>.md` (steps + Mermaid), fills todos, and surfaces a **Build** action with no Y/n gate. Edit in chat, then Build or flip back to Agent. In the CLI: `/plan` (sessions start in Agent mode; the status bar shows plan mode only when on).

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/showcase-plan-mode-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="images/showcase-plan-mode-light.png">
    <img alt="Plan mode: composer toggle, created plan with Build, and plan markdown preview" src="images/showcase-plan-mode-light.png" width="720" style="max-width:100%; border-radius:8px;">
  </picture>
</p>

**Multimodal.** `@`-attach workspace files in the same composer. Gemini models accept image, PDF, audio, and video natively; Dashboard → **Models** → **Multimodal support** lists what each model can take.

**Voice input (desktop).** In Sandwalk.app, Dashboard → **Voice** installs OpenAI Whisper Base (English) locally, then a mic check unlocks dictation in the composer. Speak, confirm, and the transcript lands in the draft (nothing is auto-sent). Capture and transcription run in the Tauri process; model weights live under Sandwalk app data `models/` (also listed on Dashboard → **Storage**). Browser builds show a desktop-only notice. No Web Speech / cloud STT fallback. Supported on macOS 12+ Apple Silicon and Windows 10 22H2 / 11 x64.

### Skills and MCPs

Type `/` in chat to browse skills and MCPs for the active specialist. Open a skill for docs and **Try** example prompts without leaving the thread. Mentions like `/lab-notes` in chat link to skill details.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/showcase-skills-mcps-picker-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="images/showcase-skills-mcps-picker-light.png">
    <img alt="Composer skills and MCPs picker with boltz examples" src="images/showcase-skills-mcps-picker-light.png" width="720" style="max-width:100%; border-radius:8px;">
  </picture>
</p>

#### Find and create skills (with the agent)

You can manage skills from the dashboard **or** by asking the agent in chat / CLI:

| Goal | How |
|------|-----|
| **Find** | Ask to find skills for a task (e.g. “find a Google Calendar skill”). The agent uses **skill-find**: Fastfold catalog first, then [skills.sh](https://skills.sh) / curated collections. It can **try once** without installing, or **install** after you confirm. |
| **Create** | Ask to create a skill. The agent uses **skill-creator** to scaffold `SKILL.md` (optional scripts), validate, package, and install. New skills are tagged **Created by Me** under your local user name and appear in `/` on the next turn. |
| **Lifecycle** | Enable, disable, remove, or list skills via the same `skills.manage` flow (`sandwalk skills …` also works). |

#### Human-in-the-loop (approve / reject)

When the agent installs, removes, or otherwise changes skill lifecycle in a way that needs a gate, the run **pauses** for your decision:

- **Desktop / web chat**: an approval card with **Approve**, **Edit**, or **Reject** (and batch approve for the rest of the run when applicable).
- **Interactive CLI**: a terminal HITL prompt with the same decisions.
- Notifications can surface pending approvals when the window is in the background.

This is separate from chat “yes/no”. The primary gate is the approval UI so installs don’t proceed on a casual confirmation alone.

Manage MCP servers under Dashboard → **MCPs**: toggle catalog entries, connect when auth is required, or add a custom URL. Credentials live under Integrations / keys.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/showcase-mcp-servers-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="images/showcase-mcp-servers-light.png">
    <img alt="MCP servers management with toggles and catalog entries" src="images/showcase-mcp-servers-light.png" width="720" style="max-width:100%; border-radius:8px;">
  </picture>
</p>

Config is stored as standard `mcpServers` JSON in `~/.sandwalk/mcp.json`, the same shape Cursor and other MCP clients use. Edit from **Edit mcp.json** and **Save MCPs**, or hand-edit the file.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/showcase-mcp-json-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="images/showcase-mcp-json-light.png">
    <img alt="Edit mcp.json dialog with Cursor-compatible mcpServers config" src="images/showcase-mcp-json-light.png" width="720" style="max-width:100%; border-radius:8px;">
  </picture>
</p>

For packaged workflows, open Dashboard → **Skills**. Toggle **Skills.sh** to search the [skills.sh](https://skills.sh) registry (results show install counts), or import from GitHub (`owner/repo`, `owner/repo@path`, or a URL, same as `sandwalk skills add`).

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/showcase-skills-sh-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="images/showcase-skills-sh-light.png">
    <img alt="Skills.sh catalog search with install counts" src="images/showcase-skills-sh-light.png" width="720" style="max-width:100%; border-radius:8px;">
  </picture>
</p>

Open a skill for the install command, enable/disable toggle, links to Skills.sh and GitHub, plus install count and security audit badges (Socket, Snyk, and others).

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/showcase-skills-manage-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="images/showcase-skills-manage-light.png">
    <img alt="Skill detail with install count and security audits" src="images/showcase-skills-manage-light.png" width="720" style="max-width:100%; border-radius:8px;">
  </picture>
</p>

### Integrations: Slack

Connect Slack from Dashboard → **Integrations** → **Slack** on the desktop (or local web UI). Two modes:

| Mode | How it works |
|------|----------------|
| **One-click** | Sign in to Fastfold Cloud, authorize Slack, and Sandwalk receives Events API traffic over a cloud relay. No bot/app tokens to paste. After OAuth, the browser returns to a local success page and the desktop imports the workspace automatically. |
| **Manual Socket Mode** | Paste bot + app-level tokens for your own Slack app; Sandwalk opens a Socket Mode connection locally. |

Both modes support DMs and channel `@mentions`, Slack’s **Agents & AI Apps** messaging container, and Block Kit replies (not a single text blob). Pause or resume a workspace to stop/start the agent without disconnecting; Disconnect removes the connection. You can run different workspaces in different modes at once (one mode per workspace).

Fastfold Cloud → Integrations → **Sandwalk** is view/revoke only. Connect and manage live status from the Sandwalk desktop.

### Artifacts and terminal

When the agent produces structures, plots, or reports, open them in **Artifacts** beside the chat: JSON, SVG (PAE, pLDDT), and CIF/PDB in a 3D viewer.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/showcase-artifacts-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="images/showcase-artifacts-light.png">
    <img alt="Artifacts grid with PAE heatmap, pLDDT plot, and structure viewer" src="images/showcase-artifacts-light.png" width="720" style="max-width:100%; border-radius:8px;">
  </picture>
</p>

Below the workspace, a multi-tab terminal follows your theme. It is a real shell: run Codex, Claude, OpenCode, Pi, or any other CLI in the same working UI. The CLI tab mirrors interactive `sandwalk` (`/` autocomplete; status bar shows model, specialist, sandbox, cwd, and context usage).

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/showcase-terminal-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="images/showcase-terminal-light.png">
    <img alt="CLI terminal with slash-command autocomplete" src="images/showcase-terminal-light.png" width="720" style="max-width:100%; border-radius:8px;">
  </picture>
</p>

### Sidebar

| Area | What you configure |
|------|--------------------|
| **Models** | Cloud providers and local OpenAI-compatible endpoints |
| **Tools** | Browse and enable curated tools; install more anytime |
| **Skills / MCPs** | Installs, skills.sh, GitHub import, `mcp.json` |
| **Datasets** | Local corpora (DepMap, PRISM, L1000, …) |
| **Specialists** | Skill + MCP + instruction packs |
| **Integrations** | Modal, Boltz, Fastfold Cloud, LangSmith, Tavily, Slack (one-click / Socket Mode), … |
| **Runtime** | Defaults, context, sandbox, doctor, storage, env |

Server process controls (bind, auth, logs) live in the **Sandwalk Server** menubar Settings on macOS, or via `sandwalk serve` / `sandwalk auth` on the CLI.

## Usage

```bash
sandwalk "What is known about KRAS G12C inhibitors?"
sandwalk --smiles "CCO" "Profile this compound"
sandwalk                 # interactive; /sandbox picker, /plan (starts off)
sandwalk serve           # dashboard at http://127.0.0.1:8969
```

```bash
sandwalk config show|set <key> <value>
sandwalk tool list
sandwalk skills list
sandwalk mcp list
sandwalk data list
sandwalk doctor
sandwalk --help
```

Interactive highlights: `/model`, `/sandbox` (Local / Modal presets + base image), `/plan`, `/usage`. See [`cli/README.md`](cli/README.md) and the [CLI docs](https://docs.sandwalk.ai/cli/terminal) (or `docs/content/cli/`).

Config and data live under `~/.sandwalk/` (legacy `~/.fastfold-cli/` / `~/.ct/` are copied once if present). On macOS, Sandwalk.app also stores server settings in Application Support.

## Documentation

Product docs (Fumadocs, same stack as Fastfold Cloud docs) live in [`docs/`](docs/):

```bash
pnpm install
pnpm dev:docs    # http://localhost:3001
```

Contributor / CI testing notes: [`.github/TESTING.md`](.github/TESTING.md).

## License

Apache License 2.0. Copyright © 2026 Fastfold AI Labs. See [LICENSE](LICENSE).

## Contributing / from source

Monorepo: `cli/`, `apps/local-web/` (+ Tauri in `src-tauri/`), `apps/sandwalk-mac/`, `apps/packaging/`. Day-to-day use [Get started](#-get-started); to hack on the repo see [CONTRIBUTING.md](CONTRIBUTING.md).

Prerequisites: [uv](https://docs.astral.sh/uv/), Python 3.11+, Node 20+, pnpm. For the macOS desktop build also: Xcode CLT and Rust (`rustup`).

```bash
git clone https://github.com/fastfold-ai/sandwalk.git
cd sandwalk
pnpm install
cd cli && uv sync && uv run sandwalk serve          # agent API (:8787)
# another terminal:
pnpm --filter @sandwalk/agent-local-web dev         # web UI (Vite)
# optional science stacks:
# cd cli && uv sync --extra all
```

**Packaged Mac app** (Apple Silicon, ad-hoc signed). Build, install to `~/Applications`, and open:

```bash
osascript -e 'quit app "Sandwalk"' 2>/dev/null || true
pkill -x sandwalk-desktop 2>/dev/null || true
INSTALL=1 pnpm --filter @sandwalk/agent-local-web package:dmg && open ~/Applications/Sandwalk.app
```

DMG lands at `apps/packaging/dist/Sandwalk-<version>-macos-arm64.dmg`. Details: [`apps/packaging/README.md`](apps/packaging/README.md).

**Tauri + agent server (hot reload).** Two terminals; Tauri does **not** start the API:

```bash
# Terminal 1: agent API
cd cli && uv sync && uv run sandwalk serve --host 127.0.0.1 --port 8787

# Terminal 2: Tauri desktop UI
pnpm --filter @sandwalk/agent-local-web tauri:dev
```

`uv sync` installs the CLI, Local Sandbox, and agent server. `--extra all` adds chemistry / single-cell / ML / DuckDB.

```bash
cd cli && uv run ruff check src && uv run mypy
pnpm --filter @sandwalk/agent-local-web lint:check
pnpm --filter @sandwalk/agent-local-web build

pnpm test:coverage       # Local Web UI
pnpm test:cli:coverage   # Agent CLI + Agent Server
pnpm test:mac            # Mac app (Xcode required)
```

Coverage gate is **≥80%** per component; CI uploads to [Codecov](https://app.codecov.io/gh/fastfold-ai/sandwalk). Full guide: [`.github/TESTING.md`](.github/TESTING.md). Package notes: [`apps/packaging/README.md`](apps/packaging/README.md), [`apps/local-web/DESKTOP.md`](apps/local-web/DESKTOP.md), [`apps/sandwalk-mac/README.md`](apps/sandwalk-mac/README.md), [`cli/README.md`](cli/README.md).
