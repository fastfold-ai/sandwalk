# sandwalk-bench

Formal agent benchmarking package for Sandwalk.

## Dashboard Bench (primary)

In the Sandwalk app: **Dashboard → Bench** (`/dashboard/bench`).

The local agent-server exposes `/v1/bench/*` (packs, spawn, active progress, cancel, results). The UI lets you pick suites, sample sizes, a model (plus optional compare models queued sequentially), watch progress on **Results**, and download or clear scored results. You can queue more runs from **New** while one is in progress.

**Headless CLI** (no UI; uses a running `sandwalk serve` when available, otherwise in-process):

```bash
sandwalk eval suites
sandwalk eval run -s mmlu -n 5 -m deepseek/deepseek-v4-flash-0731
sandwalk eval results
```

Results are written to `~/.sandwalk/bench-runs/` and show up in Dashboard → Bench → Results.

**Suites:**

| Suite | Runner | Notes |
|-------|--------|-------|
| **MMLU** | Agent | Full corpus (14,042); Install to fetch, then sizes + Full |
| **MMLU-Pro** | Agent | Full corpus (12,032); Install to fetch, then sizes + Full |
| **ARC-C** | Agent | Full corpus (1,172); Install to fetch, then sizes + Full |
| **MBPP** | Agent | Python problems; host code-exec grading (sizes + Full) |
| **LiveCodeBench** | Agent | Competitive coding; host code-exec grading (sizes + Full) |
| **BixBench-Verified-50** | Agent | As-is upstream questions + CapsuleData; needs `HF_TOKEN` + accepted dataset terms |
| **Bio-Capybara-full** | Agent | Featured skills + MCP coverage pack (`sandwalk_skills_mcp`) |

Only 30-question **sample fixtures** for MMLU / MMLU-Pro / ARC-C are committed to
git. Until you click **Install** on the suite card, those cards offer sample sizes
up to 30 only — the larger picks appear once the full corpus is cached under
`.cache/mcq/`. Install pulls a single parquet from Hugging Face (no token needed),
falling back to the paged rows API when no parquet reader is present.

## Managing cached datasets

Suite cards show what each dataset uses on disk (`Cached · 7.2 MB · 14,042
questions`) and the Bench tab shows the cache total. **Remove** deletes a suite's
cached files to reclaim space — the card falls back to its sample fixture, so the
suite stays runnable at small sizes and can be re-installed later. Removal is
blocked while a download is in progress, and BixBench removal includes its
downloaded capsule data.

The fast single-request install needs a parquet reader:

```bash
cd cli && uv sync --extra bench   # or: pip install -e ".[bench]"
```

Without it, installs fall back to a paged Hugging Face API that gets rate-limited
on the larger corpora (MMLU needs ~141 pages), and the suite card says so.
`--extra all` already includes it.

Persisted run JSON lives under `~/.sandwalk/bench-runs/` (or `$SANDWALK_CONFIG_DIR/bench-runs/`).

The CLI below remains useful for pack authoring, dry-runs, and HF download helpers. It still talks to session APIs directly (`sandwalk-bench spawn`); the Dashboard uses the in-process `/v1/bench` queue.

**Pack coverage:**

1. **MCQ knowledge suites** — MMLU / MMLU-Pro / ARC-C sample fixtures under `fixtures/`.
2. **sandwalk-native packs** — Featured skills + MCPs (`packs/sandwalk_skills_mcp.yaml`).
3. **BixBench as-is** — full Verified-50 via `sandwalk_bench.bixbench` (Dashboard suite card + `sandwalk-bench bixbench download`).

---

## Does spawn create normal chat sessions?

**Yes.** `sandwalk-bench spawn` talks to the same local agent-server the web UI uses (`http://127.0.0.1:8787` by default). For each matrix cell it:

1. `POST /v1/projects` — create one **Project** for the batch (name + description + agent context)
2. `PATCH /v1/settings/runtime` — set OpenRouter provider + model (sequential latch; model is still process-global)
3. `POST /v1/sessions` with `projectId` — real chat sessions under that project (same as New Agent)
4. Copy fixtures into that session’s `workspacePath` (`inputs/` or `data/`)
5. `POST /v1/sessions/{id}/messages` — send the **question text** as the first user message (same as Send)

Agent-facing prompts are intentionally plain (AIME-style): the real question + a short “data is under `data/` / end with `Answer:`” cue. No “you are being benchmarked” manifesto, autonomy rules dump, skill/MCP shopping list, or model latch note. Pack YAML still holds ideals/verifiers for humans and `sandwalk-bench grade`.

In the UI: open the **Project** to browse just that batch’s chats. Session titles look like `Fold + PyMOL + RayMol ubiquitin · qwen3.7-max`. You can watch traces, interrupt, and continue chatting as usual.

**Many concurrent chats:** the UI streams tokens for the *open* chat only; background runs keep going on the agent-server and update via a fast sessions-status poll. Spawn the whole matrix — don’t throttle for browser connection limits. Machine CPU/RAM/API rate limits are the real ceiling.

`--dry-run` only prints the planned project + cells — **nothing is created**.

### Project naming

Default project name:

```text
bench · <pack-id> · <matrix> · <UTC YYYY-MM-DD HHMM>
```

Auto description includes pack version, matrix, session count, models, and question ids (human-facing project metadata only — not injected into the agent prompt).

```bash
# custom name / description
sandwalk-bench spawn sandwalk_skills_mcp.yaml full-coverage \
  --project-name "skills MCP bakeoff · luna sweep" \
  --project-description "OpenRouter favorites; Featured skills+MCPs; 2026-08-07"

# attach to an existing project instead of creating one
sandwalk-bench spawn sandwalk_skills_mcp.yaml full-coverage --project-id <uuid>

# opt out (flat sidebar, old behavior)
sandwalk-bench spawn … --no-project
```

---

## How to run the bench

### 0. Prerequisites

- Sandwalk agent-server + UI running (e.g. `sandwalk serve` / your usual desktop app).
- Models reachable (OpenRouter key in sandwalk config).
- Skills / MCPs you want to exercise **enabled** in Settings.
- API auth if enabled: `sandwalk auth show` (or `SANDWALK_API_KEY`).

### 1. Install the package

```bash
cd apps/benchmarking
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
# optional: Hugging Face helpers for full Verified-50 download
uv pip install -e ".[hf]"
```

Confirm:

```bash
sandwalk-bench packs
sandwalk-bench version
```

### 2. Preview (no sessions)

```bash
# List packs + matrices
sandwalk-bench packs

# Inspect questions
sandwalk-bench show sandwalk_skills_mcp.yaml

# Expand a matrix (question × model cells)
sandwalk-bench matrix sandwalk_skills_mcp.yaml full-coverage

# Dry-run spawn (prints titles/models/prompt sizes; creates nothing)
sandwalk-bench spawn sandwalk_skills_mcp.yaml full-coverage --dry-run
```

### 3. Spawn real chat sessions (under a Project)

With the UI/server up:

```bash
# Native skills + MCP coverage → 1 Project + 12 chats
sandwalk-bench spawn sandwalk_skills_mcp.yaml full-coverage \
  --out .runs/skills-full-$(date +%Y%m%d-%H%M%S).json
```

Optional flags:

| Flag | Meaning |
|------|---------|
| `--base-url URL` | Agent server (default `http://127.0.0.1:8787`) |
| `--api-key KEY` | Or env `SANDWALK_API_KEY`; else runs `sandwalk auth show` |
| `--dry-run` | Preview project + cells only |
| `--out path.json` | Write `{ project, sessions }` manifest |
| `--project-name` | Override auto project name |
| `--project-description` | Override auto description |
| `--project-id` | Reuse existing project |
| `--no-project` | Skip Project; create orphan sessions |

After spawn:

1. Open Sandwalk UI → select the new **Project** (pinned by default).
2. Browse only that batch’s chats; watch runs stream normally.
3. Keep the JSON manifest (`project` + `sessions[]`) for grading / comparison.

**Note:** Spawn flips the global runtime model between cells, then restores the previous model. Don’t manually change the model picker mid-spawn.

### 4. Grade a finished answer (Bix-adapted)

For packs with `ideal` + `eval_mode` (`str_verifier` / `range_verifier`):

```bash
# Put the assistant’s final text (or a file containing Answer: …) in a file
sandwalk-bench grade \
  --eval-mode range_verifier \
  --ideal '(0.07,0.08)' \
  -f /path/to/assistant_reply.txt
```

Exit code `0` = pass, `1` = fail. `llm_verifier` still needs a judge pass (todo).

### 5. BixBench-Verified-50 cache (optional / later as-is)

```bash
# Accept dataset terms on Hugging Face, then:
export HF_TOKEN=hf_...
sandwalk-bench bixbench download
sandwalk-bench bixbench info
sandwalk-bench bixbench list -n 50
```

This caches the JSONL under `.cache/` (gitignored). Dashboard Bench runs Verified-50 as agent sessions with capsule download.

---

## Which matrix should I run?

| Goal | Pack | Matrix | Sessions |
|------|------|--------|----------|
| Stress Featured skills + MCPs | `sandwalk_skills_mcp.yaml` | `full-coverage` | 12 |
| Same 12 Qs, one model | `sandwalk_skills_mcp.yaml` | `full-coverage-same-model` | 12 |
| One fold+viz Q × 5 models | `sandwalk_skills_mcp.yaml` | `B02-models` | 5 |

MCQ knowledge suites (MMLU / MMLU-Pro / ARC-C) are started from **Dashboard → Bench**, not YAML matrices.

---

## Layout

```text
apps/benchmarking/
  packs/                      # YAML question banks + matrices
  fixtures/                   # MCQ samples + sandwalk_inputs/
  fixtures/sandwalk_inputs/   # PDF / PPTX / CSV for skill tests
  src/sandwalk_bench/         # schema, loaders, spawn, verify, CLI
  .cache/                     # HF downloads (gitignored)
  .runs/                      # optional local manifests (gitignored)
```

## Schema (BixBench-aligned)

Upstream Verified-50 fields we preserve / map:

| Field | Role |
|-------|------|
| `question_id` / `id` | Stable ID |
| `question` | Upstream stem |
| `ideal` | Ground truth |
| `eval_mode` | `str_verifier` \| `range_verifier` \| `llm_verifier` |
| `distractors` | MCQ options |
| `capsule_uuid` / `data_folder` | Capsule zip |
| `categories`, `paper`, `canary`, … | Metadata in `source` |

Sandwalk extensions: `prompt` (agent-facing wrap), `skills`, `mcps`, `inputs`, `fixture_dir`, `title`.

## Adapted five (bridge)

| ID | Upstream | Fit |
|----|----------|-----|
| `BX-bix-51-q2` | BMI logistic AIC | table/stats + convert |
| `BX-bix-30-q3` | miRNA DE ratio | DE table |
| `BX-bix-18-q3` | colony area reduction | CSV imaging metrics |
| `BX-bix-41-q5` | swarming ratio | CSV imaging |
| `BX-bix-26-q3` | FeMinus pathway genes | `.rds` DE + enrichment |

Reference notebooks are **withheld** (only `CapsuleData`). Graders look for `Answer:` / `FINAL_ANSWER:` / last-line value.

## Auth / secrets

- Hugging Face: `HF_TOKEN` env only — never commit tokens.
- Agent server: `SANDWALK_API_KEY` or `sandwalk auth show`.

## Citation

BixBench: Mitchener et al., [arXiv:2503.00096](https://arxiv.org/abs/2503.00096). Dataset: [phylobio/BixBench-Verified-50](https://huggingface.co/datasets/phylobio/BixBench-Verified-50) (Apache-2.0).
