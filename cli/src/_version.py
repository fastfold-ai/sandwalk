"""fastfold-agent-cli: An autonomous agent for drug discovery research."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("fastfold-agent-cli")
except PackageNotFoundError:  # pragma: no cover - local source tree before install
    __version__ = "0.0.0"
