<p align="center">
  <a href="https://github.com/fastfold-ai/sandwalk"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/sandwalk-logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="images/sandwalk-logo-light.svg">
    <img alt="sandwalk" src="images/sandwalk-logo-light.svg" height="64" style="max-width:100%;">
  </picture></a>
</p>

<p align="center">
  <strong>An agent harness for ambitious work.</strong><br>
  Self-hosted. Many tools, many models, many agents at once — in one window, one terminal, one session list.
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#quickstart">Quickstart</a> ·
  <a href="#features">Features</a> ·
  <a href="#models">Models</a> ·
  <a href="#cli">CLI</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="#development">Development</a> ·
  <a href="https://sandwalk.sh">sandwalk.sh</a>
</p>

<p align="center">
  <img alt="Sandwalk desktop: a chat, the files it produced, and a terminal, side by side" src="images/showcase.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

> *Research does not fit in one chat. A real question needs a model, a few tools, some data on disk, a GPU for an hour, and often more than one agent pulling on different threads at once. Every harness I tried gave me one of those and made me stitch the rest together by hand.*
>
> *Sandwalk is the harness with all of it already wired. Skills, MCP servers, local and cloud models, a sandbox on your Mac or on Modal, a grid of agents working side by side, and a place to turn the result into a page you can send someone. It runs on your own compute, and the CLI, the Mac app, and a remote server all share the same sessions.*

## Install

### macOS App

Download the `.dmg` from [Releases](https://github.com/fastfold-ai/sandwalk/releases/latest/download/Sandwalk-macos-arm64.dmg), drag Sandwalk to Applications, open it. The disk is signed with a Developer ID certificate. The app bundles the agent server, a Python runtime, and the dashboard, so nothing else needs to be installed. Updates arrive in-app.

Requires macOS 12.0+ and Apple Silicon.

### CLI

```bash
curl -fsSL https://sandwalk.sh/install | bash
sandwalk setup
```

The installer puts `sandwalk` on your `PATH` with `uv`. `sandwalk setup` walks through providers, keys, and a default model. Upgrade later with `sandwalk upgrade`.

### From source

```bash
git clone https://github.com/fastfold-ai/sandwalk.git
cd sandwalk
pnpm install
cd cli && uv sync --extra all && cd ..
scripts/dev-api.sh        # agent API on :8787
scripts/dev-ui.sh         # Tauri window + Vite on :1420 (`web` for browser only)
```

See [Development](#development) for the test and packaging loop.

## Quickstart

### macOS App

The first window asks where the agent runs. **Connect locally** uses this Mac. **Open remote** finds a Sandwalk server on the LAN or takes a pasted URL and API key. Under that, Recent lists every server you have opened — a MacBook, a Mac mini at `192.168.2.178`, a Linux box called `ai-server` — so getting back onto a machine is one click.

<p align="center">
  <img alt="Welcome window: Connect locally, Open remote, and a list of recent servers" src="images/welcome.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

A new agent is one composer on an empty pane. The project scope is above it, the model is in the bar, and three chips wait underneath: **Plan** (Shift-Tab), **Skills**, and **Run in sandbox**. Type a question and send. The pane fills with the transcript; files the agent writes open beside it.

<p align="center">
  <img alt="New agent: an empty pane with the composer, model picker, and Plan, Skills, and sandbox chips" src="images/new-agent.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

### CLI

```bash
sandwalk                                            # interactive session
sandwalk "What is known about KRAS G12C inhibitors?" # one question, then exit
sandwalk serve                                      # the API the Mac app and remote clients talk to
```

Sessions started in the terminal show up in the Mac app, and the other way round. Both read `~/.sandwalk/`.

## Features

### Capy

Capy is a meta agent that floats over whatever you are doing. It does not take a sidebar row. Open it from the bottom of the sidebar or press **Ctrl + Ctrl**. It can start chats, lay them out in a grid, run Doctor, start a Bench suite, and read the last results, all while the session behind it keeps going.

In this shot the chat underneath has just run `nvidia-smi` in a Modal sandbox and printed a Tesla T4 table. Capy sits on top with its own model and four starter prompts.

<p align="center">
  <img alt="Capy panel floating over a chat that ran nvidia-smi in a Modal sandbox" src="images/capy.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

### Grid

A group is a real grid of sessions, not a stack of tabs. Split the focused pane with **⌘D** (right) or **⇧⌘D** (down), or ask Capy to build the layout for you.

Here Capy was told to start a 4×2 grid on the latest in protein design. The panel on the right shows the `capy.spawn_sessions` call and its reply: eight worker chats, four across by two down, each seeded with the same brief. Every cell is a full session with its own stream, model, and composer. One is still searching while the others are already summarizing RFdiffusion, AlphaFold 3, and the validation bottleneck.

<p align="center">
  <img alt="Capy spawned a 4 by 2 grid of chats, each researching protein design" src="images/grid.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

### Plan mode

With the gold **Plan** chip on, the agent writes a plan before it touches anything. The plan is a markdown file under `plans/` with the steps and a Mermaid flowchart, and it opens in the file pane next to the chat. **Build** turns it into a run.

The user asked for a small-molecule screening campaign in Boltz. The left side shows the plan card, a to-do, and the agent asking which target and library to use. The right side is `boltz_screening_campaign.md` with the step list and the flowchart from User Query down to Done.

<p align="center">
  <img alt="Plan mode: a Boltz screening plan on the left, its markdown and Mermaid flowchart on the right with a Build button" src="images/plan-mode.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

### Skills and MCP

Skills are instructions and scripts the agent loads on demand; MCP servers are tools it can call. The **+** button on the composer is one menu for everything a turn can use. The top rows switch between **Agent** and **Plan**. Below that: Files, Skills, MCP, Specialist, Sandbox. Pick a skill and it rides along with the message.

A **specialist** is a saved profile that pins a set of skills, MCP servers, and extra instructions for one kind of session, such as a genomics analyst or a structure-prediction profile.

<p align="center">
  <img alt="The plus menu with Skills selected and the installed skills flyout open" src="images/skills.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

Dashboard → Skills is the manager. Flip the **Skills.sh** toggle and the page becomes the public [skills.sh](https://skills.sh) leaderboard: 1.3 million installs, ranked All Time, Trending (24h), or Hot. Each row is a skill, its source repo, and an install count. **Add skill** installs from there, from any GitHub repo, or from a local path.

The catalog search authenticates through Vercel. Dashboard → Integrations → **Vercel** → **Add** opens a setup terminal in `~/.sandwalk/vercel-integration` and runs `vercel login`, `vercel link`, and `vercel env pull`. That saves `VERCEL_OIDC_TOKEN`, the toggle lights up, and the leaderboard loads. The dropdown next to Add takes a pasted token instead.

<p align="center">
  <img alt="Skills manager with the Skills.sh toggle on, showing the public leaderboard ranked by installs" src="images/skills-sh.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

MCP config is `~/.sandwalk/mcp.json`, the same shape Cursor uses. Dashboard → MCPs lists installed servers, their tool counts, and a **Connect** button for the ones that need a key.

### Sandbox

Code the agent runs goes through a sandbox. **Local Sandbox** is this machine. **Modal Sandbox** is a fresh container on Modal with CPU presets (2·8, 4·16, …) or GPU presets (T4, L4, A10, A100, H100). Pick it from the **Run in sandbox** chip, the **+** menu, or `/sandbox` in the CLI, and edit the base image inline if the default is not what you need. Files the sandbox produces land in the session workspace either way.

### Artifacts

Every session has a workspace on disk, and **Artifacts** is the view of it. Anything the agent produces lands there — whether it ran locally, in the local sandbox, or on a Modal GPU — and comes back to the same folder. Files are grouped by origin: **Your uploads**, **Generated outputs**, **Project folder**, and whatever a tool wrote. CIF and PDB render in 3D. CSV, YAML, PPTX, and PDF show a preview card. The workspace path is printed at the bottom so you can open it in Finder or a terminal.

Here the agent ran a binder design on Modal. The chat on the left is its Go/No-Go assessment with iPTM, pTM, and PAE. The Artifacts pane on the right holds what the run produced: `workflow.yml`, `gfp_binder.yaml`, a rendered `1ema.cif`, a PowerPoint overview, and a CSV of lysozyme variants.

<p align="center">
  <img alt="Artifacts pane listing the files a sandbox binder run produced, including a rendered CIF structure" src="images/artifacts.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

### Structures

Structure files are first-class artifacts. A BoltzGen GFP binder run: the chat ranks the designed sequences, links each candidate to its structure, and gives a Go/no-go — the workflow completed, but interface confidence is too weak for immediate biological interpretation. On the right the Artifacts pane renders `rank1_2.cif` and `rank2_0.cif` in 3D next to the metrics CSVs and a results overview PDF.

<p align="center">
  <img alt="BoltzGen binder chat with ranked candidates, and two rendered CIF structures in the Artifacts pane" src="images/structures.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

### Sites

Sites turns a result into a page you can send someone. Ask for a report, a dashboard, or a landing page and the agent uses the built-in `sites-building` skill: a static site from a report shell with charts, math, Mermaid, and a theme toggle already wired in. It builds a clean `dist/`, validates it, and previews it in the right pane. When you are happy, `sites-hosting` packages that exact output and publishes it to `https://<slug>.sandwalk.site`. **Sites** in the sidebar lists everything you have built, published or not.

The user asked, through the Paperclip MCP, which open-weight model is most referenced in arXiv methods sections since 2024, with a top-five line plot. The left side is the chat: tool calls, the Result, a proxy-count table. The right side is the published site — the **Published** badge and URL are in its header — with the monthly chart for Qwen, Llama, Gemma, GLM, and DeepSeek and a family comparison below. That page is live.

<p align="center">
  <img alt="A published Sandwalk Site beside the chat that produced it, showing a model trends line chart" src="images/sites.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

### Benchmarking

Bench runs question suites through real agent sessions, so a score reflects the whole harness and not just the model. Pick a suite, a model, and an optional specialist; set the sample size and how many runs go out in parallel. Suites in the box: MMLU, MMLU-Pro, ARC-C, MBPP, LiveCodeBench, BixBench-Verified-50, and Bio-Capybara-full. Results list every run with its score, duration, correct count, provider, token use, and date. **Compare** puts two runs side by side. Runs stay off the chat list. From the terminal: `sandwalk eval`.

<p align="center">
  <img alt="Benchmarking results table with the suite filter open" src="images/bench.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

### Overview

Dashboard Overview is the usage board. Lifetime tokens at the top, cards for the longest agent run, chat count, and streaks, an activity heatmap by day, and a 30-day chart of which models you actually ran. **Add widget** rearranges the board. Project Home has the same board scoped to one project.

<p align="center">
  <img alt="Dashboard overview: lifetime tokens, streak cards, an activity heatmap, and a models chart" src="images/overview.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

### Remote sessions

Run `sandwalk serve` on a Mac mini or a cluster node and open it from your laptop. The Mac app and the CLI both take a URL and an API key. The session list you see is the one on that server, so a long run keeps going after you close the lid. `sandwalk auth` manages the key.

### Science toolkit

Live databases are tools the agent can call: PubChem, ChEMBL, UniProt, PDB, Open Targets, ClinicalTrials.gov, and others. Optional local corpora install with `sandwalk data pull-all` (DepMap, MSigDB, STRING). `sandwalk tool list` shows what is loaded. The toolkit is a starting point, not the ceiling; skills and MCP servers extend it to any domain.

## Models

Dashboard → Models lists every provider in a grid with a Connected or Not set up badge. Keys stay on this computer. Connected providers show up in the composer picker; the composer shows the model, effort, and how much of the context window the turn is using.

<p align="center">
  <img alt="Models settings: cloud providers with Connected badges and local endpoints below" src="images/models.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

| Kind | Providers |
|------|-----------|
| Cloud | OpenAI, Claude (Anthropic), Gemini (Google), xAI, Kimi (Moonshot), NVIDIA, OpenCode Zen, DeepSeek, MiniMax, Mistral, Qwen Cloud, Together AI, OpenRouter, Cerebras, Groq, Fireworks AI, Amazon Bedrock |
| Local | Ollama, oMLX, Unsloth, DS4, llama.cpp, LM Studio, any OpenAI-compatible endpoint |

Local endpoints are discovered from `/v1/models` or Ollama's `/api/tags`. Add one with **Add Local LLM**, or in the CLI with `/model-manager`.

## CLI

`sandwalk` is the same agent in a terminal. Run it two ways:

- **Standalone.** Open Terminal, iTerm, Warp, or whatever you use, and type `sandwalk`. The first screenshot is that: Warp, a fresh session, GPT-6 Astra on OpenAI, 192 tools and 307 skills loaded.
- **Inside the app.** Press **⌘⇧T** or pick **Terminal** on a blank pane and a terminal opens in the grid next to your chats. Type `sandwalk` there and it is the same session list, the same `~/.sandwalk/`, the same artifacts. The second screenshot is that: the terminal is a pane in Sandwalk, with the sidebar and the other tabs around it.

Either way, typing `/` opens the command list. `/help` shows the full reference with examples. The status line at the bottom reports the mode, model, provider, sandbox, and context use.

<p align="center">
  <img alt="Sandwalk CLI in a standalone terminal with the slash command list open" src="images/cli-terminal.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

<p align="center">
  <img alt="Sandwalk CLI inside a terminal pane in the Mac app" src="images/cli.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

### Commands

```bash
sandwalk setup                    # providers, keys, default model
sandwalk                          # interactive session
sandwalk "question"               # one-shot
sandwalk serve                    # local agent API on :8787
sandwalk serve --host 0.0.0.0     # expose to the LAN (needs sandwalk auth)
sandwalk auth                     # manage the API key for serve
sandwalk doctor                   # environment and configuration checks
sandwalk eval                     # run Bench suites headlessly
sandwalk skills add fastfold-ai/skills
sandwalk mcp list
sandwalk sandbox status           # Local Sandbox or Modal Sandbox
sandwalk data pull-all            # DepMap, MSigDB, STRING
sandwalk tool list
sandwalk upgrade
```

### Slash commands

| Command | What it does |
|---------|--------------|
| `/models`, `/effort` | Switch the model; set Low / Medium / High / Fast for models with thinking controls |
| `/plan` | Toggle Plan mode. Writes `plans/*.md` until you switch back to Agent |
| `/sandbox` | Pick Local or a Modal CPU/GPU preset; edit the base image inline |
| `/specialist` | Use, clear, or list specialists |
| `/skills`, `/skills-add`, `/skills-find` | Loaded skills; install from GitHub or a path; search the catalog |
| `/mcps` | Connect, enable, validate, add, or remove MCP servers |
| `/tools`, `/data` | Tool status; local datasets |
| `/usage`, `/compact` | Token and cost for the session; compress context |
| `/sessions`, `/resume`, `/new` | List, resume, or start sessions |
| `/export`, `/notebook` | Transcript to markdown; session to `.ipynb` |
| `/agents` | Run a question across N parallel agents |
| `/doctor` | Readiness diagnostics with fix hints |

`Enter` submits, `Ctrl+J` inserts a newline, paste an image to attach it, `Ctrl+C` interrupts. Full reference: [`cli/README.md`](cli/README.md).

## Configuration

Everything lives under `~/.sandwalk/`:

| Path | Contents |
|------|----------|
| `config.json` | Providers, keys, default model, sandbox preferences |
| `mcp.json` | MCP servers, Cursor-compatible |
| `skills/` | Installed skills |
| `workspaces/<session>/` | Per-session artifacts: `uploads/`, `outputs/`, `plans/`, `project/` |
| `data/` | Local datasets from `sandwalk data pull` |
| `agent-server.db` | Sessions, shared by the CLI and the app |

The Mac app stores its own window and server settings in `~/Library/Application Support/Sandwalk/`. `sandwalk config show` prints the active configuration; `sandwalk config set <key> <value>` changes one key.

Provider keys can also come from the environment (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `MOONSHOT_API_KEY`, and so on). Modal needs `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET`, or run `modal setup`.

## Development

Monorepo:

| Directory | Contents |
|-----------|----------|
| `cli/` | Python agent, tools, skills, and the FastAPI server |
| `apps/local-web/` | React dashboard and the Tauri shell |
| `apps/sandwalk-mac/` | Swift menubar helper that supervises the server |
| `apps/packaging/` | Signed DMG, notarization, updater artifacts |
| `docs/` | Product docs site (`pnpm dev:docs`) |

```bash
scripts/verify.sh         # typecheck, lint, build, unit tests + coverage gates (web + cli) — the CI gate
scripts/verify.sh e2e     # Playwright: grid, terminals, PTY round-trip
pnpm e2e:bench            # perf report → apps/local-web/e2e/results/grid-latest.json
./apps/packaging/package-macos-dmg.sh    # signed DMG; INSTALL=1 copies it to ~/Applications
```

Working with an AI agent? [AGENTS.md](AGENTS.md) and the project skills in `.cursor/skills/` encode the dev and test loop. See [CONTRIBUTING.md](CONTRIBUTING.md), [.github/TESTING.md](.github/TESTING.md), and [apps/packaging/APPLE-SIGNING.md](apps/packaging/APPLE-SIGNING.md).

## License

[Apache License 2.0](LICENSE). Copyright © 2026 Fastfold AI Labs.
