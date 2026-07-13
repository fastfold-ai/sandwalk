"""sandwalk: a thinking path for open science."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sandwalk")
except PackageNotFoundError:  # pragma: no cover - local source tree before install
    __version__ = "0.0.1"
