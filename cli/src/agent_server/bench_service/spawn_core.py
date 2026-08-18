"""In-process agent-suite spawn + grade (no HTTP loopback)."""

from __future__ import annotations

import logging
import shutil
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from agent_server.app_deps import AppDeps
from agent_server.bench_service.bootstrap import ensure_sandwalk_bench_importable
from agent_server.bench_service.checkpoint import delete_checkpoint, save_checkpoint
from agent_server.bench_service.cleanup import delete_bench_project_data
from agent_server.bench_service.environment import capture_bench_environment
from agent_server.bench_service.grade import build_result, extract_answer, grade_row
from agent_server.bench_service.judge import (
    collect_tool_names_from_events,
    heuristic_checklist,
    run_llm_judge,
)
from agent_server.bench_service.results_store import (
    get_result,
    new_run_id,
    resolve_bench_provider,
    save_result,
)
from agent_server.bench_service.usage_rollup import rollup_suite_usage
from agent_server.settings_service import SettingsService

logger = logging.getLogger(__name__)

CHECKPOINT_EVERY = 10
StopCheck = Callable[[], str | None]


def run_agent_suite(
    *,
    deps: AppDeps,
    suite_id: str,
    pack_id: str,
    matrix: str | None,
    model_id: str,
    provider: str | None,
    sample_size: int | None,
    project_name: str | None,
    specialist_id: str | None = None,
    thinking: bool = False,
    client_surface: str = "ui",
    run_id: str | None = None,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    stop_check: StopCheck | None = None,
    concurrency: int = 1,
    cleanup_sessions: bool = False,
    resume_checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not ensure_sandwalk_bench_importable():
        raise RuntimeError(
            "sandwalk-bench packs not available (set SANDWALK_BENCH_ROOT)"
        )

    from sandwalk_bench.spawn import (
        bench_kickoff_message,
        build_project_description,
        default_project_name,
    )

    run_id = run_id or (
        str(resume_checkpoint.get("run_id")) if resume_checkpoint else None
    ) or new_run_id()
    from agent_server.bench_service.coding_suites import CODING_SUITES
    from agent_server.bench_service.mcq_suites import MCQ_SUITES

    def _reason() -> str | None:
        if stop_check:
            return stop_check()
        if cancel_check and cancel_check():
            return "cancel"
        return None

    skipped_meta: list[dict[str, Any]] = []
    if suite_id in MCQ_SUITES or pack_id in MCQ_SUITES:
        cells, pack, benchmark = _resolve_mcq_cells(
            suite_id=suite_id if suite_id in MCQ_SUITES else pack_id,
            sample_size=sample_size,
            model_id=model_id,
            provider=provider,
        )
    elif suite_id in CODING_SUITES or pack_id in CODING_SUITES:
        cells, pack, benchmark = _resolve_coding_cells(
            suite_id=suite_id if suite_id in CODING_SUITES else pack_id,
            sample_size=sample_size,
            model_id=model_id,
            provider=provider,
        )
    else:
        cells, pack, benchmark, skipped_meta = _resolve_cells(
            pack_id=pack_id,
            matrix=matrix,
            suite_id=suite_id,
            sample_size=sample_size,
            model_id=model_id,
            provider=provider,
            store=deps.store,
        )
    if not cells and skipped_meta:
        raise RuntimeError(
            f"All questions for {suite_id} were skipped — install missing "
            "skills/MCPs or pick another suite."
        )
    if not cells:
        raise RuntimeError(f"No cells for suite {suite_id}")

    settings = SettingsService.get()
    use_provider = resolve_bench_provider(
        provider or str(getattr(cells[0], "provider", None) or settings.provider),
        profile_id=getattr(settings, "openai_profile_id", None),
    ) or provider or str(getattr(cells[0], "provider", None) or settings.provider)
    use_model = model_id or cells[0].model_id
    workers = max(1, int(concurrency or 1))

    prior = get_result(run_id) if resume_checkpoint else None
    completed_ids: set[str] = {
        str(x)
        for x in ((resume_checkpoint or {}).get("completed_question_ids") or [])
    }
    question_rows: list[dict[str, Any]] = []
    if resume_checkpoint and prior and isinstance(prior.get("questions"), list):
        question_rows = list(prior["questions"])
        for row in question_rows:
            qid = row.get("question_id")
            if qid:
                completed_ids.add(str(qid))

    if resume_checkpoint and resume_checkpoint.get("environment"):
        environment = dict(resume_checkpoint["environment"])
    else:
        environment = capture_bench_environment(
            deps,
            model_id=use_model,
            provider=use_provider,
            specialist_id=specialist_id,
            thinking=thinking,
            suite_id=suite_id,
            sample_size=sample_size,
            pack_id=pack_id,
            matrix=matrix,
        )

    project_id = (
        str(resume_checkpoint.get("project_id"))
        if resume_checkpoint and resume_checkpoint.get("project_id")
        else None
    )
    workers_store = deps.worker_store()
    workers_svc = deps.worker_service()
    if project_id:
        project = workers_store.get_project(project_id)
        if project is None:
            project_id = None
    if not project_id:
        from agent_server.bench_service.catalog import pack_display_title

        name = project_name or default_project_name(
            pack_display_title(pack.id) or pack.id,
            matrix or suite_id,
        )
        desc = build_project_description(
            pack=pack, matrix_name=matrix or suite_id, cells=cells
        )
        project = workers_store.create_project(
            name=name,
            description=desc,
            agent_context=None,
            icon="sparkles",
            color="purple",
            pinned=True,
        )
        project_id = project.id
    else:
        project = workers_store.get_project(project_id)

    pending = [
        (idx, cell)
        for idx, cell in enumerate(cells)
        if str(cell.question_id) not in completed_ids
    ]
    total = len(cells)
    done_count = total - len(pending)
    elapsed_base = float(
        (resume_checkpoint or {}).get("elapsed_s")
        or (prior or {}).get("time_s")
        or 0
    )
    start = time.time()
    stop_reason: str | None = None
    merge_lock = threading.Lock()
    in_flight: set[str] = set()

    def _checkpoint(status: str) -> None:
        remaining = [
            str(c.question_id) for c in cells if str(c.question_id) not in completed_ids
        ]
        save_checkpoint(
            {
                "run_id": run_id,
                "status": status,
                "suite_id": suite_id,
                "pack_id": pack_id,
                "matrix": matrix,
                "model_id": use_model,
                "provider": use_provider,
                "sample_size": sample_size,
                "project_id": project_id,
                "project_name": project_name,
                "specialist_id": specialist_id,
                "thinking": thinking,
                "client_surface": client_surface,
                "concurrency": workers,
                "cleanup_sessions": cleanup_sessions,
                "completed_question_ids": sorted(completed_ids),
                "remaining_question_ids": remaining,
                "environment": environment,
                "elapsed_s": elapsed_base + (time.time() - start),
                "benchmark": benchmark,
            }
        )

    def _persist_partial(status: str) -> dict[str, Any]:
        with merge_lock:
            rows = list(question_rows)
        result = build_result(
            run_id=run_id,
            model_id=use_model,
            benchmark=benchmark,
            questions=rows,
            time_s=elapsed_base + (time.time() - start),
            thinking_used=thinking,
            project_id=project_id,
            environment=environment,
        )
        result["status"] = status
        result["provider"] = use_provider
        prior_name = (resume_checkpoint or {}).get("name") or (prior or {}).get("name")
        if prior_name:
            result["name"] = prior_name
        save_result(result)
        rollup_suite_usage(
            chat_store=deps.store,
            bench_store=workers_store,
            result=result,
            surface=client_surface,
        )
        save_result(result)
        _checkpoint(status)
        return result

    def _progress(
        *,
        phase: str,
        message: str,
        bench_current: int,
        in_flight_n: int = 0,
    ) -> None:
        if not on_progress:
            return
        on_progress(
            {
                "type": "progress",
                "phase": phase,
                "model_id": use_model,
                "benchmark": benchmark,
                "message": message,
                "current": 0,
                "total": 1,
                "bench_current": bench_current,
                "bench_total": total,
                "in_flight": in_flight_n,
            }
        )

    def _run_cell(idx: int, cell: Any) -> dict[str, Any] | None:
        nonlocal stop_reason
        reason = _reason()
        if reason:
            stop_reason = reason
            return None
        cell_model = use_model or cell.model_id
        # Per-session model — do not churn global SettingsService (disk + env)
        # under multi-worker load.
        session = workers_svc.create_session(
            title=cell.title,
            workspace_path=None,
            project_id=project_id,
            specialist_id=specialist_id,
            client_surface=client_surface,
            source="bench",
            provider=use_provider,
            model=cell_model,
        )
        session = workers_svc.ensure_workspace(session.id)
        sid = session.id
        with merge_lock:
            in_flight.add(sid)
            flying = len(in_flight)
            completed_n = len(completed_ids)
        _progress(
            phase="running",
            message=f"Running {cell.question_id} ({completed_n + 1}/{total})...",
            bench_current=completed_n,
            in_flight_n=flying,
        )
        try:
            ws = Path(session.workspace_path or "")
            if ws:
                _copy_inputs(pack, cell, ws)
                (ws / "BENCH_PROMPT.md").write_text(cell.prompt, encoding="utf-8")
            # Chat stores only a short kickoff — full text stays in BENCH_PROMPT.md.
            if _reason():
                stop_reason = _reason() or "pause"
                return None
            try:
                workers_svc.submit_message(
                    session_id=sid,
                    content=bench_kickoff_message(question_id=cell.question_id),
                )
            except RuntimeError as exc:
                if "event loop" in str(exc).lower():
                    stop_reason = stop_reason or "pause"
                    return None
                raise
            _wait_until_settled(deps, sid, stop_check=_reason, timeout_s=3600)
            reason = _reason()
            if reason:
                stop_reason = reason
                try:
                    workers_svc.interrupt(sid)
                except Exception:  # noqa: BLE001
                    pass
                return None
            return _grade_session(
                deps,
                session_id=sid,
                cell=cell,
                index=idx,
            )
        finally:
            with merge_lock:
                in_flight.discard(sid)

    _persist_partial("running")
    _progress(
        phase="spawning",
        message=f"Resuming {suite_id}…" if resume_checkpoint else f"Starting {suite_id}…",
        bench_current=done_count,
    )

    work: list[tuple[int, Any]] = list(pending)
    work_lock = threading.Lock()

    def _claim() -> tuple[int, Any] | None:
        reason = _reason()
        if reason:
            return None
        with work_lock:
            if not work:
                return None
            return work.pop(0)

    def _worker() -> None:
        nonlocal stop_reason
        while True:
            claimed = _claim()
            if claimed is None:
                reason = _reason()
                if reason:
                    stop_reason = reason
                return
            idx, cell = claimed
            try:
                row = _run_cell(idx, cell)
            except RuntimeError as exc:
                if "event loop" in str(exc).lower():
                    stop_reason = stop_reason or "pause"
                    return
                logger.exception("bench cell failed: %s", exc)
                row = {
                    "id": str(idx),
                    "correct": False,
                    "expected": "",
                    "predicted": "",
                    "question": str(getattr(cell, "prompt", ""))[:2000],
                    "raw_response": "",
                    "category": str(cell.question_id),
                    "question_id": str(cell.question_id),
                    "time_s": 0,
                    "session_id": None,
                    "eval_mode": "error",
                    "judge": {"error": str(exc)},
                    "tools_seen": [],
                    "heuristics": {},
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception("bench cell failed: %s", exc)
                row = {
                    "id": str(idx),
                    "correct": False,
                    "expected": "",
                    "predicted": "",
                    "question": str(getattr(cell, "prompt", ""))[:2000],
                    "raw_response": "",
                    "category": str(cell.question_id),
                    "question_id": str(cell.question_id),
                    "time_s": 0,
                    "session_id": None,
                    "eval_mode": "error",
                    "judge": {"error": str(exc)},
                    "tools_seen": [],
                    "heuristics": {},
                }
            if row is None:
                reason = _reason() or "pause"
                stop_reason = reason
                with merge_lock:
                    sessions = list(in_flight)
                for sid in sessions:
                    try:
                        workers_svc.interrupt(sid)
                    except Exception:  # noqa: BLE001
                        pass
                return
            with merge_lock:
                row["question_id"] = str(cell.question_id)
                question_rows.append(row)
                completed_ids.add(str(cell.question_id))
                n = len(completed_ids)
                flying = len(in_flight)
            if n % CHECKPOINT_EVERY == 0:
                _persist_partial("running")
            _progress(
                phase="grading",
                message=f"Completed {cell.question_id} ({n}/{total})",
                bench_current=n,
                in_flight_n=flying,
            )

    if workers == 1:
        _worker()
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(_worker) for _ in range(workers)]
            for fut in as_completed(futs):
                fut.result()
    if stop_reason is None:
        stop_reason = _reason()

    if stop_reason is None and skipped_meta and not resume_checkpoint:
        base = len(question_rows)
        for skip_idx, item in enumerate(skipped_meta):
            question_rows.append(
                _skipped_question_row(item, index=base + skip_idx)
            )

    if stop_reason == "pause":
        result = _persist_partial("paused")
        _progress(
            phase="paused",
            message="Paused — resume to continue",
            bench_current=len(completed_ids),
            in_flight_n=0,
        )
        return result
    if stop_reason == "cancel":
        result = _persist_partial("cancelled")
        delete_checkpoint(run_id)
        _progress(
            phase="idle",
            message="Cancelled",
            bench_current=len(completed_ids),
            in_flight_n=0,
        )
        return result

    result = build_result(
        run_id=run_id,
        model_id=use_model,
        benchmark=benchmark,
        questions=question_rows,
        time_s=elapsed_base + (time.time() - start),
        thinking_used=thinking,
        project_id=project_id,
        environment=environment,
    )
    result["status"] = "completed"
    result["provider"] = use_provider
    prior_name = (resume_checkpoint or {}).get("name") or (prior or {}).get("name")
    if prior_name:
        result["name"] = prior_name
    save_result(result)
    rollup_suite_usage(
        chat_store=deps.store,
        bench_store=workers_store,
        result=result,
        surface=client_surface,
    )
    save_result(result)
    delete_checkpoint(run_id)
    if cleanup_sessions:
        delete_bench_project_data(workers_store, project_id)
        result["project_id"] = None
        result["sessions_cleaned"] = True
        save_result(result)
    return result


def _resolve_mcq_cells(
    *,
    suite_id: str,
    sample_size: int | None,
    model_id: str,
    provider: str | None,
):
    """MCQ suites (MMLU / MMLU-Pro / ARC-C) as agent-session cells."""
    from sandwalk_bench.schema import MatrixCell, Pack, Question

    from agent_server.bench_service.mcq_suites import (
        MCQ_SUITES,
        format_mcq_prompt,
        load_mcq_items,
    )

    suite = MCQ_SUITES[suite_id]
    items = load_mcq_items(suite_id, int(sample_size or suite.default_sample_size))
    mid = model_id or "openai/gpt-5.6-luna-pro"
    prov = provider or "openrouter"
    questions: list[Question] = []
    cells: list[MatrixCell] = []
    for idx, item in enumerate(items):
        subject = str(item.get("subject") or "unknown")
        prompt = (
            f"{format_mcq_prompt(suite_id, item).rstrip()}\n\n"
            "End with a single line: Answer: <letter>"
        )
        qid = item.get("id") or f"{suite_id}-{idx}"
        q = Question(
            id=str(qid),
            question=str(item["question"]),
            ideal=str(item["answer"]),
            eval_mode="mcq",
            title=f"{suite.title} · {subject.replace('_', ' ')}",
            focus=subject,
            prompt=prompt,
            source={"subject": subject, "suite": suite_id},
        )
        questions.append(q)
        cells.append(
            MatrixCell(
                question_id=q.id,
                model_key=mid,
                model_id=mid,
                provider=prov,
                title=f"{q.title} · {mid.split('/')[-1]}",
                prompt=prompt,
                question=q,
            )
        )
    pack = Pack(
        id=suite_id,
        version="1.0",
        description=f"{suite.title} via Sandwalk agent sessions",
        questions=questions,
        matrices={},
    )
    return cells, pack, suite_id


def _resolve_coding_cells(
    *,
    suite_id: str,
    sample_size: int | None,
    model_id: str,
    provider: str | None,
):
    """MBPP / LiveCodeBench as agent-session cells (host-side code exec grade)."""
    from sandwalk_bench.schema import MatrixCell, Pack, Question

    from agent_server.bench_service.coding_suites import (
        CODING_SUITES,
        format_coding_prompt,
        load_coding_items,
    )

    suite = CODING_SUITES[suite_id]
    items = load_coding_items(suite_id, int(sample_size or suite.default_sample_size))
    mid = model_id or "openai/gpt-5.6-luna-pro"
    prov = provider or "openrouter"
    questions: list[Question] = []
    cells: list[MatrixCell] = []
    for idx, item in enumerate(items):
        subject = str(item.get("subject") or "coding")
        prompt = format_coding_prompt(suite_id, item)
        qid = item.get("id") or f"{suite_id}-{idx}"
        source = {"suite": suite_id, **{k: v for k, v in item.items() if k != "question"}}
        title_bit = item.get("title") or subject
        q = Question(
            id=str(qid),
            question=str(item["question"]),
            ideal="(test cases)",
            eval_mode="code_exec",
            title=f"{suite.title} · {title_bit}",
            focus=subject,
            prompt=prompt,
            source=source,
        )
        questions.append(q)
        cells.append(
            MatrixCell(
                question_id=q.id,
                model_key=mid,
                model_id=mid,
                provider=prov,
                title=f"{q.title} · {mid.split('/')[-1]}",
                prompt=prompt,
                question=q,
            )
        )
    pack = Pack(
        id=suite_id,
        version="1.0",
        description=f"{suite.title} via Sandwalk agent sessions",
        questions=questions,
        matrices={},
    )
    return cells, pack, suite_id


def _resolve_cells(
    *,
    pack_id: str,
    matrix: str | None,
    suite_id: str,
    sample_size: int | None,
    model_id: str,
    provider: str | None,
    store: Any | None = None,
):
    from sandwalk_bench.bixbench import as_is_pack, jsonl_path, load_jsonl
    from sandwalk_bench.pack import expand_matrix, load_pack
    from sandwalk_bench.paths import PACKS_DIR
    from sandwalk_bench.schema import MatrixCell
    from sandwalk_bench.spawn import copy_cell_inputs  # noqa: F401

    from agent_server.bench_service.pack_requirements import (
        partition_cells_by_requirements,
    )

    if pack_id == "bixbench-verified-50" or suite_id == "bixbench-verified-50":
        if not jsonl_path().is_file():
            raise FileNotFoundError(
                "BixBench-Verified-50 JSONL missing. Run sandwalk-bench bixbench download"
            )
        pack = as_is_pack(load_jsonl())
        questions = list(pack.questions)
        if sample_size and sample_size > 0:
            questions = questions[:sample_size]
        mid = model_id or "openai/gpt-5.6-luna-pro"
        prov = provider or "openrouter"
        cells = []
        for q in questions:
            prompt = (
                f"{q.question.strip()}\n\n"
                "Data for this analysis is under `data/` in the workspace. "
                "Work from those files.\n"
                "End with a single line: Answer: <value>"
            )
            cells.append(
                MatrixCell(
                    question_id=q.id,
                    model_key=mid,
                    model_id=mid,
                    provider=prov,
                    title=f"{q.title or q.id} · {mid.split('/')[-1]}",
                    prompt=prompt,
                    question=q,
                )
            )
        return cells, pack, "bixbench-verified-50", []

    # YAML pack + matrix — filename may differ from pack.id
    # (e.g. sandwalk_skills_mcp.yaml → pack: bio-capybara-full).
    from sandwalk_bench.pack import list_packs

    from agent_server.bench_service.catalog import pack_matches_id

    path = PACKS_DIR / f"{pack_id}.yaml"
    if not path.is_file():
        path = PACKS_DIR / f"{pack_id}.yml"
    if not path.is_file():
        for candidate in list_packs():
            try:
                loaded = load_pack(candidate)
            except Exception:  # noqa: BLE001
                continue
            if pack_matches_id(loaded, pack_id) or candidate.stem == pack_id:
                path = candidate
                break
    pack = load_pack(path)
    if not matrix:
        # suite_id like pack:matrix, or bare pack id from Bench UI
        if ":" in suite_id:
            matrix = suite_id.split(":", 1)[1]
        else:
            from agent_server.bench_service.catalog import _preferred_matrix

            preferred, _ = _preferred_matrix(pack)
            matrix = preferred or next(iter(pack.matrices))
    cells = expand_matrix(pack, matrix)
    if model_id:
        from dataclasses import replace

        # Bench UI owns the model — overwrite YAML matrix models and keep
        # one cell per question (ignore multi-model product sweeps).
        deduped: list[Any] = []
        seen_q: set[str] = set()
        for cell in cells:
            qid = str(cell.question_id)
            if qid in seen_q:
                continue
            seen_q.add(qid)
            deduped.append(
                replace(
                    cell,
                    model_id=model_id,
                    provider=provider or cell.provider,
                )
            )
        cells = deduped
    # Soft-skip questions that need missing skills/MCPs, then sample.
    cells, skipped_meta = partition_cells_by_requirements(cells, store=store)
    if sample_size and sample_size > 0:
        cells = cells[:sample_size]
    from agent_server.bench_service.catalog import pack_display_title

    # Prefer the Dashboard card title (e.g. Bio-Capybara-full) over the
    # stable YAML pack id (bio-capybara-full).
    return cells, pack, pack_display_title(pack.id) or pack.id, skipped_meta


def _skipped_question_row(item: dict[str, Any], *, index: int) -> dict[str, Any]:
    cell = item["cell"]
    question = getattr(cell, "question", None)
    return {
        "id": str(index),
        "correct": False,
        "skipped": True,
        "skip_reason": item.get("reason") or "Missing skills/MCPs",
        "missing_skills": list(item.get("missing_skills") or []),
        "missing_mcps": list(item.get("missing_mcps") or []),
        "expected": (question.ideal if question else "") or "",
        "predicted": "",
        "question": (
            (question.question if question else cell.prompt) or ""
        )[:2000],
        "raw_response": "",
        "category": (
            (question.focus if question and question.focus else None)
            or (question.id if question else cell.question_id)
        ),
        "time_s": 0,
        "session_id": None,
        "eval_mode": str(question.eval_mode if question else "checklist"),
        "judge": None,
        "tools_seen": [],
        "heuristics": {},
    }


def _copy_inputs(pack: Any, cell: Any, workspace: Path) -> None:
    from sandwalk_bench.spawn import copy_cell_inputs

    from agent_server.bench_service.coding_suites import CODING_SUITES
    from agent_server.bench_service.mcq_suites import MCQ_SUITES

    if getattr(pack, "id", None) in MCQ_SUITES or getattr(pack, "id", None) in CODING_SUITES:
        return
    q = cell.question
    # Verified-50: try cached capsule
    if q and q.source.get("data_folder"):
        if _copy_bix_capsule(q.source, workspace):
            return
    copy_cell_inputs(pack, cell, workspace)


def _copy_bix_capsule(source: dict[str, Any], workspace: Path) -> bool:
    """Copy CapsuleData from HF cache (download on demand)."""
    folder = str(source.get("data_folder") or "")
    if not folder:
        return False
    try:
        from sandwalk_bench.capsules import ensure_capsule

        from agent_server.bench_service.dataset_install import resolve_hf_token

        data = ensure_capsule(folder, token=resolve_hf_token() or None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Capsule download failed for %s: %s", folder, exc)
        data = None
    if data and data.is_dir():
        dest = workspace / "data"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(data, dest)
        return True
    logger.warning("Capsule data missing for %s — session has empty data/", folder)
    (workspace / "data").mkdir(parents=True, exist_ok=True)
    return False


def _wait_until_settled(
    deps: AppDeps,
    session_id: str,
    *,
    cancel_check: Callable[[], bool] | None = None,
    stop_check: StopCheck | None = None,
    timeout_s: float,
) -> None:
    deadline = time.time() + timeout_s
    saw_running = False
    while time.time() < deadline:
        reason = stop_check() if stop_check else None
        if reason is None and cancel_check and cancel_check():
            reason = "cancel"
        if reason:
            try:
                deps.worker_service().interrupt(session_id)
            except Exception:  # noqa: BLE001
                pass
            return
        session = deps.worker_store().get_session(session_id)
        if session is None:
            return
        status = session.status
        if status in {"running", "awaiting_approval"}:
            saw_running = True
        if saw_running and status in {"idle", "error", "interrupted"}:
            return
        if not saw_running and status == "idle":
            # wait a bit for status to flip to running
            time.sleep(0.5)
            session = deps.worker_store().get_session(session_id)
            if session and session.status == "idle":
                # maybe finished very fast
                msgs = deps.worker_store().list_messages(session_id)
                if any(m.role == "assistant" for m in msgs):
                    return
        time.sleep(1.0)


def _grade_session(deps: AppDeps, *, session_id: str, cell: Any, index: int) -> dict[str, Any]:
    msgs = deps.worker_store().list_messages(session_id)
    assistant = ""
    for m in reversed(msgs):
        if m.role == "assistant" and (m.content or "").strip():
            assistant = m.content or ""
            break
    q = cell.question
    eval_mode = str(q.eval_mode if q else "checklist")
    ideal = q.ideal if q else None
    source = (q.source if q else {}) or {}
    # Code-exec suites grade the full assistant transcript (code blocks), not
    # a trailing Answer: line.
    predicted = assistant if eval_mode == "code_exec" else extract_answer(assistant)
    events = deps.worker_store().list_events(session_id) if hasattr(deps.worker_store(), "list_events") else []
    tool_names = collect_tool_names_from_events(events)
    meta = (q.metadata if q else {}) or {}
    checklist = list(meta.get("checklist") or [])
    heur = heuristic_checklist(tool_names, checklist) if checklist else {}
    judge_payload = None
    judge_ok = None
    if eval_mode in {"llm_verifier", "checklist"}:
        evidence = assistant[-8000:]
        if tool_names:
            evidence = "Tools: " + ", ".join(tool_names[:40]) + "\n\n" + evidence
        judge_payload = run_llm_judge(
            evidence=evidence,
            ideal=ideal,
            rubric=str(meta.get("judge_rubric") or "") or None,
            checklist=checklist,
        )
        judge_ok = bool(judge_payload.get("overall_pass"))
        if judge_payload.get("predicted"):
            predicted = str(judge_payload["predicted"])
        # Merge heuristics: fail if any required heuristic failed
        if heur and not all(heur.values()):
            judge_ok = False
    ok = grade_row(
        eval_mode=eval_mode,
        ideal=ideal,
        predicted=predicted,
        judge_ok=judge_ok,
        source=source,
    )
    return {
        "id": str(index),
        "question_id": str(cell.question_id),
        "correct": ok,
        "expected": ideal or "",
        "predicted": predicted,
        "question": (q.question if q else cell.prompt)[:2000],
        "raw_response": assistant[:4000],
        "category": (q.focus if q and q.focus else None)
        or (q.source.get("categories") if q else None)
        or (q.id if q else cell.question_id),
        "time_s": 0,
        "session_id": session_id,
        "eval_mode": eval_mode,
        "judge": judge_payload,
        "tools_seen": tool_names[:50],
        "heuristics": heur,
    }

