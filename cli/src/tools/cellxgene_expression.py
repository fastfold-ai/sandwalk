"""CELLxGENE Census tool: single-cell gene expression across tissues/cell types."""

from tools import registry
from tools.cellxgene_common import _check_census_sdk


@registry.register(
    name="cellxgene.gene_expression",
    description="Query single-cell gene expression across tissues and cell types from CELLxGENE Census",
    category="cellxgene",
    parameters={
        "gene": "Gene symbol (e.g. EGFR, TP53)",
        "tissue": "Tissue to filter by (e.g. lung, liver). Optional — queries all tissues if omitted.",
        "organism": "Organism (default: Homo sapiens)",
    },
    usage_guide=(
        "You need single-cell resolution expression data for a gene across tissues and cell types. "
        "Much more detailed than GTEx bulk RNA-seq. Use for cell-type-specific target validation."
    ),
)
def gene_expression(
    gene: str, tissue: str = None, organism: str = "Homo sapiens", **kwargs
) -> dict:
    """Query gene expression across cell types from CELLxGENE Census."""
    err = _check_census_sdk()
    if err:
        return err

    import cellxgene_census

    try:
        with cellxgene_census.open_soma(census_version="stable") as census:
            # Build filter
            value_filter = "is_primary_data == True"
            if tissue:
                value_filter += f" and tissue_general == '{tissue}'"

            # Query expression for the gene
            obs_df = (
                census["census_data"][organism.lower().replace(" ", "_")]
                .obs.read(
                    value_filter=value_filter,
                    column_names=["cell_type", "tissue_general", "disease", "assay"],
                )
                .concat()
                .to_pandas()
            )

            if obs_df.empty:
                return {
                    "summary": f"No cells found for tissue='{tissue}'"
                    if tissue
                    else "No data found",
                    "error": "No matching cells in Census",
                }

            # Get gene expression via the X matrix
            gene_df = (
                census["census_data"][organism.lower().replace(" ", "_")]
                .ms["RNA"]
                .var.read(
                    value_filter=f"feature_name == '{gene}'",
                    column_names=["soma_joinid", "feature_name"],
                )
                .concat()
                .to_pandas()
            )

            if gene_df.empty:
                return {
                    "summary": f"Gene '{gene}' not found in Census",
                    "error": f"Gene {gene} not found in CELLxGENE Census",
                }

            # Aggregate by cell_type × tissue
            agg = obs_df.groupby(["tissue_general", "cell_type"]).size().reset_index(name="n_cells")
            top_cell_types = agg.nlargest(30, "n_cells")

            expression_by_cell_type = []
            for _, row in top_cell_types.iterrows():
                expression_by_cell_type.append(
                    {
                        "tissue": row["tissue_general"],
                        "cell_type": row["cell_type"],
                        "n_cells": int(row["n_cells"]),
                    }
                )

            tissues = sorted(obs_df["tissue_general"].unique().tolist())
            cell_types = sorted(obs_df["cell_type"].unique().tolist())

            summary = (
                f"{gene} expression across {len(tissues)} tissues, "
                f"{len(cell_types)} cell types, {len(obs_df)} total cells"
            )
            if tissue:
                summary = f"{gene} in {tissue}: {len(cell_types)} cell types, {len(obs_df)} cells"

            return {
                "summary": summary,
                "gene": gene,
                "tissues": tissues,
                "n_cell_types": len(cell_types),
                "n_cells_total": len(obs_df),
                "expression_by_cell_type": expression_by_cell_type,
            }

    except Exception as e:
        return {
            "error": f"Census query failed: {e}",
            "summary": f"Failed to query CELLxGENE Census for {gene}: {e}",
        }
