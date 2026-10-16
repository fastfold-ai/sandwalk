"""Datasets that load the first time agent code touches them.

Every ``run_python`` sandbox used to read all six reference tables up front:
a 430 MB CRISPR matrix, a 150 MB mutation matrix, PRISM, L1000, and so on.
Eight concurrent chats meant eight parses at once and several hundred MB of
RAM per run, for code that mostly never looked at them. Sampling the API under
a 4×2 grid put a quarter of all busy stacks inside pandas ``read_csv``.

A :class:`LazyDataset` sits in the namespace under the usual name. The first
attribute or item access loads the real DataFrame through the cached loader,
swaps itself out of the namespace, and forwards the call. Loading is serialized
per dataset, so concurrent runs share one parse and one copy in memory.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(name: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _LOCKS.get(name)
        if lock is None:
            lock = _LOCKS[name] = threading.Lock()
        return lock


class LazyDataset:
    """Proxy for a DataFrame that is read on first use."""

    __slots__ = ("_name", "_loader", "_namespace", "_frame")

    def __init__(self, name: str, loader: Callable[[], Any], namespace: dict[str, Any]):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_loader", loader)
        object.__setattr__(self, "_namespace", namespace)
        object.__setattr__(self, "_frame", None)

    # -- loading -------------------------------------------------------------

    @property
    def loaded(self) -> bool:
        return object.__getattribute__(self, "_frame") is not None

    def load(self) -> Any:
        """Read the dataset (once per process) and put it in the namespace."""
        frame = object.__getattribute__(self, "_frame")
        if frame is not None:
            return frame
        name = object.__getattribute__(self, "_name")
        with _lock_for(name):
            frame = object.__getattribute__(self, "_frame")
            if frame is None:
                frame = object.__getattribute__(self, "_loader")()
                object.__setattr__(self, "_frame", frame)
        namespace = object.__getattribute__(self, "_namespace")
        # Later statements in the same exec, and later calls, see the real
        # DataFrame, so isinstance checks inside pandas pass from then on.
        if namespace.get(name) is self:
            namespace[name] = frame
        return frame

    # -- forwarding ----------------------------------------------------------

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.load(), attr)

    def __setattr__(self, attr: str, value: Any) -> None:
        setattr(self.load(), attr, value)

    def __getitem__(self, key: Any) -> Any:
        return self.load()[key]

    def __setitem__(self, key: Any, value: Any) -> None:
        self.load()[key] = value

    def __len__(self) -> int:
        return len(self.load())

    def __iter__(self):
        return iter(self.load())

    def __contains__(self, item: Any) -> bool:
        return item in self.load()

    def __array__(self, *args: Any, **kwargs: Any) -> Any:
        return self.load().__array__(*args, **kwargs)

    def __repr__(self) -> str:
        if self.loaded:
            return repr(object.__getattribute__(self, "_frame"))
        name = object.__getattribute__(self, "_name")
        return f"<dataset {name!r}: loads on first use>"

    def __str__(self) -> str:
        return str(self.load())


__all__ = ["LazyDataset"]
