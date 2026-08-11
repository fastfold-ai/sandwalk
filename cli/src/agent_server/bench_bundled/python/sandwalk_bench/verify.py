"""Lightweight graders for BixBench-style eval_mode values."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Grade:
    ok: bool
    mode: str
    expected: str
    predicted: str
    detail: str = ""


def extract_final_answer(text: str) -> str:
    """Pull a graded value from free-form assistant text.

    Prefers explicit cues (``Answer:``, ``FINAL_ANSWER:``, boxed, “the answer
    is”), then the last non-empty line — same spirit as AIME extractors.
    """
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


def grade(eval_mode: str, ideal: str | None, predicted: str) -> Grade:
    mode = (eval_mode or "str_verifier").strip()
    exp = (ideal or "").strip()
    pred = (predicted or "").strip()
    if mode == "range_verifier":
        return _range(exp, pred, mode)
    if mode in {"str_verifier", "mcq", "checklist", "llm_verifier"}:
        # llm_verifier needs a judge model later; exact/normalized for now
        ok = _norm(pred) == _norm(exp) or _norm(exp) in _norm(pred)
        return Grade(ok=ok, mode=mode, expected=exp, predicted=pred, detail="normalized match")
    return Grade(ok=False, mode=mode, expected=exp, predicted=pred, detail="unsupported mode")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _range(ideal: str, predicted: str, mode: str) -> Grade:
    """Ideal like ``(0.07,0.08)`` or ``(184000,185000)``."""
    m = re.search(r"\(\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)\s*,\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)\s*\)", ideal)
    if not m:
        return Grade(ok=False, mode=mode, expected=ideal, predicted=predicted, detail="bad ideal range")
    lo, hi = float(m.group(1)), float(m.group(2))
    if lo > hi:
        lo, hi = hi, lo
    nums = re.findall(r"[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?", predicted.replace(",", ""))
    if not nums:
        return Grade(ok=False, mode=mode, expected=ideal, predicted=predicted, detail="no number in prediction")
    val = float(nums[-1])
    ok = lo <= val <= hi
    return Grade(ok=ok, mode=mode, expected=ideal, predicted=predicted, detail=f"value={val}")
