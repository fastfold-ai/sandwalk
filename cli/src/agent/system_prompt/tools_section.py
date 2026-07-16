"""Tool catalog prompt section: PTC compact catalog vs native per-tool listing."""

from __future__ import annotations

import logging

logger = logging.getLogger("system_prompt")


def build_tools_section(
    tool_mode: str,
    tool_names: list[str] | None,
    exclude_categories: set[str] | None,
    exclude_tools: set[str] | None,
) -> str:
    """Build the tool-catalog section. In PTC mode this is a compact domain-tool
    catalog (category counts + names-only listing); in native mode it lists key
    per-tool schemas exposed via MCP.
    """
    ptc = str(tool_mode).strip().lower() == "ptc"
    parts: list[str] = []

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

    return "".join(parts)
