"""Thread-local storage with explicit snapshot/restore for child tasks.

The core problem: ``threading.local`` gives each thread its own storage, but a
child task (a new thread, or a coroutine scheduled onto another thread) starts
with an empty context.  There is no built-in way to copy the parent's values
into the child and later restore the parent's values when the child is done.

This module provides a small carrier object that wraps a ``threading.local``
and adds two explicit operations:

* ``snapshot()`` returns a plain dict of the current thread's values.
* ``restore(mapping)`` replaces the current thread's values with the given
  mapping (removing keys that are not present).

A child thread can therefore call ``snapshot()`` on the parent's carrier,
``restore()`` the result into its own carrier, do its work, and then restore
its original state.  The carrier is intentionally not a context manager and
does not try to be clever about inheritance; explicit is better than implicit
when the values are request-scoped and the threads are long-lived.

Only the standard library is used.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Iterator, Optional

__all__ = ["ContextCarrier", "current_context", "new_context"]


class ContextCarrier:
    """A thread-local mapping with snapshot and restore.

    Each thread sees its own independent set of key/value pairs.  The
    ``snapshot`` and ``restore`` methods are the only way to move values
    between threads, which keeps the propagation explicit.

    The carrier stores arbitrary Python objects.  Keys must be hashable, but
    that is enforced by the underlying dict and not re-checked here.
    """

    def __init__(self) -> None:
        # ``threading.local`` is created per carrier instance, so two carriers
        # never share storage even if they are used from the same thread.
        self._local = threading.local()

    def _storage(self) -> Dict[Any, Any]:
        """Return the current thread's dict, creating it on first access."""
        storage = getattr(self._local, "storage", None)
        if storage is None:
            storage = {}
            self._local.storage = storage
        return storage

    def get(self, key: Any, default: Optional[Any] = None) -> Any:
        """Return the value for *key* in the current thread, or *default*."""
        return self._storage().get(key, default)

    def set(self, key: Any, value: Any) -> None:
        """Set *key* to *value* in the current thread."""
        self._storage()[key] = value

    def delete(self, key: Any) -> None:
        """Remove *key* from the current thread.

        Raises ``KeyError`` if the key is not present, matching ``dict``
        semantics.  Callers that want a silent delete should check first.
        """
        del self._storage()[key]

    def clear(self) -> None:
        """Remove all values for the current thread."""
        self._storage().clear()

    def snapshot(self) -> Dict[Any, Any]:
        """Return a shallow copy of the current thread's values.

        The copy is a plain dict, so it can be passed to another thread and
        restored there without sharing the carrier's internal storage.
        """
        return dict(self._storage())

    def restore(self, mapping: Dict[Any, Any]) -> None:
        """Replace the current thread's values with *mapping*.

        Keys present in the current thread but absent from *mapping* are
        removed.  The mapping is copied, so later changes to it do not affect
        the carrier.
        """
        storage = self._storage()
        storage.clear()
        storage.update(mapping)

    def keys(self) -> Iterator[Any]:
        """Iterate over the keys visible to the current thread."""
        return iter(self._storage().keys())

    def __contains__(self, key: Any) -> bool:
        return key in self._storage()

    def __len__(self) -> int:
        return len(self._storage())

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._storage()!r})"


# A module-level carrier for callers that want a shared default context.
_default_context = ContextCarrier()


def current_context() -> ContextCarrier:
    """Return the process-wide default carrier.

    This is a convenience for applications that only need one context.
    Libraries should accept a ``ContextCarrier`` argument instead of relying
    on this global, so that multiple independent contexts can coexist.
    """
    return _default_context


def new_context() -> ContextCarrier:
    """Create a fresh, independent carrier.

    Each carrier has its own ``threading.local`` storage; values set on one
    are not visible on another, even within the same thread.
    """
    return ContextCarrier()
