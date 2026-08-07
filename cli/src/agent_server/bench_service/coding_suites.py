"""Coding suites (MBPP / LiveCodeBench) for Sandwalk agent-session Bench.

Grading runs sandboxed code exec on the host after the agent session finishes —
we are testing that the Sandwalk harness can code.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_server.bench_service.bootstrap import bench_root, fixtures_dir
from agent_server.bench_service.code_exec import parse_lcb_public_tests
from agent_server.bench_service.mcq_suites import SAMPLE_SEED


@dataclass(frozen=True)
class CodingSuite:
    id: str
    title: str
    full_fixture: str
    description: str
    author: str
    author_avatar: str | None
    subject_label: str
    full_size: int
    default_sample_size: int
    sample_sizes: tuple[int, ...]
    code_exec: bool = True


CODING_SUITES: dict[str, CodingSuite] = {
    "mbpp": CodingSuite(
        id="mbpp",
        title="MBPP",
        full_fixture="mbpp.jsonl",
        description="Python problems · assert-based tests. Agent sessions + code exec.",
        author="Google Research",
        author_avatar=None,
        subject_label="Python problems",
        full_size=500,
        default_sample_size=200,
        sample_sizes=(30, 50, 100, 200, 300),
    ),
    "livecodebench": CodingSuite(
        id="livecodebench",
        title="LiveCodeBench",
        full_fixture="livecodebench.jsonl",
        description="Code generation · stdin/stdout tests. Agent sessions + code exec.",
        author="LiveCodeBench",
        author_avatar=None,
        subject_label="Code generation",
        full_size=1055,
        default_sample_size=100,
        sample_sizes=(30, 50, 100, 200, 300),
    ),
}


def catalog_sample_sizes(suite: CodingSuite) -> list[int]:
    sizes = [n for n in suite.sample_sizes if n < suite.full_size]
    return sizes + [suite.full_size]


def count_fixture(suite_id: str) -> int:
    suite = CODING_SUITES.get(suite_id)
    return suite.full_size if suite else 0


def dataset_available(suite_id: str) -> bool:
    suite = CODING_SUITES.get(suite_id)
    if suite is None:
        return False
    return resolve_dataset_path(suite) is not None


def resolve_dataset_path(suite: CodingSuite) -> Path | None:
    candidates: list[Path] = []
    root = bench_root()
    fix = fixtures_dir()
    if root is not None:
        candidates.append(root / ".cache" / "mcq" / suite.full_fixture)
        candidates.append(root / ".cache" / "bench" / suite.full_fixture)
    if fix is not None:
        candidates.append(fix / suite.full_fixture)
        candidates.append(fix / "mcq" / suite.full_fixture)
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_coding_items(suite_id: str, sample_size: int = 30) -> list[dict[str, Any]]:
    suite = CODING_SUITES[suite_id]
    path = resolve_dataset_path(suite)
    if path is None:
        raise FileNotFoundError(
            f"Missing {suite.title} dataset ({suite.full_fixture}). "
            f"Place it under apps/benchmarking/.cache/mcq/"
        )
    items: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            raw = json.loads(line)
            item = _normalize(suite_id, raw)
            if item is not None:
                items.append(item)
    if sample_size <= 0 or sample_size >= len(items):
        return items
    rng = random.Random(SAMPLE_SEED)
    return rng.sample(items, sample_size)


def format_coding_prompt(suite_id: str, item: dict[str, Any]) -> str:
    if suite_id == "mbpp":
        tests = "\n".join(list(item.get("test_list") or [])[:3])
        return (
            "Write a Python function to solve the following problem. "
            "You may use the workspace / shell tools. "
            "When done, put the complete function in a ```python``` block "
            "(no explanations outside the block).\n\n"
            f"Problem: {item['question']}\n\n"
            f"Test cases:\n{tests}\n\n"
            "Solution:"
        )
    description = str(item.get("question") or "")
    return (
        "Solve the following programming problem in Python. "
        "Read input from stdin and print the output to stdout. "
        "You may use the workspace / shell tools. "
        "When done, put the complete program in a ```python``` block.\n\n"
        f"Problem:\n{description}\n\n"
        "Solution:"
    )


def _normalize(suite_id: str, raw: dict[str, Any]) -> dict[str, Any] | None:
    if suite_id == "mbpp":
        tests = raw.get("test_list") or []
        if not tests:
            return None
        return {
            "id": str(raw.get("task_id") or ""),
            "question": str(raw.get("prompt") or ""),
            "test_list": list(tests),
            "test_setup_code": str(raw.get("test_setup_code") or ""),
            "subject": "python",
        }
    inputs, outputs = parse_lcb_public_tests(raw.get("public_test_cases"))
    if not inputs or not outputs:
        return None
    return {
        "id": str(raw.get("question_id") or ""),
        "question": str(raw.get("question_content") or ""),
        "title": str(raw.get("question_title") or ""),
        "inputs": inputs,
        "outputs": outputs,
        "difficulty": str(raw.get("difficulty") or ""),
        "subject": str(raw.get("difficulty") or "coding"),
    }
