"""Pharmacokinetics tools for quick noncompartmental analysis (NCA)."""

from __future__ import annotations

import numpy as np

from tools import registry
from tools.pk_calc import (
    _auc_extrapolate,
    _auc_last,
    _clearance_metrics,
    _prepare_series,
    _safe_round,
    _terminal_phase,
    _to_float_list,
)


@registry.register(
    name="pk.nca_basic",
    description="Run basic noncompartmental PK analysis (Cmax/Tmax/AUC/lambda_z/t1/2; CL if dose provided)",
    category="pk",
    parameters={
        "times": "Sampling times (e.g., [0, 0.5, 1, 2, 4, 8, 24])",
        "concentrations": "Observed concentrations aligned with times",
        "dose": "Optional administered dose for CL/F and Vz/F",
        "route": "Route type: 'iv' or 'extravascular' (default extravascular)",
        "n_terminal_points": "Number of terminal points for lambda_z fit (default 3)",
        "lloq": "Optional lower limit of quantification; values below are set to 0",
        "subject_id": "Optional subject identifier for report labeling",
    },
    usage_guide=(
        "Use when you have concentration-time data and need rapid PK triage metrics. "
        "Returns noncompartmental metrics plus terminal-phase fit diagnostics."
    ),
)
def nca_basic(
    times: list | None = None,
    concentrations: list | None = None,
    dose: float | None = None,
    route: str = "extravascular",
    n_terminal_points: int = 3,
    lloq: float | None = None,
    subject_id: str = "",
    **kwargs,
) -> dict:
    """Perform a basic NCA workflow from concentration-time observations."""
    del kwargs

    t_list, t_error = _to_float_list(times, "times")
    if t_error:
        return {"summary": t_error, "error": "invalid_times"}
    c_list, c_error = _to_float_list(concentrations, "concentrations")
    if c_error:
        return {"summary": c_error, "error": "invalid_concentrations"}

    assert t_list is not None and c_list is not None

    if len(t_list) != len(c_list):
        return {
            "summary": f"Length mismatch: {len(t_list)} times vs {len(c_list)} concentrations",
            "error": "length_mismatch",
        }
    if len(t_list) < 3:
        return {
            "summary": f"Need at least 3 observations for NCA, got {len(t_list)}",
            "error": "insufficient_points",
        }

    times_sorted, conc_sorted, warnings, error = _prepare_series(t_list, c_list, lloq)
    if error:
        return error
    assert times_sorted is not None and conc_sorted is not None

    n_terminal_points = int(n_terminal_points or 3)
    if n_terminal_points < 3:
        n_terminal_points = 3
        warnings.append("n_terminal_points < 3 is not robust; using 3.")

    cmax_idx = int(np.argmax(conc_sorted))
    cmax = float(conc_sorted[cmax_idx])
    tmax = float(times_sorted[cmax_idx])

    auc_last, auc_error = _auc_last(times_sorted, conc_sorted)
    if auc_error:
        return auc_error
    assert auc_last is not None

    lambda_z, terminal_r2, half_life, terminal_points_used, term_warnings = _terminal_phase(
        times_sorted, conc_sorted, n_terminal_points
    )
    warnings.extend(term_warnings)

    clast = float(conc_sorted[-1])
    auc_extrap, auc_inf, extrapolated_fraction, extrap_warnings = _auc_extrapolate(
        auc_last, clast, lambda_z
    )
    warnings.extend(extrap_warnings)

    route_norm = str(route or "extravascular").strip().lower()
    if route_norm not in {"iv", "extravascular"}:
        return {"summary": "route must be 'iv' or 'extravascular'.", "error": "invalid_route"}

    dose_value = None
    if dose is not None:
        try:
            dose_value = float(dose)
        except Exception:
            return {"summary": "dose must be numeric when provided.", "error": "invalid_dose"}
        if dose_value <= 0:
            return {"summary": "dose must be > 0 when provided.", "error": "invalid_dose"}

    clearance, apparent_clearance, volume, apparent_volume = _clearance_metrics(
        route_norm, dose_value, auc_inf, lambda_z
    )

    label = subject_id.strip() if subject_id else "sample"
    hl_text = f"{half_life:.3g}" if half_life is not None else "NA"
    summary = (
        f"Basic NCA for {label}: Cmax={cmax:.4g} at Tmax={tmax:.4g}, "
        f"AUC_last={auc_last:.4g}, t1/2={hl_text}."
    )

    return {
        "summary": summary,
        "subject_id": subject_id.strip() or None,
        "n_points": int(len(times_sorted)),
        "terminal_points_used": int(terminal_points_used),
        "route": route_norm,
        "dose": _safe_round(dose_value, 6),
        "cmax": _safe_round(cmax, 6),
        "tmax": _safe_round(tmax, 6),
        "auc_last": _safe_round(auc_last, 6),
        "clast": _safe_round(clast, 6),
        "lambda_z": _safe_round(lambda_z, 6),
        "terminal_r_squared": _safe_round(terminal_r2, 6),
        "half_life": _safe_round(half_life, 6),
        "auc_extrapolated": _safe_round(auc_extrap, 6),
        "auc_inf": _safe_round(auc_inf, 6),
        "extrapolated_fraction": _safe_round(extrapolated_fraction, 6),
        "clearance": _safe_round(clearance, 6),
        "volume_distribution": _safe_round(volume, 6),
        "apparent_clearance": _safe_round(apparent_clearance, 6),
        "apparent_volume_distribution": _safe_round(apparent_volume, 6),
        "warnings": warnings,
    }
