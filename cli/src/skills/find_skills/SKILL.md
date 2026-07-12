---
name: find-skills
description: Discover and install agent skills — first from the official Fastfold catalog (github.com/fastfold-ai/skills), then from the open skills.sh ecosystem (npx skills find). Use when the user wants to find, search, browse, list, or add new skills/capabilities (e.g. fold, MD, protein design) to the agent CLI.
---

# Find Skills

> **This skill has no scripts.** Do not run `python scripts/...` for it. Use the
> `skills.manage` tool (actions: `find`, `install`, `list`, `info`, `remove`), and
> only fall back to the `fastfold skills ...` CLI or `npx skills ...` when the tool is unavailable.

Help the user discover agent skills and install the ones they want. Search in two
tiers — the trusted Fastfold catalog first, then the broader open ecosystem — and
always scan live, because both catalogs grow over time.

- **Fastfold catalog (first-party, trusted):** https://github.com/fastfold-ai/skills (skills under `skills/<name>/`)
- **Open ecosystem (skills.sh):** https://skills.sh — the package manager for community skills

## When to Use This Skill
- The user asks to "find skills", "search skills", "what skills are available", "list fastfold skills", or "add a skill".
- The user asks "how do I do X", "is there a skill for X", or "can you do X" where X is a specialized capability the agent lacks.
- The user wants to extend the agent with folding, MD, protein design, reporting, or other packaged workflows.

## Workflow

### Tier 1 — Fastfold catalog (try this first)
The Fastfold catalog is first-party and curated. Scan it live with the `skills.manage` tool:

```
skills.manage(action="find")                   # list everything currently available
skills.manage(action="find", query="protein")  # filter by name/description/tag
```

Present the returned `name`, `install_source`, and `description` as a short numbered list.
(Equivalent CLI: `fastfold skills find [query]`.)

### Tier 2 — Suggested provider collections
When the Fastfold catalog lacks a capability, also consider these curated third-party
collections (install the whole collection, or browse it first). Each is installable with
`fastfold skills add <source>` or `npx skills add <source>`:

- **K-Dense-AI** — scientific agent skills: `K-Dense-AI/scientific-agent-skills` (https://github.com/K-Dense-AI/scientific-agent-skills)
- **Anthropic** — life-sciences skills: `anthropics/life-sciences` (https://github.com/anthropics/life-sciences#skills)
- **DeepMind** — science skills: `google-deepmind/science-skills` (https://github.com/google-deepmind/science-skills)

### Tier 3 — Open ecosystem (skills.sh)
For anything else, search the open ecosystem with the Skills CLI (requires Node/`npx`):

```
npx -y skills find <query>
```

`npx skills` is the package manager for the open agent-skills ecosystem (https://skills.sh).
When recommending ecosystem skills, **prefer quality signals**:
- Official / audited sources (e.g. Fastfold, Anthropic, Vercel) over unknown authors.
- Higher install counts (prefer ~1K+) and GitHub stars.
- Check the skills.sh leaderboard / "official" listings before suggesting niche repos.

Always summarize a few ranked options with their source and install command — do not auto-pick.

### Confirm
Ask the user which skill(s) to install. Never install without explicit confirmation.
Ecosystem skills run third-party code; call this out before installing anything outside the Fastfold catalog.

### Install
Prefer the agent tool when enabled:

```
skills.manage(action="install", source="fastfold-ai/skills@skills/<name>")
skills.manage(action="install", source="<owner>/<repo>@<subpath>")   # ecosystem skill
```

If the tool returns `blocked: true` (agent-initiated install disabled), tell the user to run one of:

- **One Fastfold skill (native):** `fastfold skills add fastfold-ai/skills@skills/<name>`
- **All Fastfold skills at once:** `fastfold skills add fastfold-ai/skills`
- **Inside the interactive session:** `/skills-add <install source>`
- **From the ecosystem (Node):** `npx skills add <owner>/<repo>` (optionally `--skill <name>`)
- Or enable agent installs: `fastfold config set skills.allow_agent_install true`

### Confirm availability
Installed skills are picked up on the next message (the system prompt reloads each turn) — no restart needed. Verify with `skills.manage(action="list")` or `fastfold skills list`.

## Sources You Can Install From
- Fastfold catalog (whole repo): `fastfold-ai/skills`
- Fastfold catalog (one skill): `fastfold-ai/skills@skills/<name>`
- Any GitHub URL: `https://github.com/<owner>/<repo>/tree/<ref>/<subpath>`
- GitHub shorthand: `<owner>/<repo>@<subpath>`
- A local path to a skill directory.

## Notes
- Installs use a native `git clone` and fall back to `npx skills add` automatically when needed.
- Both catalogs are dynamic — re-run discovery instead of assuming a fixed set of skills.
- Default to the Fastfold catalog; reach for the open ecosystem only when the catalog lacks the capability, and prefer trusted/popular/audited skills there.
