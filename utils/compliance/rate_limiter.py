"""Domain-based rate limiter for respectful scraping.

Usage
-----
    from utils.compliance import RateLimiter

    limiter = RateLimiter()
    limiter.wait_for_domain("https://www.bakirkoy.bel.tr/etkinlik/")
    # → sleeps as needed, then returns
    response = requests.get(url)
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)

# Per-domain rate limit configuration.
# Key: lowercase domain (netloc). Value: minimum delay in seconds between requests.
# "default" applies when no specific entry matches.
RATE_LIMITS: Dict[str, float] = {
    # Public Ticketmaster Discovery API: 5 req/s tier but we stay conservative
    "api.ticketmaster.com":  5.0,
    # SerpAPI: plan-dependent, 2 s is safe for standard plans
    "serpapi.com":           2.0,
    # Biletix detail pages — scraped with explicit permission (affiliate partner);
    # stay polite to avoid burdening their site.
    "www.biletix.com":       1.5,
    # Default for all municipal sites and unknown domains
    "default":               1.5,
}


class RateLimiter:
    """
    Thread-safe domain-based rate limiter using last-request timestamps.

    ``wait_for_domain(url)`` sleeps the calling thread until the configured
    minimum delay since the last request to that domain has elapsed, then
    records *now* as the new last-request time.

    Design notes
    ------------
    - Uses a per-instance lock; share one instance across all scrapers.
    - Domain is derived from the URL netloc (scheme+host, port stripped).
    - If the domain is not in RATE_LIMITS, the "default" limit applies.
    """

    def __init__(self) -> None:
        self._last_request: Dict[str, float] = {}
        self._lock = threading.Lock()

    def wait_for_domain(self, url: str) -> None:
        """Sleep if necessary to honour the per-domain rate limit, then return."""
        domain = self._extract_domain(url)
        delay = self._get_delay(domain)

        with self._lock:
            last = self._last_request.get(domain, 0.0)
            elapsed = time.monotonic() - last
            sleep_for = max(0.0, delay - elapsed)

        if sleep_for > 0:
            _logger.debug("RateLimiter: sleeping %.2fs for domain=%s", sleep_for, domain)
            time.sleep(sleep_for)

        with self._lock:
            self._last_request[domain] = time.monotonic()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_domain(url: str) -> str:
        return urlparse(url).netloc.lower()

    @staticmethod
    def _get_delay(domain: str) -> float:
        if domain in RATE_LIMITS:
            return RATE_LIMITS[domain]
        # Partial-match: e.g. "sub.serpapi.com" → match "serpapi.com"
        for key, delay in RATE_LIMITS.items():
            if key != "default" and domain.endswith(key):
                return delay
        return RATE_LIMITS.get("default", 3.0)
