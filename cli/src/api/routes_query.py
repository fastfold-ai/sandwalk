"""Query, gene-summary, and compound-summary endpoints for the ct Data API.

Handlers re-import the mockable globals (``engine``, ``DATASET_REGISTRY``) from
``api.app`` on every call so tests can ``patch("api.app.<name>")`` and have the
patched value take effect regardless of which module defines the route.
"""

from __future__ import annotations

import statistics
from typing import Any

from fastapi import APIRouter, HTTPException

from api.schemas import QueryRequest, QueryResponse

router = APIRouter()


def _resolve_compound_filters(req: QueryRequest, ds_config: dict[str, Any]) -> dict[str, Any]:
    filters: dict[str, Any] = dict(req.filters) if req.filters else {}
    if req.gene:
        filters["gene"] = req.gene
    if req.compound:
        for col in ["compound", "molecule_chembl_id", "pert_name", "compound_name"]:
            if col in ds_config.get("filterable", []):
                filters[col] = req.compound
                break
        else:
            filters["compound"] = req.compound
    return filters


@router.post("/query", response_model=QueryResponse)
def query_dataset(req: QueryRequest) -> QueryResponse:
    """Run a filtered query against a dataset."""
    from api.app import engine, DATASET_REGISTRY

    if req.dataset not in DATASET_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {req.dataset}")

    ds_config = DATASET_REGISTRY[req.dataset]
    filters = _resolve_compound_filters(req, ds_config)

    try:
        data = engine.query_parquet(
            file_pattern=str(ds_config["path_pattern"]),
            filters=filters if filters else None,
            columns=req.columns,
            limit=req.limit,
            order_by=req.order_by,
        )
        return QueryResponse(
            dataset=req.dataset,
            total_rows=len(data),
            data=data,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail=f"Dataset '{req.dataset}' files not found on disk",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/datasets/{name}/gene/{gene}")
def gene_summary(name: str, gene: str) -> dict[str, Any]:
    """Get a gene-level summary from a dataset."""
    from api.app import engine, DATASET_REGISTRY

    if name not in DATASET_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {name}")

    ds_config = DATASET_REGISTRY[name]

    try:
        data = engine.query_parquet(
            file_pattern=str(ds_config["path_pattern"]),
            filters={"gene": gene},
            limit=1000,
        )

        if not data:
            raise HTTPException(status_code=404, detail=f"Gene {gene} not found in {name}")

        effects = [r.get("log2FoldChange", r.get("lfc", 0)) for r in data if r.get("log2FoldChange") or r.get("lfc")]
        mean_effect = statistics.mean(effects) if effects else 0
        n_perturbations = len(data)

        return {
            "gene": gene,
            "dataset": name,
            "n_perturbations": n_perturbations,
            "mean_effect": round(mean_effect, 4),
            "n_significant": sum(
                1 for r in data
                if (r.get("padj") or r.get("pvalue", 1)) < 0.05
            ),
            "sample_data": data[:10],
        }
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail=f"Dataset '{name}' files not found")


@router.get("/datasets/{name}/compound/{compound}")
def compound_summary(name: str, compound: str) -> dict[str, Any]:
    """Get a compound-level summary from a dataset."""
    from api.app import engine, DATASET_REGISTRY

    if name not in DATASET_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {name}")

    ds_config = DATASET_REGISTRY[name]

    filters: dict[str, Any] = {}
    filterable = ds_config.get("filterable", [])
    for col in ["compound", "molecule_chembl_id", "pert_name", "compound_name"]:
        if col in filterable:
            filters[col] = compound
            break
    else:
        filters["compound"] = compound

    try:
        data = engine.query_parquet(
            file_pattern=str(ds_config["path_pattern"]),
            filters=filters,
            limit=1000,
        )

        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"Compound {compound} not found in {name}",
            )

        return {
            "compound": compound,
            "dataset": name,
            "n_records": len(data),
            "sample_data": data[:10],
        }
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail=f"Dataset '{name}' files not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
