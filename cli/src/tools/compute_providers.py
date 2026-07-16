"""GPU compute tools: list providers and estimate job cost (static reference pricing)."""

from tools import registry


@registry.register(
    name="compute.list_providers",
    description="List available GPU cloud providers with reference pricing for each GPU type (from built-in directory)",
    category="compute",
    parameters={},
    usage_guide="You need to see available GPU cloud providers and their pricing before submitting a compute job.",
)
def list_providers(**kwargs) -> dict:
    """List all GPU cloud providers and their available GPU types with pricing."""
    from tools.compute import _load_providers  # indirect import for test patchability

    data = _load_providers()
    providers = []
    for p in data["providers"]:
        gpu_list = [
            {
                "id": gpu["id"],
                "name": gpu["name"],
                "vram_gb": gpu["vram_gb"],
                "price_per_hour": gpu["price_per_hour"],
            }
            for gpu in p["gpu_types"]
        ]
        providers.append({
            "id": p["id"],
            "name": p["name"],
            "website": p["website"],
            "gpu_types": gpu_list,
        })

    lines = []
    for p in providers:
        gpu_strs = [f"{g['name']} (${g['price_per_hour']:.2f}/hr)" for g in p["gpu_types"]]
        lines.append(f"{p['name']}: {', '.join(gpu_strs)}")

    return {
        "summary": f"[PLACEHOLDER] {len(providers)} GPU cloud providers (static reference pricing — may be outdated):\n" + "\n".join(lines),
        "placeholder": True,
        "providers": providers,
    }


@registry.register(
    name="compute.estimate_cost",
    description="Estimate cost and time for a GPU computation job based on built-in templates (Boltz-2, AlphaFold, MD, virtual screening, training)",
    category="compute",
    parameters={
        "job_type": "Type of job: boltz2, alphafold, molecular_dynamics, virtual_screening, model_training",
        "n_samples": "Number of samples/structures to process (default 1)",
        "gpu_type": "Specific GPU type to use (optional, auto-selects cheapest if omitted)",
        "provider": "Provider ID: lambda or runpod (optional, auto-selects cheapest if omitted)",
    },
    usage_guide="You need to estimate the cost and time for a GPU computation (Boltz-2, AlphaFold, MD simulation, etc.) before deciding whether to proceed.",
)
def estimate_cost(job_type: str, n_samples: int = 1, gpu_type: str = None, provider: str = None, **kwargs) -> dict:
    """Estimate cost and time for a compute job.

    Looks up the job template, finds the best GPU option, and calculates
    estimated_hours and estimated_cost based on per-sample time and pricing.
    """
    from tools.compute import _find_cheapest_gpu, _load_providers  # indirect import for test patchability

    data = _load_providers()
    templates = data["job_templates"]

    if job_type not in templates:
        valid = ", ".join(templates.keys())
        return {"error": f"Unknown job type '{job_type}'. Valid types: {valid}", "summary": f"Unknown job type '{job_type}'. Valid types: {valid}"}
    template = templates[job_type]
    min_vram = template["gpu_requirement_vram_gb"]

    # Resolve GPU selection
    if gpu_type and provider:
        # Find specific GPU at specific provider
        selected = None
        for p in data["providers"]:
            if p["id"] == provider:
                for g in p["gpu_types"]:
                    if g["id"] == gpu_type:
                        selected = {
                            "provider_id": p["id"],
                            "provider_name": p["name"],
                            "gpu_id": g["id"],
                            "gpu_name": g["name"],
                            "vram_gb": g["vram_gb"],
                            "price_per_hour": g["price_per_hour"],
                        }
                        break
        if not selected:
            return {"error": f"GPU '{gpu_type}' not found at provider '{provider}'", "summary": f"GPU '{gpu_type}' not found at provider '{provider}'"}
        if selected["vram_gb"] < min_vram:
            return {"error": f"GPU {gpu_type} has {selected['vram_gb']}GB VRAM but {job_type} requires {min_vram}GB", "summary": f"GPU {gpu_type} has {selected['vram_gb']}GB VRAM but {job_type} requires {min_vram}GB"}
    else:
        selected = _find_cheapest_gpu(min_vram, provider_id=provider, data=data)
        if not selected:
            msg = f"No GPU found with >= {min_vram}GB VRAM" + (f" at provider '{provider}'" if provider else "")
            return {"error": msg, "summary": msg}

    # Calculate cost
    time_per_sample = template["estimated_time_per_sample_minutes"]
    total_minutes = time_per_sample * n_samples
    total_hours = total_minutes / 60.0
    estimated_cost = total_hours * selected["price_per_hour"]

    return {
        "summary": (
            f"[PLACEHOLDER] {template['description']}: {n_samples} sample(s) on {selected['gpu_name']} ({selected['provider_name']})\n"
            f"Estimated time: {total_hours:.1f} hours | Estimated cost: ${estimated_cost:.2f} (based on static reference pricing — may be outdated)"
        ),
        "placeholder": True,
        "job_type": job_type,
        "n_samples": n_samples,
        "estimated_hours": round(total_hours, 2),
        "estimated_cost": round(estimated_cost, 2),
        "gpu": selected["gpu_id"],
        "gpu_name": selected["gpu_name"],
        "vram_gb": selected["vram_gb"],
        "provider": selected["provider_id"],
        "provider_name": selected["provider_name"],
        "price_per_hour": selected["price_per_hour"],
        "time_per_sample_minutes": time_per_sample,
    }
