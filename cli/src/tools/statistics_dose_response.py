"""statistics.dose_response_fit: 4-parameter logistic (Hill equation) fitting.

Split from tools/statistics.py.
"""

from __future__ import annotations

import numpy as np

from tools import registry


@registry.register(
    name="statistics.dose_response_fit",
    description="Fit a 4-parameter logistic (Hill equation) dose-response curve and compute IC50",
    category="statistics",
    parameters={
        "doses": "List of dose concentrations (floats)",
        "responses": "List of response values (floats, e.g. viability or inhibition %)",
        "compound_name": "Optional compound name for labeling",
    },
    requires_data=[],
    usage_guide="You have dose-response data and want to fit a curve to compute IC50, Hill slope, "
                "and assess curve quality. Provide matched lists of doses and responses. "
                "Works with any dose-response data (viability, inhibition, binding, etc.).",
)
def dose_response_fit(doses: list = None, responses: list = None,
                      compound_name: str = "unknown", **kwargs) -> dict:
    """Fit a 4-parameter logistic (Hill equation) dose-response curve.

    Hill equation: f(x) = bottom + (top - bottom) / (1 + (IC50/x)^slope)

    Parameters
    ----------
    doses : list of float
        Concentration values (must be positive).
    responses : list of float
        Response values (e.g. % viability, % inhibition).
    compound_name : str
        Label for the compound.

    Returns
    -------
    dict with fitted parameters, IC50, R-squared, quality assessment.
    """
    from scipy.optimize import curve_fit

    if doses is None or responses is None:
        return {"error": "Both 'doses' and 'responses' lists are required", "summary": "Both 'doses' and 'responses' lists are required"}
    doses = [float(d) for d in doses]
    responses = [float(r) for r in responses]

    if len(doses) != len(responses):
        return {"error": f"Length mismatch: {len(doses)} doses vs {len(responses)} responses", "summary": f"Length mismatch: {len(doses)} doses vs {len(responses)} responses"}
    if len(doses) < 4:
        return {"error": f"Need at least 4 data points for 4PL fit, got {len(doses)}", "summary": f"Need at least 4 data points for 4PL fit, got {len(doses)}"}
    # Filter out non-positive doses (log-space fitting)
    valid = [(d, r) for d, r in zip(doses, responses) if d > 0]
    if len(valid) < 4:
        return {"error": "Need at least 4 positive dose values", "summary": "Need at least 4 positive dose values"}
    doses_arr = np.array([v[0] for v in valid])
    resp_arr = np.array([v[1] for v in valid])

    # 4-parameter logistic (Hill equation)
    def hill(x, bottom, top, ic50, slope):
        return bottom + (top - bottom) / (1.0 + (ic50 / x) ** slope)

    # Initial parameter guesses
    bottom_guess = float(np.min(resp_arr))
    top_guess = float(np.max(resp_arr))
    ic50_guess = float(np.median(doses_arr))
    slope_guess = 1.0

    try:
        popt, pcov = curve_fit(
            hill, doses_arr, resp_arr,
            p0=[bottom_guess, top_guess, ic50_guess, slope_guess],
            bounds=(
                [-np.inf, -np.inf, 1e-15, 0.01],   # lower bounds (IC50 > 0, slope > 0)
                [np.inf, np.inf, np.inf, 100.0]      # upper bounds
            ),
            maxfev=10000,
        )
        bottom, top, ic50, slope = popt
        perr = np.sqrt(np.diag(pcov))

        # Compute R-squared
        predicted = hill(doses_arr, *popt)
        ss_res = np.sum((resp_arr - predicted) ** 2)
        ss_tot = np.sum((resp_arr - np.mean(resp_arr)) ** 2)
        r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        # Quality assessment
        if r_squared > 0.95 and perr[2] / abs(ic50) < 0.5:
            quality = "HIGH"
            quality_detail = "Excellent fit with tight IC50 confidence"
        elif r_squared > 0.8:
            quality = "MEDIUM"
            quality_detail = "Good fit, IC50 estimate reliable"
        elif r_squared > 0.5:
            quality = "LOW"
            quality_detail = "Marginal fit, IC50 estimate approximate"
        else:
            quality = "POOR"
            quality_detail = "Poor fit, IC50 unreliable"

        # Max effect (dynamic range)
        max_effect = abs(top - bottom)

        summary = (
            f"Dose-response fit for {compound_name}:\n"
            f"IC50 = {ic50:.4g}, Hill slope = {slope:.2f}\n"
            f"R² = {r_squared:.4f}, Quality: {quality}\n"
            f"Bottom = {bottom:.2f}, Top = {top:.2f}, Max effect = {max_effect:.2f}"
        )

        return {
            "summary": summary,
            "compound": compound_name,
            "ic50": round(float(ic50), 6),
            "hill_slope": round(float(slope), 4),
            "bottom": round(float(bottom), 4),
            "top": round(float(top), 4),
            "r_squared": round(float(r_squared), 4),
            "max_effect": round(float(max_effect), 4),
            "parameter_errors": {
                "bottom_se": round(float(perr[0]), 4),
                "top_se": round(float(perr[1]), 4),
                "ic50_se": round(float(perr[2]), 6),
                "slope_se": round(float(perr[3]), 4),
            },
            "quality": quality,
            "quality_detail": quality_detail,
            "n_points": len(doses_arr),
        }

    except RuntimeError as e:
        return {
            "summary": f"Dose-response fit FAILED for {compound_name}: curve fitting did not converge",
            "error": f"Convergence failure: {str(e)}",
            "compound": compound_name,
            "n_points": len(doses_arr),
            "dose_range": [float(np.min(doses_arr)), float(np.max(doses_arr))],
            "response_range": [float(np.min(resp_arr)), float(np.max(resp_arr))],
        }
    except Exception as e:
        return {
            "summary": f"Dose-response fit FAILED for {compound_name}: {str(e)}",
            "error": str(e),
            "compound": compound_name,
        }
