<p align="center">
  <a href="https://github.com/fastfold-ai/sandwalk"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/sandwalk-logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="images/sandwalk-logo-light.svg">
    <img alt="sandwalk" src="images/sandwalk-logo-light.svg" height="64" style="max-width:100%;">
  </picture></a>
</p>

<p align="center">
  <strong>A workspace where humans and agents do real work, on a machine you own.</strong>
</p>

<p align="center">
  <a href="#what-is-this-really">What it is</a> ·
  <a href="#stuff-you-do-in-sandwalk">What you do</a> ·
  <a href="#a-look-inside">Inside</a> ·
  <a href="#getting-started">Install</a> ·
  <a href="#cli">CLI</a> ·
  <a href="#how-memory-works">Memory</a> ·
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
  <sub><em>A chat, the files it produced, and a terminal, side by side.</em></sub>
</p>

---

## What is this, really?

Sandwalk is a local-first workspace and CLI for running AI agents on work that takes days, not a single prompt.

Most agent tools trap you in one model vendor's chat box and forget everything the moment you close the tab. When you start a new thread on Monday, you explain your codebase, your cluster, and your preferences all over again.

In Sandwalk, the server runs on your machine (or a remote Linux box you SSH into) and keeps everything in plain files under `~/.sandwalk/`. The desktop app, the web UI, and the `sandwalk` terminal CLI all talk to the same local server, share the same sessions, and read the same workspace on disk.

In practice it feels like a clean desktop app and terminal. Under the hood it is a Python agent server, a Tauri shell, a Rust graph engine, and a quiet refusal to pay $200/month for a wrapper around your own API keys.

Yes, it is another agent tool. The difference is what stays behind after a session ends: a curated memory file that does not bust your prompt cache, a Markdown wiki on disk, a local knowledge graph with provenance, and reusable `SKILL.md` files that make the next agent faster than the last one.

---

## Stuff you do in Sandwalk

- **Put four models on the same problem and see who is bluffing.** Ask **Capy** (the built-in meta-agent) to fan a question across a `2×2` grid of different models or Specialists. Watch them work side by side instead of tab-switching between four browser windows.
- **Connect to a remote Linux box or GPU cluster in one click.** Paste `user@host` into **SSH**. Sandwalk logs in, installs itself in `~/.local/bin` without `sudo`, starts a background daemon that survives disconnects, and opens a window tunneled to that machine.
- **Leave an agent watching a job while you sleep.** Schedule an Automation (`every 15m`, `daily at 9am`, or cron) that runs a check on your machine or over SSH and only wakes the LLM when the output actually changes.
- **Keep using Claude Code, Codex, OpenCode, or Hermes.** Run them inside Sandwalk terminals with live status badges, convert their transcripts into Sandwalk chats, or hand a Sandwalk chat directly into `claude --resume` or `codex resume`.
- **Stop re-explaining your project to every new chat.** Distill finished sessions into your **Living Wiki** and **Omnigraph**, then click **Create Skill** to package the workflow into `~/.sandwalk/skills/<slug>/SKILL.md`.
- **Run compute where the GPUs are.** Execute code locally or spin up a Modal container (`T4`, `L4`, `A10`, `A100`, `H100`) per session. Every plot, 3D molecular structure, or notebook comes back to your local folder, ready to publish to `sandwalk.site`.

---

## A look inside

<table>
<tr>
<td width="50%" valign="top">
<img src="images/welcome.png" alt="Welcome: connect locally or open a remote server" width="100%"><br>
<sub><strong>Runs locally by default.</strong> Or opens a remote server on your LAN, Tailnet, or over SSH.</sub>
</td>
<td width="50%" valign="top">
<img src="images/new-agent.png" alt="An empty session with model, Plan, Skills, and sandbox" width="100%"><br>
<sub><strong>The composer is where a session starts.</strong> Model, Plan, Skills, Specialist, and Sandbox sit right on the bar.</sub>
</td>
</tr>
<tr>
<td colspan="2" valign="top">
<img src="images/capy.png" alt="Capy over a session that ran a command in a Modal sandbox" width="100%"><br>
<sub><strong>Capy runs the workspace.</strong> Spawn parallel sessions, lay out a split grid, manage memory and skills, or kick off benchmarks by voice or text.</sub>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<img src="images/grid.png" alt="A grid of sessions on one research question" width="100%"><br>
<sub><strong>Several agents, one question.</strong> Same brief across different models or Specialists in a live split grid.</sub>
</td>
<td width="50%" valign="top">
<img src="images/plan-mode.png" alt="A plan with a flowchart beside the session" width="100%"><br>
<sub><strong>Start with a plan.</strong> Draft steps and a flowchart first, then click Build to execute.</sub>
</td>
</tr>
<tr>
<td colspan="2" valign="top">
<img src="images/specialists.png" alt="Specialists grid with + New specialist button and Otium's Profile & Priors drawer" width="100%"><br>
<sub><strong>Specialists with their own priors.</strong> Start from built-in personas (Otium, Soren, Milo, Nova, Atlas) and scientific profiles, or build your own with custom instructions, model, skills, and MCPs.</sub>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<img src="images/memory.png" alt="Memory & Knowledge showing MEMORY.md operating rules, USER.md profile, and Pending Approvals" width="100%"><br>
<sub><strong>Bounded memory that does not rot the prompt.</strong> Curated <code>MEMORY.md</code> rules, <code>USER.md</code> profile, and human review before anything sticks.</sub>
</td>
<td width="50%" valign="top">
<img src="images/wiki.png" alt="Living Markdown Wiki in Split View with live preview, [[wikilinks]], Full Screen, and To Skill" width="100%"><br>
<sub><strong>A Markdown wiki on disk.</strong> Split-view editor, clickable <code>[[wikilinks]]</code>, full-screen mode, and one-click export to a Skill.</sub>
</td>
</tr>
<tr>
<td colspan="2" valign="top">
<img src="images/omnigraph.png" alt="Omnigraph Knowledge Graph explorer with Cookbook modes, Supports/Contradicts edges, and branches" width="100%"><br>
<sub><strong>Versioned knowledge graph with Omnigraph.</strong> Six runnable Cookbook modes (01 to 06), supporting vs. contradicting claims, Git-style branches, and one-click Skill creation.</sub>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<img src="images/automations.png" alt="Automations hub with scheduled workflows and starter templates" width="100%"><br>
<sub><strong>Scheduled Automations.</strong> Run recurring or one-shot jobs (<code>every 15m</code>, <code>daily at 9am</code>, cron, or webhooks) in a fresh chat or the same thread.</sub>
</td>
<td width="50%" valign="top">
<img src="images/ssh.png" alt="SSH server manager with 1-click remote auto-install and tunneling" width="100%"><br>
<sub><strong>1-click Remote-SSH.</strong> Connect to any Linux or macOS server over SSH. Sandwalk installs in user space and keeps running after you close your laptop.</sub>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<img src="images/skills.png" alt="The composer menu with skills open" width="100%"><br>
<sub><strong>Skills ride with the message.</strong> Attach Files, Skills, MCP servers, a Specialist, or a Sandbox inline.</sub>
</td>
<td width="50%" valign="top">
<img src="images/skills-sh.png" alt="The public skills catalog ranked by installs" width="100%"><br>
<sub><strong>Install from skills.sh or write your own.</strong> Browse the public catalog ranked by installs, or turn your own Wiki and graph into a reusable <code>/skill</code>.</sub>
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
<sub><strong>The agent brings the files back.</strong> Local or cloud GPU, every output lands in the session folder.</sub>
</td>
<td width="50%" valign="top">
<img src="images/sites.png" alt="A site preview beside the session that built it" width="100%"><br>
<sub><strong>A result can become a page.</strong> Preview locally, then publish to <code>sandwalk.site</code> when you are ready.</sub>
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

## Three little stories

**Cold start with a save file.** You spend a week debugging a gnarly service or investigating a biological target across ten chats. Instead of starting chat #11 from zero, Sandwalk distills the durable lessons into `MEMORY.md`, links the notes in your **Living Wiki**, records the claims in **Omnigraph**, and turns the whole setup into a `/skill` with one click. The next agent loads the save file and gets straight to work.

**Remote-SSH that stays awake.** You type `user@gpu-box` in **SSH** and click **Connect**. Sandwalk logs in, installs the CLI in `~/.local/bin`, starts a persistent background server with a `crontab` watchdog, copies over your model config, and opens a native window tunneled to that machine. You set an Automation to check your Slurm queue every 15 minutes and close your laptop. The remote server keeps working.

**Four minds on one question.** You ask **Capy** to test four hypotheses at once. Capy opens a `2×2` grid with four Specialists on different models, runs the heavy compute on a Modal GPU, drops the plots and 3D structures into your workspace, and publishes the write-up to `sandwalk.site`.

---

## How memory works

Dumping old transcripts into a vector database or a giant system prompt is a great way to ruin both reasoning quality and your LLM prompt cache.

Sandwalk freezes a small, byte-stable snapshot at the start of a session (`USER.md`, `MEMORY.md`, `PRIORS.md`, the Wiki table of contents, and the active graph schema) so KV caches stay warm across turns. Deeper context lives on disk under `~/.sandwalk/` and is pulled only when the agent asks for it:

```mermaid
flowchart LR
    S1["Past Sessions"] --> A1["Chat Memory"]
    S2["Docs & Notes"] --> A2["Living Wiki"]
    S3["Domain Data"] --> A3["Omnigraph"]
    S4["Completed Tasks"] --> A4["Skills"]

    A1 & A2 & A3 & A4 --> Hub[("~/.sandwalk/")]
    Hub --> Next["Next Agent"]
```

Full walkthrough: [sandwalk.sh/docs/memory](https://sandwalk.sh/docs/memory).

---

## Works today · Being wired up

| ✅ Works today | 🚧 Being wired up |
|---|---|
| macOS & Ubuntu desktop app (Tauri + React) + terminal TUI (`sandwalk`) | Long-horizon memory & Omnigraph recall benchmark suite |
| 17 cloud providers, **Sign in with ChatGPT** (Plus/Pro), and local GGUF (`llama.cpp`, Ollama, oMLX) | Skill crystallization lift evals (measuring accuracy before vs. after packaging a `/skill`) |
| **Capy** meta-agent, `2×2` / `3×2` split grids, and customizable **Specialists** | Multi-Specialist grid vs. single-agent ablations |
| Bounded `USER.md` / `MEMORY.md`, **Living Wiki**, and **Omnigraph** (6 Cookbook modes) | SWE-bench Verified & Terminal-Bench PTY evaluation suites |
| **Automations** (`sandwalk cron`: intervals, cron, webhooks, `wake_on_change_only`) | |
| **1-click Remote-SSH** (`sandwalk ssh`: auto-install, persistent daemon, local tunnel, `rsync`) | |
| Local sandboxes, Modal cloud GPUs (`T4` to `H100`), 190+ scientific tools, and `sandwalk eval` | |
| Live terminal interchange with **Claude Code**, **Codex**, **OpenCode**, **fx**, and **Hermes** | |

---

## Getting started

Pick the path that matches how you work.

### I just want the desktop app

Grab an installer from the [latest release](https://github.com/fastfold-ai/sandwalk/releases/latest):

| Platform | File |
|---|---|
| macOS (Apple Silicon, 12.0+) | [Sandwalk-macos-arm64.dmg](https://github.com/fastfold-ai/sandwalk/releases/latest/download/Sandwalk-macos-arm64.dmg) |
| Ubuntu (amd64) | [Sandwalk_0.1.14_amd64.deb](https://github.com/fastfold-ai/sandwalk/releases/latest/download/Sandwalk_0.1.14_amd64.deb) |
| Ubuntu (arm64) | [Sandwalk_0.1.14_arm64.deb](https://github.com/fastfold-ai/sandwalk/releases/latest/download/Sandwalk_0.1.14_arm64.deb) |

On Ubuntu 24.04 or 26.04, you can also install from the signed APT repo:

```bash
curl -fsSL https://apt.sandwalk.sh/sandwalk.gpg | sudo gpg --dearmor -o /usr/share/keyrings/sandwalk.gpg
echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/sandwalk.gpg] https://apt.sandwalk.sh stable main" | sudo tee /etc/apt/sources.list.d/sandwalk.list
sudo apt update && sudo apt install sandwalk
```

### I want the CLI (and optionally the desktop app)

```bash
curl -fsSL https://sandwalk.sh/install.sh | bash
sandwalk setup      # providers, keys, or ChatGPT Plus/Pro sign-in
sandwalk desktop    # downloads and installs the desktop app for your OS
```

### I want to run from source

```bash
git clone https://github.com/fastfold-ai/sandwalk.git
cd sandwalk
pnpm install
cd cli && uv sync --extra all && cd ..
scripts/dev-api.sh        # agent API on :8787
scripts/dev-ui.sh         # Tauri window + Vite on :1420 (`web` for browser only)
```

---

## CLI

Type `sandwalk` in any terminal, or press **⌘⇧T** inside the app.

```bash
sandwalk                          # interactive TUI session
sandwalk "question"               # one-shot prompt
sandwalk setup                    # configure providers, keys, and default model
sandwalk login chatgpt            # use a ChatGPT Plus/Pro plan for OpenAI models
sandwalk serve                    # run the local agent API on :8787
sandwalk cron list                # list and trigger scheduled Automations
sandwalk ssh list                 # manage SSH hosts, remote commands, and tunnels
sandwalk skills add fastfold-ai/skills
sandwalk mcp list
sandwalk sandbox status           # Local or Modal GPU sandbox
sandwalk eval                     # run benchmark suites (MMLU-Pro, LiveCodeBench, BixBench)
sandwalk doctor                   # check environment and provider health
sandwalk upgrade
```

Inside an interactive session, `/` opens the command menu (`/models`, `/effort`, `/plan`, `/specialist`, `/skills`, `/mcps`, `/sandbox`, `/agents`, `/compact`, `/export`). Full CLI docs: [`cli/README.md`](cli/README.md).

---

## Where things live (`~/.sandwalk/`)

| Path | What is inside |
|------|----------------|
| `config.json` | Providers, API keys, active model, sandbox and memory settings |
| `mcp.json` | MCP servers (Cursor-compatible, including the local `omnigraph` server) |
| `skills/` | Installed and user-created skills (`<slug>/SKILL.md` + `references/`) |
| `memory/` | `USER.md`, `MEMORY.md`, `memory.db`, `wiki/<scope>/*.md`, and `omni/<scope>/graph.omni` |
| `bin/` | Managed local binaries (`omnigraph`, `omnigraph-server`, `sandwalk-omnigraph-mcp`) |
| `workspaces/<session>/` | Per-session files: `uploads/`, `outputs/`, `plans/`, `project/` |
| `agent-server.db` | Sessions, Automations, and SSH hosts shared by the CLI and desktop app |

---

## Development

| Directory | Contents |
|-----------|----------|
| `cli/` | Python agent, 190+ tools, built-in skills, Automations & SSH services, FastAPI server |
| `apps/local-web/` | React dashboard and Tauri desktop shell |
| `apps/sandwalk-mac/` | Swift menubar helper that supervises the local server |
| `apps/packaging/` | Signed macOS DMG, notarization, Ubuntu `.deb` & APT scripts |

```bash
scripts/verify.sh         # typecheck, lint, build, unit tests + coverage gates (web + cli)
scripts/verify.sh e2e     # Playwright: grid, terminals, PTY round-trip
pnpm e2e:bench            # perf report -> apps/local-web/e2e/results/grid-latest.json
```

See [AGENTS.md](AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md), [.github/TESTING.md](.github/TESTING.md), and [apps/packaging/APPLE-SIGNING.md](apps/packaging/APPLE-SIGNING.md).

## Acknowledgments

Sandwalk builds on and draws inspiration from:
- **[Omnigraph (`ModernRelay/omnigraph`)](https://github.com/ModernRelay/omnigraph)** & **[omnigraph.dev](https://www.omnigraph.dev/)**: Versioned Rust + Lance graph engine, `.pg` schemas, `.gq` queries, Git-style branching, and Cookbook ontologies.
- **[LangChain](https://github.com/langchain-ai/langchain)**, **[LangGraph](https://github.com/langchain-ai/langgraph)** & **[Deep Agents (`langchain-ai/deepagents`)](https://github.com/langchain-ai/deepagents)**: Core agent execution graph, streaming tool orchestration, and model adapters.
- **[Hermes Agent (`NousResearch/hermes-agent`)](https://github.com/NousResearch/hermes-agent)**: Bounded session-start `USER.md` / `MEMORY.md` snapshot design and SQLite FTS5 `session_search`.
- **[TencentDB Agent Memory (`TencentCloud/TencentDB-Agent-Memory`)](https://github.com/TencentCloud/TencentDB-Agent-Memory)**: Four-asset memory hub (`Chat Memory`, `Skill`, `Wiki`, `Graph`) and the save-file skill model.
- **[skills.sh (`vercel-labs/skills`)](https://skills.sh)**: Open `SKILL.md` specification and public skills catalog.
- **[llama.cpp (`ggml-org/llama.cpp`)](https://github.com/ggml-org/llama.cpp)** & **[Modal](https://modal.com)**: Local GGUF inference and on-demand cloud CPU/GPU sandboxes.

## License

[Apache License 2.0](LICENSE). Copyright © 2026 Fastfold AI Labs.
