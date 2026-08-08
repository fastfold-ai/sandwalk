"""Unified suite catalog: MCQ knowledge + Bix + Skills/MCP."""

from __future__ import annotations

from typing import Any

from agent_server.bench_service.bootstrap import (
    ensure_sandwalk_bench_importable,
    packs_dir,
)
from agent_server.bench_service.coding_suites import (
    CODING_SUITES,
    catalog_sample_sizes as coding_sample_sizes,
    count_fixture as coding_count,
    dataset_available as coding_available,
)
from agent_server.bench_service.dataset_install import (
    INSTALLABLE_SUITE_IDS,
    hf_token_configured,
)
from agent_server.bench_service.install_jobs import install_error, is_installing
from agent_server.bench_service.mcq_suites import (
    MCQ_SUITES,
    catalog_sample_sizes,
    count_fixture,
    dataset_available,
)
from agent_server.bench_service.pack_requirements import (
    missing_pack_requirements,
    required_skills_mcps,
)
from agent_server.models.bench import BenchSuiteCard

# Friendly titles for YAML packs (UI picks models; one card per pack).
_PACK_TITLES = {
    "skills-mcp-bakeoff": "Bio-Capybara-full",
}

# Author attribution shown on suite cards (local-web serves /brand/bench/*).
_PACK_AUTHORS = {
    "skills-mcp-bakeoff": ("Sandwalk", "/brand/bench/sandwalk-mark.svg"),
}

def list_suite_cards(store: Any | None = None) -> list[BenchSuiteCard]:
    cards: list[BenchSuiteCard] = []
    hf_ready = hf_token_configured()
    for suite in MCQ_SUITES.values():
        n = count_fixture(suite.id)
        ok = dataset_available(suite.id)
        cards.append(
            BenchSuiteCard(
                id=suite.id,
                title=suite.title,
                description=suite.description,
                lane="intelligence",
                runner="agent",
                question_count=n,
                sample_sizes=catalog_sample_sizes(suite),
                default_sample_size=suite.default_sample_size,
                available=ok,
                unavailable_reason=None
                if ok
                else (
                    f"{suite.title} dataset missing. Place "
                    f"{suite.full_fixture} under apps/benchmarking/.cache/mcq/"
                ),
                author=suite.author,
                author_avatar=suite.author_avatar,
                code_exec=False,
            )
        )

    for suite in CODING_SUITES.values():
        n = coding_count(suite.id)
        ok = coding_available(suite.id)
        installable = suite.id in INSTALLABLE_SUITE_IDS
        installing = is_installing(suite.id)
        err = install_error(suite.id)
        if ok:
            reason = None
        elif installing:
            reason = f"Downloading {suite.title} in the background…"
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
            )
        )

    bix_ok = _bix50_available()
    bix_installing = is_installing("bixbench-verified-50")
    bix_err = install_error("bixbench-verified-50")
    if bix_ok:
        bix_reason = None
    elif bix_installing:
        bix_reason = "Downloading BixBench-Verified-50 in the background…"
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
            author, avatar = _PACK_AUTHORS.get(pack.id, (None, None))
            req_skills, req_mcps = required_skills_mcps(pack)
            miss_skills, miss_mcps = missing_pack_requirements(pack, store=store)
            ready = not miss_skills and not miss_mcps
            if ready:
                reason = None
            elif miss_skills and miss_mcps:
                reason = (
                    f"Missing required skills ({len(miss_skills)}) and "
                    f"MCPs ({len(miss_mcps)}). Enable/install them before running."
                )
            elif miss_skills:
                reason = (
                    f"Missing required skills: {', '.join(miss_skills)}. "
                    "Install/enable them under Skills."
                )
            else:
                reason = (
                    f"Missing required MCPs: {', '.join(miss_mcps)}. "
                    "Install/enable them under MCP."
                )
            cards.append(
                BenchSuiteCard(
                    id=pack.id,
                    title=_PACK_TITLES.get(pack.id, pack.id),
                    description=(pack.description or "")[:240],
                    lane="skills"
                    if "skills" in pack.id or "bakeoff" in pack.id
                    else "intelligence",
                    runner="agent",
                    pack_id=pack.id,
                    matrix=matrix_name,
                    question_count=n,
                    sample_sizes=sample_sizes,
                    default_sample_size=n or None,
                    available=ready,
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
