#!/usr/bin/env python3
"""Benchmark cloud catalog models across questions and reasoning effort levels.

This is the CLI front-end for ``agent.model_benchmark``. The same library is
intended to power a future local-web **Benchmark** UI / ``/v1/benchmarks`` API.

Examples (from cli/ with venv active):

    # Dry-run: print the expanded matrix only
    python scripts/benchmark.py --dry-run

    # OpenAI only, medium + fast effort, write JSON report
    python scripts/benchmark.py --provider openai --effort medium,fast \\
        --output /tmp/bench-openai.json

    # Full cloud catalog × default suite × all efforts (expensive)
    python scripts/benchmark.py --cloud-only --with-tools

    # Single model smoke
    python scripts/benchmark.py --model gpt-5.6-sol --effort fast --limit 3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _parse_csv(raw: str | None) -> list[str] | None:
    if raw is None or not str(raw).strip():
        return None
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--suite",
        type=Path,
        default=None,
        help="Path to questions JSON (default: configs/model_benchmarks.json)",
    )
    parser.add_argument("--provider", help="Only this provider (openai, anthropic, …)")
    parser.add_argument("--model", help="Only this model id")
    parser.add_argument(
        "--effort",
        default="low,medium,high,fast",
        help="Comma-separated efforts for reasoning models (default: low,medium,high,fast)",
    )
    parser.add_argument(
        "--question",
        help="Comma-separated question ids to include (default: all in suite)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max cases after matrix expand (0 = all)",
    )
    parser.add_argument(
        "--cloud-only",
        action="store_true",
        default=True,
        help="Cloud catalog only (default)",
    )
    parser.add_argument(
        "--with-tools",
        action="store_true",
        default=True,
        help="Bind a dummy tool (default on; catches Responses/tools regressions)",
    )
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="Do not bind tools",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the case matrix as JSON and exit without calling models",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write full run report JSON to this path",
    )
    args = parser.parse_args()

    from agent.config import Config
    from agent.model_benchmark import (
        cases_to_preview,
        collect_cloud_targets,
        expand_cases,
        load_suite,
        run_benchmark,
        write_run_report,
    )

    suite_name, questions = load_suite(args.suite)
    question_filter = set(_parse_csv(args.question) or [])
    if question_filter:
        questions = [q for q in questions if q.id in question_filter]
        if not questions:
            print("Error: no questions matched --question filter", file=sys.stderr)
            return 2

    config = Config.load()

    def has_key(provider: str) -> bool:
        try:
            return bool(str(config.llm_api_key(provider) or "").strip())
        except Exception:
            return False

    targets = collect_cloud_targets(
        provider=args.provider,
        model=args.model,
        has_key=has_key,
    )
    if not targets:
        print(
            "Error: no catalog targets matched (check API keys / --provider / --model)",
            file=sys.stderr,
        )
        return 2

    efforts = _parse_csv(args.effort)
    cases = expand_cases(targets, questions, efforts=efforts)
    if args.limit and args.limit > 0:
        cases = cases[: args.limit]

    if args.dry_run:
        preview = {
            "suite": suite_name,
            "caseCount": len(cases),
            "cases": cases_to_preview(cases),
        }
        print(json.dumps(preview, indent=2))
        print(f"\n{len(cases)} case(s) (dry-run)", file=sys.stderr)
        return 0

    def on_start(index: int, total: int, case) -> None:
        effort = case.effort or "default"
        print(
            f"[{index}/{total}] {case.target.provider}/{case.target.model} "
            f"effort={effort} q={case.question.id} …",
            file=sys.stderr,
            flush=True,
        )

    def on_done(result) -> None:
        status = "ok" if result.ok else "FAIL"
        detail = result.preview or result.error or ""
        print(
            f"  {status} ({result.latency_ms}ms) {detail[:100]!r}",
            file=sys.stderr,
            flush=True,
        )

    run = run_benchmark(
        cases,
        suite_name=suite_name,
        with_tools=not args.no_tools,
        on_case_start=on_start,
        on_case_done=on_done,
        config=config,
    )
    report = run.to_dict()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.output:
        write_run_report(run, args.output)
        print(f"Wrote {args.output}", file=sys.stderr)

    summary = report["summary"]
    print(
        f"\n{summary['passed']}/{summary['total']} passed, "
        f"{summary['failed']} failed",
        file=sys.stderr,
    )
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
