"""Curated case study definitions and runner for ct.

Provides pre-defined multi-agent research profiles for landmark drugs,
designed for demos, conference presentations, and sales collateral.

Each case study defines 3-4 complementary research angles that are
executed in parallel via the ResearchOrchestrator (bypassing the LLM
decomposition step).
"""

import logging

from agent.case_studies.model import CaseStudy
from agent.case_studies.registry_keytruda_ozempic import KEYTRUDA, OZEMPIC
from agent.case_studies.registry_revlimid_gleevec import GLEEVEC, REVLIMID
from agent.case_studies.registry_xalkori import XALKORI
from agent.orchestrator import OrchestratorResult, ResearchOrchestrator, ThreadGoal

logger = logging.getLogger("case_studies")

CASE_STUDIES: dict[str, CaseStudy] = {
    "revlimid": REVLIMID,
    "gleevec": GLEEVEC,
    "keytruda": KEYTRUDA,
    "ozempic": OZEMPIC,
    "xalkori": XALKORI,
}


def build_thread_goals(case: CaseStudy) -> list[ThreadGoal]:
    """Convert case study thread_goals dicts into ThreadGoal objects.

    Parameters
    ----------
    case : CaseStudy
        The case study whose thread goals to build.

    Returns
    -------
    list[ThreadGoal]
        Ordered list of ThreadGoal objects with sequential IDs.
    """
    goals = []
    for i, g in enumerate(case.thread_goals, start=1):
        goals.append(
            ThreadGoal(
                thread_id=i,
                angle=g["angle"],
                goal=g["goal"],
                suggested_tools=g.get("suggested_tools", []),
            )
        )
    return goals


def run_case_study(
    session,
    case_id: str,
    n_threads: int = None,
) -> OrchestratorResult:
    """Run a curated case study through the multi-agent orchestrator.

    Parameters
    ----------
    session : Session
        Active ct session.
    case_id : str
        Case study slug (e.g. "revlimid", "gleevec").
    n_threads : int, optional
        Number of threads. Defaults to the number of thread goals defined
        in the case study.

    Returns
    -------
    OrchestratorResult
        Merged results from all research threads.

    Raises
    ------
    ValueError
        If *case_id* is not found in the registry.
    """
    if case_id not in CASE_STUDIES:
        available = ", ".join(sorted(CASE_STUDIES.keys()))
        raise ValueError(
            f"Unknown case study '{case_id}'. Available: {available}"
        )

    case = CASE_STUDIES[case_id]
    goals = build_thread_goals(case)

    if n_threads is None:
        n_threads = len(goals)

    query = (
        f"Comprehensive analysis of {case.name}: {case.description} "
        f"Compound: {case.compound}. "
        f"Primary targets: {', '.join(case.targets)}. "
        f"Indication: {case.indication}."
    )

    context = {
        "compound": case.compound,
        "targets": ", ".join(case.targets),
        "indication": case.indication,
        "case_study": case.id,
    }

    orchestrator = ResearchOrchestrator(session, n_threads=n_threads)
    return orchestrator.run(query, context, preset_goals=goals)
