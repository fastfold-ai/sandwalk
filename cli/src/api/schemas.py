"""Pydantic request/response models for the ct Data Query API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from api.config import DEFAULT_QUERY_LIMIT


class QueryRequest(BaseModel):
    dataset: str = Field(..., description="Dataset name (e.g. 'perturbatlas', 'chembl')")
    gene: str | None = Field(None, description="Filter by gene symbol")
    compound: str | None = Field(None, description="Filter by compound name/ID")
    filters: dict[str, Any] | None = Field(None, description="Additional column filters")
    columns: list[str] | None = Field(None, description="Columns to return")
    limit: int = Field(DEFAULT_QUERY_LIMIT, ge=1, le=10000, description="Max rows")
    order_by: str | None = Field(None, description="Column to sort by")


class QueryResponse(BaseModel):
    dataset: str
    total_rows: int
    data: list[dict[str, Any]]
