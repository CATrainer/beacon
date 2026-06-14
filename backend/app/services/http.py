"""Polite HTTP helpers shared by adapters and (later) the research agent.

Enforces the design doc's fetching etiquette (§9): honest User-Agent,
≤1 req/sec/host rate limiting, and robots.txt respect for HTML page fetches.
Synchronous on purpose — adapters are simple sync code; the worker runs them in
a thread so the event loop stays responsive.
"""

from __future__ import annotations

import logging
import threading
import time
from urllib import robotparser
from urllib.parse import urlparse

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=10.0)


def _headers() -> dict[str, str]:
    return {"User-Agent": settings.user_agent}


class RateLimiter:
    """Per-host minimum-interval limiter (process-local, thread-safe)."""

    def __init__(self, rps: float) -> None:
        self._min_interval = 1.0 / rps if rps > 0 else 0.0
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            last = self._last.get(host, 0.0)
            delay = self._min_interval - (now - last)
            if delay > 0:
                time.sleep(delay)
            self._last[host] = time.monotonic()


# Shared, process-wide limiter keyed on the configured per-host RPS.
rate_limiter = RateLimiter(settings.fetch_max_rps_per_host)

_robots_cache: dict[str, robotparser.RobotFileParser | None] = {}
_robots_lock = threading.Lock()


def _robots_for(host_url: str) -> robotparser.RobotFileParser | None:
    """Fetch & cache the robots.txt parser for a scheme://host. None if absent/unreadable."""
    with _robots_lock:
        if host_url in _robots_cache:
            return _robots_cache[host_url]
    rp = robotparser.RobotFileParser()
    robots_url = f"{host_url}/robots.txt"
    try:
        resp = httpx.get(robots_url, headers=_headers(), timeout=_DEFAULT_TIMEOUT)
        if resp.status_code >= 400:
            rp = None  # no robots.txt → allowed by default
        else:
            rp.parse(resp.text.splitlines())
    except httpx.HTTPError:
        rp = None
    with _robots_lock:
        _robots_cache[host_url] = rp
    return rp


def can_fetch(url: str) -> bool:
    """True if robots.txt permits our User-Agent to fetch this URL (allow if no robots)."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    host_url = f"{parsed.scheme}://{parsed.netloc}"
    rp = _robots_for(host_url)
    if rp is None:
        return True
    return rp.can_fetch(settings.user_agent, url)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
def get_json(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: httpx.Timeout | None = None,
) -> dict:
    """GET a JSON API endpoint with retry. Rate-limited per host. robots.txt does
    not apply to API endpoints, so it is intentionally not checked here."""
    host = urlparse(url).netloc
    rate_limiter.wait(host)
    merged = {**_headers(), **(headers or {})}
    resp = httpx.get(url, params=params, headers=merged, timeout=timeout or _DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
def post_json(
    url: str,
    *,
    json_body: dict,
    headers: dict | None = None,
    timeout: httpx.Timeout | None = None,
) -> dict:
    """POST a JSON body to an API endpoint with retry. Rate-limited per host."""
    host = urlparse(url).netloc
    rate_limiter.wait(host)
    merged = {**_headers(), **(headers or {})}
    resp = httpx.post(url, json=json_body, headers=merged, timeout=timeout or _DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_html(url: str, *, timeout: httpx.Timeout | None = None) -> str | None:
    """Fetch an HTML page politely: robots-respected, rate-limited. Returns None
    if disallowed by robots.txt or on error."""
    if not can_fetch(url):
        log.info("robots.txt disallows fetch: %s", url)
        return None
    host = urlparse(url).netloc
    rate_limiter.wait(host)
    try:
        resp = httpx.get(
            url, headers=_headers(), timeout=timeout or _DEFAULT_TIMEOUT, follow_redirects=True
        )
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError as exc:
        log.info("fetch_html failed for %s: %s", url, exc)
        return None
