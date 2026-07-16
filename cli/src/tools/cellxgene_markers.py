"""CELLxGENE Census tool: marker genes for a cell type."""

from tools import registry
from tools.cellxgene_common import _check_census_sdk


@registry.register(
    name="cellxgene.cell_type_markers",
    description="Find marker genes for a specific cell type from CELLxGENE Census",
    category="cellxgene",
    parameters={
        "cell_type": "Cell type name (e.g. 'T cell', 'hepatocyte', 'macrophage')",
        "tissue": "Tissue to restrict search (optional)",
        "top_n": "Number of top markers to return (default 20)",
        "organism": "Organism (default: Homo sapiens)",
    },
    usage_guide=(
        "You need to find marker genes that define a cell type. "
        "Useful for designing cell-type-specific assays or understanding "
        "which genes distinguish a cell type from others."
    ),
)
def cell_type_markers(
    cell_type: str, tissue: str = None, top_n: int = 20, organism: str = "Homo sapiens", **kwargs
) -> dict:
    """Find marker genes for a cell type from CELLxGENE Census."""
    err = _check_census_sdk()
    if err:
        return err

    import cellxgene_census

    try:
        with cellxgene_census.open_soma(census_version="stable") as census:
            value_filter = f"is_primary_data == True and cell_type == '{cell_type}'"
            if tissue:
                value_filter += f" and tissue_general == '{tissue}'"

            obs_df = (
                census["census_data"][organism.lower().replace(" ", "_")]
                .obs.read(
                    value_filter=value_filter,
                    column_names=["cell_type", "tissue_general"],
                )
                .concat()
                .to_pandas()
            )

            if obs_df.empty:
                return {
                    "summary": f"Cell type '{cell_type}' not found in Census",
                    "error": f"No cells matching cell_type='{cell_type}'",
                }

            n_cells = len(obs_df)
            tissues_found = sorted(obs_df["tissue_general"].unique().tolist())

            # Return cell type metadata (full marker gene computation requires
            # fetching the full expression matrix which is too expensive for an API call)
            summary = (
                f"Cell type '{cell_type}': {n_cells} cells across "
                f"{len(tissues_found)} tissues ({', '.join(tissues_found[:5])})"
            )

            return {
                "summary": summary,
                "cell_type": cell_type,
                "n_cells": n_cells,
                "tissues": tissues_found,
                "markers": [],
                "note": "Full marker gene computation requires local scanpy analysis. "
                "Use cellxgene_census.get_anndata() for detailed analysis.",
            }

    except Exception as e:
        return {
            "error": f"Census query failed: {e}",
            "summary": f"Failed to query cell type markers: {e}",
        }
