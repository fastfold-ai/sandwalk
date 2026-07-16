"""chemistry.retrosynthesis: IBM RXN API backend. Split from tools/chemistry.py."""
from tools import chemistry as _chemistry


def retrosynthesis_ibm_rxn(smiles: str, max_steps: int, api_key: str) -> dict:
    """Call IBM RXN API for retrosynthesis prediction."""
    import time

    base_url = "https://rxn.res.ibm.com/rxn/api/api/v1"
    headers = {"Authorization": api_key, "Content-Type": "application/json"}

    resp, error = _chemistry.request(
        "POST", f"{base_url}/retrosynthesis/predict", json={"content": smiles, "maxSteps": max_steps}, headers=headers, timeout=30, retries=2, raise_for_status=False,
    )
    if error:
        return {"error": f"IBM RXN API request failed: {error}", "summary": f"IBM RXN API request failed: {error}"}
    if resp.status_code != 200:
        return {"error": f"IBM RXN API returned status {resp.status_code}", "summary": f"IBM RXN API returned status {resp.status_code}"}
    try:
        prediction_id = resp.json().get("prediction_id")
    except Exception:
        return {"error": "IBM RXN API returned invalid JSON", "summary": "IBM RXN API returned invalid JSON"}
    if not prediction_id:
        return {"error": "IBM RXN API did not return a prediction ID", "summary": "IBM RXN API did not return a prediction ID"}

    # Poll for results (up to 60 seconds)
    for _ in range(12):
        time.sleep(5)
        poll_resp, poll_error = _chemistry.request(
            "GET", f"{base_url}/retrosynthesis/results/{prediction_id}", headers=headers, timeout=15, retries=1, raise_for_status=False,
        )
        if poll_error:
            import logging
            logging.getLogger("tools.chemistry").debug("IBM RXN poll attempt failed: %s", poll_error)
            continue
        if poll_resp.status_code == 200:
            try:
                data = poll_resp.json()
            except Exception:
                continue
            status = data.get("status", "")
            if status == "SUCCESS":
                return _parse_ibm_rxn_results(smiles, data)
            if status == "FAILED":
                return {"error": "IBM RXN retrosynthesis failed", "summary": "IBM RXN retrosynthesis failed"}
    return {"error": "IBM RXN API timed out waiting for results", "summary": "IBM RXN API timed out waiting for results"}


def _parse_ibm_rxn_results(smiles: str, data: dict) -> dict:
    """Parse IBM RXN API retrosynthesis results into standard format."""
    routes = []
    for i, route in enumerate(data.get("retrosynthetic_paths", [])):
        steps = [
            {"reaction_smiles": step.get("reaction", ""), "reactants": step.get("reactants", []), "confidence": step.get("confidence", 0.0)}
            for step in route.get("steps", [])
        ]
        routes.append({"route_id": i + 1, "n_steps": len(steps), "steps": steps, "confidence": route.get("confidence", 0.0)})

    routes.sort(key=lambda r: r["n_steps"])
    shortest = routes[0]["n_steps"] if routes else 0

    return {
        "summary": f"Retrosynthesis for {smiles}: {len(routes)} routes found via IBM RXN, shortest is {shortest} steps",
        "target": smiles,
        "source": "ibm_rxn",
        "n_routes": len(routes),
        "routes": routes,
    }
