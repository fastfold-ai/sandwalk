"""GPU compute tool: submit jobs against a provider API."""

from tools import registry


@registry.register(
    name="compute.submit_job",
    description="Submit a GPU compute job to a cloud provider (dry_run=True by default)",
    category="compute",
    parameters={
        "job_type": "Type of job: boltz2, alphafold, molecular_dynamics, virtual_screening, model_training",
        "params": "Job-specific parameters (dict with input files, config, etc.)",
        "provider": "Provider ID: lambda or runpod (default: compute.default_provider)",
        "gpu_type": "GPU type to use (optional, auto-selects if omitted)",
        "dry_run": "If True (default), only show what would be submitted without actually submitting",
    },
    usage_guide="You want to submit a GPU computation job. Always runs in dry_run mode unless explicitly overridden. Use after compute.estimate_cost.",
)
def submit_job(job_type: str, params: dict = None, provider: str | None = None, gpu_type: str = None, dry_run: bool = True, **kwargs) -> dict:
    """Submit a compute job to a cloud GPU provider.

    By default runs in dry_run mode, returning what would be submitted.
    When dry_run=False, POSTs the job to the provider API.
    """
    from tools.compute import (  # indirect import for test patchability
        _load_providers,
        _provider_api_key_config,
        _provider_info,
        _request_json,
        _resolve_provider,
        estimate_cost,
    )

    params = params or {}
    from agent.config import Config
    cfg = Config.load()
    provider = _resolve_provider(provider, cfg)

    data = _load_providers()
    templates = data["job_templates"]

    if job_type not in templates:
        valid = ", ".join(templates.keys())
        return {"error": f"Unknown job type '{job_type}'. Valid types: {valid}", "summary": f"Unknown job type '{job_type}'. Valid types: {valid}"}
    template = templates[job_type]

    cost_est = estimate_cost(job_type=job_type, n_samples=params.get("n_samples", 1), gpu_type=gpu_type, provider=provider)
    if "error" in cost_est:
        return cost_est

    provider_info = _provider_info(provider)
    if not provider_info:
        return {"error": f"Unknown provider '{provider}'", "summary": f"Unknown provider '{provider}'"}
    job_payload = {
        "job_type": job_type,
        "description": template["description"],
        "gpu_type": cost_est["gpu"],
        "provider": provider,
        "params": params,
        "estimated_hours": cost_est["estimated_hours"],
        "estimated_cost": cost_est["estimated_cost"],
    }

    if dry_run:
        return {
            "summary": (
                f"[DRY RUN] Would submit {template['description']} to {provider_info['name']}\n"
                f"GPU: {cost_est['gpu_name']} | Est. time: {cost_est['estimated_hours']:.1f}h | Est. cost: ${cost_est['estimated_cost']:.2f}\n"
                f"Set dry_run=False to actually submit."
            ),
            "dry_run": True,
            "job_payload": job_payload,
        }

    # Actual submission — validate API key first
    config_key = _provider_api_key_config(provider)
    api_key = cfg.get(config_key)
    if not api_key:
        return {
            "error": (
                f"No API key configured for {provider_info['name']}. "
                f"Set it with: sandwalk config set {config_key} <your-key>\n"
                f"Or: export {config_key.upper().replace('.', '_')}=<your-key>\n"
                f"Sign up at: {provider_info.get('website', 'N/A')}\n"
                f"Run 'sandwalk keys' to see all API key status."
            ),
            "summary": f"Job submission failed: no API key for {provider_info['name']}",
        }

    api_base = provider_info.get("api_base_url")
    if not api_base:
        return {
            "error": f"Provider '{provider}' does not have an API endpoint configured",
            "summary": f"Job submission failed: provider '{provider_info.get('name', provider)}' is not API-enabled",
        }

    api_url = f"{api_base}/jobs"
    result, request_error = _request_json(
        "POST",
        api_url,
        payload=job_payload,
        timeout=30,
        retries=2,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    if request_error:
        return {
            "error": f"Job submission failed: {request_error}",
            "summary": f"Job submission failed for {provider_info['name']}: {request_error}",
        }

    job_id = result.get("id") or result.get("job_id") or "unknown"

    return {
        "summary": (
            f"Job submitted to {provider_info['name']}: {job_id}\n"
            f"GPU: {cost_est['gpu_name']} | Est. time: {cost_est['estimated_hours']:.1f}h | Est. cost: ${cost_est['estimated_cost']:.2f}"
        ),
        "job_id": job_id,
        "provider": provider,
        "job_payload": job_payload,
        "raw_response": result,
    }
