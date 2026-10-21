---
name: knowledge-steward
description: Curate Sandwalk's persistent Memory (USER.md, MEMORY.md, Specialist PRIORS.md), Living Markdown Wiki ([[wikilinks]]), and Knowledge Graph (Omnigraph cookbooks, SPIKE signals/insights, and supporting vs. contradicting claims).
author: sandwalk
category: Built-in
version: 1.0.0
---

# Knowledge & Memory Steward

Use this skill when capturing durable knowledge from a research, engineering, or analysis session, when organizing a project's Living Wiki, or when modeling structured claims and evidence in Sandwalk's Knowledge Graph.

## 1. Choose the Right Knowledge Tier

Sandwalk separates knowledge into three distinct tiers so the system prompt stays fast and bounded while deep domain context remains one tool call away:

1. **Bounded Snapshot Memory (`memory.mutate` -> `USER.md`, `MEMORY.md`, `PRIORS.md`)**:
   - **Purpose**: Compact facts that must be present at the start of every session without a search round-trip.
   - **`target="user"` (`USER.md`, ~1,375 chars)**: User identity, communication style, preferred stack, plotting/citation conventions.
   - **`target="memory"` / `"project"` (`MEMORY.md`, ~2,200 chars)**: Environment facts, dataset caveats (e.g., *"Exclude sample_04 due to low read depth"*), architectural decisions, and verified tool workarounds.
   - **`target="specialist"` (`PRIORS.md`)**: Persona cognitive priors, skepticism heuristics, and methodological biases for the active Specialist.
   - **Rule**: Keep entries dense and specific. Use `action="patch"` with a unique `old_text` span to update existing entries instead of duplicating them.

2. **Living Markdown Wiki (`wiki.read`, `wiki.write`, `wiki.list`)**:
   - **Purpose**: Multi-paragraph synthesized knowledge stored as real `.md` files on disk (`~/.sandwalk/memory/wiki/` and `<project>/.sandwalk/wiki/`).
   - **Format**: Include concise YAML-style metadata (`title`, `tags`, `summary`) and connect related concepts with `[[wikilinks]]` (e.g. `[[kras-g12d-dossier]]`, `[[assay-protocol-v2]]`).
   - **When to use**: Target dossiers, literature syntheses, dataset inventories, architecture runbooks, and onboarding briefs that are too long for `MEMORY.md`.

3. **Typed Knowledge Graph & Omnigraph Cookbooks (`graph.record_claim`, `graph.upsert_node`, `graph.cookbook_query`, `graph.branch`)**:
   - **Purpose**: Structured entities, directed relationships, and provenance-backed claims where **supporting vs. contradicting evidence** must be tracked explicitly instead of overwritten.
   - **SPIKE Modeling Convention**:
     - `Signal`: An observed dated fact from a paper, trial, experiment, or log.
     - `Pattern`: A recurring theme supported (or contradicted) by multiple Signals.
     - `Insight`: An analytical interpretation highlighting a Pattern and its implications.
     - `Assumption` / `Hypothesis`: A belief a Program or Decision rests on—always link new Signals that `Supports` or `Contradicts` an Assumption.

## 2. Operating Rules

- **Never fabricate provenance**: Every scientific or operational claim recorded via `graph.record_claim` must cite its `source_ref` (PMID, DOI, NCT ID, file path, or session ID).
- **Preserve contradictions**: When a new experiment or paper disagrees with an existing claim, record it with `polarity="contradict"` rather than deleting the prior claim. Contested claims are high-value signals for the user.
- **Isolate speculative exploration on branches**: When testing a speculative hypothesis or bulk-loading unverified extractions, create a graph branch first (`graph.branch(action="create", name="review/...")`).
- **Crystallize Knowledge into Reusable Skills (`memory.create_skill`)**: When the user asks to turn what we know about a topic, a Living Wiki page, or an Omnigraph Cookbook ontology into a reusable Skill, call `memory.create_skill(name=..., scope=..., topic=..., wiki_slug=..., custom_instructions=...)`. It writes `~/.sandwalk/skills/<slug>/SKILL.md` plus `references/{schema.pg,queries.gq,wiki-digest.md}` so any agent or Specialist can invoke `/<slug>`.

