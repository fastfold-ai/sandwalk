"""Build the Modal ``Image`` used when creating a sandbox.

Looks up ``parse_pip_packages`` via a lazy import of the package (rather than
importing it at module scope) so tests that monkeypatch
``agent.sandbox_backend.parse_pip_packages`` are honored here too.
"""

from __future__ import annotations

from typing import Any


def _build_modal_image(config: Any, *, compute_type: str = "cpu"):
    from agent.sandbox_deps import require_modal_deps

    require_modal_deps()
    import modal

    from agent.sandbox_backend import parse_pip_packages
    from agent.sandbox_backend.profile import sandbox_image_ref

    packages = parse_pip_packages(config.get("sandbox.pip_packages"))
    python_version = "3.11"
    ref = sandbox_image_ref(config, compute_type=compute_type)
    # debian_slim is Modal's helper (Image.debian_slim), not a Docker Hub tag.
    if ref in {"debian_slim", "debian-slim"}:
        image = modal.Image.debian_slim(python_version=python_version)
    else:
        image = modal.Image.from_registry(ref)
    if packages:
        image = image.pip_install(*packages)
    return image
