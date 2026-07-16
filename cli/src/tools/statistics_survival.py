"""statistics.survival_analysis: Kaplan-Meier survival + log-rank test.

Split from tools/statistics.py.
"""

from __future__ import annotations

import numpy as np

from tools import registry


@registry.register(
    name="statistics.survival_analysis",
    description="Perform Kaplan-Meier survival analysis with optional log-rank test for group comparison",
    category="statistics",
    parameters={
        "times": "List of survival/follow-up times",
        "events": "List of event indicators (1=event occurred, 0=censored)",
        "groups": "Optional list of group labels for comparing survival between groups",
    },
    requires_data=[],
    usage_guide="You have time-to-event data and want to estimate survival curves, median survival, "
                "and compare groups. Provide times, event indicators, and optionally group labels. "
                "Use for clinical trial analysis, patient stratification, or biomarker validation.",
)
def survival_analysis(times: list = None, events: list = None,
                      groups: list = None, **kwargs) -> dict:
    """Perform Kaplan-Meier survival analysis with log-rank test.

    Implements the Kaplan-Meier estimator from scratch:
    S(t) = product of (1 - d_i/n_i) for all event times t_i <= t

    If groups are provided, computes separate KM curves and a log-rank test.

    Parameters
    ----------
    times : list of float
        Survival or follow-up times.
    events : list of int
        Event indicators: 1 = event (death/progression), 0 = censored.
    groups : list, optional
        Group labels for stratified analysis (e.g., ["high", "low", "high", ...]).
    """
    from scipy import stats as sp_stats

    if times is None or events is None:
        return {"error": "Both 'times' and 'events' lists are required", "summary": "Both 'times' and 'events' lists are required"}
    times = [float(t) for t in times]
    events = [int(e) for e in events]

    if len(times) != len(events):
        return {"error": f"Length mismatch: {len(times)} times vs {len(events)} events", "summary": f"Length mismatch: {len(times)} times vs {len(events)} events"}
    if len(times) < 3:
        return {"error": f"Need at least 3 observations, got {len(times)}", "summary": f"Need at least 3 observations, got {len(times)}"}
    def _kaplan_meier(t_arr, e_arr):
        """Compute KM survival curve from times and events arrays."""
        # Sort by time
        order = np.argsort(t_arr)
        t_sorted = t_arr[order]
        e_sorted = e_arr[order]

        # Get unique event times (only where event=1)
        event_times = np.unique(t_sorted[e_sorted == 1])

        km_times = [0.0]
        km_survival = [1.0]
        n_at_risk = len(t_sorted)
        current_s = 1.0

        for et in event_times:
            # Number who have been censored or had event before this time
            # n_at_risk at time et: those with time >= et
            n_at_risk = int(np.sum(t_sorted >= et))
            # Deaths at this time
            d = int(np.sum((t_sorted == et) & (e_sorted == 1)))

            if n_at_risk > 0:
                current_s *= (1.0 - d / n_at_risk)

            km_times.append(float(et))
            km_survival.append(round(current_s, 6))

        # Median survival: first time S(t) <= 0.5
        median_surv = None
        for t_val, s_val in zip(km_times, km_survival):
            if s_val <= 0.5:
                median_surv = t_val
                break

        return {
            "times": km_times,
            "survival": km_survival,
            "median_survival": median_surv,
            "n_events": int(np.sum(e_sorted)),
            "n_censored": int(np.sum(e_sorted == 0)),
            "n_total": len(t_sorted),
        }

    t_arr = np.array(times)
    e_arr = np.array(events)

    # Single-group analysis
    if groups is None:
        km = _kaplan_meier(t_arr, e_arr)
        median_str = f"{km['median_survival']:.1f}" if km['median_survival'] is not None else "not reached"
        summary = (
            f"Kaplan-Meier survival analysis (n={km['n_total']}):\n"
            f"Events: {km['n_events']}, Censored: {km['n_censored']}\n"
            f"Median survival: {median_str}"
        )
        return {
            "summary": summary,
            "kaplan_meier": km,
        }

    # Multi-group analysis
    groups = list(groups)
    if len(groups) != len(times):
        return {"error": f"Length mismatch: {len(times)} times vs {len(groups)} groups", "summary": f"Length mismatch: {len(times)} times vs {len(groups)} groups"}
    unique_groups = sorted(set(groups))
    if len(unique_groups) < 2:
        return {"error": f"Need at least 2 groups for comparison, got {len(unique_groups)}", "summary": f"Need at least 2 groups for comparison, got {len(unique_groups)}"}
    group_arr = np.array(groups)
    group_results = {}

    for g in unique_groups:
        mask = group_arr == g
        group_results[str(g)] = _kaplan_meier(t_arr[mask], e_arr[mask])

    # Log-rank test (for 2 groups, generalizable)
    # Implementation: compare observed vs expected events in each group
    # at each unique event time across all groups
    all_event_times = np.unique(t_arr[e_arr == 1])

    # Compute chi-squared statistic for log-rank
    observed_minus_expected = {str(g): 0.0 for g in unique_groups}
    variance_sum = 0.0

    for et in all_event_times:
        # Total at risk and total events at this time
        at_risk_total = int(np.sum(t_arr >= et))
        events_total = int(np.sum((t_arr == et) & (e_arr == 1)))

        if at_risk_total == 0:
            continue

        for g in unique_groups:
            mask = group_arr == g
            at_risk_g = int(np.sum(t_arr[mask] >= et))
            events_g = int(np.sum((t_arr[mask] == et) & (e_arr[mask] == 1)))

            # Expected events under null
            expected_g = at_risk_g * events_total / at_risk_total if at_risk_total > 0 else 0
            observed_minus_expected[str(g)] += (events_g - expected_g)

        # Variance contribution (hypergeometric variance)
        if at_risk_total > 1:
            for g in unique_groups:
                mask = group_arr == g
                n_g = int(np.sum(t_arr[mask] >= et))
                frac = n_g / at_risk_total
                censored_total = at_risk_total - events_total
                var_contrib = (events_total * censored_total * frac * (1 - frac)) / (at_risk_total - 1)
                # Only accumulate for the first group (2-group test)
                if g == unique_groups[0]:
                    variance_sum += var_contrib

    # Chi-squared statistic (1 df for 2 groups)
    if variance_sum > 0:
        chi2 = (observed_minus_expected[str(unique_groups[0])] ** 2) / variance_sum
        p_value = float(1.0 - sp_stats.chi2.cdf(chi2, df=len(unique_groups) - 1))
    else:
        chi2 = 0.0
        p_value = 1.0

    # Event rate ratio (simplified — not a proper Cox hazard ratio).
    # Computed as (events_1 / total_time_1) / (events_2 / total_time_2).
    hr = None
    hr_str = "N/A"
    if len(unique_groups) == 2:
        g1, g2 = str(unique_groups[0]), str(unique_groups[1])
        r1 = group_results[g1]
        r2 = group_results[g2]
        rate1 = r1["n_events"] / max(np.sum(t_arr[group_arr == unique_groups[0]]), 1e-10)
        rate2 = r2["n_events"] / max(np.sum(t_arr[group_arr == unique_groups[1]]), 1e-10)
        if rate2 > 0:
            hr = round(float(rate1 / rate2), 4)
            hr_str = f"{hr:.3f}"

    # Build summary
    median_parts = []
    for g in unique_groups:
        med = group_results[str(g)]["median_survival"]
        med_str = f"{med:.1f}" if med is not None else "NR"
        n = group_results[str(g)]["n_total"]
        median_parts.append(f"{g}(n={n}): {med_str}")

    significance = "significant" if p_value < 0.05 else "not significant"

    summary = (
        f"Kaplan-Meier survival analysis ({len(unique_groups)} groups, n={len(times)}):\n"
        f"Median survival: {', '.join(median_parts)}\n"
        f"Log-rank p = {p_value:.4g} ({significance})\n"
        f"Event rate ratio (simplified HR): {hr_str}"
    )

    return {
        "summary": summary,
        "groups": group_results,
        "log_rank": {
            "chi2": round(float(chi2), 4),
            "p_value": round(float(p_value), 6),
            "significant": p_value < 0.05,
        },
        "hazard_ratio": hr,  # Note: simplified event rate ratio, not Cox regression HR
    }
