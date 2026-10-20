---
name: omnigraph
description: Operate Sandwalk's local Omnigraph engine and runnable Cookbook Modes (Biomed Research, Pharma Intel, Industry Intel SPIKE, Context Graph, VC OS, Second Brain) for .pg schemas, .gq stored queries, hybrid BM25/vector search, and git-style graph branches.
author: sandwalk
category: Built-in
version: 1.0.0
---

# Omnigraph & Cookbook Modes

Sandwalk integrates a self-hosted local Omnigraph engine (`~/.sandwalk/bin/omnigraph` + `.omni` Lance storage) alongside its built-in SQLite + Knowledge Substrate fallback.

## 1. Runnable Cookbook Modes

Every Sandwalk scope (`global`, `project:<id>`, or `specialist:<id>`) binds an active Cookbook Mode that defines its **Ontology Layers**, **Node Types**, **Edge Predicates**, and **Stored Queries**:

| Cookbook ID | Name | Primary Layers & Node Types | Key Stored Queries |
|---|---|---|---|
| `biomed-research` | **05 Biomed Research** | *Entities* (`Gene`, `Protein`, `Compound`, `Disease`, `CellLine`) -> *Evidence* (`Paper`, `Dataset`, `AssayResult`) -> *Synthesis* (`Hypothesis`, `Claim`) | `contested_claims`, `evidence_for_target`, `hypothesis_support_matrix`, `recent_lab_findings` |
| `pharma-intel` | **02 Pharma Intel** | *External Pipeline* (`Compound`, `Mechanism`, `Trial`, `Company`, `Deal`, `RegulatoryAction`) -> *SPIKE* (`Signal`, `Pattern`, `Insight`) -> *Internal Thesis* (`Program`, `Assumption`, `Decision`, `OpenQuestion`) | `signals_contradicting_assumptions`, `decisions_at_risk`, `pipeline_by_mechanism`, `open_questions_status` |
| `industry-intel` | **01 Industry Intel** | *Sources* (`SourceArtifact`, `Element`) -> *SPIKE* (`Signal`, `Pattern`, `Insight`, `KnowHow`) | `recent_signals`, `emerging_patterns`, `contradicted_patterns`, `insights_by_element` |
| `context-graph` | **03 Context Graph** | *Org* (`Person`, `Team`, `Project`) -> *Evidence* (`Source`, `Claim`) -> *Commitments* (`Decision`, `ActionItem`) | `current_decisions`, `contested_claims`, `why_superseded`, `open_action_items` |
| `vc-os` | **04 VC OS** | *Network* (`Organization`, `Person`, `Deal`) -> *Thesis* (`InvestmentBelief`, `Signal`, `Meeting`, `ActionItem`) | `active_deals`, `signals_testing_beliefs`, `founder_network`, `follow_ups` |
| `second-brain` | **06 Second Brain** | *People & World* (`Person`, `Organization`) -> *Capture & Action* (`Note`, `Task`, `Project`, `Goal`, `Routine`, `Artifact`) | `active_goals_and_tasks`, `people_cadence`, `notes_by_topic`, `recent_artifacts` |

## 2. Using Built-In Graph Tools First

Prefer Sandwalk's built-in `graph.*` tools for everyday operations—they automatically resolve the active scope, cookbook schema, and `.omni` store:

- `graph.cookbook_query(query_name="contested_claims", scope="project")`: Run a pre-built stored query from the active cookbook.
- `graph.upsert_node(node_type="Assumption", slug="oral-glp1-tolerability", name="Oral GLP-1 matches injectable tolerability", properties={...})`: Add or update a typed node in the active ontology.
- `graph.record_claim(subject="signal:ct996-gi-ae", predicate="Contradicts", object="assumption:oral-glp1-tolerability", polarity="contradict", summary="...", source_ref="NCT05930405")`: Record a directed edge with provenance.
- `graph.branch(action="create" | "list" | "merge", name="review/hypothesis-1")`: Manage Git-style graph branches.

## 3. Direct CLI & Schema Adaptation (`schema.pg` / `queries.gq`)

When customizing a `.pg` schema or authoring new `.gq` stored queries with `~/.sandwalk/bin/omnigraph`:

- Use `//` comments in `.pg` and `.gq`.
- Declare `@key` on `slug: String` and `@index` on searchable text or enum properties.
- Every `.gq` block uses `query <name>(...) { match { ... } return { ... } }`.
- Use `bm25($n.summary, $q)` for full-text ranking and `rrf(nearest($n.embedding, $q), bm25($n.summary, $q))` with an explicit `limit` for hybrid search.
- Lint schema and queries before applying:
  ```bash
  ~/.sandwalk/bin/omnigraph lint --schema schema.pg --query queries.gq
  ```
