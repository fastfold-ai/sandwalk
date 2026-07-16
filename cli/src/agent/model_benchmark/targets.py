"""Cloud catalog target collection for the benchmark matrix."""

from __future__ import annotations

from collections.abc import Callable

from agent.model_benchmark.models import BenchmarkTarget
from agent.model_catalog import (
    cloud_catalog_models,
    model_supports_reasoning_effort,
    resolve_catalog_model_id,
)


def collect_cloud_targets(
    *,
    provider: str | None = None,
    model: str | None = None,
    has_key: Callable[[str], bool] | None = None,
    discover: bool = True,
) -> list[BenchmarkTarget]:
    """Cloud catalog targets for providers with a configured API key.

    When ``discover`` is True and an OpenCode Zen key is set, also include
    live-discovered Zen models (minus the unsupported denylist).
    """
    targets: list[BenchmarkTarget] = []
    seen: set[tuple[str, str]] = set()
    for entry in cloud_catalog_models():
        prov = entry["provider"]
        mid = resolve_catalog_model_id(entry["id"])
        if provider and prov != provider:
            continue
        if model and mid != model and entry["id"] != model:
            continue
        if has_key is not None and not has_key(prov):
            continue
        seen.add((prov, mid))
        targets.append(
            BenchmarkTarget(
                provider=prov,
                model=mid,
                label=entry["label"],
                source="cloud",
                profile_id=None,
                supports_reasoning_effort=model_supports_reasoning_effort(
                    prov, mid
                ),
            )
        )

    if discover and (provider is None or provider == "opencode"):
        if has_key is None or has_key("opencode"):
            try:
                from agent_server.models_service import ModelsService

                listed = ModelsService().list_models(
                    discover=True, enabled_only=False
                )
            except Exception:
                listed = None
            if listed is not None:
                for item in listed.data:
                    if item.provider != "opencode":
                        continue
                    mid = resolve_catalog_model_id(item.id)
                    if model and mid != model and item.id != model:
                        continue
                    key = ("opencode", mid)
                    if key in seen:
                        continue
                    seen.add(key)
                    targets.append(
                        BenchmarkTarget(
                            provider="opencode",
                            model=mid,
                            label=item.label,
                            source="cloud",
                            profile_id=None,
                            supports_reasoning_effort=model_supports_reasoning_effort(
                                "opencode", mid
                            ),
                        )
                    )
    return targets
