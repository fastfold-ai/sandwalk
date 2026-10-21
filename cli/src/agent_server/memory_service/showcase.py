"""End-to-end starter showcase for Memory, Living Wiki, Omnigraph Cookbooks, and Persona Chats."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

SHOWCASE_SEEDED_SCOPE = "__meta_showcase_v2__"


def _seed_global_second_brain_wiki(wiki: Any) -> None:
    """Populate the Global Brain Living Wiki with Personal Second Brain pages."""
    for old_slug in ("glp1r-binding-pocket", "sw-204-herg-contradiction", "otium-synthesis-log"):
        try:
            wiki.delete_page(old_slug, "global")
        except Exception:
            pass

    wiki.write_page(
        slug="index",
        scope="global",
        title="Julio’s Second Brain & Operating Hub",
        summary="Personal operating graph: preferences, hybrid model routing, active projects, and R&D syntheses.",
        tags=["second-brain", "hub", "preferences"],
        content=(
            "Welcome to your **Global Second Brain** (`06 Second brain`). These Markdown pages live on disk at "
            "`~/.sandwalk/memory/wiki/global/` and cross-link with `[[wikilinks]]`.\n\n"
            "## Personal Operating Manual\n"
            "- [[user-operating-manual]] — Working style, engineering standards, hardware setup, and specialist persona roster.\n"
            "- [[model-routing-playbook]] — How Sandwalk routes chat, background distillation, and Omnigraph embeddings across Cloud & Local `llama.cpp`.\n"
            "- [[sandwalk-architecture-notes]] — Design notes on Hermes-style bounded `USER.md`/`MEMORY.md` snapshots and `.omni` Lance graphs.\n"
            "- [[oral-glp1r-program-brief]] — Active biotech research thread (`SW-204` vs `hERG` safety gate) led by **Otium** and **Soren**.\n"
        ),
    )
    wiki.write_page(
        slug="user-operating-manual",
        scope="global",
        title="User Preferences, Stack & Specialist Roster",
        summary="Julio’s coding standards, local-first preferences, and when to summon each specialist persona.",
        tags=["user", "preferences", "personas"],
        content=(
            "## Core Preferences (`USER.md`)\n"
            "- **Environment**: macOS Apple Silicon workstation running Sandwalk (`:8787` FastAPI + `:1420` Vite/Tauri + `:9931` local `llama.cpp`).\n"
            "- **Engineering Bar**: Always run `scripts/verify.sh`, maintain `>= 90%` test coverage, keep UI responsive, and never log secrets.\n"
            "- **Knowledge Style**: Prefer structured Living Wiki pages (linked from [[index]]) and explicit `Supports` / `Contradicts` edges in Omnigraph over raw chat transcripts.\n\n"
            "## Persona Roster\n"
            "- **Otium (`Relaxed` Capybara)**: Calm synthesis, de-escalating complexity, and Living Wiki curation.\n"
            "- **Soren (`Skeptical Reviewer` Barn Owl)**: Red-team audits, `Contradicts` claims, and statistical/safety gates (see [[oral-glp1r-program-brief]]).\n"
            "- **Nova (`Dreamer` Red Fox)**: Divergent hypotheses and early weak-signal exploration.\n"
            "- **Milo (`Project Manager` Badger)**: Milestones, decisions, and action items.\n"
            "- **Atlas (`Ambitious Generalist` Timber Wolf)**: High-agency full-stack and scientific execution.\n"
        ),
    )
    wiki.write_page(
        slug="model-routing-playbook",
        scope="global",
        title="Hybrid Cloud + Local Model Routing Playbook",
        summary="Reuse active chat models for warm KV caches and defer distillation while local llama.cpp GPU is busy.",
        tags=["models", "llama.cpp", "openrouter", "omnigraph"],
        content=(
            "## Unified Model Strategy\n"
            "Configured in **Dashboard → Memory & Wiki → Models, Control & Omnigraph** (and linked from [[index]]):\n\n"
            "1. **Session-Start Frozen Prefix**: `USER.md` (`1,375` chars) and `MEMORY.md` (`2,200` chars) are snapshotted once per session so Anthropic/OpenAI/OpenRouter and local `llama.cpp` KV caches never invalidate mid-chat.\n"
            "2. **Idle-GPU Distillation**: When `llama.cpp` (`:9931`) has active inference slots, background session distillation automatically defers so token streaming stays butter-smooth.\n"
            "3. **Zero-Cost Hybrid Retrieval**: Omnigraph defaults to BM25 + graph traversal (`0` embedding cost) and can switch to OpenRouter, OpenAI, Gemini, or local `llama.cpp` embeddings in 1 click ([[sandwalk-architecture-notes]]).\n"
        ),
    )
    wiki.write_page(
        slug="sandwalk-architecture-notes",
        scope="global",
        title="Sandwalk Memory, Living Wiki & Omnigraph Architecture",
        summary="How SQLite FTS5, Markdown Wiki files, and Lance-backed .omni graphs fit together.",
        tags=["architecture", "omnigraph", "wiki"],
        content=(
            "## Three-Tier Knowledge Hierarchy\n"
            "- **Tier 1 — Bounded Prompt Snapshot (`USER.md` & `MEMORY.md`)**: Instant recall of user preferences ([[user-operating-manual]]) and high-signal rules.\n"
            "- **Tier 2 — Living Markdown Wiki (`~/.sandwalk/memory/wiki/`)**: Human-readable `.md` notes with `[[wikilinks]]` and automatic backlinks ([[index]]).\n"
            "- **Tier 3 — Omnigraph Cookbook Ontologies (`~/.sandwalk/memory/omni/*.omni`)**: Typed `.pg` schemas, `.gq` stored queries, and Git-style `review/*` branches.\n"
        ),
    )
    wiki.write_page(
        slug="oral-glp1r-program-brief",
        scope="global",
        title="Oral GLP-1R Agonist (SW-204 / SW-204b) Executive Brief",
        summary="Cross-persona summary of the SW-204 Trp33 pocket potency vs Soren's hERG safety contradiction.",
        tags=["glp1r", "sw-204", "biomed"],
        content=(
            "## Executive Summary\n"
            "Tracked in detail inside **Otium’s Brain** (`05 Biomed research`) and summarized here in [[index]]:\n\n"
            "- **Potency (`Supports`)**: `SW-204` achieves `cAMP EC50 = 1.4 nM` via conserved `Trp33` pi-stacking in the upper TM1/TM7 pocket.\n"
            "- **Safety Contradiction (`Contradicts`)**: Soren’s QPatch audit flagged `hERG IC50 = 1.8 µM` (`< 30x` margin).\n"
            "- **Next Action**: Evaluate the pKa-attenuated **C-7 gem-difluoro** derivative (`SW-204b`) on branch `review/soren-herg-audit`.\n"
        ),
    )


def _seed_global_second_brain_graph(graph: Any) -> None:
    """Populate the Global Brain (`global`) with a rich `06 Second brain` personal operating graph."""
    with graph.store._lock, graph.store._connect() as conn:
        conn.execute("DELETE FROM graph_nodes WHERE scope = 'global'")
        conn.execute("DELETE FROM graph_edges WHERE scope = 'global'")

    graph.load_cookbook_seed("global", "second-brain", branch="main")

    nodes = [
        (
            "Person",
            "julio-cesar",
            "Julio Cesar (Principal AI & CompBio Architect)",
            "Builds Sandwalk on macOS Apple Silicon; prefers local-first graphs, concise Wiki syntheses, and rigorous contradiction checks.",
            ["founder", "architect"],
            "wiki:user-operating-manual",
        ),
        (
            "Organization",
            "fastfold-ai",
            "FastFold AI · Sandwalk",
            "Local-first multi-agent desktop & CLI platform for scientific discovery and software engineering.",
            ["organization", "platform"],
            "wiki:index",
        ),
        (
            "Goal",
            "goal-zero-latency-local-ai",
            "Sub-second Local + Cloud Hybrid Agent Workflow",
            "Keep KV prefix caches warm and defer background distillation whenever local llama.cpp (:9931) is busy.",
            ["performance", "models"],
            "wiki:model-routing-playbook",
        ),
        (
            "Project",
            "proj-oral-glp1r",
            "Oral Non-Peptide GLP-1R Lead Optimization (SW-204)",
            "Cross-persona R&D workstream with Otium (synthesis) and Soren (red-team hERG safety audit).",
            ["biomed", "glp1r"],
            "wiki:oral-glp1r-program-brief",
        ),
        (
            "Note",
            "note-user-preferences",
            "User Operating Manual: Direct answers, 90% coverage gate, Specialist personas",
            "Core working preferences mirrored in USER.md and [[user-operating-manual]].",
            ["preferences", "workflow"],
            "wiki:user-operating-manual",
        ),
        (
            "Note",
            "note-model-routing",
            "Hybrid Model Routing & Idle-GPU Distillation Playbook",
            "Reuses active chat model for distillation and shares API keys with Omnigraph embeddings.",
            ["models", "distiller"],
            "wiki:model-routing-playbook",
        ),
        (
            "Artifact",
            "art-sandwalk-monorepo",
            "Sandwalk Monorepo (~/Projects/sandwalk)",
            "cli/ (FastAPI :8787) + apps/local-web/ (React/Tauri :1420) + ~/.sandwalk/memory/ store.",
            ["repo", "codebase"],
            "wiki:sandwalk-architecture-notes",
        ),
        (
            "Task",
            "task-sw204b-difluoro-qpatch",
            "Run QPatch hERG assay on C-7 difluoro analog SW-204b (> 25 uM gate)",
            "Required before scheduling in vivo dog telemetry for the oral GLP-1R lead series.",
            ["next-action", "glp1r"],
            "wiki:oral-glp1r-program-brief",
        ),
        (
            "Task",
            "task-unbounded-prompt-dump",
            "Anti-Pattern: Injecting raw 50k-token chat history into every system prompt",
            "Invalidates LLM KV cache on every turn and starves local llama.cpp context budget.",
            ["anti-pattern", "latency"],
            "wiki:model-routing-playbook",
        ),
    ]
    for n_type, slug, name, summary, tags, src in nodes:
        graph.upsert_node(
            scope="global",
            branch="main",
            node_type=n_type,
            slug=slug,
            name=name,
            summary=summary,
            tags=tags,
            source_ref=src,
        )

    claims = [
        (
            "Person:julio-cesar",
            "WorksWith",
            "Organization:fastfold-ai",
            "support",
            0.99,
            "Creator and lead architect of Sandwalk.",
        ),
        (
            "Project:proj-sandwalk-memory",
            "AdvancesGoal",
            "Goal:goal-zero-latency-local-ai",
            "support",
            0.96,
            "Frozen session-start snapshots + on-demand Wiki/Graph tools keep prompt tokens compact.",
        ),
        (
            "Project:proj-oral-glp1r",
            "AdvancesGoal",
            "Goal:goal-autonomous-rd",
            "support",
            0.94,
            "Demonstrates multi-persona memory + Contradicts graph auditing on a real drug discovery workflow.",
        ),
        (
            "Note:note-user-preferences",
            "InformsProject",
            "Project:proj-sandwalk-memory",
            "support",
            0.95,
            "Defines persona roster (Otium, Soren, Nova, Milo, Atlas) and verification gates.",
        ),
        (
            "Note:note-model-routing",
            "InformsProject",
            "Project:proj-sandwalk-memory",
            "support",
            0.93,
            "Governs idle-GPU distillation deferral and shared embedding credentials.",
        ),
        (
            "Task:task-sw204b-difluoro-qpatch",
            "TaskForProject",
            "Project:proj-oral-glp1r",
            "support",
            0.92,
            "Unblocks preclinical safety gate for SW-204 series.",
        ),
        (
            "Task:task-unbounded-prompt-dump",
            "ContradictsGoal",
            "Goal:goal-zero-latency-local-ai",
            "contradict",
            0.97,
            "Unbounded prompt mutation breaks prefix caching and causes latency spikes on local GPU.",
        ),
    ]
    for subj, pred, obj, pol, score, summary in claims:
        graph.record_claim(
            scope="global",
            branch="main",
            subject_id=subj,
            predicate=pred,
            object_id=obj,
            polarity=pol,
            score=score,
            summary=summary,
            source_ref="wiki:index",
        )

    graph.manage_branch(
        scope="global",
        action="create",
        name="review/q4-roadmap-notes",
        target_branch="main",
    )
    graph.upsert_node(
        scope="global",
        branch="review/q4-roadmap-notes",
        node_type="Goal",
        slug="goal-voice-memory-distill",
        name="Hands-free Voice Session Distillation with Capy",
        summary="Distill voice brainstorming sessions directly into Second Brain notes and tasks.",
        tags=["roadmap", "capy"],
        source_ref="wiki:index",
    )
    graph.record_claim(
        scope="global",
        branch="review/q4-roadmap-notes",
        subject_id="Project:proj-sandwalk-memory",
        predicate="AdvancesGoal",
        object_id="Goal:goal-voice-memory-distill",
        polarity="support",
        score=0.89,
        summary="Staged Q4 goal on review branch.",
        source_ref="wiki:index",
    )
    graph.sync_omnigraph_bundle("global", branch="main")


def _seed_biomed_wiki_for_scope(wiki: Any, scope: str) -> None:
    wiki.write_page(
        slug="index",
        scope=scope,
        title="Oral GLP-1R Agonist Discovery Hub",
        summary="Central hub linking pocket structure, SW-204 hERG contradiction audit, and Otium decision logs.",
        tags=["hub", "glp1r", "program"],
        content=(
            "Welcome to the **Living Wiki** for the Oral GLP-1R Non-Peptide Agonist program.\n\n"
            "## Core Knowledge Pages\n"
            "- [[glp1r-binding-pocket]] — Cryo-EM pocket geometry around `Trp33`, `Phe230`, and `Arg380`.\n"
            "- [[sw-204-herg-contradiction]] — Active red-team audit on lead scaffold `SW-204` vs `hERG` patch-clamp liability.\n"
            "- [[otium-synthesis-log]] — Otium's calm architectural synthesis & next-step decision log.\n"
        ),
    )
    wiki.write_page(
        slug="glp1r-binding-pocket",
        scope=scope,
        title="GLP-1R Trp33 / Phe230 Allosteric Pocket",
        summary="Cryo-EM upper helical bundle pocket stabilized by Trp33 pi-stacking and Phe230 water network.",
        tags=["structure", "glp1r", "cryo-em"],
        content=(
            "## Binding Mode Overview\n"
            "Non-peptide agonists occupy the upper helical bundle between **TM1, TM2, ECL2, and TM7**, "
            "anchored by a critical pi-stack against `Trp33` in the extracellular domain (ECD).\n\n"
            "- **Key Residues**: `Trp33` (ECD cap), `Phe230` (TM3 hydrophobic shelf), `Arg380` (TM7 salt bridge).\n"
            "- **Lead Series**: `SW-204` introduces a rigidified dihydropyrazole core (`EC50 = 1.4 nM`), documented in [[index]].\n"
            "- **Open Risk**: Basic amine tail increases lipophilic cation character (see [[sw-204-herg-contradiction]]).\n"
        ),
    )
    wiki.write_page(
        slug="sw-204-herg-contradiction",
        scope=scope,
        title="Contested Claim: SW-204 Oral Lead vs hERG Liability",
        summary="QPatch hERG IC50 = 1.8 uM contradicts advancing unmodified SW-204 to in vivo dog telemetry.",
        tags=["contradiction", "safety", "herg", "soren"],
        content=(
            "## Contradiction Summary (`polarity = contradict`)\n"
            "- **Optimistic Claim (`Claim:sw204-oral-lead`)**: `SW-204` hits `cAMP EC50 = 1.4 nM` and rat `F = 44%`.\n"
            "- **Contradicting Evidence (`Assay:herg-safety`)**: QPatch measured `hERG IC50 = 1.8 uM` (`< 25 uM` gate).\n"
            "- **Resolution Path**: Synthesize C-7 gem-difluoro `SW-204b` ([[otium-synthesis-log]], [[glp1r-binding-pocket]]).\n"
        ),
    )
    wiki.write_page(
        slug="otium-synthesis-log",
        scope=scope,
        title="Otium's Calm Synthesis & Decision Log",
        summary="Pause unmodified SW-204 telemetry; evaluate C-7 difluoro analog SW-204b on review branch first.",
        tags=["otium", "decisions", "synthesis"],
        content=(
            "## Otium's Reflective Summary\n"
            "1. **What is solid**: The upper TM1/TM7 binding mode in [[glp1r-binding-pocket]] is well-validated.\n"
            "2. **What is contested**: `SW-204` carries a tight hERG margin ([[sw-204-herg-contradiction]]).\n"
            "3. **Calm Next Step**: Test `SW-204b` (C-7 difluoro) on branch `review/soren-herg-audit` ([[index]]).\n"
        ),
    )


def _seed_glp1r_graph_for_scope(graph: Any, scope: str, cookbook_id: str = "biomed-research") -> None:
    graph.load_cookbook_seed(scope, cookbook_id, branch="main")
    graph.upsert_node(
        scope=scope,
        branch="main",
        node_type="Compound",
        slug="sw-204",
        name="SW-204 (Oral GLP-1R Lead)",
        summary="Dihydropyrazole non-peptide GLP-1R agonist (cAMP EC50 = 1.4 nM, rat F = 44%, hERG IC50 = 1.8 uM).",
        tags=["lead", "glp1r", "contested"],
        source_ref="wiki:sw-204-herg-contradiction",
    )
    graph.record_claim(
        scope=scope,
        branch="main",
        subject_id="Compound:sw-204",
        predicate="Targets",
        object_id="Target:glp1r",
        polarity="support",
        score=0.95,
        summary="SW-204 engages GLP-1R upper TM1/TM7 pocket via Trp33 pi-stack.",
        source_ref="wiki:glp1r-binding-pocket",
    )
    graph.record_claim(
        scope=scope,
        branch="main",
        subject_id="Assay:herg-safety",
        predicate="Contradicts",
        object_id="Compound:sw-204",
        polarity="contradict",
        score=0.94,
        summary="QPatch hERG IC50 = 1.8 uM contradicts progression of unmodified SW-204 to dog telemetry.",
        source_ref="wiki:sw-204-herg-contradiction",
    )
    graph.manage_branch(
        scope=scope,
        action="create",
        name="review/soren-herg-audit",
        target_branch="main",
    )
    graph.upsert_node(
        scope=scope,
        branch="review/soren-herg-audit",
        node_type="Compound",
        slug="sw-204b-difluoro",
        name="SW-204b (C-7 Difluoro Analog)",
        summary="pKa-attenuated C-7 gem-difluoro derivative predicted to shift hERG IC50 > 30 uM.",
        tags=["candidate", "difluoro"],
        source_ref="wiki:otium-synthesis-log",
    )
    graph.record_claim(
        scope=scope,
        branch="review/soren-herg-audit",
        subject_id="Compound:sw-204b-difluoro",
        predicate="Supports",
        object_id="Hypothesis:oral-glp1-pocket",
        polarity="support",
        score=0.91,
        summary="Retains Trp33 pi-stack while eliminating basic amine hERG pharmacophore.",
        source_ref="wiki:otium-synthesis-log",
    )
    graph.sync_omnigraph_bundle(scope, branch="main")


def seed_end_to_end_showcase(
    memory_service: Any,
    agent_store: Any | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Populate realistic Personal Second Brain (Global) + Domain/Persona Brains + Example Multi-Turn Chats."""
    store = memory_service.store
    graph = memory_service.graph
    wiki = memory_service.wiki

    if not force and store.get_scope_cookbook(SHOWCASE_SEEDED_SCOPE) == "seeded":
        return {"ok": True, "already_seeded": True, "seeded_sessions": []}

    # 1. Seed USER.md (Personal Preferences, Stack, Coding Bar & Persona Roster)
    if force:
        for old in store.list_entries(scope="user", include_user=False).data:
            store.delete_entry(old.id)
    if force or not store.list_entries(scope="user", include_user=False).data:
        user_facts = [
            (
                "Julio Cesar — Principal AI & Computational Biology Architect building Sandwalk on Apple Silicon macOS (local llama.cpp :9931 + OpenRouter / Anthropic / OpenAI).",
                ["identity", "stack"],
            ),
            (
                "Engineering bar: run scripts/verify.sh before commits, keep Codecov >= 90%, use English UI copy, never log API keys/tokens, and verify UI changes visually.",
                ["preferences", "engineering"],
            ),
            (
                "Specialist roster preference: use starter personas — Otium (Relaxed), Soren (Skeptical Reviewer), Nova (Dreamer), Milo (Project Manager), Atlas (Ambitious Generalist).",
                ["preferences", "personas"],
            ),
            (
                "Knowledge preference: keep Global Brain as a Personal Second Brain (06 Second brain) with [[wikilinks]] and explicit Supports/Contradicts graph edges rather than raw chat dumps.",
                ["preferences", "second-brain"],
            ),
        ]
        for content, tags in user_facts:
            store.add_entry(
                scope="user",
                target="user",
                content=content,
                tags=tags,
                pinned=True,
                source_session_id="demo-otium-glp1r-memory-walkthrough",
                bypass_approval=True,
            )

    # 2. Seed Global MEMORY.md (Second Brain Durable Rules & Cross-Project Facts)
    if force:
        for old in store.list_entries(scope="global", include_user=False).data:
            store.delete_entry(old.id)
    if force or not store.list_entries(scope="global", include_user=False).data:
        global_facts = [
            (
                "SECOND BRAIN RULE: Freeze USER.md (~1,375 chars) and MEMORY.md (~2,200 chars) at session start to keep LLM KV prefix caches 100% warm; fetch deep notes via wiki_read and graph_cookbook_query.",
                ["architecture", "kv-cache", "second-brain"],
            ),
            (
                "LOCAL GPU RULE: Defer background session distillation while local llama.cpp (:9931) has active inference slots; run immediately when using cloud models.",
                ["runtime", "llama.cpp", "distiller"],
            ),
            (
                "DEV WORKFLOW FACT: Checkout API runs on :8787 (scripts/dev-api.sh, restart after Python edits) and Vite UI runs on :1420 (scripts/dev-ui.sh, hot-reloads TS/React).",
                ["workflow", "sandwalk"],
            ),
            (
                "ACTIVE R&D ALERT (GLP-1R): Lead scaffold SW-204 hits cAMP EC50 = 1.4 nM (Trp33 pi-stack), but Soren's QPatch audit measured hERG IC50 = 1.8 uM (< 30x margin). Evaluate C-7 difluoro SW-204b on review/soren-herg-audit.",
                ["glp1r", "sw-204", "contradiction"],
            ),
        ]
        for content, tags in global_facts:
            store.add_entry(
                scope="global",
                target="memory",
                content=content,
                tags=tags,
                pinned=True,
                source_session_id="demo-otium-glp1r-memory-walkthrough",
                bypass_approval=True,
            )

    # 3. Seed 1 Pending Approval Write so the user can test Approve / Reject in the UI
    if force:
        for p in store.list_pending_writes():
            store.reject_pending_write(p.id)
    if not store.list_pending_writes():
        store.stage_pending_write(
            scope="global",
            kind="memory",
            action="add",
            summary="Gate SW-204 dog telemetry until C-7 difluoro analog SW-204b clears hERG IC50 > 25 uM.",
            payload={
                "scope": "global",
                "target": "memory",
                "layer": "L1",
                "content": (
                    "Gate SW-204 in vivo dog telemetry until C-7 difluoro analog SW-204b demonstrates "
                    "hERG IC50 > 25 uM in automated QPatch assay."
                ),
                "tags": ["gate", "safety", "sw-204b"],
                "pinned": True,
            },
            source_session_id="demo-soren-sw204-red-team-audit",
        )

    # 4. Seed Global Brain as `06 Second brain` (Personal Operating Graph + Personal Wiki)
    _seed_global_second_brain_wiki(wiki)
    _seed_global_second_brain_graph(graph)

    # 5. Seed Persona Brains (Otium, Soren, Nova, Milo, Atlas) + Example Multi-Turn Chat Sessions
    seeded_sessions: list[str] = []
    if agent_store is not None:
        try:
            specialists = agent_store.list_specialists()
            by_slug = {s.slug: s for s in specialists}

            persona_seeds: list[tuple[str, str, list[tuple[str, list[str]]]]] = [
                (
                    "otium-relaxed",
                    "biomed-research",
                    [
                        (
                            "When a lead scaffold shows a high-confidence Contradicts edge (e.g. SW-204 hERG IC50 = 1.8 uM), pause downstream in vivo tasks and isolate the structural fix (SW-204b) on a review branch.",
                            ["otium", "heuristic", "glp1r"],
                        ),
                        (
                            "Keep Living Wiki pages under 250 lines with explicit [[wikilinks]] between structural pockets ([[glp1r-binding-pocket]]), safety audits ([[sw-204-herg-contradiction]]), and decision logs ([[otium-synthesis-log]]).",
                            ["wiki", "stewardship"],
                        ),
                        (
                            "Prefer C-7 gem-difluoro pKa attenuation (pKa 8.4 -> 6.9) over bulky tail replacements so the Trp33 pi-stack in the GLP-1R ECD remains undisturbed.",
                            ["medchem", "sw-204b"],
                        ),
                    ],
                ),
                (
                    "skeptical-reviewer",
                    "pharma-intel",
                    [
                        (
                            "Never endorse an oral GPCR small molecule for preclinical toxicology unless hERG IC50 / primary EC50 ratio exceeds 1,000x in manual or QPatch clamp.",
                            ["safety", "herg", "red-team"],
                        ),
                        (
                            "Flag unbound portal Cmax > 0.15 uM when hERG IC50 < 5 uM as a hard Contradicts edge on the main knowledge graph.",
                            ["pk-pd", "audit"],
                        ),
                    ],
                ),
                (
                    "dreamer",
                    "industry-intel",
                    [
                        (
                            "Hypothesis: replacing the TM2 bridged water molecule with a cyano-thiazole warhead could unlock picomolar biased G-protein signaling without beta-arrestin recruitment.",
                            ["hypothesis", "glp1r", "biased-agonism"],
                        ),
                    ],
                ),
                (
                    "project-manager",
                    "context-graph",
                    [
                        (
                            "Milestone M2 (Lead Optimization): resolve SW-204 hERG liability via SW-204b synthesis before scheduling CRO dog PK.",
                            ["milestone", "roadmap"],
                        ),
                    ],
                ),
                (
                    "ambitious-generalist",
                    "second-brain",
                    [
                        (
                            "All Boltz-2 / Chai-1 pose scores and QPatch assay CSVs should sync into the project Omnigraph store so Contradicts queries run in <15ms.",
                            ["pipeline", "omnigraph"],
                        ),
                    ],
                ),
            ]

            for slug, cbook_id, mem_rows in persona_seeds:
                spec = by_slug.get(slug)
                if spec is None:
                    continue
                p_scope = f"specialist:{spec.id}"
                existing_p = store.list_entries(scope=p_scope, include_user=False).data
                if force or not existing_p:
                    for m_content, m_tags in mem_rows:
                        store.add_entry(
                            scope=p_scope,
                            target="memory",
                            content=m_content,
                            tags=m_tags,
                            pinned=True,
                            source_session_id="demo-otium-glp1r-memory-walkthrough",
                            bypass_approval=True,
                        )
                if slug == "otium-relaxed":
                    _seed_biomed_wiki_for_scope(wiki, p_scope)
                    _seed_glp1r_graph_for_scope(graph, p_scope, "biomed-research")
                else:
                    snap = graph.get_snapshot(p_scope)
                    if force or not snap.nodes:
                        graph.load_cookbook_seed(p_scope, cbook_id, branch="main")

            otium_spec = by_slug.get("otium-relaxed")
            soren_spec = by_slug.get("skeptical-reviewer")
            seeded_sessions = _seed_demo_chat_sessions(
                agent_store,
                otium_id=otium_spec.id if otium_spec else None,
                soren_id=soren_spec.id if soren_spec else None,
                force=force,
            )
        except Exception:
            pass

    store.set_scope_cookbook(SHOWCASE_SEEDED_SCOPE, "seeded")
    return {
        "ok": True,
        "already_seeded": False,
        "seeded_sessions": seeded_sessions,
    }


def _seed_demo_chat_sessions(
    agent_store: Any,
    *,
    otium_id: str | None,
    soren_id: str | None,
    force: bool = False,
) -> list[str]:
    """Create 2 realistic multi-turn chat sessions if not already present."""
    existing = agent_store.list_sessions()
    existing_ids = {s.id for s in existing}
    now = datetime.now(UTC)
    created_ids: list[str] = []

    if force:
        for sid in ("demo-otium-glp1r-memory-walkthrough", "demo-soren-sw204-red-team-audit"):
            if sid in existing_ids:
                try:
                    agent_store.delete_session(sid)
                    existing_ids.discard(sid)
                except Exception:
                    pass

    otium_session_id = "demo-otium-glp1r-memory-walkthrough"
    if otium_session_id not in existing_ids:
        sess = agent_store.ensure_session(
            otium_session_id,
            title="Otium · GLP-1R Memory, Wiki & Omnigraph Walkthrough",
            workspace_path=None,
            specialist_id=otium_id,
        )
        t0 = now - timedelta(seconds=40)
        agent_store.add_message(
            session_id=sess.id,
            role="user",
            content=(
                "Otium, can you check our Omnigraph for any contested claims on our oral GLP-1R lead "
                "`SW-204`, update the Living Wiki with a calm synthesis of the `Trp33` pocket vs "
                "`hERG` risk, and save the key rule to our Second Brain `MEMORY.md`?"
            ),
            created_at=t0,
        )
        agent_store.append_event(
            session_id=sess.id,
            event_type="tool.started",
            payload={
                "name": "memory.graph_cookbook_query",
                "arguments": {"query_name": "contested_claims", "scope": f"specialist:{otium_id or 'otium'}"},
                "toolCallId": "call_demo_omni_1",
            },
            notify=False,
        )
        agent_store.append_event(
            session_id=sess.id,
            event_type="tool.completed",
            payload={
                "name": "memory.graph_cookbook_query",
                "output": (
                    '{"cookbook":"05 Biomed research","matched_nodes":["Assay:herg-safety","Compound:sw-204","Hypothesis:oral-glp1-pocket"],'
                    '"contradictions":[{"source":"Assay:herg-safety","predicate":"Contradicts","target":"Compound:sw-204",'
                    '"summary":"QPatch hERG IC50 = 1.8 uM contradicts progression of unmodified SW-204"}]}'
                ),
                "isError": False,
                "durationSeconds": 0.04,
                "toolCallId": "call_demo_omni_1",
            },
            notify=False,
        )
        agent_store.append_event(
            session_id=sess.id,
            event_type="tool.started",
            payload={
                "name": "memory.wiki_write",
                "arguments": {
                    "slug": "oral-glp1r-program-brief",
                    "title": "Oral GLP-1R Agonist (SW-204 / SW-204b) Executive Brief",
                    "tags": "glp1r,sw-204,biomed",
                },
                "toolCallId": "call_demo_wiki_1",
            },
            notify=False,
        )
        agent_store.append_event(
            session_id=sess.id,
            event_type="tool.completed",
            payload={
                "name": "memory.wiki_write",
                "output": '{"ok":true,"slug":"oral-glp1r-program-brief","wikilinks":["index"]}',
                "isError": False,
                "durationSeconds": 0.02,
                "toolCallId": "call_demo_wiki_1",
            },
            notify=False,
        )
        agent_store.append_event(
            session_id=sess.id,
            event_type="tool.started",
            payload={
                "name": "memory.mutate",
                "arguments": {
                    "action": "add",
                    "scope": "global",
                    "content": "ACTIVE R&D ALERT (GLP-1R): Lead scaffold SW-204 hits cAMP EC50 = 1.4 nM (Trp33 pi-stack), but QPatch hERG IC50 = 1.8 uM (< 30x margin). Evaluate C-7 difluoro SW-204b on review/soren-herg-audit.",
                },
                "toolCallId": "call_demo_mem_1",
            },
            notify=False,
        )
        agent_store.append_event(
            session_id=sess.id,
            event_type="tool.completed",
            payload={
                "name": "memory.mutate",
                "output": '{"status":"applied","scope":"global"}',
                "isError": False,
                "durationSeconds": 0.01,
                "toolCallId": "call_demo_mem_1",
            },
            notify=False,
        )
        agent_store.add_message(
            session_id=sess.id,
            role="assistant",
            content=(
                "I checked the **05 Biomed research** Omnigraph (`contested_claims`), updated your Global Second Brain "
                "Living Wiki (`[[oral-glp1r-program-brief]]`), and saved the rule into `MEMORY.md`.\n\n"
                "### 1. What the Omnigraph Shows\n"
                "- **Supported Binding Mechanism (`polarity = support`)**: `Compound:sw-204` anchors the upper "
                "TM1/TM7 bundle of `Target:glp1r` via the `Trp33` pi-stack (`cAMP EC50 = 1.4 nM`).\n"
                "- **Active Contradiction (`polarity = contradict`)**: `Assay:herg-safety` (`QPatch IC50 = 1.8 µM`) "
                "directly contradicts advancing unmodified `SW-204` into dog telemetry.\n\n"
                "### 2. Second Brain & Living Wiki Updates\n"
                "- Linked `[[oral-glp1r-program-brief]]` from your Second Brain hub (`[[index]]`) alongside "
                "`[[user-operating-manual]]` and `[[model-routing-playbook]]`.\n"
                "- Isolated the **C-7 gem-difluoro** fix (`Compound:sw-204b-difluoro`) on branch `review/soren-herg-audit`."
            ),
            created_at=t0 + timedelta(seconds=10),
        )
        agent_store.add_message(
            session_id=sess.id,
            role="user",
            content=(
                "Why does the C-7 gem-difluoro substitution on SW-204b fix the hERG channel block without "
                "losing the Trp33 pi-stack?"
            ),
            created_at=t0 + timedelta(seconds=20),
        )
        agent_store.add_message(
            session_id=sess.id,
            role="assistant",
            content=(
                "It comes down to separating the **electrostatic basicity** of the tail from the **aromatic "
                "geometry** of the headgroup:\n\n"
                "1. **Why hERG binds `SW-204`**: The central cavity of the hERG (`Kv11.1`) potassium channel "
                "(`Tyr652` / `Phe656`) preferentially traps protonated lipophilic amines (`pKa ≈ 8.4`).\n"
                "2. **What C-7 `gem`-difluoro (`SW-204b`) changes**: Inductive electron withdrawal from the two "
                "fluorines drops the amine `pKa` from `8.4` to `6.9`, leaving `< 10%` protonated at physiological "
                "`pH 7.4` and shifting predicted `hERG IC50 > 30 µM`.\n"
                "3. **Why GLP-1R potency holds**: The dihydropyrazole—`Trp33` pi-stack and `Phe230` water network "
                "sit `11.5 Å` away in the extracellular vestibule (`[[glp1r-binding-pocket]]`), undisturbed by "
                "C-7 fluorination."
            ),
            created_at=t0 + timedelta(seconds=30),
        )
        created_ids.append(sess.id)

    soren_session_id = "demo-soren-sw204-red-team-audit"
    if soren_session_id not in existing_ids:
        sess2 = agent_store.ensure_session(
            soren_session_id,
            title="Soren · Red-Team Audit of SW-204 hERG Contradiction",
            workspace_path=None,
            specialist_id=soren_id,
        )
        t1 = now - timedelta(seconds=90)
        agent_store.add_message(
            session_id=sess2.id,
            role="user",
            content=(
                "Soren, review the SW-204 preclinical package and flag any assumptions that fail our "
                "safety gates."
            ),
            created_at=t1,
        )
        agent_store.append_event(
            session_id=sess2.id,
            event_type="tool.started",
            payload={
                "name": "memory.graph_record_claim",
                "arguments": {
                    "subject_id": "Assay:herg-safety",
                    "predicate": "Contradicts",
                    "object_id": "Compound:sw-204",
                    "polarity": "contradict",
                    "score": 0.94,
                },
                "toolCallId": "call_demo_soren_1",
            },
            notify=False,
        )
        agent_store.append_event(
            session_id=sess2.id,
            event_type="tool.completed",
            payload={
                "name": "memory.graph_record_claim",
                "output": '{"id":"edge:Assay:herg-safety->Contradicts->Compound:sw-204:contradict","polarity":"contradict"}',
                "isError": False,
                "durationSeconds": 0.03,
                "toolCallId": "call_demo_soren_1",
            },
            notify=False,
        )
        agent_store.add_message(
            session_id=sess2.id,
            role="assistant",
            content=(
                "### Red-Team Audit Findings (`polarity = contradict`)\n\n"
                "I have recorded a high-severity **`Contradicts`** edge (`score = 0.94`) between "
                "`Assay:herg-safety` and `Compound:sw-204` and staged a progression gate in your "
                "**Memory Approval Queue**:\n\n"
                "- **Unbound Cmax vs hERG IC50**: At the projected 30 mg/kg dog dose, unbound portal `Cmax` reaches "
                "`0.19 µM`, yielding a `9.5x` margin against `hERG IC50 = 1.8 µM` (target `> 30x`).\n"
                "- **Required Falsification Experiment**: Run automated QPatch on the C-7 difluoro analog "
                "`SW-204b` (`branch: review/soren-herg-audit`) before booking telemetry slots."
            ),
            created_at=t1 + timedelta(seconds=20),
        )
        created_ids.append(sess2.id)

    return created_ids
