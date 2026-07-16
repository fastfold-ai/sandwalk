"""GPU compute tool: check job status against a provider API."""

from tools import registry


@registry.register(
    name="compute.job_status",
    description="Check the status of a previously submitted compute job",
    category="compute",
    parameters={
        "job_id": "Job ID returned from compute.submit_job",
        "provider": "Provider ID: lambda or runpod (default: compute.default_provider)",
    },
    usage_guide="You want to check the status of a previously submitted compute job.",
)
def job_status(job_id: str, provider: str | None = None, **kwargs) -> dict:
    """Check the status of a compute job via the provider API."""
    from tools.compute import (  # indirect import for test patchability
        _provider_api_key_config,
        _provider_info,
        _request_json,
        _resolve_provider,
    )

    from agent.config import Config
    cfg = Config.load()
    provider = _resolve_provider(provider, cfg)

    provider_info = _provider_info(provider)
    if not provider_info:
        return {"error": f"Unknown provider '{provider}'", "summary": f"Unknown provider '{provider}'"}
    config_key = _provider_api_key_config(provider)
    api_key = cfg.get(config_key)
    if not api_key:
        return {
            "error": (
                f"No API key configured for {provider_info['name']}. "
                f"Set it with: sandwalk config set {config_key} <your-key>\n"
                f"Run 'sandwalk keys' to see all API key status."
            ),
            "summary": f"Job status check failed: no API key for {provider_info['name']}",
        }

    api_base = provider_info.get("api_base_url")
    if not api_base:
        return {
            "error": f"Provider '{provider}' does not have an API endpoint configured",
            "summary": f"Job status check failed: provider '{provider_info.get('name', provider)}' is not API-enabled",
        }

    api_url = f"{api_base}/jobs/{job_id}"
    result, request_error = _request_json(
        "GET",
        api_url,
        timeout=30,
        retries=2,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    if request_error:
        return {
            "error": f"Failed to check job status: {request_error}",
            "summary": f"Job status check failed for {provider_info['name']}: {request_error}",
        }

    status = result.get("status", "unknown")
    progress = result.get("progress", None)
    elapsed = result.get("elapsed_seconds", None)

    elapsed_str = ""
    if elapsed is not None:
        hours = elapsed / 3600
        elapsed_str = f" | Elapsed: {hours:.1f}h"

    progress_str = ""
    if progress is not None:
        progress_str = f" | Progress: {progress}%"

    return {
        "summary": f"Job {job_id} ({provider_info['name']}): {status}{progress_str}{elapsed_str}",
        "job_id": job_id,
        "provider": provider,
        "status": status,
        "progress": progress,
        "elapsed_seconds": elapsed,
        "raw_response": result,
    }
