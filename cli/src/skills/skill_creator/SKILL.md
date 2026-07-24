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

2. **Scaffold (prefer the tool).** Create + optionally install in one step:

   ```
   skills.manage(action="create", name="<skill-name>", install=true)
   skills.manage(action="create", name="<skill-name>", path="./skills", install=false)
   ```

   Or via the script (same scaffolder the tool wraps):

   ```bash
   python scripts/init_skill.py <skill-name> --path <output-dir> [--author "Your Name"] [--with-scripts]
   ```

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

6. **Install** (if create used `install=false`, or after packaging):

   ```
   skills.manage(action="install", source="<path/to/skill>")
   skills.manage(action="install", source="<path/to/skill.skill>")  # zip / .skill
   ```

   Also valid: GitHub URL or `owner/repo@subpath`.

7. **Verify.** `skills.manage(action="list")` — the skill should show your user name as author and category Created by Me.
   Tell the user it appears in the composer `/` menu and is usable on the **next
   user message** (not mid-same-turn), including the CLI (`sandwalk` / terminal agent).

8. **Always mention the skill in your reply** as a slash chip so the UI can link
   to skill details (same format as composer `/` inserts), e.g.:

   ```
   Installed /lab-notes — open it from Skills or type /lab-notes in the composer.
   ```

   Prefer the plain `/skill-name` form (not a markdown URL). Do this for create,
   install, enable, disable, and remove confirmations.

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
