"""Public API reachability probe and runtime tool-health summary."""

from __future__ import annotations

from agent.doctor.models import DoctorCheck

# APIs to probe with HEAD requests (short timeout, best-effort)
_API_PROBES = [
    ("PubMed eutils", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi"),
    ("Enrichr", "https://maayanlab.cloud/Enrichr/"),
    ("GDC API", "https://api.gdc.cancer.gov/status"),
]


def _check_api_connectivity() -> list[DoctorCheck]:
    """Quick HEAD/GET probe against key public APIs."""
    checks = []
    try:
        import httpx
    except ImportError:
        checks.append(
            DoctorCheck(
                name="api_connectivity",
                status="warn",
                detail="httpx not installed — skipping API connectivity probes",
            )
        )
        return checks

    reachable = []
    unreachable = []
    for label, url in _API_PROBES:
        try:
            resp = httpx.head(url, timeout=5, follow_redirects=True)
            if resp.status_code < 500:
                reachable.append(label)
            else:
                unreachable.append(f"{label} (HTTP {resp.status_code})")
        except Exception:
            unreachable.append(label)

    if not unreachable:
        checks.append(
            DoctorCheck(
                name="api_connectivity",
                status="ok",
                detail=f"All probes passed: {', '.join(reachable)}",
            )
        )
    elif reachable:
        checks.append(
            DoctorCheck(
                name="api_connectivity",
                status="warn",
                detail=f"Unreachable: {', '.join(unreachable)} (reachable: {', '.join(reachable)})",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="api_connectivity",
                status="warn",
                detail=f"All API probes failed: {', '.join(unreachable)}. Check network connectivity.",
            )
        )
    return checks


def _check_tool_health(session) -> DoctorCheck:
    """Report runtime tool suppression state from session."""
    if session is None:
        return DoctorCheck(
            name="tool_health",
            status="warn",
            detail="No active session context; run /doctor in interactive mode for runtime tool-health diagnostics",
        )

    suppressed = set()
    failure_counts: dict[str, int] = {}
    if hasattr(session, "tool_health_suppressed_tools"):
        suppressed = session.tool_health_suppressed_tools()
    if hasattr(session, "_tool_health_failures"):
        failure_counts = {
            name: len(timestamps)
            for name, timestamps in session._tool_health_failures.items()
            if timestamps
        }

    if not suppressed and not failure_counts:
        return DoctorCheck(
            name="tool_health",
            status="ok",
            detail="No tool failures or suppressions in this session",
        )

    parts = []
    if suppressed:
        parts.append(f"Suppressed: {', '.join(sorted(suppressed))}")
    if failure_counts:
        failing = [f"{n}({c})" for n, c in sorted(failure_counts.items()) if n not in suppressed]
        if failing:
            parts.append(f"Recent failures: {', '.join(failing)}")

    return DoctorCheck(
        name="tool_health",
        status="warn",
        detail="; ".join(parts),
    )
