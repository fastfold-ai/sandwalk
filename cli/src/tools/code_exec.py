"""
code.execute: sandbox orchestration (single-shot + agentic) and the
registered ``code.execute`` tool.

Split from tools/code.py. Calls back into the ``tools.code`` facade for
``_generate_and_execute_code`` (via ``from tools import code as _code``) so
that ``patch("tools.code._generate_and_execute_code")`` in tests continues to
work regardless of which submodule performs the call.
"""

from pathlib import Path

from tools import code as _code
from tools import registry
from tools.code_agentic import _agentic_code_loop
from tools.code_prompts import (
    AGENTIC_CODE_ADDENDUM,
    CODE_GEN_SYSTEM_PROMPT,
    ERROR_RETRY_PROMPT,
    REFLECTION_PROMPT,
)
from tools.code_prompts_bio import BIOINFORMATICS_CODE_GEN_PROMPT
from tools.code_script import _extract_code, _generate_and_save_script, _is_script_authoring_goal


def _generate_and_execute_code(
    goal: str,
    system_prompt_template: str,
    session,
    prior_results=None,
) -> dict:
    """Shared code-gen helper: LLM code generation -> sandbox execution -> retry loop.

    Domain tools call this with a focused system prompt template containing
    ``{namespace_description}`` which gets filled with the sandbox's namespace
    description at runtime.

    Args:
        goal: Natural language description of the analysis to perform.
        system_prompt_template: System prompt with ``{namespace_description}``
            placeholder (and optionally ``{data_files_description}``).
        session: Active ct session (provides config, LLM, console).
        prior_results: Dict of prior step results to inject into the sandbox.

    Returns:
        Standard tool result dict with ``summary``, ``code``, ``stdout``, etc.
    """
    if session is None:
        return {
            "summary": "Code execution unavailable: no active session.",
            "error": "No session provided.",
        }

    from agent.sandbox import Sandbox

    config = session.config
    timeout = int(config.get("sandbox.timeout", 30))
    output_dir = config.get("sandbox.output_dir")
    max_retries = int(config.get("sandbox.max_retries", 2))
    llm = session.get_llm()

    # Collect extra read directories (e.g., capsule data dirs for bioinformatics mode)
    extra_read_dirs = []
    extra_read_str = config.get("sandbox.extra_read_dirs")
    if extra_read_str:
        for d in str(extra_read_str).split(","):
            d = d.strip()
            if d and Path(d).exists():
                extra_read_dirs.append(Path(d))

    # Create sandbox and load datasets
    sandbox = Sandbox(
        timeout=timeout,
        output_dir=output_dir,
        max_retries=max_retries,
        extra_read_dirs=extra_read_dirs or None,
    )
    sandbox.load_datasets()
    if prior_results:
        sandbox.inject_prior_results(prior_results)

    # Build the system prompt with namespace info
    ns_desc = sandbox.describe_namespace()
    format_kwargs = {"namespace_description": ns_desc}

    # Provide a data_files_description if the template expects one
    if "{data_files_description}" in system_prompt_template:
        format_kwargs["data_files_description"] = _describe_data_files(extra_dirs=extra_read_dirs)

    system_prompt = system_prompt_template.format(**format_kwargs)

    # ── Multi-turn agentic path ─────────────────────────────────────────
    max_turns = int(config.get("sandbox.max_turns", 0))
    if max_turns > 0:
        agentic_prompt = system_prompt + AGENTIC_CODE_ADDENDUM
        return _agentic_code_loop(
            goal=goal,
            system_prompt=agentic_prompt,
            llm=llm,
            sandbox=sandbox,
            session=session,
            max_turns=max_turns,
        )

    # ── Legacy single-shot path ─────────────────────────────────────────
    code = None
    exec_result = {"error": "No code generated"}

    for attempt in range(1, max_retries + 2):  # 1 initial + max_retries fixes
        if attempt == 1:
            user_msg = f"Goal: {goal}"
        else:
            user_msg = ERROR_RETRY_PROMPT.format(code=code, error=exec_result["error"])

        with session.console.status(
            f"[green]{'Generating' if attempt == 1 else 'Fixing'} code...[/green]",
            spinner="dots",
        ):
            response = llm.chat(
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.2,
            )

        code = _extract_code(response.content)
        exec_result = sandbox.execute(code)

        if exec_result["error"] is None:
            # Reflection: let the LLM review its own output for logical errors
            max_reflect = int(config.get("sandbox.max_reflect", 2))
            for reflect_turn in range(max_reflect):
                stdout_text = exec_result.get("stdout", "") or ""
                result_obj = exec_result.get("result")
                # Only reflect if there's meaningful output to check
                if not stdout_text and not result_obj:
                    break
                result_preview = str(result_obj)[:1000] if result_obj else "(no result dict)"
                reflect_msg = REFLECTION_PROMPT.format(
                    goal=goal,
                    code=code,
                    stdout=stdout_text[:3000],
                    result=result_preview,
                )
                with session.console.status(
                    f"[cyan]Reviewing output (turn {reflect_turn + 1})...[/cyan]",
                    spinner="dots",
                ):
                    try:
                        reflect_response = llm.chat(
                            system=system_prompt,
                            messages=[{"role": "user", "content": reflect_msg}],
                            temperature=0.2,
                        )
                    except Exception:
                        # Reflection is best-effort; if unavailable, keep current successful result.
                        break
                reflect_text = reflect_response.content.strip()
                if reflect_text.upper().startswith("LGTM"):
                    break  # LLM says output is correct
                # LLM returned corrected code — execute it
                fixed_code = _extract_code(reflect_text)
                if not fixed_code or fixed_code == code:
                    break  # No new code or same code — stop
                code = fixed_code
                exec_result = sandbox.execute(code)
                if exec_result["error"] is not None:
                    break  # New code errored — fall through to error retry

            # Return result (either original or reflection-fixed)
            if exec_result["error"] is None:
                summary = ""
                if exec_result["result"] and isinstance(exec_result["result"], dict):
                    summary = exec_result["result"].get("summary", "")
                if not summary and exec_result["stdout"]:
                    summary = exec_result["stdout"][:500]
                if not summary:
                    summary = "Code executed successfully."

                return {
                    "summary": summary,
                    "code": code,
                    "stdout": exec_result["stdout"],
                    "result": exec_result["result"],
                    "plots": exec_result["plots"],
                    "exports": exec_result["exports"],
                }

        if attempt > max_retries:
            break

    return {
        "summary": f"Code execution failed after {max_retries + 1} attempts: {exec_result['error'][:200]}",
        "error": exec_result["error"],
        "code": code,
        "stdout": exec_result.get("stdout", ""),
    }


def _describe_data_files(extra_dirs: list[Path] | None = None) -> str:
    """List data files in CWD and extra directories for domain tool prompts."""
    data_exts = {
        ".csv",
        ".tsv",
        ".xlsx",
        ".xls",
        ".parquet",
        ".vcf",
        ".bed",
        ".bam",
        ".fasta",
        ".fa",
        ".faa",
        ".fastq",
        ".gff",
        ".gtf",
        ".nwk",
        ".nex",
        ".tree",
        ".mafft",
        ".clipkit",
        ".aln",
        ".phy",
        ".gz",
        ".zip",
        ".rds",
        ".rdata",
        ".gmt",
        ".json",
    }

    def _scan_dir(directory: Path, label: str) -> list[str]:
        entries = []
        if not directory.exists():
            return entries
        try:
            for f in sorted(directory.rglob("*")):
                if f.is_file() and (f.suffix.lower() in data_exts):
                    size = f.stat().st_size
                    if size > 1_000_000:
                        size_str = f"{size / 1_000_000:.1f} MB"
                    elif size > 1_000:
                        size_str = f"{size / 1_000:.1f} KB"
                    else:
                        size_str = f"{size} bytes"
                    try:
                        rel = f.relative_to(directory)
                    except ValueError:
                        rel = f.name
                    entries.append(f"- {rel} ({size_str})")
        except PermissionError:
            pass
        return entries[:80]

    sections = []
    cwd = Path.cwd()
    cwd_files = _scan_dir(cwd, "working directory")
    if cwd_files:
        sections.append("Files in working directory:\n" + "\n".join(cwd_files))

    for d in extra_dirs or []:
        d_files = _scan_dir(d, str(d))
        if d_files:
            sections.append(f"Files in {d}:\n" + "\n".join(d_files))
            sections.append(f"\nData directory accessible for reading: {d}")

    if not sections:
        return "No data files found in the working directory."
    return "\n\n".join(sections)


@registry.register(
    name="code.execute",
    description="Generate and execute custom Python analysis code",
    category="code",
    parameters={"goal": "Natural language description of the analysis to perform"},
    usage_guide=(
        "Use ONLY when no pre-built tool covers the analysis. Good for: custom visualizations, "
        "statistical tests, data exploration, combining/filtering data in novel ways, generating plots. "
        "Pre-built tools are preferred — this is the escape hatch."
    ),
)
def execute(goal: str, _session=None, _prior_results=None, **kwargs) -> dict:
    """Generate and execute Python code for a custom analysis goal."""
    if _session is None:
        return {
            "summary": "Code execution unavailable: no active session.",
            "error": "No session provided. code.execute requires an active ct session.",
        }

    # Handle "write script to file" goals directly (outside sandbox execution path).
    if _is_script_authoring_goal(goal):
        llm = _session.get_llm()
        max_retries = int(_session.config.get("sandbox.max_retries", 2))
        return _generate_and_save_script(
            goal=goal,
            llm=llm,
            max_retries=max_retries,
            session=_session,
        )

    # Use bioinformatics prompt when data files are present in the sandbox,
    # otherwise use the generic code-gen prompt.  Domain-specific knowledge
    # (phylo, KEGG ORA, variant classification) lives in the dedicated domain
    # tools (phylo.analyze, omics.kegg_ora, genomics.variant_classify) which
    # the planner selects directly.
    prompt = (
        BIOINFORMATICS_CODE_GEN_PROMPT
        if _session.config.get("agent.bioinformatics_mode")
        else CODE_GEN_SYSTEM_PROMPT
    )

    return _code._generate_and_execute_code(
        goal=goal,
        system_prompt_template=prompt,
        session=_session,
        prior_results=_prior_results,
    )
