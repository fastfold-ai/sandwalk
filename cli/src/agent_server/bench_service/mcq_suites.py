"""MCQ suites (MMLU / MMLU-Pro / ARC-C) for Sandwalk agent-session Bench.

Sample sizes and seed-42 sampling stay fixed across models for fair compare.
Runs go through Sandwalk agent sessions — we are testing the harness.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_server.bench_service.bootstrap import (
    bench_cache_root,
    bench_root,
    fixtures_dir,
)

LETTERS = "ABCDEFGHIJ"
SAMPLE_SEED = 42


@dataclass(frozen=True)
class McqSuite:
    id: str
    title: str
    full_fixture: str
    sample_fixture: str
    description: str
    author: str
    author_avatar: str | None
    subject_label: str | None
    full_size: int
    default_sample_size: int
    sample_sizes: tuple[int, ...]
    prompt_intro: str
    letters: str = "ABCD"
    stratify_key: str | None = None  # e.g. "subject" for MMLU-Pro


MCQ_SUITES: dict[str, McqSuite] = {
    "mmlu": McqSuite(
        id="mmlu",
        title="MMLU",
        full_fixture="mmlu_test.jsonl",
        sample_fixture="mmlu_sample_30.jsonl",
        description=(
            "Multiple choice · 57 subjects. "
            "Runs via Sandwalk agent sessions (harness)."
        ),
        author="Hendrycks et al.",
        author_avatar=None,
        subject_label="57 subjects",
        full_size=14042,
        default_sample_size=30,
        sample_sizes=(30, 50, 100, 200, 300, 500, 1000, 2000),
        prompt_intro="The following are multiple choice questions about {topic}.",
        letters="ABCD",
    ),
    "mmlu-pro": McqSuite(
        id="mmlu-pro",
        title="MMLU-Pro",
        full_fixture="mmlu_pro_test.jsonl",
        sample_fixture="mmlu_pro_sample_30.jsonl",
        description=(
            "Hard MCQ · 14 subjects (up to 10-way). "
            "Runs via Sandwalk agent sessions (harness)."
        ),
        author="TIGER-Lab",
        author_avatar=None,
        subject_label="14 subjects",
        full_size=12032,
        default_sample_size=30,
        sample_sizes=(30, 50, 100, 200, 300, 500, 1000, 2000),
        prompt_intro="Answer the following multiple-choice question about {topic}.",
        letters="ABCDEFGHIJ",
        stratify_key="subject",
    ),
    "arc-challenge": McqSuite(
        id="arc-challenge",
        title="ARC-C",
        full_fixture="arc_challenge.jsonl",
        sample_fixture="arc_challenge_sample_30.jsonl",
        description=(
            "Science reasoning MCQ (AI2 ARC Challenge). "
            "Runs via Sandwalk agent sessions (harness)."
        ),
        author="Allen Institute for AI",
        author_avatar="/brand/bench/ai2-mark.png",
        subject_label="science reasoning",
        full_size=1172,
        default_sample_size=30,
        sample_sizes=(30, 50, 100, 200, 300),
        prompt_intro="Answer the following science question.",
        letters="ABCD",
    ),
}


def catalog_sample_sizes(
    suite: McqSuite, *, full_available: bool = True
) -> list[int]:
    """Discrete sizes under full, then Full (= full_size).

    With only the sample fixture on disk, cap the list at what that fixture can
    serve — offering 100 when 30 rows exist just fails once the run starts.
    """
    if not full_available:
        n = sample_fixture_size(suite)
        if n <= 0:
            return [suite.default_sample_size]
        return [size for size in suite.sample_sizes if size <= n] or [n]
    sizes = [n for n in suite.sample_sizes if n < suite.full_size]
    return sizes + [suite.full_size]


def sample_fixture_size(suite: McqSuite) -> int:
    """Row count of the small bundled fixture (0 when absent)."""
    fix = fixtures_dir()
    if fix is None:
        return 0
    path = fix / suite.sample_fixture
    if not path.is_file():
        return 0
    try:
        return _count_records(path)
    except OSError:
        return 0


def _count_records(path: Path) -> int:
    """Count JSONL records as the loader reads them (newline-delimited only).

    ``str.splitlines`` also splits on U+0085 / U+2028 / U+2029, which occur inside
    a few MMLU questions and would inflate the count.
    """
    with path.open(encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def full_dataset_available(suite_id: str) -> bool:
    """True when the full corpus is cached (not just the sample fixture)."""
    suite = MCQ_SUITES.get(suite_id)
    if suite is None:
        return False
    return resolve_dataset_path(suite, prefer_full=True) is not None


def count_fixture(suite_id: str) -> int:
    """Declared full dataset size for suite cards."""
    suite = MCQ_SUITES.get(suite_id)
    return suite.full_size if suite else 0


def dataset_available(suite_id: str) -> bool:
    suite = MCQ_SUITES.get(suite_id)
    if suite is None:
        return False
    return resolve_dataset_path(suite, prefer_full=False) is not None


def resolve_dataset_path(suite: McqSuite, *, prefer_full: bool) -> Path | None:
    """Locate full JSONL under cache/fixtures, else the small sample fixture."""
    candidates: list[Path] = []
    cache = bench_cache_root()
    root = bench_root()
    fix = fixtures_dir()
    candidates.append(cache / ".cache" / "mcq" / suite.full_fixture)
    if root is not None:
        candidates.append(root / ".cache" / "mcq" / suite.full_fixture)
    if fix is not None:
        candidates.append(fix / "mcq" / suite.full_fixture)
        candidates.append(fix / suite.full_fixture)

    for path in candidates:
        if path.is_file():
            return path

    if prefer_full:
        return None
    if fix is not None:
        sample = fix / suite.sample_fixture
        if sample.is_file():
            return sample
    return None


def ensure_dataset_path(suite: McqSuite, sample_size: int) -> Path:
    """Return a dataset path that can satisfy sample_size (0 / full_size = full)."""
    # Prefer the full corpus so seed-42 sampling is stable across models.
    path = resolve_dataset_path(suite, prefer_full=True)
    if path is None:
        path = resolve_dataset_path(suite, prefer_full=False)
    if path is None:
        raise FileNotFoundError(
            f"Missing {suite.title} dataset ({suite.full_fixture}). "
            f"Install it from Dashboard → Bench (the suite card's Install button)."
        )
    if path.name == suite.sample_fixture:
        n_lines = _count_records(path)
        need = suite.full_size if sample_size <= 0 else sample_size
        if need > n_lines:
            raise FileNotFoundError(
                f"{suite.title}: only the {n_lines}-question sample fixture is "
                f"installed, but {need} questions were requested. Install the full "
                f"{suite.title} dataset from Dashboard → Bench, or pick a sample "
                f"size of {n_lines} or fewer."
            )
    return path


def load_mcq_items(suite_id: str, sample_size: int = 30) -> list[dict[str, Any]]:
    suite = MCQ_SUITES[suite_id]
    path = ensure_dataset_path(suite, sample_size)
    items: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            raw = json.loads(line)
            items.append(_normalize_item(raw, suite))

    # 0 or >= full_size ⇒ full set
    if sample_size <= 0 or sample_size >= len(items):
        return items
    if suite.stratify_key:
        return _stratified_sample(items, sample_size, suite.stratify_key)
    return _deterministic_sample(items, sample_size)


def format_mcq_prompt(suite_id: str, item: dict[str, Any]) -> str:
    suite = MCQ_SUITES[suite_id]
    topic = str(item.get("subject") or "general knowledge").replace("_", " ").title()
    intro = suite.prompt_intro.format(topic=topic)
    labels = item.get("labels") or list(suite.letters[: len(item["choices"])])
    letter_hint = ", ".join(labels[:4])
    if len(labels) > 4:
        letter_hint = f"{labels[0]}–{labels[-1]}"
    parts = [
        f"{intro} Answer with just the letter ({letter_hint}).\n",
        str(item["question"]),
    ]
    for label, choice in zip(labels, item["choices"], strict=False):
        parts.append(f"{label}. {choice}")
    parts.append("\nAnswer:")
    return "\n".join(parts)


def _deterministic_sample(items: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    if n >= len(items):
        return items
    rng = random.Random(SAMPLE_SEED)
    return rng.sample(items, n)


def _stratified_sample(
    items: list[dict[str, Any]], n: int, key: str
) -> list[dict[str, Any]]:
    """Proportional sample by category with a fixed seed."""
    if n >= len(items):
        return items
    rng = random.Random(SAMPLE_SEED)
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        groups.setdefault(str(item.get(key) or "unknown"), []).append(item)

    total = len(items)
    sampled: list[dict[str, Any]] = []
    remaining = n
    sorted_cats = sorted(groups.keys())
    for i, cat in enumerate(sorted_cats):
        group = groups[cat]
        if i == len(sorted_cats) - 1:
            count = remaining
        else:
            count = max(1, round(len(group) / total * n))
            count = min(count, remaining, len(group))
        selected = rng.sample(group, min(count, len(group)))
        sampled.extend(selected)
        remaining -= len(selected)
        if remaining <= 0:
            break
    return sampled


def _normalize_item(raw: dict[str, Any], suite: McqSuite) -> dict[str, Any]:
    choices = raw.get("choices") or []
    if isinstance(choices, str):
        choices = json.loads(choices.replace("'", '"'))
    choices = list(choices)
    labels = raw.get("labels")
    if not labels:
        labels = list(suite.letters[: len(choices)])
    else:
        labels = [str(x).upper() for x in labels]

    answer = raw.get("answer", 0)
    if isinstance(answer, str) and answer.strip().upper()[:1] in LETTERS:
        letter = answer.strip().upper()[:1]
    else:
        try:
            idx = int(answer)
        except (TypeError, ValueError):
            idx = 0
        letter = labels[idx] if 0 <= idx < len(labels) else labels[0]

    return {
        "id": str(raw.get("id") or ""),
        "question": raw["question"],
        "choices": choices,
        "labels": labels,
        "answer": letter,
        "subject": raw.get("subject")
        or ("science" if suite.id == "arc-challenge" else "unknown"),
    }
