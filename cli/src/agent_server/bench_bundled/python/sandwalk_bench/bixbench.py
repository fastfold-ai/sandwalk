"""BixBench-Verified-50 helpers.

Cache upstream JSONL and expose as-is questions for Dashboard Bench /
``sandwalk-bench bixbench download``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from sandwalk_bench.paths import CACHE_DIR
from sandwalk_bench.schema import Pack, Question

REPO_ID = "phylobio/BixBench-Verified-50"
JSONL_NAME = "BixBench-Verified-50.jsonl"
HF_RESOLVE = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{JSONL_NAME}"


def cache_dir() -> Path:
    d = CACHE_DIR / "bixbench-verified-50"
    d.mkdir(parents=True, exist_ok=True)
    return d


def jsonl_path() -> Path:
    return cache_dir() / JSONL_NAME


def download_jsonl(token: str | None = None, force: bool = False) -> Path:
    """Download the Verified-50 JSONL (gated; needs HF token + accepted terms)."""
    out = jsonl_path()
    if out.is_file() and out.stat().st_size > 0 and not force:
        return out
    tok = (token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip()
    if not tok:
        raise RuntimeError(
            "HF token required. Set HF_TOKEN (and accept the dataset terms on Hugging Face)."
        )
    req = Request(HF_RESOLVE, headers={"Authorization": f"Bearer {tok}"})
    with urlopen(req, timeout=120) as resp:  # noqa: S310 — fixed HF URL
        out.write_bytes(resp.read())
    return out


def load_jsonl(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or jsonl_path()
    if not p.is_file():
        raise FileNotFoundError(
            f"Missing {p}. Run: sandwalk-bench bixbench download  (with HF_TOKEN set)"
        )
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def as_is_pack(rows: list[dict[str, Any]] | None = None) -> Pack:
    """Normalize full Verified-50 into the common Pack schema (no sandwalk wrap).

    Capsules are *not* downloaded here — ``source.data_folder`` / ``capsule_uuid``
    remain for a future capsule fetcher.
    """
    rows = rows if rows is not None else load_jsonl()
    questions = [_row_to_question(r) for r in rows]
    return Pack(
        id="bixbench-verified-50",
        version="1.5",
        description=(
            "phylobio/BixBench-Verified-50 loaded as-is "
            "(https://huggingface.co/datasets/phylobio/BixBench-Verified-50)"
        ),
        questions=questions,
        title_template="{title} · {model_short}",
    )


def _row_to_question(r: dict[str, Any]) -> Question:
    qid = str(r.get("question_id") or r.get("short_id") or r.get("id") or "")
    return Question(
        id=qid,
        question=str(r.get("question") or ""),
        ideal=None if r.get("ideal") is None else str(r.get("ideal")),
        eval_mode=str(r.get("eval_mode") or "llm_verifier"),
        title=qid,
        distractors=list(r.get("distractors") or []),
        prompt=str(r.get("question") or ""),
        source={
            "pack": REPO_ID,
            "question_id": qid,
            "id": r.get("id"),
            "capsule_uuid": r.get("capsule_uuid"),
            "data_folder": r.get("data_folder"),
            "categories": r.get("categories"),
            "paper": r.get("paper"),
            "version": r.get("version"),
            "canary": r.get("canary"),
            "hypothesis": r.get("hypothesis"),
            "result": r.get("result"),
            "answer": r.get("answer"),
            "example_id": r.get("example_id"),
        },
    )


def summarize(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = rows if rows is not None else load_jsonl()
    modes: dict[str, int] = {}
    for r in rows:
        m = str(r.get("eval_mode") or "?")
        modes[m] = modes.get(m, 0) + 1
    return {
        "dataset": REPO_ID,
        "n_questions": len(rows),
        "eval_mode_counts": modes,
        "fields": sorted(rows[0].keys()) if rows else [],
        "jsonl": str(jsonl_path()),
    }
