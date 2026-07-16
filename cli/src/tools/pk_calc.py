"""NCA calculation helpers extracted from pk.nca_basic (kept ≤150 lines/file)."""

from __future__ import annotations

import math

import numpy as np


def _to_float_list(values: list | None, field_name: str) -> tuple[list[float] | None, str | None]:
    if values is None:
        return None, f"'{field_name}' is required"
    out: list[float] = []
    try:
        for value in values:
            out.append(float(value))
    except Exception:
        return None, f"'{field_name}' must be a list of numeric values"
    return out, None


def _safe_round(value: float | None, ndigits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), ndigits)


def _prepare_series(
    t_list: list[float], c_list: list[float], lloq: float | None
) -> tuple[np.ndarray | None, np.ndarray | None, list[str], dict | None]:
    """Validate, sort, dedup, and LLOQ-clip the concentration-time series."""
    warnings: list[str] = []
    pairs = []
    for time_value, conc_value in zip(t_list, c_list):
        if not np.isfinite(time_value) or not np.isfinite(conc_value):
            continue
        pairs.append((float(time_value), float(conc_value)))
    if len(pairs) < 3:
        return None, None, warnings, {
            "summary": "Need at least 3 finite concentration-time points after filtering.",
            "error": "insufficient_finite_points",
        }

    pairs.sort(key=lambda x: x[0])
    if pairs[0][0] < 0:
        return None, None, warnings, {
            "summary": "Negative sampling times are not allowed.", "error": "negative_time"
        }

    dedup: dict[float, list[float]] = {}
    for t_val, c_val in pairs:
        dedup.setdefault(t_val, []).append(c_val)
    if len(dedup) < len(pairs):
        warnings.append("Duplicate time points detected; concentrations were averaged per unique time.")

    times_sorted = np.array(sorted(dedup.keys()), dtype=float)
    conc_sorted = np.array([float(np.mean(dedup[t])) for t in times_sorted], dtype=float)
    if len(times_sorted) < 3:
        return None, None, warnings, {
            "summary": "Need at least 3 unique time points after deduplication.",
            "error": "insufficient_unique_times",
        }

    if lloq is not None:
        try:
            lloq_value = float(lloq)
        except Exception:
            return None, None, warnings, {"summary": "lloq must be numeric.", "error": "invalid_lloq"}
        if lloq_value < 0:
            return None, None, warnings, {"summary": "lloq cannot be negative.", "error": "invalid_lloq"}
        below = int(np.sum(conc_sorted < lloq_value))
        if below > 0:
            warnings.append(f"{below} concentration values below LLOQ were set to 0.")
            conc_sorted = np.where(conc_sorted < lloq_value, 0.0, conc_sorted)

    return times_sorted, conc_sorted, warnings, None


def _auc_last(times_sorted: np.ndarray, conc_sorted: np.ndarray) -> tuple[float | None, dict | None]:
    auc_last = 0.0
    for i in range(1, len(times_sorted)):
        dt = float(times_sorted[i] - times_sorted[i - 1])
        if dt <= 0:
            return None, {
                "summary": "Sampling times must be strictly increasing after deduplication.",
                "error": "non_increasing_time",
            }
        auc_last += 0.5 * float(conc_sorted[i] + conc_sorted[i - 1]) * dt
    return auc_last, None


def _terminal_phase(
    times_sorted: np.ndarray, conc_sorted: np.ndarray, n_terminal_points: int
) -> tuple[float | None, float | None, float | None, int, list[str]]:
    """Fit terminal elimination phase; returns lambda_z, r2, half_life, n_used, warnings."""
    warnings: list[str] = []
    lambda_z = None
    terminal_r2 = None
    half_life = None
    terminal_points_used = 0

    positive_idx = np.where(conc_sorted > 0)[0]
    if len(positive_idx) >= 3:
        choose = min(n_terminal_points, len(positive_idx))
        terminal_slice = positive_idx[-choose:]
        t_term = times_sorted[terminal_slice]
        c_term = conc_sorted[terminal_slice]
        if len(c_term) >= 3 and np.all(c_term > 0):
            slope, intercept = np.polyfit(t_term, np.log(c_term), 1)
            terminal_points_used = len(c_term)
            pred = slope * t_term + intercept
            ss_res = float(np.sum((np.log(c_term) - pred) ** 2))
            ss_tot = float(np.sum((np.log(c_term) - np.mean(np.log(c_term))) ** 2))
            terminal_r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else None
            if slope < 0:
                lambda_z = float(-slope)
                half_life = float(math.log(2.0) / lambda_z) if lambda_z > 0 else None
            else:
                warnings.append(
                    "Terminal slope is non-negative; lambda_z and half-life are not reliable."
                )
        else:
            warnings.append("Insufficient positive terminal points for lambda_z estimation.")
    else:
        warnings.append("Fewer than 3 positive concentration points; cannot estimate lambda_z.")

    return lambda_z, terminal_r2, half_life, terminal_points_used, warnings


def _auc_extrapolate(
    auc_last: float, clast: float, lambda_z: float | None
) -> tuple[float | None, float | None, float | None, list[str]]:
    warnings: list[str] = []
    auc_extrap = None
    auc_inf = None
    extrapolated_fraction = None
    if lambda_z and lambda_z > 0 and clast > 0:
        auc_extrap = float(clast / lambda_z)
        auc_inf = float(auc_last + auc_extrap)
        if auc_inf > 0:
            extrapolated_fraction = float(auc_extrap / auc_inf)
            if extrapolated_fraction > 0.2:
                warnings.append(
                    "Extrapolated AUC fraction > 20%; terminal sampling may be insufficient."
                )
    return auc_extrap, auc_inf, extrapolated_fraction, warnings


def _clearance_metrics(
    route_norm: str, dose_value: float | None, auc_inf: float | None, lambda_z: float | None
) -> tuple[float | None, float | None, float | None, float | None]:
    clearance = None
    apparent_clearance = None
    volume = None
    apparent_volume = None
    if dose_value is not None and auc_inf and auc_inf > 0:
        if route_norm == "iv":
            clearance = float(dose_value / auc_inf)
            if lambda_z and lambda_z > 0:
                volume = float(clearance / lambda_z)
        else:
            apparent_clearance = float(dose_value / auc_inf)
            if lambda_z and lambda_z > 0:
                apparent_volume = float(apparent_clearance / lambda_z)
    return clearance, apparent_clearance, volume, apparent_volume
