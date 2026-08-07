# Agent session benchmarking (multi-model spawn)

How to seed sandwalk agent-server sessions for LLM bakeoffs: **same question × different models**, **different questions × same model**, or mixed matrices. This is the operational recipe used for the Aug 2026 skills/MCP stress bakeoff; it is meant to grow into a proper benchmarking suite.

## Goals

- Spawn N local web / agent-server chats with known titles and prompts
- Pin each run to a specific provider/model (today: mostly OpenRouter)
- Exercise enabled **skills** and **MCPs**, not just chat quality
- Leave artifacts (`BAKEOFF_PROMPT.md`, job IDs, workspace files) for scoring

## Prerequisites

1. Agent server running locally (default `http://127.0.0.1:8787`).
2. API key auth if enabled:

   ```bash
   cd cli && uv run sandwalk auth show   # prints sk-sandwalk-…
   ```

3. Models reachable (e.g. `llm.openrouter_api_key` set; favorites/recent optional).
4. Skills / MCPs you intend to score are **enabled** (`sandwalk skills list`, `sandwalk mcp list`).

## Critical constraint: model is global

Runtime model lives in process config (`PATCH /v1/settings/runtime` → `provider` + `model`), **not** on the session row.

Implications:

- Concurrent runs started while flipping the global model can race.
- Seed **sequentially**: set model → create session → send message → wait until `status=running` (and a short latch delay) → next model.
- Restore the previous runtime model after the matrix is submitted so the UI does not stay on the last bakeoff model.

Long-term suite should snapshot provider/model into the run at submit time (or store per-session overrides). Until then, use the sequential latch pattern below.

## API surface

Auth header: `Authorization: Bearer <api-key>` (or `X-API-Key`).

| Step | Method | Path | Body (camelCase JSON) |
|------|--------|------|------------------------|
| Read runtime | `GET` | `/v1/settings/runtime` | — |
| Set model | `PATCH` | `/v1/settings/runtime` | `{ "provider": "openrouter", "model": "qwen/qwen3.7-max" }` |
| Create chat | `POST` | `/v1/sessions` | `{ "title": "Fold+PyMOL ubiquitin · qwen-max" }` |
| Start run | `POST` | `/v1/sessions/{id}/messages` | `{ "content": "…" }` |
| Poll status | `GET` | `/v1/sessions/{id}` | — |

Notes:

- `CreateSessionRequest` has no model field; title + workspace only.
- `SendMessageRequest` is content-only; the runner reads `llm.provider` / `llm.model` when the agent builds.
- Workspace path is on the session (`workspacePath`); write `BAKEOFF_PROMPT.md` there for human re-runs.

Model IDs in runtime are **without** the `openrouter:` prefix (provider is separate). Favorites in config use `openrouter:vendor/model`.

## Suite shapes

### A. Same question × different models

One prompt, N OpenRouter (or other) bases. Best for tool-calling / honesty comparisons.

```text
matrix:
  questions: [Q1]
  models: [M1, M2, M3, M4, M5]
→ 5 sessions
```

### B. Different questions × same model

N prompts, one base. Best for skill/MCP coverage under a fixed LLM.

```text
matrix:
  questions: [Q1, Q2, Q3, Q4, Q5]
  models: [M1]
→ 5 sessions
```

### C. Full matrix (future)

```text
sessions = questions × models
```

Title every session with task + model shortname only — no `[bakeoffN]` prefix.

## Suggested title convention

```text
<short-task> · <model-shortname>
```

Examples:

- `Exa+AFDB lysozyme · kimi-k3`
- `Fold+PyMOL ubiquitin · qwen-max`

Model shortname makes side-by-side scoring easier without noisy prefixes.

## Seed algorithm (sequential latch)

1. `GET /v1/settings/runtime` → save `orig_provider`, `orig_model`.
2. For each cell `(question, model)` in the matrix:
   1. `PATCH` runtime to `{ provider, model }`.
   2. Confirm with `GET` that runtime matches.
   3. `POST /v1/sessions` with bakeoff title.
   4. Write `BAKEOFF_PROMPT.md` into `workspacePath` (title, model label, full prompt).
   5. `POST …/messages` with the prompt (optionally include a one-line “confirm model” instruction).
   6. Poll until `status` ∈ `running | awaiting_approval | error | interrupted`.
   7. Sleep ~1–2s so agent construction can read config before the next PATCH.
3. `PATCH` runtime back to `orig_*`.
4. Emit a JSON manifest (sessionId, runId, model, question id, workspace).

## Minimal Python seeder

Run from `cli/` with the server up:

```python
import json, time, urllib.request, subprocess
from pathlib import Path

BASE = "http://127.0.0.1:8787"
KEY = subprocess.check_output(["uv", "run", "sandwalk", "auth", "show"], text=True).strip()

def req(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(r, timeout=60) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else None

runtime = req("GET", "/v1/settings/runtime")
orig = (runtime["provider"], runtime["model"])

# Example: same question × 5 OpenRouter models
QUESTION = "…"  # full stress prompt
MODELS = [
    "moonshotai/kimi-k3",
    "qwen/qwen3.7-max",
    "openai/gpt-5.6-luna-pro",
    "deepseek/deepseek-v4-pro",
    "deepseek/deepseek-v4-flash-0731",
]

manifest = []
for i, model in enumerate(MODELS, 1):
    req("PATCH", "/v1/settings/runtime", {"provider": "openrouter", "model": model})
    time.sleep(0.3)
    sess = req("POST", "/v1/sessions", {
        "title": f"Exa+AFDB lysozyme · {model.split('/')[-1]}",
    })
    ws = sess.get("workspacePath") or ""
    if ws:
        Path(ws).mkdir(parents=True, exist_ok=True)
        (Path(ws) / "BAKEOFF_PROMPT.md").write_text(
            f"# bakeoff\n\nModel: openrouter:{model}\n\n{QUESTION}\n",
            encoding="utf-8",
        )
    run = req("POST", f"/v1/sessions/{sess['id']}/messages", {"content": QUESTION})
    for _ in range(40):
        s = req("GET", f"/v1/sessions/{sess['id']}")
        if s["status"] in ("running", "awaiting_approval", "error", "interrupted"):
            break
        time.sleep(0.25)
    time.sleep(2.0)
    manifest.append({
        "sessionId": sess["id"],
        "runId": run["runId"],
        "model": f"openrouter:{model}",
        "status": s["status"],
        "workspace": ws,
    })

req("PATCH", "/v1/settings/runtime", {"provider": orig[0], "model": orig[1]})
print(json.dumps(manifest, indent=2))
```

## Bio-risk filter (OpenRouter / OpenAI)

Some hosts return HTTP 400 *“flagged for possible biological risk”* on pathogen/virus/toxin wording (even textbook SARS-CoV-2 RBD examples). For bakeoffs:

- Prefer **benign** systems: ubiquitin, lysozyme, insulin A-chain, GFP, hemoglobin, poly-GS IDPs, classic PDBs (`1UBQ`).
- Avoid: viruses, pathogens, toxins, dual-use, “spike/RBD” pathogen epitopes, gain-of-function language.
- Prefix prompts with an explicit benign-only constraint.
- If flagged, rephrase to methods/structure on the benign list above — do not argue with the filter.

## Reference bakeoff prompts (skills + MCPs)

### Bakeoff1 (5 cells)

| ID | Focus | Skills / MCPs |
|----|--------|----------------|
| Q1 | Lit + structure + diagram | Exa/Tavily, `alphafold-database-fetch-and-analyze`, `diagrams_mermaid` |
| Q2 | Fold + local viz | `fold`, PyMOL, RayMol |
| Q3 | Design + cloud bio | `protein_design_boltzgen`, `skill-find`, Tamarind, Hugging Face |
| Q4 | MD submit/poll | Exa/Tavily, `md_openmm_calvados` / `md_openmmdl` |
| Q5 | Ops + docs + report | Linear, Paperclip, Tavily, `convert-documents-to-markdown`, `slack_report` |

### Full coverage pack (v3 — Featured skills + MCPs)

**Source of truth:** [`apps/benchmarking/`](../../apps/benchmarking/) (`sandwalk-bench`)  
**Packs:** `apps/benchmarking/packs/sandwalk_skills_mcp.yaml` (+ MCQ fixtures under `fixtures/`)  
**Input fixtures:** `apps/benchmarking/fixtures/`  
**Ignored MCPs:** Linear, Lucid  

Titles: `{question.title} · {model_short}`. Every prompt gets autonomy rules (no follow-ups; wait/poll; finish the task).

| ID | Focus | Skills | MCPs |
|----|--------|--------|------|
| B01 | Docs → markdown + diagram + search | `convert-documents-to-markdown`, `diagrams_mermaid` | Exa, Tavily |
| B02 | Fold + dual viz | `fold` | PyMOL, RayMol |
| B03 | Boltz + cloud bio | `boltz`, `skill-find` | Tamarind, Neurosnap |
| B04 | Design + HF | `protein_design_boltzgen`, `skill-find` | Hugging Face |
| B05 | CALVADOS | `md_openmm_calvados` | Exa |
| B06 | OpenMMDL | `md_openmmdl` | Tavily |
| B07 | Latch + Paperclip + CSV | `convert-documents-to-markdown` | Latch, Paperclip |
| B08 | Static site | `sites-building`, `sites-hosting`, `diagrams_mermaid` | — |
| B09 | Skill authoring | `skill-find`, `skill-creator` | Hugging Face |
| B10 | 1UBQ viz + Slack | `slack_report`, `diagrams_mermaid` | PyMOL, RayMol, Exa |
| B11 | Insulin fold + cloud | `fold` | Neurosnap, Tamarind |
| B12 | Platform status | `slack_report` | Latch, Tavily, Paperclip |

Matrix: `full-coverage` (12 pairs). Seeders should `copy_inputs: true` into each session workspace.

## Scoring checklist (manual v0)

For each session in the manifest:

- [ ] Correct model acknowledged / traces show expected provider route
- [ ] Right skills/MCPs selected (not hallucinated alternatives)
- [ ] Auth / OAuth failures reported honestly
- [ ] Jobs/workflows: real IDs + poll loop (no fake COMPLETED)
- [ ] Workspace artifacts present when claimed
- [ ] Latency / cost (optional: OpenRouter usage, wall clock)

## Future suite (todo)

Turn this doc into first-class tooling under something like `sandwalk bench sessions`:

1. **YAML/JSON matrix** — `questions[]`, `models[]`, `mode: product|zip|pairs`.
2. **CLI** — `sandwalk bench spawn matrix.yaml` → writes `manifest.json`.
3. **Per-run model snapshot** — eliminate global-model latch races.
4. **Scorer** — parse events/messages for tool names, job IDs, checklists.
5. **Question packs** — skills/MCP stress, fold-only, search-only, ops-only.
6. **Optional stagger** — delay between fold/MD cells to avoid shared queue contention.

## Related

- External packs + common schema: [benchmark-packs.md](./benchmark-packs.md) (BixBench-Verified-50, BioMysteryBench, LAB-Bench, …)
- CLI benchmark (BixBench): `sandwalk bench`
- Knowledge quality gates: `sandwalk knowledge benchmark`
- MCP catalog: `docs/mcp-defaults/`
- Local server: `sandwalk serve` (port `8787` by default)
