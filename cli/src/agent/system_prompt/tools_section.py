"""Tool catalog prompt section: PTC compact catalog vs native per-tool listing."""

from __future__ import annotations

import logging

logger = logging.getLogger("system_prompt")


_PTC_RUNTIME_BLURB = (
    "\nOther tools: **run_python** (write code here; the `tools` namespace is "
    "pre-bound), **shell_run** (run skill scripts / shell "
    "commands), **search_tools** (look up domain-tool signatures), "
    "**sandbox_status** / **sandbox_start** / **sandbox_stop** (inspect or "
    "control Modal).\n"
)

_PTC_COMPACT = """\
## Domain tools (PTC)
Domain tools are available as ``tools.<category>.<name>(**kwargs)`` inside
``run_python``. Call **search_tools** to look up signatures by keyword. Prefer
``shell_run`` for skill scripts and ``run_python`` for analysis / domain calls.
"""

_PTC_STUB = """\
## Tools
Use ``run_python`` (``tools.*`` for domain calls), ``shell_run`` for skill
scripts, and ``search_tools`` to discover signatures. Use sandbox control tools
when the user asks about Local vs Modal.
"""


def build_tools_section(
    tool_mode: str,
    tool_names: list[str] | None,
    exclude_categories: set[str] | None,
    exclude_tools: set[str] | None,
    *,
    ptc_catalog: str = "full",
) -> str:
    """Build the tool-catalog section. In PTC mode this is a compact domain-tool
    catalog (category counts + names-only listing); in native mode it lists key
    per-tool schemas exposed via MCP.

    ``ptc_catalog``: ``full`` (default name list), ``compact``, or ``stub`` —
    controlled by Knowledge Level.
    """
    ptc = str(tool_mode).strip().lower() == "ptc"
    parts: list[str] = []
    catalog_mode = str(ptc_catalog or "full").strip().lower()

    if ptc:
        if catalog_mode == "stub":
            parts.append("\n" + _PTC_STUB)
        elif catalog_mode == "compact":
            parts.append("\n" + _PTC_COMPACT)
            parts.append(_PTC_RUNTIME_BLURB)
        else:
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
            parts.append(_PTC_RUNTIME_BLURB)
    elif tool_names:
        parts.append(f"\n## Available Tools ({len(tool_names)} total)\n")
        parts.append(
            "You have access to all tools via MCP. Key tools:\n"
            "- **shell.run**: Execute terminal commands (best for skill scripts, e.g. `python scripts/<name>.py ...` from a skill's directory).\n"
            "- **run_python**: Execute Python code in a sandbox (pd, np, plt, scipy, sklearn, pysam, gseapy, pydeseq2, BioPython). Variables persist between calls.\n"
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

    return "".join(parts)
