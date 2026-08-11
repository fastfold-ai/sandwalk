"""
FastAPI application for the ct Data Query API.

Serves filtered queries against large datasets (PerturbAtlas, ChEMBL, etc.)
using DuckDB for efficient Parquet/CSV.gz querying.

Run with: uvicorn api.app:app --host 0.0.0.0 --port 8000

Route handlers live in ``api.routes_health`` and ``api.routes_query``; they
re-import ``engine``/``discover_datasets``/``DATASET_REGISTRY``/etc. from this
module on each call so ``patch("api.app.<name>")`` in tests still works.
"""

from __future__ import annotations

from fastapi import FastAPI

from _version import __version__
from api.config import DATASET_REGISTRY, DEFAULT_QUERY_LIMIT, discover_datasets, validate_schema
from api.engine import QueryEngine
from api.routes_health import router as health_router
from api.routes_query import router as query_router
from api.schemas import QueryRequest, QueryResponse

__all__ = [
    "app",
    "engine",
    "discover_datasets",
    "validate_schema",
    "DATASET_REGISTRY",
    "DEFAULT_QUERY_LIMIT",
    "QueryRequest",
    "QueryResponse",
]

app = FastAPI(
    title="ct Data API",
    description="Query large drug discovery datasets via DuckDB",
    version=__version__,
)

engine = QueryEngine()

app.include_router(health_router)
app.include_router(query_router)
