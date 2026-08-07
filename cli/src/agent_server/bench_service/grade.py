"""Grade agent transcripts / completion answers into bench result rows."""

from __future__ import annotations

import re
from typing import Any


def extract_answer(text: str) -> str:
    if not text:
        return ""
    patterns = (
        r"^\s*FINAL_ANSWER\s*:\s*(.+?)\s*$",
        r"^\s*Answer\s*:\s*(.+?)\s*$",
        r"\\boxed\{([^}]+)\}",
        r"(?:the )?(?:final )?answer is[:\s]+(.+?)\s*$",
    )
    for line in reversed(text.splitlines()):
        raw = line.strip()
        if not raw:
            continue
        for pat in patterns:
            m = re.search(pat, raw, flags=re.I)
            if m:
                return m.group(1).strip().rstrip(".")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def grade_str(ideal: str | None, predicted: str) -> bool:
    if ideal is None:
        return False
    a = _norm(ideal)
    b = _norm(predicted)
    return a == b or a in b


def grade_range(ideal: str | None, predicted: str) -> bool:
    if not ideal:
        return False
    m = re.search(
        r"\(\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)\s*,\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)\s*\)",
        ideal,
    )
    if not m:
        return False
    lo, hi = float(m.group(1)), float(m.group(2))
    if lo > hi:
        lo, hi = hi, lo
    nums = re.findall(r"[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?", predicted.replace(",", ""))
    if not nums:
        return False
    val = float(nums[-1])
    return lo <= val <= hi


def extract_mc_letter(predicted: str) -> str:
    """Pull A–J from model text; prefer Answer: lines, else the last letter token."""
    pred = (predicted or "").strip().upper()
    if not pred:
        return ""
    for pat in (
        r"(?:FINAL_)?ANSWER\s*:\s*([A-J])\b",
        r"(?:THE )?(?:FINAL )?ANSWER IS[:\s]+([A-J])\b",
        r"\\BOXED\{([A-J])\}",
    ):
        m = re.search(pat, pred)
        if m:
            return m.group(1)
    # Last standalone letter avoids matching leading "I think B…"
    matches = list(re.finditer(r"\b([A-J])\b", pred))
    if matches:
        return matches[-1].group(1)
    return pred[:1] if pred[:1] in "ABCDEFGHIJ" else ""


def grade_mc_letter(ideal: str | None, predicted: str) -> bool:
    """Grade A–J multiple-choice letters (MMLU / ARC-C / MMLU-Pro)."""
    if not ideal:
        return False
    exp = ideal.strip().upper()[:1]
    if exp not in "ABCDEFGHIJ":
        return False
    return extract_mc_letter(predicted) == exp


def grade_row(
    *,
    eval_mode: str,
    ideal: str | None,
    predicted: str,
    judge_ok: bool | None = None,
    source: dict[str, Any] | None = None,
) -> bool:
    mode = (eval_mode or "str_verifier").strip()
    if mode == "range_verifier":
        return grade_range(ideal, predicted)
    if mode == "mcq":
        return grade_mc_letter(ideal, predicted)
    if mode == "code_exec":
        from agent_server.bench_service.code_exec import grade_code_exec

        src = source or {}
        suite_id = str(src.get("suite") or "")
        return grade_code_exec(suite_id=suite_id, source=src, predicted=predicted)
    if mode == "str_verifier":
        return grade_str(ideal, predicted)
    if mode == "llm_verifier":
        if judge_ok is not None:
            return judge_ok
        return grade_str(ideal, predicted)
    if mode == "checklist":
        if judge_ok is not None:
            return judge_ok
        return bool(predicted.strip())
    return grade_str(ideal, predicted)


def build_result(
    *,
    run_id: str,
    model_id: str,
    benchmark: str,
    questions: list[dict[str, Any]],
    time_s: float,
    thinking_used: bool = False,
    project_id: str | None = None,
    environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    correct = sum(1 for q in questions if q.get("correct"))
    total = len(questions)
    category_scores: dict[str, float] = {}
    buckets: dict[str, list[bool]] = {}
    for q in questions:
        cat = str(q.get("category") or "all")
        buckets.setdefault(cat, []).append(bool(q.get("correct")))
    for cat, flags in buckets.items():
        category_scores[cat] = (sum(flags) / len(flags)) if flags else 0.0
    result: dict[str, Any] = {
        "run_id": run_id,
        "model_id": model_id,
        "benchmark": benchmark,
        "accuracy": (correct / total) if total else 0.0,
        "correct": correct,
        "total": total,
        "time_s": round(time_s, 1),
        "thinking_used": thinking_used,
        "category_scores": category_scores,
        "questions": questions,
        "project_id": project_id,
    }
    if environment is not None:
        result["environment"] = environment
    return result


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())
