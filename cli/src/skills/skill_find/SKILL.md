---
name: skill-find
description: Discover and install agent skills — first from the official Fastfold catalog (github.com/fastfold-ai/skills), then from the open skills.sh ecosystem (npx skills find). Use when the user wants to find, search, browse, list, add, enable, disable, or remove skills/capabilities (e.g. fold, MD, protein design, Google Calendar).
---

# Skill Find

> **This skill has no scripts.** Do not run `python scripts/...` for it. Use the
> `skills.manage` tool (actions: `find`, `list`, `info`, `install`, `remove`,
> `enable`, `disable`), and only fall back to the `sandwalk skills ...` CLI or
> `npx skills ...` when the tool is unavailable.

Help the user discover agent skills and install the ones they want. Search in two
tiers — the trusted Fastfold catalog first, then the broader open ecosystem — and
always scan live, because both catalogs grow over time.

- **Fastfold catalog (first-party, trusted):** https://github.com/fastfold-ai/skills (skills under `skills/<name>/`)
- **Open ecosystem (skills.sh):** https://skills.sh — the package manager for community skills

## When to Use This Skill
- The user asks to "find skills", "search skills", "what skills are available", "list sandwalk skills", or "add a skill".
- The user asks "how do I do X", "is there a skill for X", or "can you do X" where X is a specialized capability the agent lacks.
- The user wants to enable, disable, or remove an installed skill.
- The user wants to extend the agent with folding, MD, protein design, reporting, or other packaged workflows.

## Workflow

### Tier 1 — Fastfold catalog (try this first)
Scan live with the agent tool (catalog + ecosystem when `query` is set):

```
skills.manage(action="find")                   # Fastfold catalog listing
skills.manage(action="find", query="protein")  # catalog + public ecosystem (npx)
skills.manage(action="find", query="google calendar")
```

Present `name`, `install_source`, and `description` as a short numbered list.
Never auto-pick an ecosystem skill — confirm with the user first.

### Tier 2 — Suggested provider collections
When the Fastfold catalog lacks a capability, also consider these curated third-party
collections:

- **K-Dense-AI** — `K-Dense-AI/scientific-agent-skills`
- **Anthropic** — `anthropics/life-sciences`
- **DeepMind** — `google-deepmind/science-skills`

### Tier 3 — Open ecosystem (skills.sh)
`skills.manage(action="find", query="...")` already runs `npx -y skills find <query>`
when Node is available. If npx is missing, tell the user to install Node or browse
https://skills.sh. Prefer official/audited sources and higher install counts.

Do **not** use the desktop Skills UI Vercel login path from the agent — that catalog
browser stays Integrations → Vercel only.

### Confirm
Ask which skill(s) to install. Ecosystem skills run third-party code; call that out
before installing anything outside the Fastfold catalog.

### Install
```
skills.manage(action="install", source="fastfold-ai/skills@skills/<name>")
skills.manage(action="install", source="<owner>/<repo>@<subpath>")
skills.manage(action="install", source="https://github.com/<owner>/<repo>/tree/<ref>/<subpath>")
skills.manage(action="install", source="/path/to/skill-dir")
skills.manage(action="install", source="/path/to/skill.zip")   # or .skill bundle
```

If the tool returns `blocked: true`, ask the user to run `sandwalk skills add <source>`
or `sandwalk config set skills.allow_agent_install true`.

### Enable / disable / remove
```
skills.manage(action="list")
skills.manage(action="disable", name="<skill-name>")
skills.manage(action="enable", name="<skill-name>")
skills.manage(action="remove", name="<skill-name>")
```

### Confirm availability
Installed or re-enabled skills are picked up on the **next user message** (the system
prompt reloads each turn) — not mid-same-turn. They also appear in the composer `/`
menu after the UI refreshes. Verify with `skills.manage(action="list")`.

**Always include the skill slash mention in your reply** (e.g. `/fold` or
`/lab-notes`) so the desktop UI renders a clickable chip to skill details — same
as when the user inserts a skill via `/` in the composer.

## Sources You Can Install From
- Fastfold catalog (whole repo): `fastfold-ai/skills`
- Fastfold catalog (one skill): `fastfold-ai/skills@skills/<name>`
- Any GitHub URL: `https://github.com/<owner>/<repo>/tree/<ref>/<subpath>`
- GitHub shorthand: `<owner>/<repo>@<subpath>`
- A local path to a skill directory
- A local `.zip` or `.skill` archive containing `SKILL.md`

## Notes
- Installs use native `git clone` and fall back to `npx skills add` when needed.
- Both catalogs are dynamic — re-run discovery instead of assuming a fixed set.
- Default to the Fastfold catalog; reach for the open ecosystem only when needed.
