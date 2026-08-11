from __future__ import annotations

from pydantic import Field

from agent_server.models.base import ApiModel


class StorageLocation(ApiModel):
    path: str
    label: str = "default location"
    bytes: int = 0


class StorageCategory(ApiModel):
    id: str
    label: str
    color: str
    bytes: int = 0
    path: str | None = None
    children: list[StorageCategory] = Field(default_factory=list)


class StorageDatabaseProbe(ApiModel):
    """Integrity / size snapshot for ~/.sandwalk/agent-server.db."""

    path: str
    exists: bool = False
    bytes: int = 0
    wal_bytes: int = 0
    shm_bytes: int = 0
    integrity: str = "missing"
    page_count: int | None = None
    page_size: int | None = None
    journal_mode: str | None = None
    session_count: int | None = None
    message_count: int | None = None
    backup_path: str | None = None
    backup_bytes: int = 0
    backup_integrity: str | None = None
    auto_heal_enabled: bool = True
    quarantine_count: int = 0


class StorageReport(ApiModel):
    location: StorageLocation
    categories: list[StorageCategory] = Field(default_factory=list)
    total_bytes: int = 0
    available_bytes: int = 0
    checked_at: str
    database: StorageDatabaseProbe | None = None
