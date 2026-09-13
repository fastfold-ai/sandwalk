"""Queue extra question ids onto a bench run that is already executing."""

from __future__ import annotations

import threading

_lock = threading.Lock()
_extra: dict[str, list[str]] = {}


def add_extra_retry(run_id: str, question_ids: list[str]) -> list[str]:
    rid = str(run_id or "").strip()
    added: list[str] = []
    if not rid:
        return added
    with _lock:
        bucket = _extra.setdefault(rid, [])
        have = set(bucket)
        for raw in question_ids:
            qid = str(raw or "").strip()
            if qid and qid not in have:
                bucket.append(qid)
                have.add(qid)
                added.append(qid)
    return added


def take_extra_retry(run_id: str) -> list[str]:
    rid = str(run_id or "").strip()
    if not rid:
        return []
    with _lock:
        return list(_extra.pop(rid, []))


def clear_extra_retry(run_id: str | None = None) -> None:
    with _lock:
        if run_id is None:
            _extra.clear()
            return
        _extra.pop(str(run_id), None)
