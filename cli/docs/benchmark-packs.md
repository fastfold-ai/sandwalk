# Benchmark packs — align the sandwalk suite

Catalog of external biology / bioinformatics agent benchmarks we should support, how each is structured, and a **common internal schema** so `sandwalk bench` (and session bakeoffs) can load any pack the same way.

Related ops doc: [agent-session-benchmarking.md](./agent-session-benchmarking.md) (spawn sessions × models). Existing CLI entrypoint: `sandwalk bench` (currently BixBench-50-oriented; runner expected via `bench.runner.BenchRunner` + a local `manifest.json`).

---

## Priority packs (include first)

### 1. BixBench-Verified-50 (Phylo)

| | |
|---|---|
| **HF** | [phylobio/BixBench-Verified-50](https://huggingface.co/datasets/phylobio/BixBench-Verified-50) |
| **Also** | Full/revised upstream: [futurehouse/BixBench](https://huggingface.co/datasets/futurehouse/BixBench) (v1.5 ≈ 205 Qs); paper [arXiv:2503.00096](https://arxiv.org/abs/2503.00096); harness [Future-House/BixBench](https://github.com/Future-House/BixBench) |
| **Size** | 50 questions, 33 data capsules (~2.8 GB with zips) |
| **What it tests** | Open-ended computational biology analysis on real notebook-derived capsules: explore data → multi-step code/analysis → interpret results |
| **Why Verified-50** | Curated subset that removes/fixes broken items from original BixBench; better for reliable agent scoring (see Phylo blog: *Evaluating AI Agents in Biology*) |
| **Access** | HF gated (accept conditions / share contact) |

**Native schema (JSONL row):**

| Field | Role |
|-------|------|
| `question_id` | Stable ID |
| `question` | Prompt shown to agent |
| `ideal` | Ground-truth answer |
| `eval_mode` | `str_verifier` \| `range_verifier` \| `llm_verifier` |
| `capsule_uuid` / `data_folder` | Capsule zip name (`CapsuleFolder-{uuid}.zip`) |
| `hypothesis`, `result`, `answer` | Extra scientific context |
| `categories`, `paper` | Metadata |
| `distractors` | MCQ wrong options (optional mode) |
| `canary` | Contamination canary |

**Capsule layout:** zip → `CapsuleData-{uuid}/` (inputs) + `CapsuleNotebook-{uuid}/` (reference notebook).

**Eval split in Verified-50:** llm_verifier 20 / str_verifier 17 / range_verifier 13.

**Sandwalk fit:** This is what `sandwalk bench` already targets (`--manifest` with `question_id`, `question`, `ideal`, `data_dir`). Prefer Verified-50 as the default pack; keep full BixBench v1.5 as an optional larger pack.

---

### 2. BioMysteryBench (Anthropic)

| | |
|---|---|
| **HF** | [Anthropic/BioMysteryBench-full](https://huggingface.co/datasets/Anthropic/BioMysteryBench-full) |
| **Writeup** | [Anthropic research post](https://www.anthropic.com/research/Evaluating-Claude-For-Bioinformatics-With-BioMysteryBench) |
| **Size** | ~90 problems; data archives large (~155 GB total set) |
| **What it tests** | Mystery bioinformatics: anonymized real data files; must run analysis (alignment, expression, variants, motifs, structure, etc.). Source study lookup via GEO/SRA/ENA/BioProject **forbidden**; standard DB/BLAST/ref genomes **allowed** |
| **Access** | Gated; **eval/benchmark only** — do **not** use for train/finetune/distill (CC BY 4.0 on statements/rubrics) |

**Native schema (`problems.csv` / parquet):**

| Field | Role |
|-------|------|
| `id` | Problem ID (e.g. `hb001`, `rec…`) |
| `question` | Task prompt |
| `answer_rubric` | Grading criterion (**contains expected answer**) |
| `allowed_domains` | Network allowlist for the solving env |
| `human_solvable` | `yes` / `no` (human baseline flag) |

**Data:** `data/<id>.zip` → extract into the working directory before solving.

**Sandwalk fit:** Map `answer_rubric` → `ideal` + `eval_mode=llm_verifier` (rubric grading). Mount each zip as `data_dir`. Enforce `allowed_domains` in sandbox network policy when we have it. Start with a **human_solvable=yes** subset + small zips before full 155 GB.

---

## Strongly related packs (phase 2)

### 3. LAB-Bench (FutureHouse)

| | |
|---|---|
| **HF** | [futurehouse/lab-bench](https://huggingface.co/datasets/futurehouse/lab-bench) |
| **Paper** | [arXiv:2407.10362](https://arxiv.org/abs/2407.10362) |
| **Size** | ~2.4k MCQs public (~80%); 20% private holdout |
| **What it tests** | Practical biology *knowledge work*: LitQA2, SuppQA, FigQA, TableQA, DbQA, ProtocolQA, SeqQA, CloningScenarios — less “analyze this capsule,” more literature/DB/figure/sequence skills |
| **Structure** | Multiple-choice per subtask; often figures/assets attached; canary string for training filters |
| **Sandwalk fit** | Good for tool/RAG/skills stress (Exa/Tavily, sequence tools) without multi-GB capsules. Map options → `distractors` + correct → `ideal`; `eval_mode=str_verifier` or exact letter match |

### 4. ScienceAgentBench

| | |
|---|---|
| **HF** | [osunlp/ScienceAgentBench](https://huggingface.co/datasets/osunlp/ScienceAgentBench) (prefer verified revision) |
| **What it tests** | Data-driven discovery across disciplines; agent must emit a **self-contained Python program**; execution + result metrics |
| **Sandwalk fit** | Code-gen track (different from open-answer Bix/Mystery). `eval_mode=code_exec` + golden program/tests from their harness |

### 5. DiscoveryBench (AllenAI)

| | |
|---|---|
| **HF / GitHub** | [allenai/discoverybench](https://huggingface.co/datasets/allenai/discoverybench) · [repo](https://github.com/allenai/discoverybench/) |
| **What it tests** | Goal + dataset(s) → statistical + semantic discovery; faceted open-ended eval |
| **Sandwalk fit** | Adjacent to BixBench open analysis; useful if we want non-bio generalization later |

### 6. Optional / narrower

| Pack | Use when |
|------|----------|
| [BioCoder](https://biocoder-benchmark.github.io/) | Function-level bioinformatics code gen (Python/Java) |
| CORE-Bench | Reproduce published analyses from paper materials (CS/social/medicine; not bio-first) |
| BLADE / SciGym | Open analysis trajectory / simulated lab (harder harness) |
| GPQA / MMLU-Pro (bio slices) | Chat-only knowledge baselines — **not** agent/data packs; keep separate from capsule benches |

---

## Common internal schema (target)

Normalize every pack into one JSON manifest the runner already almost expects (`sandwalk bench --manifest`):

```json
{
  "pack": "bixbench-verified-50",
  "pack_version": "1.0",
  "license_notes": "Apache-2.0; cite Mitchener et al. 2025",
  "questions": [
    {
      "question_id": "bbv50_001",
      "source_id": "original-id-in-upstream",
      "question": "…",
      "ideal": "…",
      "eval_mode": "str_verifier",
      "data_dir": "/abs/path/to/extracted/capsule/or/problem",
      "data_archive": "CapsuleFolder-….zip",
      "categories": ["rna-seq", "differential-expression"],
      "distractors": [],
      "allowed_domains": ["blast.ncbi.nlm.nih.gov", "…"],
      "human_solvable": true,
      "metadata": {}
    }
  ]
}
```

### `eval_mode` contract

| Mode | Grade how |
|------|-----------|
| `str_verifier` | Normalized string / exact / contains match against `ideal` |
| `range_verifier` | Numeric within tolerance (parse from `ideal` or metadata) |
| `llm_verifier` | Judge model + rubric (`ideal` or dedicated `answer_rubric`) |
| `mcq` | Pick among `ideal` + `distractors` |
| `code_exec` | Run generated code / tests (ScienceAgentBench-style) |
| `checklist` | Sandwalk skills/MCP bakeoff (manual or event-parsed) |

### Adapter responsibilities

1. **Download** — HF dataset + archives (respect gates / ToS).
2. **Extract** — capsule/problem zip → stable `data_dir`.
3. **Normalize** — upstream row → common question object.
4. **Prompt wrap** — inject sandbox rules (BioMystery: no GEO/SRA lookup; attach workspace path).
5. **Run** — agent session or `BenchRunner` with model matrix (see session bakeoff doc).
6. **Grade** — dispatch on `eval_mode`; write per-question + suite summary JSON.

---

## Recommended suite layout (repo / data)

```text
benchmarks/                          # or ~/.sandwalk/benchmarks/
  packs/
    bixbench-verified-50/
      source.jsonl                   # upstream
      manifest.json                  # normalized
      capsules/…                     # extracted
    biomysterybench/
      problems.parquet
      manifest.json
      data/<id>/…
    lab-bench/
      manifest.json
  matrices/
    smoke-or-5x5.yaml                # models × question subset
    bix50-openrouter-favs.yaml
  results/
    <run_id>/manifest.json
    <run_id>/grades.json
```

Matrix YAML (align with session bakeoff):

```yaml
pack: bixbench-verified-50
mode: product          # product | zip | pairs
questions: all         # or [id, …] or { filter: { eval_mode: str_verifier } }
models:
  - provider: openrouter
    model: moonshotai/kimi-k3
  - provider: openrouter
    model: qwen/qwen3.7-max
spawn: agent_server    # agent_server | cli_runner
```

**Formal package:** [`apps/benchmarking/`](../../apps/benchmarking/) (`sandwalk-bench`)

- Native skills/MCP pack: `apps/benchmarking/packs/sandwalk_skills_mcp.yaml`
- MCQ fixtures (MMLU / MMLU-Pro / ARC-C): `apps/benchmarking/fixtures/*_sample_30.jsonl`
- Full Verified-50 as-is: `sandwalk-bench bixbench download|info` (Dashboard Bench + capsule download)

Use **YAML for question banks**; keep **JSON for per-run manifests** (session/run IDs).

---

## How the two priority packs differ (design implications)

| Dimension | BixBench-Verified-50 | BioMysteryBench |
|-----------|----------------------|-----------------|
| Origin | FutureHouse capsules + Phylo cleanup | Anthropic mystery problems |
| Answer key | Explicit `ideal` + typed verifiers | Rubric in `answer_rubric` |
| Data size | Smaller curated set | Very large archives |
| Cheating risk | Notebook reference in capsule (don’t leak to agent) | Accession lookup banned by rule |
| Network | Usually local files enough | `allowed_domains` matters |
| Human baseline | Expert review notes | `human_solvable` flag |
| Best first slice | All 50, or str+range only | `human_solvable=yes` + N smallest zips |

**Do not** put reference notebooks or rubrics in the agent-visible workspace. Only `CapsuleData` / problem `data/` + the question text.

---

## Suggested build order

1. **Adapter: BixBench-Verified-50** → normalized `manifest.json` compatible with current `sandwalk bench` dry-run fields (`question_id`, `question`, `ideal`, `data_dir`).
2. **Verifier dispatch** — implement `str_verifier` / `range_verifier` / `llm_verifier` using upstream `eval_mode`.
3. **Adapter: BioMysteryBench** — rubric → `llm_verifier`; wire `allowed_domains`; subset runner before full download.
4. **Model matrix spawn** — reuse [agent-session-benchmarking.md](./agent-session-benchmarking.md) (same Q × many models).
5. **LAB-Bench MCQ pack** — fast CI / smoke without capsules.
6. **Sandwalk-native pack** — skills/MCP stress (Q1–Q5 bakeoff) as `eval_mode=checklist`.
7. Later: ScienceAgentBench / DiscoveryBench if we want code-exec discovery tracks.

---

## Citations / license reminders

- **BixBench:** Mitchener et al., *BixBench*, [arXiv:2503.00096](https://arxiv.org/abs/2503.00096); Verified-50 Apache-2.0 (Phylo curation).
- **BioMysteryBench:** Anthropic; CC BY 4.0 on problems/rubrics; **evaluation only** — no training use; data zips still under original archive policies.
- **LAB-Bench:** Laurent et al., [arXiv:2407.10362](https://arxiv.org/abs/2407.10362); respect canary / public-subset terms.

---

## Mapping to sandwalk code today

| Piece | Status |
|-------|--------|
| `sandwalk bench` CLI | Exists; BixBench-50 flags (`--manifest`, `--eval-model`, parallel, etc.) |
| `bench.runner.BenchRunner` | Imported by CLI; package not in-tree yet (expected external / to be landed) |
| `agent.model_benchmark` | Lightweight model×question smoke (configs/model_benchmarks.json) — chat latency, not capsules |
| Session bakeoff seeder | Documented in agent-session-benchmarking.md |
| Pack adapters | **Todo** — this doc is the contract |

Next implementation step: `benchmarks/adapters/bixbench_verified50.py` that reads HF JSONL + extracted capsules and emits the common `manifest.json` consumed by `BenchRunner` / session spawn.
