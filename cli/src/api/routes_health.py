"""Health-check and dataset-listing endpoints for the ct Data Query API.

Handlers re-import the mockable globals (``engine``, ``discover_datasets``, etc.)
from ``api.app`` on every call so tests can ``patch("api.app.<name>")`` and have
the patched value take effect regardless of which module defines the route.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
def health() -> dict[str, Any]:
    """Health check — also reports available datasets."""
    from api.app import discover_datasets

    available = discover_datasets()
    return {
        "status": "ok",
        "datasets": list(available.keys()),
        "n_datasets": len(available),
    }


@router.get("/health/schema")
def schema_health() -> JSONResponse:
    """Deep health check — validates file schemas match expectations."""
    from api.app import engine, validate_schema

    results = validate_schema(engine)
    has_invalid = any(r["status"] == "invalid" for r in results.values())

    status_code = 503 if has_invalid else 200
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "unhealthy" if has_invalid else "ok",
            "datasets": results,
        },
    )


@router.get("/datasets")
def list_datasets() -> list[dict[str, Any]]:
    """List available datasets with metadata."""
    from api.app import discover_datasets, DATASET_REGISTRY

    available = discover_datasets()
    result: list[dict[str, Any]] = []
    for name, info in available.items():
        registry_entry = DATASET_REGISTRY.get(name, {})
        result.append({
            "name": name,
            "description": info["description"],
            "format": info["format"],
            "n_files": info["n_files"],
            "total_size_mb": info["total_size_mb"],
            "filterable_columns": info.get("filterable", []),
            "columns": registry_entry.get("columns", []),
            "required_columns": registry_entry.get("required_columns", []),
        })
    return result
