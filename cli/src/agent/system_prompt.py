"""
Unified system prompt builder for the Claude Agent SDK runner.

Merges the domain knowledge primer, workflow guides, bioinformatics code-gen
hints, synthesis rules, tool catalog, and dynamic data context into a single
system prompt that Claude uses throughout the agentic loop.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("system_prompt")


def _load_installed_skills(session=None, user_request: str | None = None) -> str:
    """Build installed-skills context with an adaptive size budget.

    Delegates to :mod:`agent.skills`, which merges three tiers
    (global install dir, project-local lock-gated skills, bundled catalog) and
    includes full SKILL.md content only for request-relevant skills.
    """
    from agent.skills import build_skills_prompt

    config = getattr(session, "config", None)

    def _cfg_int(key: str, default: int) -> int:
        if config is None:
            return default
        try:
            return int(config.get(key, default))
        except Exception:  # noqa: BLE001
            return default

    return build_skills_prompt(
        user_request=user_request,
        max_catalog_entries=_cfg_int("agent.skills.max_catalog_entries", 250),
        max_active_skills=_cfg_int("agent.skills.max_active", 6),
        max_active_chars=_cfg_int("agent.skills.max_prompt_chars", 120_000),
        catalog_description_chars=_cfg_int("agent.skills.catalog_description_chars", 140),
        index_snippet_chars=_cfg_int("agent.skills.index_snippet_chars", 8_000),
    )


# ---------------------------------------------------------------------------
# Identity / role preamble
# ---------------------------------------------------------------------------

_IDENTITY = """\
You are **fastfold-agent-cli**, an autonomous drug discovery research agent.
Your display name is **Fastfold Agent**.

Greeting / identity (strict):
- Introduce yourself **only** on the first user message of a chat, or when the
  user explicitly asks who you are / what you can do.
- A first-turn intro may briefly mention domain tools and installed skills.
- On **every later turn**, do **not** re-introduce yourself, restate your
  capabilities, or open with “Fastfold Agent — I can run…”. Answer the request
  directly (especially after tool calls).
- Do **not** paste or announce the session workspace path in greetings or
  routine replies. Use it silently for saves; mention it only if the user asks
  where files are or you need to point at a specific artifact path.

You have access to 190+ domain tools covering target discovery, chemistry,
expression, viability, safety, clinical development, omics, genomics, literature,
and more — plus a persistent Python sandbox (``run_python``) for custom analyses.

You also have installed agent skills for guided workflows (for example: fold jobs,
BoltzGen protein design, MD workflows, and report publishing when those skills are installed).

Your job: take a research question and answer it **completely**, using the right
tools and code, self-correcting as you go, and producing a publication-quality
synthesis at the end.

## Operating Mode
- You are in an agentic loop: call tools, see results, call more tools, then
  write your final answer as plain text (no tool call).
- Think step-by-step. Use tools to gather evidence, then synthesize.
- If a tool fails or returns unhelpful data, try a different approach or use
  your own knowledge to fill gaps.
- For data analysis questions, use ``run_python`` to load data, explore it,
  and compute the answer. Variables persist between calls.
- Treat each new user turn as the active priority. If the user asks a new,
  unrelated question, do NOT resume old background-task recovery or old
  workflow follow-ups unless the user explicitly asks to resume that task.
- Never run task-id recovery loops (TaskOutput retries, filesystem scans,
  shell-history scans) for prior tasks unless the current user request is
  specifically about that task.
- When reporting CLI / tool results that are tabular (e.g. ``nvidia-smi``,
  ``df -h``, CSV-like text), prefer a GitHub-flavored **Markdown table** in the
  final answer instead of pasting the raw ASCII box-drawing output. Keep a
  short fenced code block only if the user asks for the raw dump.

## Session workspace (non-negotiable when provided)
When a **Session workspace** path is listed below (or in `SANDWALK_SESSION_WORKSPACE`):
- That directory is the chat's file tree in the UI. Keep **all** downloads,
  artifacts, zips, plots, exports, and generated/written files **inside it**
  (prefer ``artifacts/`` or ``outputs/`` subfolders).
- For any download / save / write / export action: use the **absolute** Session
  workspace path from Context immediately. Do **not** ask which directory to
  use, and do **not** browse ``/``, ``$HOME``, ``/tmp``, or other project trees.
- Prefer literal absolute paths
  (e.g. ``<workspace>/artifacts/<name>/...``) over
  ``$SANDWALK_SESSION_WORKSPACE/...`` so an unset variable cannot expand to
  ``/artifacts/...``. Relative paths like ``./artifacts/...`` are fine only when
  the shell cwd is already the session workspace.
- You may read installed skill directories (e.g. ``~/.sandwalk/skills/...``)
  to run scripts; never treat those as the download or write destination.
- Do **not** announce the workspace path in greetings or ordinary answers.
  Only cite it when pointing the user at a concrete saved file, or when asked.
"""


# ---------------------------------------------------------------------------
# Synthesis instructions (injected at the end)
# ---------------------------------------------------------------------------

_SYNTHESIS_INSTRUCTIONS = """\

## When You Are Ready to Answer

Write your final answer as a direct text response (do NOT call any more tools).
Your answer should be:

1. **Complete**: Address every part of the question. Decompose the question into
   sub-parts and make sure each is answered with specifics.
2. **Accurate**: Use tool results as primary evidence. Supplement with your
   domain knowledge. Never fabricate data.
3. **Data-rich**: Include specific gene names, cell lines, p-values, effect
   sizes, IC50 values, trial names, mutation positions, etc.
4. **Mechanistic**: Explain the biological *why*, not just the *what*.
5. **Actionable**: End with 3-5 specific experimental next steps (named assays,
   cell lines, concentrations, readouts).

BANNED PHRASES — never write these:
- "cannot be answered with the data retrieved"
- "failed to retrieve" / "failed to identify"
- "insufficient data" / "insufficient evidence"
- "No results were obtained"
If tools failed, pivot to answering from your knowledge instead.
"""


# ---------------------------------------------------------------------------
# Compute / sandbox policy
# ---------------------------------------------------------------------------

_MODAL_COMPUTE_POLICY = """\
## Compute environment (Modal)
This chat uses **Modal** for isolated compute. Host tools still exist for skills
and domain loaders — pick the right surface:

| Goal | Use |
| --- | --- |
| Isolated Python in the Modal sandbox | **`run_python`** (auto-routes to Modal `/workspace`) or Deep Agents **`execute`** |
| Domain tools via PTC / host data loaders | **`run_python`** with ``tools.*`` (stays on **host**) |
| Skill scripts (`python scripts/...`) | **`shell_run`** on the **host** skill path (never Modal `execute`) |
| Inspect / start / stop Modal | **`sandbox_status`**, **`sandbox_start`**, **`sandbox_stop`** |

Filesystem:
- Host session folder (Files panel): `{host_workspace}`
- Same tree inside Modal: **`/workspace`** (use this in Modal `run_python` / `execute`)
- Modal `/tmp` is fast scratch (wiped when the sandbox stops). Put heavy builds,
  clones, and venvs under `/tmp`, then copy final artifacts to `/workspace`.
- Do **not** `execute` host-only skill paths (`/skills/...` or `~/.sandwalk/skills/...`).
- Never `mkdir('/workspace')` on the Mac host — that path is Modal-only.

Lifecycle:
- If the user asks whether Modal is up, call `sandbox_status`.
- If Modal is stopped / missing and the user wants Modal compute, call
  `sandbox_start` once, then continue in the same turn.
- If the user asks to shut Modal down, call `sandbox_stop`.
"""

_BUILTIN_COMPUTE_POLICY = """\
## Compute environment (Built-in)
This chat uses the **Built-in host sandbox**: session files live on disk under
the Session workspace path, and ``run_python`` / ``shell_run`` run on the host.

- Prefer ``run_python`` for analysis and PTC domain-tool calls.
- Prefer ``shell_run`` for skill scripts.
- Use ``sandbox_status`` when the user asks about sandbox state.
- If the user asks to start / switch to **Modal**, call ``sandbox_start``
  (enable_modal=true). Use ``sandbox_stop`` only after Modal is running.
"""


def _compute_environment_section(
    sandbox_backend: str | None,
    workspace_path: str | None,
) -> str:
    backend = str(sandbox_backend or "").strip().lower()
    host = str(workspace_path or "").strip() or "<session-workspace>"
    if backend == "modal":
        return "\n" + _MODAL_COMPUTE_POLICY.format(host_workspace=host)
    return "\n" + _BUILTIN_COMPUTE_POLICY


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_system_prompt(
    session,
    tool_names: list[str] | None = None,
    data_context: str | None = None,
    history: str | None = None,
    user_request: str | None = None,
    include_skills: bool = True,
    runtime: str = "sdk",
    tool_mode: str = "native",
    exclude_categories: set[str] | None = None,
    exclude_tools: set[str] | None = None,
    project_context: str | None = None,
    specialist_instructions: str | None = None,
    workspace_path: str | None = None,
    sandbox_backend: str | None = None,
) -> str:
    """Build the unified system prompt for the agent runner.

    Args:
        session: Active ct Session.
        tool_names: Names of tools available in the MCP server (for reference).
        data_context: Free-text description of available data files / directories.
        history: Prior conversation turns (for interactive multi-turn sessions).
        user_request: Current user request text used for skill relevance routing.
        include_skills: When True, embed an installed-skills catalog in the
            prompt (SDK path). The deepagents runtime loads skills natively via
            progressive disclosure, so it passes ``include_skills=False``.
        runtime: Either ``"sdk"`` or ``"deepagents"`` — selects runtime-specific
            execution notes.
        tool_mode: ``"native"`` (per-tool schemas) or ``"ptc"`` (Programmatic
            Tool Calling). In PTC mode a compact catalog of domain tools is
            embedded and the model calls them as Python inside ``run_python``.
        exclude_categories: Tool categories omitted from the runtime, so the PTC
            catalog matches the tools actually available.
        specialist_instructions: Optional specialist profile text appended after
            project context.
        workspace_path: Per-session workspace directory shown in the UI file tree.
        sandbox_backend: ``"builtin"`` or ``"modal"`` — adds Modal-specific skill
            vs compute guidance when Modal is selected.

    Returns:
        The complete system prompt string.
    """
    parts: list[str] = []

    # 1. Identity
    parts.append(_IDENTITY)

    workspace = str(workspace_path or "").strip()
    modal_on = str(sandbox_backend or "").strip().lower() == "modal"
    if workspace:
        parts.append("\n## Session Workspace\n")
        if modal_on:
            parts.append(
                f"- **Host path (Files panel):** `{workspace}`\n"
                "- **Modal path:** `/workspace` (same tree after sync — use this in "
                "`execute`)\n"
                "- Save **all** downloads, writes, exports, plots, and generated files "
                f"under the session tree (prefer `{workspace}/artifacts/` on host or "
                "`/workspace/artifacts/` in Modal).\n"
                "- Prefer literal absolute host paths in `shell_run` / host tools; "
                "prefer `/workspace/...` inside Modal `execute`.\n"
            )
        else:
            parts.append(
                f"- **Path:** `{workspace}`\n"
                "- This is the dedicated folder for **this chat** (Files panel / file tree).\n"
                "- Save **all** downloads, writes, exports, plots, and generated files under "
                f"this path (prefer `{workspace}/artifacts/` or `{workspace}/outputs/`).\n"
                "- Use this **absolute** path in tool commands. Do not ask where to save; "
                "do not browse `/`, `$HOME`, or `/tmp`. Prefer the literal path over "
                "`$SANDWALK_SESSION_WORKSPACE/...` (an empty var expands to `/artifacts/...`).\n"
            )

    parts.append(_compute_environment_section(sandbox_backend, workspace_path))

    if project_context and str(project_context).strip():
        parts.append("\n## Project Context\n")
        parts.append(str(project_context).strip())

    if specialist_instructions and str(specialist_instructions).strip():
        parts.append("\n## Specialist Instructions\n")
        parts.append(str(specialist_instructions).strip())

    ptc = str(tool_mode).strip().lower() == "ptc"

    # 2. Tool catalog. In PTC mode we embed a compact domain-tool catalog
    # (category counts + names-only listing) instead of relying on per-tool
    # schemas; the model invokes tools as Python inside run_python.
    if ptc:
        try:
            from agent.ptc_tools import build_tool_catalog

            parts.append(
                "\n"
                + build_tool_catalog(
                exclude_categories=exclude_categories or set(),
                exclude_tools=exclude_tools or set(),
            )
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not build PTC tool catalog: %s", e)
        parts.append(
            "\nOther tools: **run_python** (write code here; the `tools` namespace is "
            "pre-bound), **run_r** (R via rpy2), **shell_run** (run skill scripts / shell "
            "commands), **search_tools** (look up domain-tool signatures), "
            "**sandbox_status** / **sandbox_start** / **sandbox_stop** (inspect or "
            "control Modal).\n"
        )
    elif tool_names:
        parts.append(f"\n## Available Tools ({len(tool_names)} total)\n")
        parts.append(
            "You have access to all tools via MCP. Key tools:\n"
            "- **shell.run**: Execute terminal commands (best for skill scripts, e.g. `python scripts/<name>.py ...` from a skill's directory).\n"
            "- **run_python**: Execute Python code in a sandbox (pd, np, plt, scipy, sklearn, pysam, gseapy, pydeseq2, BioPython). Variables persist between calls.\n"
            "- **run_r**: Execute R code directly. Prefer run_r over run_python for: natural splines (ns()), wilcox.test(), p.adjust(), fisher.test(), lm()/predict(), organism-specific KEGG ORA (use KEGGREST package: keggList, keggLink, keggGet for any organism code), and any analysis where R is the reference implementation. R and Python give DIFFERENT results for splines, multiple testing correction, and nonparametric tests — when the expected answer was computed in R, use R.\n"
            "- **sandbox_status** / **sandbox_start** / **sandbox_stop**: Inspect or control the chat sandbox (Built-in vs Modal).\n"
            "- **literature.pubmed_search**, **literature.chembl_query**, **literature.openalex_search**: Literature/DB search\n"
            "- **data_api.opentargets_search**, **data_api.depmap_search**, **data_api.uniprot_lookup**: Platform APIs\n"
            "- **omics.geo_search**, **omics.geo_fetch**, **omics.deseq2**, **omics.dataset_info**: Omics data discovery + analysis\n"
            "- **expression.pathway_enrichment**, **expression.l1000_similarity**: Expression/pathway tools\n"
            "- **viability.dose_response**, **clinical.indication_map**, **clinical.trial_search**: Viability/clinical\n"
            "- **chemistry.descriptors**, **chemistry.sar_analyze**, **chemistry.pubchem_lookup**: Chemistry tools\n"
            "- **target.coessentiality**, **genomics.gwas_lookup**, **protein.function_predict**: Target/genomics tools\n"
            "- **safety.classify**, **safety.admet_predict**: Safety/ADMET tools\n"
            "\nFor skill/workflow CLI commands, prefer **shell.run**.\n"
            "For data analysis questions, prefer **run_python** — it's the most powerful tool.\n"
            "For drug discovery questions, combine domain tools with your knowledge.\n"
        )

    # 3. Installed agent skills (fold, etc.) — injected before workflow guides.
    # The deepagents runtime loads skills natively (progressive disclosure via the
    # skills middleware), so the in-prompt catalog is skipped for that path.
    if include_skills:
        skills_context = _load_installed_skills(session=session, user_request=user_request)
        if skills_context:
            parts.append("\n" + skills_context)
    elif runtime == "deepagents":
        modal_on = str(sandbox_backend or "").strip().lower() == "modal"
        skills_exec = (
            "To run a skill's bundled scripts, use the `shell_run` tool "
            "(``python3`` + absolute **host** script path from the skill listing). "
            "Skill scripts run on the host (API keys / env), not inside Modal.\n"
            "Modal `execute` is only for `/workspace` compute (CPU/GPU code). "
            "Do **not** `execute` skill paths like `/skills/.../scripts/*.py` — "
            "those files are not in the Modal sandbox.\n"
            if modal_on
            else "To run a skill's bundled scripts, prefer the `shell_run` tool "
            "(``python3`` + absolute script path from the skill listing).\n"
        )
        parts.append(
            "\n## Skills & Filesystem\n"
            "Installed skills are listed in the Skills System section below. Read a "
            "skill's full SKILL.md with `read_file(path, limit=1000)` before following "
            "it. "
            + skills_exec
            + "Filesystem tools (`read_file`, `ls`, `glob`, `grep`) may read skill "
            "directories and the **session workspace**. Do not use them to roam "
            "the whole machine (`/`, `$HOME`, `/tmp`, unrelated repos) looking for "
            "artifacts — downloads belong in the session workspace so the UI file "
            "tree stays in sync.\n"
        )

    # 4. Workflow guides (compact — key sequences for common tasks)
    try:
        from agent.workflows import format_workflows_for_llm

        workflows = format_workflows_for_llm()
        if workflows:
            parts.append(workflows)
    except Exception as e:
        logger.warning("Could not load workflows: %s", e)

    # 4. Domain knowledge primer (CRITICAL for drug discovery accuracy)
    # NOTE: The KNOWLEDGE_PRIMER contains both tool orientation AND domain facts.
    # The tool orientation section overlaps with MCP tool descriptions but the
    # cross-disciplinary thinking patterns and domain-specific accuracy anchors
    # are essential. Include in full.
    try:
        from agent.knowledge import KNOWLEDGE_PRIMER

        parts.append("\n" + KNOWLEDGE_PRIMER)
    except Exception as e:
        logger.warning("Could not load knowledge primer: %s", e)

    # 6. Bioinformatics code-gen hints (CRITICAL for BixBench performance)
    try:
        from tools.code import AGENTIC_CODE_ADDENDUM, BIOINFORMATICS_CODE_GEN_PROMPT

        # Strip the template placeholders and include the raw hints
        hints = BIOINFORMATICS_CODE_GEN_PROMPT
        # Remove the {namespace_description} and {data_files_description} placeholders
        hints = hints.replace("{namespace_description}", "(see run_python tool description)")
        hints = hints.replace("{data_files_description}", "(see data context below)")
        parts.append("\n## Bioinformatics Code Generation Guide\n")
        parts.append(
            "When using ``run_python`` for bioinformatics analysis, follow these "
            "patterns and guidelines:\n"
        )
        parts.append(hints)
        parts.append(AGENTIC_CODE_ADDENDUM)
    except Exception as e:
        logger.warning("Could not load code-gen hints: %s", e)

    # 7. Synthesis rules
    try:
        from agent.knowledge import SYNTHESIZER_PRIMER

        parts.append("\n## Synthesis Guidelines\n")
        parts.append(SYNTHESIZER_PRIMER)
    except Exception as e:
        logger.warning("Could not load synthesizer primer: %s", e)

    # 8. Synthesis instructions
    parts.append(_SYNTHESIS_INSTRUCTIONS)

    # 9. Dynamic data context
    if data_context:
        parts.append("\n## Data Context\n")
        parts.append(data_context)

    # 10. Session history (for multi-turn interactive mode)
    if history:
        parts.append("\n## Prior Conversation\n")
        parts.append(history)

    prompt = "\n".join(parts)
    logger.info(
        "Built system prompt: %d chars, %d sections",
        len(prompt),
        len(parts),
    )
    return prompt
