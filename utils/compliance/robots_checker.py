"""Robots.txt compliance checker with per-domain caching.

Usage
-----
    from utils.compliance import RobotsChecker

    checker = RobotsChecker()
    if not checker.is_allowed("https://example.com/etkinlik/", user_agent="IstanbulEtkinlikBot/1.0"):
        raise RuntimeError("Scraping disallowed by robots.txt")

    delay = checker.crawl_delay("https://example.com/")
    if delay:
        time.sleep(delay)
"""

from __future__ import annotations

import logging
import threading
import time
import urllib.robotparser
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)

# Cache TTL: 1 hour
_CACHE_TTL_SECONDS: int = 3600

# Per-domain cache: {domain: (parser, fetched_at)}
_cache: Dict[str, Tuple[urllib.robotparser.RobotFileParser, float]] = {}
_cache_lock = threading.Lock()


class RobotsChecker:
    """
    Checks robots.txt before any scraping request.

    - Results are cached per-domain for 1 hour to avoid hammering the target.
    - On fetch failure (network error / non-200) the checker defaults to ALLOW
      and logs a warning — we must not block scraping on infrastructure errors,
      but the warning should be investigated.
    - Thread-safe: uses a module-level lock around cache reads/writes.
    """

    def __init__(self, ttl_seconds: int = _CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_allowed(self, url: str, user_agent: str = "IstanbulEtkinlikBot/1.0") -> bool:
        """Return True if the URL is allowed by the domain's robots.txt.

        On any error (network, parse) defaults to True (allow) and logs warning.
        """
        try:
            parser = self._get_parser(url)
            allowed: bool = parser.can_fetch(user_agent, url)
            if not allowed:
                _logger.warning("RobotsChecker: disallowed url=%s ua=%s", url, user_agent)
            return allowed
        except Exception as exc:
            _logger.warning("RobotsChecker: failed to check url=%s reason=%s — defaulting to ALLOW", url, exc)
            return True

    def crawl_delay(self, url: str, user_agent: str = "IstanbulEtkinlikBot/1.0") -> Optional[float]:
        """Return the Crawl-delay directive for the domain, if any."""
        try:
            parser = self._get_parser(url)
            delay = parser.crawl_delay(user_agent)
            return float(delay) if delay is not None else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_parser(self, url: str) -> urllib.robotparser.RobotFileParser:
        domain = self._extract_domain(url)
        with _cache_lock:
            if domain in _cache:
                parser, fetched_at = _cache[domain]
                if time.monotonic() - fetched_at < self._ttl:
                    return parser

        # Fetch outside lock to avoid blocking other threads
        robots_url = self._robots_url(domain)
        parser = urllib.robotparser.RobotFileParser(url=robots_url)
        try:
            parser.read()
            _logger.debug("RobotsChecker: fetched robots.txt from %s", robots_url)
        except Exception as exc:
            _logger.warning("RobotsChecker: failed to fetch %s reason=%s", robots_url, exc)

        with _cache_lock:
            _cache[domain] = (parser, time.monotonic())

        return parser

    @staticmethod
    def _extract_domain(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _robots_url(domain: str) -> str:
        return f"{domain}/robots.txt"
