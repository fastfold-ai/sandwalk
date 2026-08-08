"""In-process agent-suite spawn + grade (no HTTP loopback)."""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Any, Callable

from agent_server.app_deps import AppDeps
from agent_server.bench_service.bootstrap import ensure_sandwalk_bench_importable
from agent_server.bench_service.environment import capture_bench_environment
from agent_server.bench_service.grade import build_result, extract_answer, grade_row
from agent_server.bench_service.judge import (
    collect_tool_names_from_events,
    heuristic_checklist,
    run_llm_judge,
)
from agent_server.bench_service.results_store import new_run_id, save_result
from agent_server.models import UpdateRuntimeSettingsRequest
from agent_server.settings_service import SettingsService

logger = logging.getLogger(__name__)


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
) -> dict[str, Any]:
    if not ensure_sandwalk_bench_importable():
        raise RuntimeError(
            "sandwalk-bench packs not available (set SANDWALK_BENCH_ROOT)"
        )

    from sandwalk_bench.spawn import (
        build_project_description,
        default_project_name,
    )

    run_id = run_id or new_run_id()
    from agent_server.bench_service.coding_suites import CODING_SUITES
    from agent_server.bench_service.mcq_suites import MCQ_SUITES

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
        cells, pack, benchmark = _resolve_cells(
            pack_id=pack_id,
            matrix=matrix,
            suite_id=suite_id,
            sample_size=sample_size,
            model_id=model_id,
            provider=provider,
        )
    if not cells:
        raise RuntimeError(f"No cells for suite {suite_id}")

    settings = SettingsService.get()
    orig = (settings.provider, settings.model)
    use_provider = provider or str(getattr(cells[0], "provider", None) or settings.provider)
    use_model = model_id or cells[0].model_id

    # Snapshot before mutating runtime settings / creating sessions.
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

    name = project_name or default_project_name(pack.id, matrix or suite_id)
    desc = build_project_description(pack=pack, matrix_name=matrix or suite_id, cells=cells)
    project = deps.store.create_project(
        name=name,
        description=desc,
        agent_context=None,
        icon="sparkles",
        color="purple",
        pinned=True,
    )

    start = time.time()
    question_rows: list[dict[str, Any]] = []
    try:
        total = len(cells)
        for idx, cell in enumerate(cells):
            if cancel_check and cancel_check():
                break
            cell_model = use_model or cell.model_id
            if on_progress:
                on_progress(
                    {
                        "type": "progress",
                        "phase": "spawning",
                        "model_id": cell_model,
                        "benchmark": benchmark,
                        "message": f"Evaluating {cell.question_id} ({idx}/{total})...",
                        "current": 0,
                        "total": 1,
                        "bench_current": idx,
                        "bench_total": total,
                    }
                )
            SettingsService.update(
                UpdateRuntimeSettingsRequest(provider=use_provider, model=cell_model)
            )
            time.sleep(0.2)
            session = deps.service.create_session(
                title=cell.title,
                workspace_path=None,
                project_id=project.id,
                specialist_id=specialist_id,
                client_surface=client_surface,
            )
            session = deps.service.ensure_workspace(session.id)
            ws = Path(session.workspace_path or "")
            if ws:
                _copy_inputs(pack, cell, ws)
                (ws / "BENCH_PROMPT.md").write_text(cell.prompt, encoding="utf-8")

            if on_progress:
                on_progress(
                    {
                        "type": "progress",
                        "phase": "running",
                        "model_id": cell_model,
                        "benchmark": benchmark,
                        "message": f"Running {cell.question_id} ({idx + 1}/{total})...",
                        "current": 0,
                        "total": 1,
                        "bench_current": idx,
                        "bench_total": total,
                    }
                )
            deps.service.submit_message(session_id=session.id, content=cell.prompt)
            _wait_until_settled(deps, session.id, cancel_check=cancel_check, timeout_s=3600)

            if on_progress:
                on_progress(
                    {
                        "type": "progress",
                        "phase": "grading",
                        "model_id": cell_model,
                        "benchmark": benchmark,
                        "message": f"Grading {cell.question_id}...",
                        "current": 0,
                        "total": 1,
                        "bench_current": idx,
                        "bench_total": total,
                    }
                )
            question_rows.append(
                _grade_session(
                    deps,
                    session_id=session.id,
                    cell=cell,
                    index=idx,
                )
            )
    finally:
        SettingsService.update(
            UpdateRuntimeSettingsRequest(provider=orig[0], model=orig[1])
        )

    result = build_result(
        run_id=run_id,
        model_id=use_model,
        benchmark=benchmark,
        questions=question_rows,
        time_s=time.time() - start,
        thinking_used=thinking,
        project_id=project.id,
        environment=environment,
    )
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
    from agent_server.bench_service.mcq_suites import (
        MCQ_SUITES,
        format_mcq_prompt,
        load_mcq_items,
    )
    from sandwalk_bench.schema import MatrixCell, Pack, Question

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
    from agent_server.bench_service.coding_suites import (
        CODING_SUITES,
        format_coding_prompt,
        load_coding_items,
    )
    from sandwalk_bench.schema import MatrixCell, Pack, Question

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
):
    from sandwalk_bench.bixbench import as_is_pack, jsonl_path, load_jsonl
    from sandwalk_bench.pack import expand_matrix, load_pack
    from sandwalk_bench.paths import PACKS_DIR
    from sandwalk_bench.schema import MatrixCell
    from sandwalk_bench.spawn import copy_cell_inputs  # noqa: F401

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
        return cells, pack, "bixbench-verified-50"

    # YAML pack + matrix — filename may differ from pack.id
    # (e.g. sandwalk_skills_mcp.yaml → pack: skills-mcp-bakeoff).
    from sandwalk_bench.pack import list_packs

    path = PACKS_DIR / f"{pack_id}.yaml"
    if not path.is_file():
        path = PACKS_DIR / f"{pack_id}.yml"
    if not path.is_file():
        for candidate in list_packs():
            try:
                loaded = load_pack(candidate)
            except Exception:  # noqa: BLE001
                continue
            if loaded.id == pack_id or candidate.stem == pack_id:
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
    if sample_size and sample_size > 0:
        cells = cells[:sample_size]
    return cells, pack, pack.id


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
        from agent_server.bench_service.dataset_install import resolve_hf_token
        from sandwalk_bench.capsules import ensure_capsule

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
    cancel_check: Callable[[], bool] | None,
    timeout_s: float,
) -> None:
    deadline = time.time() + timeout_s
    saw_running = False
    while time.time() < deadline:
        if cancel_check and cancel_check():
            try:
                deps.service.interrupt(session_id)
            except Exception:  # noqa: BLE001
                pass
            return
        session = deps.store.get_session(session_id)
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
            session = deps.store.get_session(session_id)
            if session and session.status == "idle":
                # maybe finished very fast
                msgs = deps.store.list_messages(session_id)
                if any(m.role == "assistant" for m in msgs):
                    return
        time.sleep(1.0)


def _grade_session(deps: AppDeps, *, session_id: str, cell: Any, index: int) -> dict[str, Any]:
    msgs = deps.store.list_messages(session_id)
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
    events = deps.store.list_events(session_id) if hasattr(deps.store, "list_events") else []
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

