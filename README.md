<p align="center">
  <a href="https://github.com/fastfold-ai/sandwalk"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/sandwalk-logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="images/sandwalk-logo-light.svg">
    <img alt="sandwalk" src="images/sandwalk-logo-light.svg" height="64" style="max-width:100%;">
  </picture></a>
</p>

<p align="center">
  <strong>An agent harness for ambitious work, on a workspace you own.</strong>
</p>

<p align="center">
  <a href="#quick-install">Quick Install</a> ·
  <a href="#getting-started">Getting Started</a> ·
  <a href="#a-look-inside">Inside Sandwalk</a> ·
  <a href="#cli--desktop-quick-reference">CLI</a> ·
  <a href="#architecture--memory">Architecture</a> ·
  <a href="#benchmarking">Benchmarking</a> ·
  <a href="https://sandwalk.sh/docs">Docs</a> ·
  <a href="https://sandwalk.sh">sandwalk.sh</a>
</p>

<p align="center">
  <a href="https://github.com/fastfold-ai/sandwalk/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/fastfold-ai/sandwalk/ci.yml?branch=main&label=CI&logo=github" alt="CI status"></a>
  <a href="https://app.codecov.io/gh/fastfold-ai/sandwalk"><img src="https://img.shields.io/codecov/c/github/fastfold-ai/sandwalk?branch=main&logo=codecov&label=coverage" alt="Codecov coverage"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License: Apache 2.0"></a>
</p>

<p align="center">
  <img alt="Sandwalk desktop: a chat, the files it produced, and a terminal, side by side" src="images/showcase.png" width="1024" style="max-width:100%; border-radius:8px;">
</p>

<p align="center">
  <sub><em>Sessions, workspace files, terminals, and parallel agents in one local-first harness.</em></sub>
</p>

**The local-first AI agent workspace and CLI built by [Fastfold AI](https://sandwalk.sh).** It is built for work that takes days or weeks, not a single prompt — combining a native macOS and Linux desktop app, a full terminal TUI, an orchestrating meta-agent (**Capy**), and a closed learning loop (`USER.md` / `MEMORY.md`, a Living Markdown Wiki, a versioned Omnigraph knowledge graph, and 1-click `SKILL.md` crystallization). Run it on your laptop, an always-on Mac mini, a remote Linux server over 1-click SSH, or on-demand Modal GPUs.

Use any model you want — 17 cloud providers (OpenAI, Anthropic, Gemini, xAI, OpenRouter, DeepSeek, Bedrock, and more), your existing **ChatGPT Plus/Pro plan**, local GGUF models via `llama.cpp` / Ollama / oMLX, or your own OpenAI-compatible endpoint. Switch models mid-session with `/models` — no subscription walls, no lock-in.

<table>
<tr><td><b>One workspace everywhere</b></td><td>Native macOS & Ubuntu desktop app, terminal TUI (<code>sandwalk</code>), Web UI, and remote windows over LAN or SSH — all sharing the same sessions, files, and memory.</td></tr>
<tr><td><b>Capy & parallel grids</b></td><td>Built-in meta-agent (<b>Capy</b>) that spawns parallel sessions, lays out <code>2×2</code> / <code>3×2</code> split grids, coordinates custom <b>Specialists</b> (<b>Otium</b>, <b>Atlas</b>, <b>Nova</b>, <b>Milo</b>, <b>Soren</b>, or your own), and drives the workspace by voice or text.</td></tr>
<tr><td><b>A closed learning loop</b></td><td>Byte-stable <code>USER.md</code> & <code>MEMORY.md</code> snapshots that preserve KV caches, FTS5 cross-session search, a Living Markdown Wiki with <code>[[wikilinks]]</code>, a Lance-backed <a href="https://www.omnigraph.dev/">Omnigraph</a> knowledge graph (6 Cookbook modes), and 1-click <code>SKILL.md</code> crystallization.</td></tr>
<tr><td><b>Scheduled automations</b></td><td>Built-in cron & interval scheduler (<code>sandwalk cron</code>) with missed-run catch-up, webhook triggers, session continuity, and <code>wake_on_change_only</code> script watchers that only invoke the LLM when output changes.</td></tr>
<tr><td><b>Runs anywhere, not just your laptop</b></td><td>1-click Remote-SSH (<code>sandwalk ssh</code>) auto-installs Sandwalk in user space on any Linux/macOS machine or cluster, starts a persistent 24/7 daemon that survives disconnects, and tunnels it back to your desktop. Plus local sandboxes and serverless Modal GPUs (<code>T4</code> to <code>H100</code>).</td></tr>
<tr><td><b>Plays well with other CLIs</b></td><td>Run <b>Claude Code</b>, <b>Codex</b>, <b>OpenCode</b>, <b>fx</b>, and <b>Hermes</b> inside Sandwalk terminals with live status badges, import their transcripts as chats, or hand any Sandwalk session directly to them.</td></tr>
<tr><td><b>Research & eval-ready</b></td><td>190+ scientific & engineering tools, interactive 3D molecular structures, 1-click publishing to <code>sandwalk.site</code>, and end-to-end harness benchmarking (<code>sandwalk eval</code>) across MMLU-Pro, LiveCodeBench, BixBench, and Bio-Capybara.</td></tr>
</table>

---

## Quick Install

### CLI + Desktop (macOS & Linux)

```bash
curl -fsSL https://sandwalk.sh/install.sh | bash
sandwalk setup      # configure providers, keys, or ChatGPT sign-in
sandwalk desktop    # install the native macOS or Ubuntu desktop app
```

### Desktop Installers

| Platform | Package |
|----------|---------|
| **macOS (Apple Silicon)** | [Download `Sandwalk-macos-arm64.dmg`](https://github.com/fastfold-ai/sandwalk/releases/latest/download/Sandwalk-macos-arm64.dmg) (macOS 12.0+) |
| **Ubuntu (amd64)** | [Download `Sandwalk_0.1.14_amd64.deb`](https://github.com/fastfold-ai/sandwalk/releases/latest/download/Sandwalk_0.1.14_amd64.deb) |
| **Ubuntu (arm64)** | [Download `Sandwalk_0.1.14_arm64.deb`](https://github.com/fastfold-ai/sandwalk/releases/latest/download/Sandwalk_0.1.14_arm64.deb) |

On Ubuntu 24.04 or 26.04, you can also install and update from the signed APT repository:

```bash
curl -fsSL https://apt.sandwalk.sh/sandwalk.gpg | sudo gpg --dearmor -o /usr/share/keyrings/sandwalk.gpg
echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/sandwalk.gpg] https://apt.sandwalk.sh stable main" | sudo tee /etc/apt/sources.list.d/sandwalk.list
sudo apt update && sudo apt install sandwalk
```

### From source

```bash
git clone https://github.com/fastfold-ai/sandwalk.git
cd sandwalk
pnpm install
cd cli && uv sync --extra all && cd ..
scripts/dev-api.sh        # agent API on :8787
scripts/dev-ui.sh         # Tauri window + Vite on :1420 (`web` for browser only)
```

---

## Getting Started

```bash
sandwalk                  # Interactive TUI — start a conversation
sandwalk "question"       # Run a one-shot prompt from the shell
sandwalk setup            # Full setup wizard (providers, keys, default model)
sandwalk login chatgpt    # Use your ChatGPT Plus/Pro plan for OpenAI models
sandwalk serve            # Start the local agent API on :8787
sandwalk cron list        # List and manage scheduled Automations
sandwalk ssh list         # Manage SSH hosts, remote commands, and tunnels
sandwalk eval             # Run benchmark suites headlessly
sandwalk doctor           # Diagnose environment and provider health
sandwalk upgrade          # Upgrade to the latest release
```

📖 **[Full documentation →](https://sandwalk.sh/docs)**

---

## Three little stories

**Cold start with a save file.** You spend a week investigating a codebase or a biological target across ten chats. Instead of starting chat #11 from zero, Sandwalk distills the durable operating rules into `MEMORY.md`, links the findings in your **Living Wiki**, maps the entities and claims into **Omnigraph**, and crystallizes the workflow into a reusable `/skill` with one click. The next agent loads the save file and starts warm.

**Remote-SSH that stays awake.** You type `user@gpu-box` in **SSH** and click **Connect**. Sandwalk logs in, installs the CLI in `~/.local/bin` (no `sudo` required), starts a persistent background server with a `crontab` watchdog, syncs your model configuration, and opens a native client window tunneled to that machine. You schedule an Automation to check your jobs every 15 minutes (`wake_on_change_only`) and close your laptop — the remote daemon keeps running 24/7.

**Four minds on one hard question.** You ask **Capy** to compare four hypotheses in parallel. Capy opens a `2×2` split grid with four Specialists on different models, runs the compute in a Modal GPU sandbox, pulls the plots and 3D structures back into the session workspace, and publishes the final interactive report to `sandwalk.site`.

---

## A look inside

<table>
<tr>
<td width="50%" valign="top">
<img src="images/welcome.png" alt="Welcome: connect locally or open a remote server" width="100%"><br>
<sub><strong>Local by default, remote in one click.</strong> Connect to this Mac or open a remote server over LAN, Tailscale, or SSH.</sub>
</td>
<td width="50%" valign="top">
<img src="images/new-agent.png" alt="An empty session with model, Plan, Skills, and sandbox" width="100%"><br>
<sub><strong>Everything starts in the composer.</strong> Model, Plan, Skills, Specialist, and Sandbox sit right on the bar.</sub>
</td>
</tr>
<tr>
<td colspan="2" valign="top">
<img src="images/capy.png" alt="Capy over a session that ran a command in a Modal sandbox" width="100%"><br>
<sub><strong>Capy orchestrates the workspace.</strong> Spawn parallel sessions, lay out a multi-agent grid, manage memories and skills, or launch evals from one meta-agent.</sub>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<img src="images/grid.png" alt="A grid of sessions on one research question" width="100%"><br>
<sub><strong>Several agents, one question.</strong> Fan the same brief across different models or Specialists in a live split grid.</sub>
</td>
<td width="50%" valign="top">
<img src="images/plan-mode.png" alt="A plan with a flowchart beside the session" width="100%"><br>
<sub><strong>Start with a plan.</strong> Draft steps and a Mermaid flowchart first, then click Build to execute.</sub>
</td>
</tr>
<tr>
<td colspan="2" valign="top">
<img src="images/specialists.png" alt="Specialists grid with + New specialist button and Otium's Profile & Priors drawer" width="100%"><br>
<sub><strong>Specialists with their own brains.</strong> Start from built-in personas (Otium, Soren, Milo, Nova, Atlas) and scientific profiles, or create your own with custom priors, model, skills, and MCPs.</sub>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<img src="images/memory.png" alt="Memory & Knowledge showing MEMORY.md operating rules, USER.md profile, and Pending Approvals" width="100%"><br>
<sub><strong>Bounded memory that never rots the prompt.</strong> Curated <code>MEMORY.md</code> rules, <code>USER.md</code> profile, and human-in-the-loop approvals.</sub>
</td>
<td width="50%" valign="top">
<img src="images/wiki.png" alt="Living Markdown Wiki in Split View with live preview, [[wikilinks]], Full Screen, and To Skill" width="100%"><br>
<sub><strong>A Living Markdown Wiki on disk.</strong> Split-view editor, clickable <code>[[wikilinks]]</code>, full-screen mode, and one-click conversion to a Skill.</sub>
</td>
</tr>
<tr>
<td colspan="2" valign="top">
<img src="images/omnigraph.png" alt="Omnigraph Knowledge Graph explorer with Cookbook modes, Supports/Contradicts edges, and branches" width="100%"><br>
<sub><strong>Versioned Knowledge Graph with Omnigraph.</strong> Six runnable Cookbook modes (01–06), supporting vs. contradicting claims, Git-style hypothesis branches, and one-click Skill crystallization.</sub>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<img src="images/automations.png" alt="Automations hub with scheduled workflows and starter templates" width="100%"><br>
<sub><strong>Always-on Automations.</strong> Schedule recurring or one-shot agent workflows (<code>every 15m</code>, <code>daily at 9am</code>, cron, or webhooks) in a fresh session or the same thread.</sub>
</td>
<td width="50%" valign="top">
<img src="images/ssh.png" alt="SSH server manager with 1-click remote auto-install and tunneling" width="100%"><br>
<sub><strong>1-Click Remote-SSH.</strong> Connect to any Linux, macOS, or GPU server over SSH — Sandwalk installs automatically in user space and keeps running 24/7 after you disconnect.</sub>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<img src="images/skills.png" alt="The composer menu with skills open" width="100%"><br>
<sub><strong>Skills ride with the message.</strong> Attach Files, Skills, MCP servers, a Specialist, or a Sandbox inline.</sub>
</td>
<td width="50%" valign="top">
<img src="images/skills-sh.png" alt="The public skills catalog ranked by installs" width="100%"><br>
<sub><strong>Install from skills.sh — or crystallize your own.</strong> Browse the public catalog ranked by installs, or turn your own Wiki and Ontology into a reusable <code>/skill</code>.</sub>
</td>
</tr>
<tr>
<td colspan="2" valign="top">
<img src="images/structures.png" alt="Ranked binder candidates and rendered structures" width="100%"><br>
<sub><strong>A design round stays in the session.</strong> Ranked candidates, rendered 3D structures, and confidence metrics side by side.</sub>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<img src="images/artifacts.png" alt="Files from a sandbox run, including a structure" width="100%"><br>
<sub><strong>The agent brings the files back.</strong> Local or cloud GPU, every artifact lands in the session workspace.</sub>
</td>
<td width="50%" valign="top">
<img src="images/sites.png" alt="A site preview beside the session that built it" width="100%"><br>
<sub><strong>A result can become a page.</strong> Preview locally, then publish to <code>sandwalk.site</code> after confirmation.</sub>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<img src="images/bench.png" alt="Eval results with a suite filter" width="100%"><br>
<sub><strong>Evals score the whole harness.</strong> Measure model, Specialist, skills, tools, and sandbox together.</sub>
</td>
<td width="50%" valign="top">
<img src="images/models.png" alt="Connected cloud providers and local models" width="100%"><br>
<sub><strong>Keys stay on the machine.</strong> 17 cloud providers, ChatGPT plan sign-in, and local GGUF models.</sub>
</td>
</tr>
<tr>
<td colspan="2" valign="top">
<img src="images/cli.png" alt="The CLI inside a terminal pane in the Mac app" width="100%"><br>
<sub><strong>The same agent runs in the terminal.</strong> Shared sessions, shared memory, shared files.</sub>
</td>
</tr>
</table>

---

## CLI & Desktop Quick Reference

Sandwalk shares the same database, workspaces, and memory between the terminal TUI (`sandwalk`) and the Desktop / Web app:

| Action | CLI / Slash Command | Desktop App |
|--------|---------------------|-------------|
| Start or switch sessions | `sandwalk`, `/new`, `/sessions`, `/resume` | **New Agent** (`⌘N`) or sidebar session list |
| Switch model & reasoning effort | `/models`, `/effort` | Composer model picker (`Fast`, `Effort`, `Model`) |
| Toggle Plan vs. Agent mode | `/plan` | `Plan` (`⇧Tab`) pill in the composer |
| Pick a Specialist persona | `/specialist` | `+` menu → **Specialist** or **Dashboard → Specialists** |
| Attach or install Skills | `/skills`, `/skills-add`, `/skills-find` | `+` menu → **Skills** or **Dashboard → Skills** |
| Manage MCP servers | `sandwalk mcp list`, `/mcps` | `+` menu → **MCP** or **Dashboard → MCPs** |
| Switch Local vs. Modal GPU sandbox | `sandwalk sandbox status`, `/sandbox` | `+` menu → **Sandbox** (`Local` / `Modal T4–H100`) |
| Schedule recurring Automations | `sandwalk cron list \| add \| run` | **Dashboard → Automations** |
| Connect to remote SSH servers | `sandwalk ssh list \| connect \| exec \| sync` | **File → New Window (Remote)…** or **Dashboard → SSH** |
| Run parallel agents on one prompt | `/agents` | Ask **Capy** or drag tabs into a `2×2` / `3×2` split grid |
| Export or check token usage | `/export`, `/notebook`, `/usage`, `/compact` | Session header export menu & usage inspector |

Full CLI reference: [`cli/README.md`](cli/README.md).

### Models & Providers

| Kind | Supported Providers |
|------|---------------------|
| **Cloud** | OpenAI, Claude (Anthropic), Gemini (Google), xAI, Kimi (Moonshot), NVIDIA, OpenCode Zen, DeepSeek, MiniMax, Mistral, Qwen Cloud, Together AI, OpenRouter, Cerebras, Groq, Fireworks AI, Amazon Bedrock |
| **ChatGPT Plan** | Sign in with a **ChatGPT Plus or Pro** subscription (`sandwalk login chatgpt` or **Dashboard → Models**) — no API key required |
| **Local & Custom** | `llama.cpp` (built-in GGUF manager), Ollama, oMLX, Unsloth, LM Studio, or any OpenAI-compatible `/v1/models` endpoint (vLLM, SGLang, TGI, LiteLLM) |

### Interoperability with Other Coding CLIs

Sandwalk reads and writes the session stores of **Claude Code**, **Codex**, **OpenCode**, **fx**, and **Hermes**:
- **Run inline**: Launch any of them from the `+` terminal tab menu (`⌘⇧T`) with live status badges.
- **Import to chat**: Right-click a terminal running an external CLI and choose **Convert to chat**, or ask Capy to import and distill its takeaways into your Wiki and Omnigraph.
- **Continue in…**: Hand any Sandwalk chat directly to Claude Code (`claude --resume`) or Codex (`codex resume`) with synthesized native history and a `.sandwalk/handoff-<id>.md` brief.

---

## Architecture & Memory

Instead of dumping raw transcripts into an ever-growing system prompt, Sandwalk freezes a **byte-stable prompt prefix** at session start (`USER.md` + `MEMORY.md` + `PRIORS.md` + Living Wiki TOC + Active Ontology) so LLM KV caches stay warm, and turns everything your agents learn into a **governed local save file** under `~/.sandwalk/`:

```mermaid
flowchart LR
    S1["Past Sessions"] --> A1["Chat Memory"]
    S2["Docs & Notes"] --> A2["Living Wiki"]
    S3["Domain Data"] --> A3["Omnigraph"]
    S4["Completed Tasks"] --> A4["Skills"]

    A1 & A2 & A3 & A4 --> Hub[("~/.sandwalk/")]
    Hub --> Next["Next Agent"]
```

| Path in `~/.sandwalk/` | Contents |
|------------------------|----------|
| `config.json` | Providers, keys, default model, sandbox & memory preferences |
| `mcp.json` | Cursor-compatible MCP server definitions (including `omnigraph` stdio MCP) |
| `skills/` | Installed & crystallized skills (`<slug>/SKILL.md` + `references/`) |
| `memory/` | `USER.md`, `MEMORY.md`, `memory.db`, `wiki/<scope>/*.md`, and `omni/<scope>/graph.omni` |
| `bin/` | Managed local binaries (`omnigraph`, `omnigraph-server`, `sandwalk-omnigraph-mcp`) |
| `workspaces/<session>/` | Per-session files: `uploads/`, `outputs/`, `plans/`, `project/` |
| `agent-server.db` | Sessions, Automations, and SSH hosts shared by the CLI and Desktop app |

Full memory & Omnigraph guide: [sandwalk.sh/docs/memory](https://sandwalk.sh/docs/memory).

---

## Benchmarking

Changing a model, a Specialist, a skill, or a memory architecture should be **measured, not guessed**. Sandwalk ships with an end-to-end evaluation harness (**Dashboard → Benchmarking** and `sandwalk eval`):

| ✅ Shipped Today | 🚧 In Active Development |
|---|---|
| **MMLU**, **MMLU-Pro**, **ARC-C**, **MBPP**, **LiveCodeBench** | **Long-Horizon Memory & Omnigraph Recall Bench** (multi-session fact retention & KV-cache efficiency across Cookbook modes `01–06`) |
| **BixBench** (bioinformatics & computational biology) & **Bio-Capybara** | **Skill Crystallization Lift Eval** (accuracy & step-count gains before vs. after crystallizing `/skill` packages) |
| Side-by-side multi-model / multi-Specialist A/B comparisons | **Multi-Specialist Grid vs. Single-Agent Ablations** |
| Per-question trajectory, tool trace, and token/cost breakdowns | **SWE-bench Verified** & **Terminal-Bench** PTY suites |

---

## Development

| Directory | Contents |
|-----------|----------|
| `cli/` | Python agent runtime, 190+ tools, built-in skills, Automations & SSH services, and FastAPI server |
| `apps/local-web/` | React dashboard and Tauri desktop shell |
| `apps/sandwalk-mac/` | Swift menubar helper that supervises the local server |
| `apps/packaging/` | Signed macOS DMG, notarization, Ubuntu `.deb` & APT publishing |

```bash
scripts/verify.sh         # typecheck, lint, build, unit tests + coverage gates (web + cli)
scripts/verify.sh e2e     # Playwright: grid, terminals, PTY round-trip
pnpm e2e:bench            # perf report → apps/local-web/e2e/results/grid-latest.json
```

Working with an AI agent? [AGENTS.md](AGENTS.md) and `.cursor/skills/` encode the dev and test loop. See [CONTRIBUTING.md](CONTRIBUTING.md), [.github/TESTING.md](.github/TESTING.md), and [apps/packaging/APPLE-SIGNING.md](apps/packaging/APPLE-SIGNING.md).

## Acknowledgments

Sandwalk builds on and draws direct inspiration from:
- **[Omnigraph (`ModernRelay/omnigraph`)](https://github.com/ModernRelay/omnigraph)** & **[omnigraph.dev](https://www.omnigraph.dev/)** — Versioned Rust + Lance graph engine, `.pg` schemas, `.gq` queries, Git-style branching, and runnable Cookbook ontologies.
- **[LangChain](https://github.com/langchain-ai/langchain)**, **[LangGraph](https://github.com/langchain-ai/langgraph)** & **[Deep Agents (`langchain-ai/deepagents`)](https://github.com/langchain-ai/deepagents)** — Core agent execution graph, streaming tool orchestration, and model adapters.
- **[Hermes Agent (`NousResearch/hermes-agent`)](https://github.com/NousResearch/hermes-agent)** — Bounded session-start `USER.md` / `MEMORY.md` snapshot architecture and SQLite FTS5 `session_search`.
- **[TencentDB Agent Memory (`TencentCloud/TencentDB-Agent-Memory`)](https://github.com/TencentCloud/TencentDB-Agent-Memory)** — Four-asset memory hub (`Chat Memory`, `Skill`, `Wiki`, `Graph`) and the "Cold Start: Load the Save File" crystallization model.
- **[skills.sh (`vercel-labs/skills`)](https://skills.sh)** — Open `SKILL.md` package specification and public agent skills catalog.
- **[llama.cpp (`ggml-org/llama.cpp`)](https://github.com/ggml-org/llama.cpp)** & **[Modal](https://modal.com)** — Local GGUF model/embedding inference and on-demand cloud CPU/GPU sandboxes.

## License

[Apache License 2.0](LICENSE). Copyright © 2026 Fastfold AI Labs.
