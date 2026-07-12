"""Dataset catalog + install management for the agent server."""

from __future__ import annotations

from agent_server.models import (
    DatasetInstallResponse,
    DatasetList,
    DatasetSummary,
)


class DatasetsService:
    def _records(self) -> list[dict]:
        from data.downloader import list_dataset_records

        return list_dataset_records()

    def _to_summary(self, record: dict) -> DatasetSummary:
        return DatasetSummary(
            id=str(record["id"]),
            description=str(record.get("description") or ""),
            status=str(record.get("status") or "missing"),  # type: ignore[arg-type]
            files_found=int(record.get("files_found") or 0),
            files_expected=int(record.get("files_expected") or 0),
            size_bytes=record.get("size_bytes"),
            size_display=str(record.get("size_display") or "-"),
            auto_download=bool(record.get("auto_download")),
            path=str(record.get("path") or ""),
            source=record.get("source"),
            note=record.get("note"),
        )

    def list_datasets(self) -> DatasetList:
        items = [self._to_summary(rec) for rec in self._records()]
        return DatasetList(data=items, count=len(items))

    def get_dataset(self, dataset_id: str) -> DatasetSummary | None:
        target = str(dataset_id or "").strip()
        for rec in self._records():
            if rec["id"] == target:
                return self._to_summary(rec)
        return None

    def install(self, dataset_id: str) -> DatasetInstallResponse:
        from data.downloader import DATASETS, download_dataset

        target = str(dataset_id or "").strip()
        if target not in DATASETS:
            raise KeyError(target)

        meta = DATASETS[target]
        if not meta.get("auto_download"):
            summary = str(meta.get("note") or "").strip() or (
                "This dataset requires a manual download from its source."
            )
            after = self.get_dataset(target)
            return DatasetInstallResponse(
                ok=False,
                id=target,
                status=after.status if after else "missing",
                summary=f"Manual download required. {summary}",
                dataset=after,
            )

        # Synchronous download (progress is written to the server console/log).
        download_dataset(target)
        after = self.get_dataset(target)
        status = after.status if after else "missing"
        if status == "complete":
            summary = f"{target} installed successfully."
            ok = True
        elif status == "partial":
            summary = f"{target} partially installed — some files failed to download."
            ok = False
        else:
            summary = f"{target} install did not complete. Check server logs."
            ok = False
        return DatasetInstallResponse(
            ok=ok, id=target, status=status, summary=summary, dataset=after
        )
