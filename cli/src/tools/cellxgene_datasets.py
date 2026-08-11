"""CELLxGENE Census tool: dataset search by tissue/disease/assay."""

from tools import registry
from tools.cellxgene_common import _check_census_sdk


@registry.register(
    name="cellxgene.dataset_search",
    description="Search CELLxGENE Census for datasets by tissue, disease, or assay",
    category="cellxgene",
    parameters={
        "tissue": "Tissue to search for (e.g. 'lung', 'brain'). Optional.",
        "disease": "Disease to search for (e.g. 'COVID-19', 'lung adenocarcinoma'). Optional.",
        "assay": "Assay type to filter (e.g. '10x 3\\' v3', 'Smart-seq2'). Optional.",
        "organism": "Organism (default: Homo sapiens)",
    },
    usage_guide=(
        "You want to find what single-cell datasets are available in CELLxGENE "
        "for a tissue, disease, or assay type. Use to scope data availability "
        "before deeper analysis."
    ),
)
def dataset_search(
    tissue: str = None,
    disease: str = None,
    assay: str = None,
    organism: str = "Homo sapiens",
    **kwargs,
) -> dict:
    """Search CELLxGENE Census for datasets matching criteria."""
    err = _check_census_sdk()
    if err:
        return err

    import cellxgene_census

    try:
        with cellxgene_census.open_soma(census_version="stable") as census:
            filters = ["is_primary_data == True"]
            if tissue:
                filters.append(f"tissue_general == '{tissue}'")
            if disease:
                filters.append(f"disease == '{disease}'")
            if assay:
                filters.append(f"assay == '{assay}'")

            value_filter = " and ".join(filters)

            obs_df = (
                census["census_data"][organism.lower().replace(" ", "_")]
                .obs.read(
                    value_filter=value_filter,
                    column_names=["dataset_id", "tissue_general", "disease", "assay", "cell_type"],
                )
                .concat()
                .to_pandas()
            )

            if obs_df.empty:
                return {
                    "summary": "No datasets found matching criteria",
                    "datasets": [],
                }

            # Aggregate by dataset
            datasets = (
                obs_df.groupby("dataset_id")
                .agg(
                    n_cells=("cell_type", "size"),
                    tissues=("tissue_general", lambda x: sorted(x.unique().tolist())),
                    diseases=("disease", lambda x: sorted(x.unique().tolist())),
                    assays=("assay", lambda x: sorted(x.unique().tolist())),
                    cell_types=("cell_type", lambda x: sorted(x.unique().tolist())),
                )
                .reset_index()
            )

            datasets = datasets.sort_values("n_cells", ascending=False)

            results = []
            for _, row in datasets.head(20).iterrows():
                results.append(
                    {
                        "dataset_id": row["dataset_id"],
                        "n_cells": int(row["n_cells"]),
                        "tissues": row["tissues"][:5],
                        "diseases": row["diseases"][:5],
                        "assays": row["assays"],
                        "n_cell_types": len(row["cell_types"]),
                    }
                )

            search_desc = (
                ", ".join(
                    f"{k}={v}"
                    for k, v in [("tissue", tissue), ("disease", disease), ("assay", assay)]
                    if v
                )
                or "all"
            )

            summary = f"Found {len(datasets)} datasets ({search_desc}), {len(obs_df)} total cells"

            return {
                "summary": summary,
                "n_datasets": len(datasets),
                "n_cells_total": len(obs_df),
                "datasets": results,
            }

    except Exception as e:
        return {
            "error": f"Census query failed: {e}",
            "summary": f"Failed to search Census datasets: {e}",
        }
