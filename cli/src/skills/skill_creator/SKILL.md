---
name: skill-creator
description: Create new agent skills and iteratively improve them. Use when the user wants to build, scaffold, author, validate, or package a new skill for the Fastfold agent CLI.
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

## Workflow

1. **Clarify.** Ask what the skill should do, its trigger phrases, and whether it needs scripts.

2. **Scaffold.** Create the directory structure with a template `SKILL.md`:

   ```bash
   python scripts/init_skill.py <skill-name> --path <output-dir>
   ```

   Default output dir is the current working directory.

3. **Author.** Edit the generated `SKILL.md`:
   - Keep it under ~500 lines; move long docs to `references/`.
   - Write a specific `description` with trigger phrases so the agent activates it correctly.
   - Prefer bundled scripts over inline code; document each script with a one-line purpose.

4. **Validate.** Check frontmatter, naming, and leftover TODO placeholders:

   ```bash
   python scripts/quick_validate.py <path/to/skill> [--strict]
   ```

5. **Package (optional).** Produce a shareable `<name>.skill` zip:

   ```bash
   python scripts/package_skill.py <path/to/skill> [output-dir]
   ```

6. **Install.** Install the new skill so the agent can use it:
   - Local: `fastfold skills add <path/to/skill>` (or `/skills-add <path>`)
   - Or via the tool: `skills.manage(action="install", source="<path/to/skill>")`

   Installed skills are available on the next message (the system prompt reloads each turn).

## Best Practices
- Name directory and frontmatter `name` consistently (kebab-case recommended).
- Make the `description` specific and trigger-rich; it determines when the skill activates.
- Keep scripts dependency-light; read secrets from environment variables, never CLI flags.
- Write progress to stderr and machine-readable output to stdout.

## Resources
- `scripts/init_skill.py` — scaffold a new skill directory
- `scripts/quick_validate.py` — validate frontmatter and naming
- `scripts/package_skill.py` — package a skill into a `.skill` zip
