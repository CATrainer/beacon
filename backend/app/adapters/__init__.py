"""Source adapters. A new source is a new class + a registry entry, nothing else.

Importing this package registers all built-in adapters (see ``registry``).
"""
# ruff: noqa: I001 — base must be imported before the side-effect adapter imports.

from app.adapters.base import (
    AdapterError,
    RawCandidate,
    SourceAdapter,
    get_adapter,
    list_adapters,
    registry,
)

# Import modules for their @register side effects.
from app.adapters import atol, cqc, directory_ingest, google_places, manual_paste  # noqa: E402,F401

__all__ = [
    "RawCandidate",
    "SourceAdapter",
    "AdapterError",
    "registry",
    "get_adapter",
    "list_adapters",
]
