"""clinical trial search and design/endpoint benchmarking tools (ClinicalTrials.gov API v2).

Split from tools/clinical.py. Calls ``request_json`` and (for endpoint_benchmark)
``trial_design_benchmark`` indirectly via the ``tools.clinical`` hub module so that
``patch("tools.clinical.request_json")`` / ``patch("tools.clinical.trial_design_benchmark")``
in tests continue to work regardless of which submodule performs the call.
"""

import re

import numpy as np

from tools import clinical as _clinical
from tools import registry

_CTGOV_STUDIES_URL = "https://clinicaltrials.gov/api/v2/studies"
_CTGOV_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "fastfold-agent-cli (research tool; +https://github.com/fastfold-ai/fastfold-agent-cli)"
    ),
}


@registry.register(
    name="clinical.trial_search",
    description="Search ClinicalTrials.gov for relevant clinical trials by gene, drug, or indication",
    category="clinical",
    parameters={
        "query": "Search term (gene name, drug name, indication, or free text)",
        "status": "Optional trial status filter: RECRUITING, COMPLETED, ACTIVE_NOT_RECRUITING, etc.",
    },
    usage_guide="You want to find clinical trials for a target, compound, or disease. Use to assess clinical precedent, competitive landscape, and development activity.",
)
def trial_search(query: str, status: str = "", **kwargs) -> dict:
    """Search ClinicalTrials.gov API v2 for clinical trials.

    Returns trial metadata including NCT ID, phase, status, conditions,
    interventions, sponsor, and enrollment.
    """
    try:
        import httpx
    except ImportError:
        return {"error": "httpx required (pip install httpx)", "summary": "httpx required (pip install httpx)"}
    url = _CTGOV_STUDIES_URL
    params = {
        "query.term": query,
        "pageSize": 20,
    }
    if status:
        params["filter.overallStatus"] = status

    data, error = _clinical.request_json(
        "GET",
        url,
        params=params,
        headers=_CTGOV_HEADERS,
        timeout=15,
        retries=2,
    )
    if error:
        return {"error": f"ClinicalTrials.gov search failed: {error}", "summary": f"ClinicalTrials.gov search failed: {error}"}
    studies = data.get("studies", [])
    total_count = len(studies)
    has_more = data.get("nextPageToken") is not None

    trials = []
    phase_counts = {}
    status_counts = {}

    for study in studies:
        proto = study.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        status_mod = proto.get("statusModule", {})
        design = proto.get("designModule", {})
        proto.get("descriptionModule", {})
        proto.get("contactsLocationsModule", {})
        arms = proto.get("armsInterventionsModule", {})
        cond_mod = proto.get("conditionsModule", {})
        sponsor_mod = proto.get("sponsorCollaboratorsModule", {})

        nct_id = ident.get("nctId", "")
        title = ident.get("briefTitle", "")
        overall_status = status_mod.get("overallStatus", "")
        start_date = status_mod.get("startDateStruct", {}).get("date", "")

        # Phase
        phases = design.get("phases", [])
        phase = ", ".join(phases) if phases else "N/A"

        # Conditions
        conditions = cond_mod.get("conditions", [])

        # Interventions
        interventions_raw = arms.get("interventions", [])
        interventions = []
        for iv in interventions_raw:
            interventions.append({
                "type": iv.get("type", ""),
                "name": iv.get("name", ""),
            })

        # Sponsor
        lead_sponsor = sponsor_mod.get("leadSponsor", {})
        sponsor_name = lead_sponsor.get("name", "")

        # Enrollment
        enrollment_info = design.get("enrollmentInfo", {})
        enrollment = enrollment_info.get("count", "")

        trial = {
            "nct_id": nct_id,
            "title": title,
            "status": overall_status,
            "phase": phase,
            "conditions": conditions[:5],  # Cap to keep output manageable
            "interventions": interventions[:5],
            "sponsor": sponsor_name,
            "enrollment": enrollment,
            "start_date": start_date,
        }
        trials.append(trial)

        # Aggregate counts
        for p in phases:
            phase_counts[p] = phase_counts.get(p, 0) + 1
        status_counts[overall_status] = status_counts.get(overall_status, 0) + 1

    # Build summary
    if trials:
        top_phases = ", ".join(f"{k}: {v}" for k, v in sorted(phase_counts.items()))
        top_statuses = ", ".join(f"{k}: {v}" for k, v in sorted(status_counts.items()))
        summary = (
            f"ClinicalTrials.gov search '{query}': {total_count}{'+ (more pages)' if has_more else ''} results\n"
            f"Phase distribution: {top_phases}\n"
            f"Status distribution: {top_statuses}"
        )
    else:
        summary = f"No clinical trials found for '{query}'"

    return {
        "summary": summary,
        "query": query,
        "total_count": total_count,
        "has_more": has_more,
        "trials": trials,
        "phase_distribution": phase_counts,
        "status_distribution": status_counts,
    }


def _normalize_phase_token(phase_value: str) -> str:
    """Normalize trial phase labels for robust filtering."""
    return re.sub(r"[^A-Z0-9]", "", str(phase_value or "").upper())


@registry.register(
    name="clinical.trial_design_benchmark",
    description="Benchmark clinical trial design patterns for a query (endpoints, enrollment, randomization, biomarker criteria)",
    category="clinical",
    parameters={
        "query": "Search term for indication/target/drug",
        "phase": "Optional phase filter (e.g., 'PHASE2', 'PHASE3', 'EARLY_PHASE1')",
        "status": "Optional trial status filter (e.g., RECRUITING, COMPLETED)",
        "max_results": "Max studies to include from ClinicalTrials.gov API v2 (default 20, max 100)",
    },
    usage_guide=(
        "Use to benchmark protocol design against the current landscape. Summarizes common "
        "endpoints, intervention patterns, enrollment benchmarks, and key eligibility traits."
    ),
)
def trial_design_benchmark(
    query: str,
    phase: str = "",
    status: str = "",
    max_results: int = 20,
    **kwargs,
) -> dict:
    """Benchmark trial design characteristics from ClinicalTrials.gov API v2."""
    if not query or not query.strip():
        return {"error": "query is required", "summary": "No query provided"}

    max_results = max(1, min(int(max_results or 20), 100))
    params = {
        "query.term": query.strip(),
        "pageSize": str(max_results),
    }
    if status:
        params["filter.overallStatus"] = status

    data, error = _clinical.request_json(
        "GET",
        _CTGOV_STUDIES_URL,
        params=params,
        headers=_CTGOV_HEADERS,
        timeout=20,
        retries=2,
    )
    if error:
        return {
            "error": f"ClinicalTrials.gov benchmark failed: {error}",
            "summary": f"Clinical trial design benchmark failed: {error}",
        }

    studies = data.get("studies", [])
    has_more = data.get("nextPageToken") is not None
    phase_filter = phase.strip()
    phase_filter_norm = _normalize_phase_token(phase_filter) if phase_filter else ""

    trials = []
    phase_counts = {}
    status_counts = {}
    endpoint_counts = {}
    intervention_counts = {}
    enrollment_values = []

    design_patterns = {
        "randomized_trials": 0,
        "blinded_trials": 0,
        "placebo_control_trials": 0,
        "biomarker_criteria_trials": 0,
        "ecog_criteria_trials": 0,
    }

    for study in studies:
        proto = study.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        status_mod = proto.get("statusModule", {})
        design_mod = proto.get("designModule", {})
        outcomes_mod = proto.get("outcomesModule", {})
        elig_mod = proto.get("eligibilityModule", {})
        arms_mod = proto.get("armsInterventionsModule", {})
        cond_mod = proto.get("conditionsModule", {})
        sponsor_mod = proto.get("sponsorCollaboratorsModule", {})

        phases = design_mod.get("phases", []) or []
        if phase_filter_norm:
            phase_tokens = {_normalize_phase_token(p) for p in phases}
            if phase_filter_norm not in phase_tokens:
                continue

        overall_status = status_mod.get("overallStatus", "") or "UNKNOWN"
        phase_label = ", ".join(phases) if phases else "N/A"
        phase_counts[phase_label] = phase_counts.get(phase_label, 0) + 1
        status_counts[overall_status] = status_counts.get(overall_status, 0) + 1

        design_info = design_mod.get("designInfo", {})
        allocation = design_info.get("allocation", "")
        intervention_model = design_info.get("interventionModel", "")
        masking = design_info.get("maskingInfo", {}).get("masking", "")

        interventions = []
        for iv in arms_mod.get("interventions", []) or []:
            iv_name = (iv.get("name", "") or "").strip()
            if iv_name:
                interventions.append(iv_name)
                intervention_counts[iv_name] = intervention_counts.get(iv_name, 0) + 1

        primary_endpoints = []
        for out in outcomes_mod.get("primaryOutcomes", []) or []:
            measure = (out.get("measure", "") or "").strip()
            if measure:
                primary_endpoints.append(measure)
                endpoint_counts[measure] = endpoint_counts.get(measure, 0) + 1

        enrollment_raw = design_mod.get("enrollmentInfo", {}).get("count")
        enrollment = None
        try:
            enrollment = int(enrollment_raw)
            enrollment_values.append(enrollment)
        except Exception:
            enrollment = enrollment_raw

        eligibility_text = (elig_mod.get("eligibilityCriteria", "") or "").lower()
        biomarker_criteria = any(
            term in eligibility_text
            for term in ("biomarker", "mutation", "genotype", "expression", "pd-l1", "her2", "egfr", "alk")
        )
        ecog_criteria = "ecog" in eligibility_text

        allocation_norm = str(allocation).strip().upper().replace("-", "_")
        if allocation_norm == "RANDOMIZED" or (
            "RANDOMIZED" in allocation_norm and "NON_RANDOMIZED" not in allocation_norm
        ):
            design_patterns["randomized_trials"] += 1
        if masking and str(masking).upper() not in {"NONE", "OPEN_LABEL"}:
            design_patterns["blinded_trials"] += 1
        if any("placebo" in iv.lower() for iv in interventions):
            design_patterns["placebo_control_trials"] += 1
        if biomarker_criteria:
            design_patterns["biomarker_criteria_trials"] += 1
        if ecog_criteria:
            design_patterns["ecog_criteria_trials"] += 1

        trials.append({
            "nct_id": ident.get("nctId", ""),
            "title": ident.get("briefTitle", ""),
            "phase": phase_label,
            "status": overall_status,
            "study_type": design_mod.get("studyType", ""),
            "allocation": allocation,
            "intervention_model": intervention_model,
            "masking": masking,
            "enrollment": enrollment,
            "conditions": (cond_mod.get("conditions", []) or [])[:5],
            "interventions": interventions[:8],
            "primary_endpoints": primary_endpoints[:8],
            "sponsor": (sponsor_mod.get("leadSponsor", {}) or {}).get("name", ""),
            "start_date": (status_mod.get("startDateStruct", {}) or {}).get("date", ""),
            "biomarker_criteria": biomarker_criteria,
            "ecog_criteria": ecog_criteria,
        })

    if not trials:
        phase_text = f", phase={phase_filter}" if phase_filter else ""
        status_text = f", status={status}" if status else ""
        return {
            "query": query,
            "phase_filter": phase_filter,
            "status_filter": status,
            "trials": [],
            "summary": f"No trials found for '{query}' with current filters{phase_text}{status_text}.",
        }

    median_enrollment = float(np.median(enrollment_values)) if enrollment_values else None

    endpoint_top = sorted(endpoint_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    intervention_top = sorted(intervention_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]

    top_endpoint_text = ", ".join(f"{name} ({count})" for name, count in endpoint_top[:3]) or "none"
    summary = (
        f"Trial design benchmark for '{query}': {len(trials)} trial(s)"
        f"{' (+ more pages)' if has_more else ''}. "
        f"Median enrollment: {int(median_enrollment) if median_enrollment is not None else 'NA'}. "
        f"Top primary endpoints: {top_endpoint_text}."
    )

    return {
        "summary": summary,
        "query": query,
        "phase_filter": phase_filter,
        "status_filter": status,
        "has_more": has_more,
        "n_trials": len(trials),
        "median_enrollment": median_enrollment,
        "phase_distribution": phase_counts,
        "status_distribution": status_counts,
        "design_patterns": design_patterns,
        "top_primary_endpoints": [{"endpoint": k, "count": v} for k, v in endpoint_top],
        "top_interventions": [{"intervention": k, "count": v} for k, v in intervention_top],
        "trials": trials,
    }


@registry.register(
    name="clinical.endpoint_benchmark",
    description="Benchmark endpoint usage patterns and enrollment norms for an indication/target query",
    category="clinical",
    parameters={
        "query": "Search term for indication/target/drug",
        "phase": "Optional phase filter",
        "status": "Optional status filter",
        "max_results": "Maximum studies to include (default 30, max 100)",
    },
    usage_guide=(
        "Use during protocol planning to benchmark what endpoints and enrollment levels are commonly used "
        "by competitors in similar trials."
    ),
)
def endpoint_benchmark(
    query: str,
    phase: str = "",
    status: str = "",
    max_results: int = 30,
    **kwargs,
) -> dict:
    """Summarize endpoint conventions from ClinicalTrials.gov records."""
    del kwargs
    base = _clinical.trial_design_benchmark(
        query=query,
        phase=phase,
        status=status,
        max_results=max_results,
    )
    if "error" in base:
        return {
            "error": base["error"],
            "summary": base["summary"],
        }

    trials = base.get("trials", []) or []
    if not trials:
        return {
            "summary": f"No trials available for endpoint benchmark on '{query}'.",
            "query": query,
            "trials": [],
        }

    endpoint_family_counts = {
        "overall_survival": 0,
        "progression_free_survival": 0,
        "response_rate": 0,
        "safety_tolerability": 0,
        "quality_of_life": 0,
        "biomarker_driven": 0,
        "other": 0,
    }

    endpoint_examples = {k: [] for k in endpoint_family_counts}
    for trial in trials:
        endpoints = trial.get("primary_endpoints", []) or []
        if not endpoints:
            endpoint_family_counts["other"] += 1
            continue
        classified = False
        for endpoint in endpoints:
            text = str(endpoint).lower()
            if "overall survival" in text or text.strip() == "os":
                key = "overall_survival"
            elif "progression-free survival" in text or "pfs" in text:
                key = "progression_free_survival"
            elif "objective response rate" in text or "orr" in text or "response rate" in text:
                key = "response_rate"
            elif "adverse event" in text or "safety" in text or "tolerability" in text:
                key = "safety_tolerability"
            elif "quality of life" in text or "qol" in text or "patient-reported" in text:
                key = "quality_of_life"
            elif any(k in text for k in ("biomarker", "mutation", "pd-l1", "ctdna", "mrd")):
                key = "biomarker_driven"
            else:
                key = "other"

            endpoint_family_counts[key] += 1
            if len(endpoint_examples[key]) < 5:
                endpoint_examples[key].append(endpoint)
            classified = True
        if not classified:
            endpoint_family_counts["other"] += 1

    # Enrollment statistics
    enrollments = []
    for trial in trials:
        value = trial.get("enrollment")
        if isinstance(value, int):
            enrollments.append(value)
    enrollment_median = float(np.median(enrollments)) if enrollments else None
    enrollment_p75 = float(np.percentile(enrollments, 75)) if len(enrollments) >= 2 else None

    ranked_families = sorted(
        endpoint_family_counts.items(),
        key=lambda kv: kv[1],
        reverse=True,
    )
    top_families = [{"family": k, "count": v} for k, v in ranked_families if v > 0][:6]
    top_family_text = ", ".join(f"{x['family']} ({x['count']})" for x in top_families[:3]) or "none"

    summary = (
        f"Endpoint benchmark for '{query}': {len(trials)} trial(s). "
        f"Top endpoint families: {top_family_text}. "
        f"Median enrollment: {int(enrollment_median) if enrollment_median is not None else 'NA'}."
    )

    return {
        "summary": summary,
        "query": query,
        "phase_filter": phase,
        "status_filter": status,
        "n_trials": len(trials),
        "endpoint_families": endpoint_family_counts,
        "top_endpoint_families": top_families,
        "endpoint_examples": endpoint_examples,
        "median_enrollment": enrollment_median,
        "p75_enrollment": enrollment_p75,
        "phase_distribution": base.get("phase_distribution", {}),
        "status_distribution": base.get("status_distribution", {}),
        "trials": trials,
    }
