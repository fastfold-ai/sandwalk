"""Unified suite catalog: MCQ knowledge + Bix + Skills/MCP."""

from __future__ import annotations

from typing import Any

from agent_server.bench_service.bootstrap import (
    ensure_sandwalk_bench_importable,
    packs_dir,
)
from agent_server.bench_service.coding_suites import (
    CODING_SUITES,
)
from agent_server.bench_service.coding_suites import (
    catalog_sample_sizes as coding_sample_sizes,
)
from agent_server.bench_service.coding_suites import (
    count_fixture as coding_count,
)
from agent_server.bench_service.coding_suites import (
    dataset_available as coding_available,
)
from agent_server.bench_service.dataset_install import (
    INSTALLABLE_SUITE_IDS,
    hf_token_configured,
    missing_parquet_dependency,
    suite_installed_bytes,
    suite_installed_count,
    total_cache_bytes,
)
from agent_server.bench_service.install_jobs import (
    get_install_job,
    install_error,
    install_progress_text,
    is_installing,
)
from agent_server.bench_service.mcq_suites import (
    MCQ_SUITES,
    catalog_sample_sizes,
    count_fixture,
    dataset_available,
    full_dataset_available,
)
from agent_server.bench_service.pack_requirements import (
    missing_pack_requirements,
    required_skills_mcps,
    skip_warning_message,
)
from agent_server.models.bench import BenchSuiteCard

# Friendly titles for YAML packs (UI picks models; one card per pack).
_PACK_TITLES = {
    "bio-capybara-full": "Bio-Capybara-full",
    # Legacy pack id (pre-rename).
    "skills-mcp-bakeoff": "Bio-Capybara-full",
}

# Author attribution shown on suite cards (local-web serves /brand/bench/*).
_PACK_AUTHORS = {
    "bio-capybara-full": ("Sandwalk", "/brand/bench/sandwalk-mark.svg"),
    "skills-mcp-bakeoff": ("Sandwalk", "/brand/bench/sandwalk-mark.svg"),
}


def pack_display_title(pack_id: str | None) -> str:
    """Human label for a pack/suite id (falls back to the raw id)."""
    if not pack_id:
        return ""
    key = str(pack_id)
    return _PACK_TITLES.get(key, key)


def pack_aliases(pack: Any) -> list[str]:
    """Legacy ids from YAML `aliases:` (plus the current pack.id)."""
    raw = getattr(pack, "raw", None) or {}
    aliases = [str(x) for x in (raw.get("aliases") or []) if x]
    return [str(pack.id), *aliases]


def pack_matches_id(pack: Any, pack_id: str) -> bool:
    return str(pack_id) in pack_aliases(pack)

def list_suite_cards(store: Any | None = None) -> list[BenchSuiteCard]:
    cards: list[BenchSuiteCard] = []
    hf_ready = hf_token_configured()
    dep_hint = missing_parquet_dependency()
    for suite in MCQ_SUITES.values():
        n = count_fixture(suite.id)
        ok = dataset_available(suite.id)
        full_ok = full_dataset_available(suite.id)
        installable = suite.id in INSTALLABLE_SUITE_IDS
        installing = is_installing(suite.id)
        err = install_error(suite.id)
        progress = install_progress_text(suite.id) if installing else None
        job = get_install_job(suite.id) if installing else None
        # Only offer sizes the local data can actually satisfy: with just the
        # 30-row sample fixture, larger picks used to fail mid-run.
        sizes = catalog_sample_sizes(suite, full_available=full_ok)
        if installing:
            reason = progress or f"Downloading {suite.title} in the background…"
        elif err:
            reason = err
        elif not ok:
            reason = (
                f"{suite.title} dataset missing. Click Install to download it."
                if installable
                else (
                    f"{suite.title} dataset missing. Place "
                    f"{suite.full_fixture} under apps/benchmarking/.cache/mcq/"
                )
            )
        elif not full_ok:
            reason = (
                f"Sample fixture only ({max(sizes)} questions). "
                f"Install {suite.title} to unlock larger sample sizes."
            )
        else:
            reason = None
        cards.append(
            BenchSuiteCard(
                id=suite.id,
                title=suite.title,
                description=suite.description,
                lane="intelligence",
                runner="agent",
                # Corpus size is a property of the benchmark; install state is
                # conveyed through available / unavailable_reason instead.
                question_count=n,
                sample_sizes=sizes,
                default_sample_size=min(suite.default_sample_size, max(sizes)),
                available=ok,
                unavailable_reason=reason,
                author=suite.author,
                author_avatar=suite.author_avatar,
                code_exec=False,
                installable=installable,
                installing=installing,
                install_error=err,
                install_progress=progress,
                install_bytes_done=job.bytes_done if job else None,
                install_bytes_total=job.bytes_total if job else None,
                installed=full_ok,
                installed_bytes=suite_installed_bytes(suite.id) or None,
                installed_count=suite_installed_count(suite.id),
                missing_dependency=dep_hint if installable else None,
            )
        )

    for suite in CODING_SUITES.values():
        n = coding_count(suite.id)
        ok = coding_available(suite.id)
        installable = suite.id in INSTALLABLE_SUITE_IDS
        installing = is_installing(suite.id)
        err = install_error(suite.id)
        progress = install_progress_text(suite.id) if installing else None
        job = get_install_job(suite.id) if installing else None
        if ok:
            reason = None
        elif installing:
            reason = progress or f"Downloading {suite.title} in the background…"
        elif err:
            reason = err
        elif installable:
            reason = f"{suite.title} dataset missing. Click Install to download it."
        else:
            reason = (
                f"{suite.title} dataset missing. Place "
                f"{suite.full_fixture} under apps/benchmarking/.cache/mcq/"
            )
        cards.append(
            BenchSuiteCard(
                id=suite.id,
                title=suite.title,
                description=suite.description,
                lane="intelligence",
                runner="agent",
                question_count=n,
                sample_sizes=coding_sample_sizes(suite),
                default_sample_size=suite.default_sample_size,
                available=ok,
                unavailable_reason=reason,
                author=suite.author,
                author_avatar=suite.author_avatar,
                code_exec=True,
                installable=installable,
                installing=installing,
                install_error=err,
                install_progress=progress,
                install_bytes_done=job.bytes_done if job else None,
                install_bytes_total=job.bytes_total if job else None,
                installed=ok,
                installed_bytes=suite_installed_bytes(suite.id) or None,
                installed_count=suite_installed_count(suite.id),
            )
        )

    bix_ok = _bix50_available()
    bix_installing = is_installing("bixbench-verified-50")
    bix_err = install_error("bixbench-verified-50")
    bix_progress = (
        install_progress_text("bixbench-verified-50") if bix_installing else None
    )
    bix_job = get_install_job("bixbench-verified-50") if bix_installing else None
    if bix_ok:
        bix_reason = None
    elif bix_installing:
        bix_reason = (
            bix_progress or "Downloading BixBench-Verified-50 in the background…"
        )
    elif bix_err:
        bix_reason = bix_err
    elif not hf_ready:
        bix_reason = (
            "Hugging Face token required. Set it under Integrations → Hugging Face, "
            "accept the dataset terms, then Install."
        )
    else:
        bix_reason = "Dataset not downloaded yet. Click Install to fetch BixBench-Verified-50."
    cards.append(
        BenchSuiteCard(
            id="bixbench-verified-50",
            title="BixBench-Verified-50",
            description=(
                "50 biology agent tasks with CapsuleData. "
                "Graded with str/range/llm verifiers."
            ),
            lane="intelligence",
            runner="agent",
            pack_id="bixbench-verified-50",
            question_count=50,
            sample_sizes=[5, 15, 50],
            default_sample_size=5,
            available=bix_ok,
            unavailable_reason=bix_reason,
            author="Phylo",
            author_avatar="/brand/bench/phylo-logo.png",
            installable=True,
            requires_hf_token=True,
            hf_token_configured=hf_ready,
            installing=bix_installing,
            install_error=bix_err,
            install_progress=bix_progress,
            install_bytes_done=bix_job.bytes_done if bix_job else None,
            install_bytes_total=bix_job.bytes_total if bix_job else None,
            installed=bix_ok,
            installed_bytes=suite_installed_bytes("bixbench-verified-50") or None,
        ),
    )

    if ensure_sandwalk_bench_importable() and packs_dir():
        from sandwalk_bench.pack import list_packs, load_pack

        for path in list_packs():
            pack = load_pack(path)
            matrix_name, matrix = _preferred_matrix(pack)
            if not matrix_name or matrix is None:
                continue
            n = _unique_question_count(pack, matrix)
            sample_sizes = [n] if n else []
            if n >= 5:
                sample_sizes = sorted({min(5, n), n})
            default_sample = min(sample_sizes) if sample_sizes else None
            author, avatar = _PACK_AUTHORS.get(pack.id, (None, None))
            req_skills, req_mcps = required_skills_mcps(pack)
            miss_skills, miss_mcps = missing_pack_requirements(pack, store=store)
            # Soft gate: suite stays selectable; runner skips questions that
            # need missing skills/MCPs.
            reason = skip_warning_message(miss_skills, miss_mcps)
            cards.append(
                BenchSuiteCard(
                    id=pack.id,
                    title=pack_display_title(pack.id),
                    description=(pack.description or "")[:240],
                    lane="skills"
                    if any(
                        token in pack.id
                        for token in ("skills", "bakeoff", "capybara")
                    )
                    or "skills" in str(getattr(pack, "path", "")).lower()
                    else "intelligence",
                    runner="agent",
                    pack_id=pack.id,
                    matrix=matrix_name,
                    question_count=n,
                    sample_sizes=sample_sizes,
                    default_sample_size=default_sample,
                    available=True,
                    unavailable_reason=reason,
                    author=author,
                    author_avatar=avatar,
                    required_skills=req_skills,
                    required_mcps=req_mcps,
                    missing_skills=miss_skills,
                    missing_mcps=miss_mcps,
                )
            )
    return cards


def _preferred_matrix(pack: Any) -> tuple[str | None, dict[str, Any] | None]:
    """Pick one matrix for Bench UI — UI owns models, so avoid model-sweep recipes."""
    matrices = pack.matrices or {}
    if not matrices:
        return None, None

    ranked: list[tuple[int, int, str, dict[str, Any]]] = []
    for name, matrix in matrices.items():
        mode = str(matrix.get("mode") or "pairs")
        n_models = len(matrix.get("models") or [])
        n_q = _unique_question_count(pack, matrix)
        # Prefer single-model product (or any product); deprioritize multi-model sweeps
        # and YAML pairs that latch models per question.
        if mode == "product" and n_models > 1:
            penalty = 1000
        elif mode == "pairs":
            penalty = 100
        elif mode == "product" and n_models <= 1:
            penalty = 0
        else:
            penalty = 50
        if "same-model" in name:
            penalty -= 10
        ranked.append((penalty, -n_q, name, matrix))
    ranked.sort(key=lambda row: (row[0], row[1], row[2]))
    _, _, name, matrix = ranked[0]
    return name, matrix


def _unique_question_count(pack: Any, matrix: dict[str, Any]) -> int:
    """Question count for UI (models are chosen in Bench, not multiplied here)."""
    mode = str(matrix.get("mode") or "pairs")
    if mode == "pairs":
        qids = {str(p.get("question")) for p in (matrix.get("pairs") or []) if p.get("question")}
        return len(qids)
    if mode == "product":
        return len(matrix.get("questions") or [])
    return len(pack.questions or [])


def _bix50_available() -> bool:
    if not ensure_sandwalk_bench_importable():
        return False
    try:
        from sandwalk_bench.bixbench import jsonl_path

        return jsonl_path().is_file()
    except Exception:
        return False
