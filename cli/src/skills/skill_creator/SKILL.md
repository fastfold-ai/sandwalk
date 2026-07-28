---
name: skill-creator
description: Create new agent skills and iteratively improve them. Use when the user wants to build, scaffold, author, validate, package, enable, or install a new user-created skill for the Sandwalk / Fastfold agent CLI.
---

# Skill Creator

Create a new agent skill end to end: scaffold, write, validate, package, and install.

## When to Use This Skill
- The user wants to create/author a new skill.
- The user wants to scaffold a `SKILL.md`, validate one, or package a skill for sharing.

## What a Skill Is
A directory containing a required `SKILL.md` (YAML frontmatter + Markdown body) and
optional `scripts/`, `references/`, and `assets/` folders. Frontmatter requires
`name` (kebab-case) and `description` (one sentence with trigger phrases).
User-authored skills set `author` to the local user name and
`category: Created by Me` so they appear under that author/category in Skills.

## Workflow

1. **Clarify.** Ask what the skill should do, its trigger phrases, and whether it needs scripts.

2. **Scaffold a draft with the tool (required).** Do not create the skill
   directory with `mkdir`, `write_file`, or `scripts/init_skill.py`; those paths
   are drafts and do not register a skill with Sandwalk. Call:

   ```
   skills.manage(action="create", name="<skill-name>", install=false, with_scripts=true)
   ```

   Use the returned `path` for all authoring. A successful create result with
   `install=false` means **draft created, not installed, not available**.

3. **Author.** Edit the generated `SKILL.md`:
   - Keep it under ~500 lines; move long docs to `references/`.
   - Write a specific `description` with trigger phrases so the agent activates it correctly.
   - Prefer bundled scripts over inline code; document each script with a one-line purpose.
   - Keep `author` (user name) and `category: Created by Me`.

4. **Validate.** Check frontmatter, naming, and leftover TODO placeholders:

   ```bash
   python scripts/quick_validate.py <path/to/skill> [--strict]
   ```

5. **Package (optional).** Produce a shareable `<name>.skill` zip:

   ```bash
   python scripts/package_skill.py <path/to/skill> [output-dir]
   ```

6. **Install (required unless the user declines).** After authoring and
   validation, call the approval-gated installer with the exact draft path:

   ```
   skills.manage(action="install", source="<path/to/skill>")
   ```

   This displays the desktop/CLI approval prompt. Do not replace it with a chat
   question. If the user rejects or the installer fails, say **created as a
   draft but not installed** and provide the draft path.

7. **Verify (hard completion gate).** Require the install result to contain
   `installation_verified=true`, then call:

   ```
   skills.manage(action="info", name="<skill-name>")
   ```

   Only say “installed”, “available”, “ready to use”, or that it appears in the
   composer when both calls succeed and `info` confirms the skill is installed
   and enabled. Validation alone never proves installation. The skill becomes
   usable on the **next user message** (not mid-same-turn), including the CLI.

8. **Mention the slash skill only after verified installation** so the UI can
   link to its installed details, e.g.:

   ```
   Installed /lab-notes — open it from Skills or type /lab-notes in the composer.
   ```

   Prefer the plain `/skill-name` form (not a markdown URL). Do not present a
   draft-only skill as an active slash command.

## Enable / disable / remove
```
skills.manage(action="disable", name="<skill-name>")
skills.manage(action="enable", name="<skill-name>")
skills.manage(action="remove", name="<skill-name>")
```

## Best Practices
- Name directory and frontmatter `name` consistently (kebab-case recommended).
- Make the `description` specific and trigger-rich; it determines when the skill activates.
- Keep scripts dependency-light; read secrets from environment variables, never CLI flags.
- Write progress to stderr and machine-readable output to stdout.

## Resources
- `scripts/init_skill.py` — scaffold a new skill directory
- `scripts/quick_validate.py` — validate frontmatter and naming
- `scripts/package_skill.py` — package a skill into a `.skill` zip
