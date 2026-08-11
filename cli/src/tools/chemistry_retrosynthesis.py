"""chemistry.retrosynthesis: retrosynthetic route planning orchestrator. Split from tools/chemistry.py."""
from tools import chemistry as _chemistry
from tools import registry
from tools.chemistry_retro_heuristic import retrosynthesis_heuristic
from tools.chemistry_retro_ibm import retrosynthesis_ibm_rxn


@registry.register(
    name="chemistry.retrosynthesis",
    description="Plan retrosynthetic routes for a target molecule — uses IBM RXN API if configured, otherwise heuristic SMARTS-based disconnections",
    category="chemistry",
    parameters={
        "smiles": "SMILES string of the target molecule",
        "max_steps": "Maximum retrosynthetic steps (default 3)",
    },
    usage_guide="You want to plan a synthetic route to make a target compound. Use for synthesis feasibility assessment, identifying key disconnections, and suggesting reagents/conditions. Provides heuristic retrosynthetic analysis using common transforms; optionally uses IBM RXN API if an API key is configured.",
)
def retrosynthesis(smiles: str, max_steps: int = 3, **kwargs) -> dict:
    """Plan retrosynthetic routes for a target molecule.

    Attempts the IBM RXN API first (if api.ibm_rxn_key is configured),
    then falls back to a heuristic RDKit-based retrosynthesis using
    common disconnection transforms.
    """
    smiles = _chemistry._extract_smiles(smiles)

    session = kwargs.get("_session", None)
    api_key = None
    if session and hasattr(session, "config"):
        api_key = session.config.get("api.ibm_rxn_key", None)

    if api_key:
        result = retrosynthesis_ibm_rxn(smiles, max_steps, api_key)
        if result and "error" not in result:
            return result

    return retrosynthesis_heuristic(smiles, max_steps)
