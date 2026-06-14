"""Source-adapter contract, registry, and fixture fallback.

Every discovery source implements ``SourceAdapter``. When an adapter's API key is
absent, ``fetch`` transparently falls back to bundled fixtures so the whole
pipeline runs locally with zero keys — the candidate's ``raw_meta`` is tagged
``{"fixture": true}`` so downstream code (and the operator) can tell.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


class AdapterError(Exception):
    """Raised when a live fetch fails in a way the caller should surface."""


@dataclass
class RawCandidate:
    """A raw top-of-funnel candidate emitted by an adapter (§3)."""

    company_name: str
    source_key: str
    website: str | None = None
    address: str | None = None
    location: str | None = None
    source_ref: str | None = None
    raw_meta: dict[str, Any] = field(default_factory=dict)


class SourceAdapter:
    """Base class for discovery adapters.

    Subclasses set ``key`` and ``fixture_file`` and implement ``available()`` and
    ``_fetch_live()``. They should NOT override ``fetch()`` — it handles the
    fixture fallback uniformly.
    """

    key: str = ""
    fixture_file: str = ""
    #: Human description shown in the UI / docs.
    description: str = ""

    def available(self, source_params: dict) -> bool:
        """Whether a live fetch is possible (e.g. the API key / data URL is set)."""
        raise NotImplementedError

    def _fetch_live(self, source_params: dict, limit: int, lane_config: dict) -> list[RawCandidate]:
        raise NotImplementedError

    def fetch(
        self,
        source_params: dict,
        limit: int,
        lane_config: dict,
        *,
        force_fixtures: bool = False,
    ) -> list[RawCandidate]:
        """Return candidates. Falls back to fixtures when unavailable."""
        if force_fixtures or not self.available(source_params):
            reason = "forced" if force_fixtures else "unavailable"
            log.info("adapter %s using fixtures (%s)", self.key, reason)
            return self._load_fixtures(limit)
        try:
            return self._fetch_live(source_params, limit, lane_config)
        except AdapterError:
            raise
        except Exception as exc:  # noqa: BLE001 — surface as AdapterError to the job
            raise AdapterError(f"{self.key} live fetch failed: {exc}") from exc

    def _load_fixtures(self, limit: int) -> list[RawCandidate]:
        if not self.fixture_file:
            return []
        path = _FIXTURE_DIR / self.fixture_file
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        out: list[RawCandidate] = []
        for row in data[:limit]:
            meta = dict(row.get("raw_meta", {}))
            meta["fixture"] = True
            out.append(
                RawCandidate(
                    company_name=row["company_name"],
                    source_key=self.key,
                    website=row.get("website"),
                    address=row.get("address"),
                    location=row.get("location"),
                    source_ref=row.get("source_ref"),
                    raw_meta=meta,
                )
            )
        return out


registry: dict[str, SourceAdapter] = {}


def register(adapter_cls: type[SourceAdapter]) -> type[SourceAdapter]:
    """Class decorator that instantiates and registers an adapter by its key."""
    instance = adapter_cls()
    if not instance.key:
        raise ValueError(f"{adapter_cls.__name__} must set a non-empty key")
    registry[instance.key] = instance
    return adapter_cls


def get_adapter(key: str) -> SourceAdapter | None:
    return registry.get(key)


def list_adapters() -> list[SourceAdapter]:
    return list(registry.values())
