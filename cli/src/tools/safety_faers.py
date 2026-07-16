"""safety openFDA/FAERS pharmacovigilance tools: faers_signal_scan, label_risk_extract.

Split from tools/safety.py. Calls ``request_json`` indirectly via the ``tools.safety``
hub module so that ``patch("tools.safety.request_json")`` in tests continues to work
regardless of which submodule performs the call.
"""

from tools import registry
from tools import safety as _safety

_OPENFDA_DRUG_EVENT_URL = "https://api.fda.gov/drug/event.json"
_OPENFDA_DRUG_LABEL_URL = "https://api.fda.gov/drug/label.json"


def _openfda_escape(term: str) -> str:
    """Escape a value for openFDA search string usage."""
    return str(term or "").replace("\\", "\\\\").replace('"', '\\"').strip()


def _openfda_total(search: str = "") -> tuple[int | None, str | None]:
    """Return total matching records from openFDA endpoint."""
    params = {"limit": "1"}
    if search:
        params["search"] = search

    data, error = _safety.request_json(
        "GET",
        _OPENFDA_DRUG_EVENT_URL,
        params=params,
        timeout=20,
        retries=2,
    )
    if error:
        return None, error

    total = data.get("meta", {}).get("results", {}).get("total")
    try:
        return int(total), None
    except Exception:
        return None, "openFDA response missing total count"


def _faers_signal_metrics(
    a: int,
    b: int,
    c: int,
    d: int,
    *,
    min_case_count: int = 3,
) -> dict:
    """Compute basic disproportionality metrics (PRR/ROR/chi-square)."""
    import math

    a = max(int(a), 0)
    b = max(int(b), 0)
    c = max(int(c), 0)
    d = max(int(d), 0)

    # Haldane-Anscombe correction stabilizes estimates when cells are zero.
    ac, bc, cc, dc = [x + 0.5 for x in (a, b, c, d)]

    prr = (ac / (ac + bc)) / (cc / (cc + dc))
    ror = (ac / bc) / (cc / dc)
    se_log_ror = math.sqrt((1 / ac) + (1 / bc) + (1 / cc) + (1 / dc))
    ror_ci95_lower = math.exp(math.log(ror) - 1.96 * se_log_ror)
    ror_ci95_upper = math.exp(math.log(ror) + 1.96 * se_log_ror)

    total = a + b + c + d
    denom = (a + b) * (c + d) * (a + c) * (b + d)
    chi_square = ((total * ((a * d - b * c) ** 2)) / denom) if denom > 0 else 0.0

    # Classic pharmacovigilance heuristic gate.
    signal = (a >= min_case_count) and (prr >= 2.0) and (chi_square >= 4.0)

    return {
        "prr": round(float(prr), 4),
        "ror": round(float(ror), 4),
        "ror_ci95_lower": round(float(ror_ci95_lower), 4),
        "ror_ci95_upper": round(float(ror_ci95_upper), 4),
        "chi_square": round(float(chi_square), 4),
        "meets_signal_criteria": bool(signal),
    }


@registry.register(
    name="safety.faers_signal_scan",
    description="Scan openFDA FAERS adverse-event reports for disproportionality signals (PRR/ROR) for a drug",
    category="safety",
    parameters={
        "drug_name": "Drug name to scan (generic or brand name)",
        "event": "Optional specific MedDRA preferred term to evaluate",
        "top_n": "If event not provided, evaluate top N reported events for this drug (default 5)",
        "min_case_count": "Minimum A-count threshold for signal flagging (default 3)",
    },
    usage_guide=(
        "Use for post-marketing pharmacovigilance triage. Computes disproportionality metrics "
        "(PRR/ROR/chi-square) from openFDA FAERS counts and flags candidate safety signals."
    ),
)
def faers_signal_scan(
    drug_name: str,
    event: str = "",
    top_n: int = 5,
    min_case_count: int = 3,
    **kwargs,
) -> dict:
    """Run a disproportionality safety scan using openFDA FAERS."""
    if not drug_name or not drug_name.strip():
        return {"error": "drug_name is required", "summary": "No drug name provided"}

    drug_term = _openfda_escape(drug_name)
    if not drug_term:
        return {"error": "drug_name is required", "summary": "No drug name provided"}

    top_n = max(1, min(int(top_n or 5), 20))
    min_case_count = max(1, int(min_case_count or 3))

    drug_search = f'patient.drug.medicinalproduct.exact:"{drug_term}"'

    all_total, error = _openfda_total("")
    if error:
        return {"error": f"openFDA total lookup failed: {error}", "summary": f"FAERS scan failed: {error}"}
    drug_total, error = _openfda_total(drug_search)
    if error:
        return {"error": f"openFDA drug lookup failed: {error}", "summary": f"FAERS scan failed for {drug_name}: {error}"}

    if drug_total <= 0:
        return {
            "drug_name": drug_name,
            "total_reports_for_drug": 0,
            "signals": [],
            "summary": f"No FAERS reports found for '{drug_name}'",
        }

    events_to_scan = []
    if event and event.strip():
        events_to_scan = [event.strip()]
    else:
        data, count_error = _safety.request_json(
            "GET",
            _OPENFDA_DRUG_EVENT_URL,
            params={
                "search": drug_search,
                "count": "patient.reaction.reactionmeddrapt.exact",
                "limit": str(top_n),
            },
            timeout=20,
            retries=2,
        )
        if count_error:
            return {
                "error": f"openFDA event aggregation failed: {count_error}",
                "summary": f"FAERS scan failed for {drug_name}: {count_error}",
            }
        events_to_scan = [r.get("term", "") for r in data.get("results", []) if r.get("term")]
        if not events_to_scan:
            return {
                "drug_name": drug_name,
                "total_reports_for_drug": int(drug_total),
                "signals": [],
                "summary": f"FAERS reports found for '{drug_name}', but no reaction terms were returned",
            }

    signals = []
    for ev in events_to_scan:
        ev_term = _openfda_escape(ev)
        if not ev_term:
            continue

        event_search = f'patient.reaction.reactionmeddrapt.exact:"{ev_term}"'
        both_search = f"{drug_search}+AND+{event_search}"

        event_total, event_err = _openfda_total(event_search)
        both_total, both_err = _openfda_total(both_search)
        if event_err or both_err:
            signals.append({
                "event": ev,
                "error": event_err or both_err,
            })
            continue

        a = int(both_total)
        b = int(drug_total) - a
        c = int(event_total) - a
        d = int(all_total) - (a + b + c)
        if d < 0:
            d = 0

        metrics = _faers_signal_metrics(a, b, c, d, min_case_count=min_case_count)
        signals.append({
            "event": ev,
            "a_drug_and_event": a,
            "b_drug_no_event": b,
            "c_no_drug_event": c,
            "d_no_drug_no_event": d,
            **metrics,
        })

    clean_signals = [s for s in signals if "error" not in s]
    clean_signals.sort(
        key=lambda x: (x.get("meets_signal_criteria", False), x.get("prr", 0.0), x.get("ror", 0.0)),
        reverse=True,
    )
    n_flagged = sum(1 for s in clean_signals if s.get("meets_signal_criteria"))
    error_count = len(signals) - len(clean_signals)

    if clean_signals:
        top = clean_signals[0]
        summary = (
            f"FAERS signal scan for {drug_name}: {len(clean_signals)} event(s) analyzed, "
            f"{n_flagged} flagged by PRR/ROR criteria. Top event: {top['event']} "
            f"(PRR={top['prr']}, ROR={top['ror']})."
        )
    else:
        summary = (
            f"FAERS signal scan for {drug_name}: no analyzable events returned"
            + (f" ({error_count} event lookup error(s))." if error_count else ".")
        )

    return {
        "summary": summary,
        "drug_name": drug_name,
        "event_filter": event.strip(),
        "total_reports_all_faers": int(all_total),
        "total_reports_for_drug": int(drug_total),
        "criteria": {
            "min_case_count": min_case_count,
            "prr_threshold": 2.0,
            "chi_square_threshold": 4.0,
        },
        "n_events_analyzed": len(clean_signals),
        "n_events_flagged": n_flagged,
        "n_event_lookup_errors": error_count,
        "signals": clean_signals,
        "errors": [s for s in signals if "error" in s],
    }


@registry.register(
    name="safety.label_risk_extract",
    description="Extract boxed warnings, contraindications, and key risk sections from openFDA drug labels",
    category="safety",
    parameters={
        "drug_name": "Drug name (generic or brand)",
        "max_labels": "Maximum label records to inspect (default 3)",
        "section_max_chars": "Max characters per extracted section (default 500)",
    },
    usage_guide=(
        "Use for rapid regulatory risk triage. Pulls key safety sections from FDA labels "
        "(boxed warning, contraindications, warnings, interactions, special populations)."
    ),
)
def label_risk_extract(
    drug_name: str,
    max_labels: int = 3,
    section_max_chars: int = 500,
    **kwargs,
) -> dict:
    """Extract key risk sections from openFDA drug label endpoint."""
    import re

    if not drug_name or not drug_name.strip():
        return {"error": "drug_name is required", "summary": "No drug name provided"}

    max_labels = max(1, min(int(max_labels or 3), 10))
    section_max_chars = max(120, min(int(section_max_chars or 500), 4000))
    drug_term = _openfda_escape(drug_name)

    search = (
        f'openfda.generic_name.exact:"{drug_term}"'
        f'+OR+openfda.brand_name.exact:"{drug_term}"'
        f'+OR+openfda.substance_name.exact:"{drug_term}"'
    )
    data, error = _safety.request_json(
        "GET",
        _OPENFDA_DRUG_LABEL_URL,
        params={"search": search, "limit": str(max_labels)},
        timeout=20,
        retries=2,
    )
    if error:
        return {"error": f"openFDA label query failed: {error}", "summary": f"Label risk extraction failed: {error}"}

    results = data.get("results", [])
    if not results:
        return {
            "drug_name": drug_name,
            "labels_found": 0,
            "risk_level": "UNKNOWN",
            "summary": f"No openFDA label records found for '{drug_name}'",
            "labels": [],
        }

    def _extract_section(entry: dict, key: str) -> str:
        value = entry.get(key, [])
        if isinstance(value, list):
            text = " ".join(str(v).strip() for v in value if str(v).strip())
        elif isinstance(value, str):
            text = value.strip()
        else:
            text = ""
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > section_max_chars:
            text = text[: section_max_chars - 3] + "..."
        return text

    label_summaries = []
    for entry in results:
        openfda = entry.get("openfda", {})
        brand = ", ".join(openfda.get("brand_name", [])[:3]) if isinstance(openfda.get("brand_name"), list) else ""
        generic = ", ".join(openfda.get("generic_name", [])[:3]) if isinstance(openfda.get("generic_name"), list) else ""
        application = ", ".join(openfda.get("application_number", [])[:3]) if isinstance(openfda.get("application_number"), list) else ""
        manufacturer = ", ".join(openfda.get("manufacturer_name", [])[:2]) if isinstance(openfda.get("manufacturer_name"), list) else ""

        sections = {
            "boxed_warning": _extract_section(entry, "boxed_warning"),
            "contraindications": _extract_section(entry, "contraindications"),
            "warnings_and_cautions": _extract_section(entry, "warnings_and_cautions"),
            "warnings": _extract_section(entry, "warnings"),
            "adverse_reactions": _extract_section(entry, "adverse_reactions"),
            "drug_interactions": _extract_section(entry, "drug_interactions"),
            "use_in_specific_populations": _extract_section(entry, "use_in_specific_populations"),
        }

        has_boxed = bool(sections["boxed_warning"])
        has_contra = bool(sections["contraindications"])
        has_warn = bool(sections["warnings"] or sections["warnings_and_cautions"])

        if has_boxed:
            risk_level = "HIGH"
        elif has_contra or has_warn:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"

        flags = []
        if has_boxed:
            flags.append("boxed_warning")
        if has_contra:
            flags.append("contraindications")
        if has_warn:
            flags.append("warnings")

        label_summaries.append({
            "brand_name": brand,
            "generic_name": generic,
            "application_number": application,
            "manufacturer": manufacturer,
            "risk_level": risk_level,
            "risk_flags": flags,
            "sections": sections,
        })

    rank = {"HIGH": 3, "MODERATE": 2, "LOW": 1}
    overall_risk = max(label_summaries, key=lambda x: rank.get(x["risk_level"], 0))["risk_level"]
    boxed_count = sum(1 for l in label_summaries if "boxed_warning" in l.get("risk_flags", []))
    contra_count = sum(1 for l in label_summaries if "contraindications" in l.get("risk_flags", []))

    summary = (
        f"Label risk extraction for {drug_name}: {len(label_summaries)} label record(s), "
        f"overall risk={overall_risk}. Boxed warning present in {boxed_count} label(s); "
        f"contraindications present in {contra_count} label(s)."
    )

    return {
        "summary": summary,
        "drug_name": drug_name,
        "labels_found": len(label_summaries),
        "risk_level": overall_risk,
        "n_boxed_warning_labels": boxed_count,
        "n_contraindication_labels": contra_count,
        "labels": label_summaries,
    }
