"""Fetches the "Etkinliğe Dair" (about event) description from biletix.com detail pages.

Biletix's Discovery API feed leaves description fields (eventInfo/eventNotes/info/
pleaseNote) empty for Biletix-branded events. Biletix confirmed by email (2026-06-08)
that — as an affiliate partner — we may scrape the "Etkinliğe Dair" text from their
detail pages automatically, provided we attribute the source. See
providers/ticketmaster/event_builder.py for how BILETIX_SOURCE_ATTRIBUTION is appended.

Compliance notes:
- We identify ourselves transparently via a descriptive User-Agent (no spoofing).
- robots.txt is honored before fetching any URL.
- Requests are throttled per-domain via the shared RateLimiter.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Dict, Optional
from urllib import robotparser
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests

from config import settings
from providers.base_http_client import BaseHttpClient
from providers.ticketmaster.constants import (
    BILETIX_DETAIL_DEFAULT_USER_AGENT,
    BILETIX_DETAIL_MAX_RETRY_BACKOFF_SECONDS,
    BILETIX_DETAIL_RETRYABLE_STATUS_CODES,
)
from utils.compliance.rate_limiter import RateLimiter
from utils.text_normalizer import strip_html

_rate_limiter = RateLimiter()

# Captures the quote character used (group 1) and backreferences it (\1) so the match
# stops at the matching closing quote — not at a quote belonging to a later attribute
# (e.g. itemprop="description" that follows content="...").
_META_DESCRIPTION_RE = re.compile(
    r'<meta\s+name=["\']description["\']\s+content=(["\'])(.*?)\1',
    re.IGNORECASE | re.DOTALL,
)

# Discovery API gives "/performance/{code}/{subcode}/{country}/{lang}" pages, which
# return HTTP 401 when fetched directly. The "/etkinlik/{code}/{country}/{lang}" page
# for the same event code renders fine and contains "Etkinliğe Dair" in its meta description.
_PERFORMANCE_PATH_RE = re.compile(r'^/performance/([A-Za-z0-9]+)/\d+/([A-Za-z]+)/(\w+)/?$')


class BiletixDetailFetcher(BaseHttpClient):
    """Fetches and extracts the about-event description from a biletix.com page."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._local = threading.local()
        self._robots: Dict[str, robotparser.RobotFileParser] = {}
        self._robots_lock = threading.Lock()

    def _get_session(self) -> requests.Session:
        if not hasattr(self._local, "session"):
            session = requests.Session()
            session.headers.update(
                {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "tr-TR,tr;q=0.9",
                    "User-Agent": settings.biletix_detail_user_agent.strip() or BILETIX_DETAIL_DEFAULT_USER_AGENT,
                }
            )
            self._local.session = session
        return self._local.session

    def setup_session(self) -> None:
        self._get_session()

    def close_session(self) -> None:
        try:
            if hasattr(self._local, "session"):
                self._local.session.close()
                del self._local.session
        except Exception as exc:
            self._logger.warning("BiletixDetail: session close failed reason=%s", exc)

    def fetch_about_description(self, url: str) -> Optional[str]:
        """Fetch the "Etkinliğe Dair" text for a biletix.com event page, or None."""
        if not url or not url.startswith("http"):
            return None
        resolved_url = self._resolve_event_url(url)
        if not resolved_url:
            self._logger.info("BiletixDetail: could not resolve biletix event url from=%s", url)
            return None
        if not self._can_fetch(resolved_url):
            self._logger.info("BiletixDetail: robots.txt disallows url=%s", resolved_url)
            return None

        html = self._fetch_with_retry(resolved_url)
        if not html:
            return None

        about = self._extract_about_description(html)
        if not about:
            self._logger.info("BiletixDetail: no description found url=%s", url)
            return None
        return about

    # ------------------------------------------------------------------
    # URL resolution
    # ------------------------------------------------------------------

    def _resolve_event_url(self, url: str) -> Optional[str]:
        """Resolve a (possibly affiliate-redirected) Ticketmaster URL to the
        biletix.com "/etkinlik/..." page that actually renders "Etkinliğe Dair".

        Discovery API's `url` field is an affiliate redirect (ticketmaster.evyy.net/c/...
        ?u=<encoded target>) pointing at biletix.com "/performance/{code}/{subcode}/
        {country}/{lang}", which returns HTTP 401 when fetched directly — so we extract
        the encoded target and rewrite its path to "/etkinlik/{code}/{country}/{lang}".
        """
        parsed = urlparse(url)
        target = url
        if "biletix.com" not in parsed.netloc.lower():
            encoded_targets = parse_qs(parsed.query).get("u") or []
            if not encoded_targets:
                return None
            target = unquote(encoded_targets[0])

        target_parsed = urlparse(target)
        if "biletix.com" not in target_parsed.netloc.lower():
            return None

        match = _PERFORMANCE_PATH_RE.match(target_parsed.path)
        if not match:
            return target_parsed._replace(query="", fragment="").geturl()

        code, country, lang = match.groups()
        rewritten = target_parsed._replace(path=f"/etkinlik/{code}/{country}/{lang}", query="", fragment="")
        return rewritten.geturl()

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _fetch_with_retry(self, url: str) -> Optional[str]:
        timeout_val = max(settings.biletix_detail_timeout_seconds, 1)
        timeout = (min(timeout_val, 20), min(timeout_val, 20))
        retries = max(settings.biletix_detail_max_retries, 1)

        for attempt in range(1, retries + 1):
            _rate_limiter.wait_for_domain(url)
            try:
                session = self._get_session()
                response = session.get(url, timeout=timeout)
            except Exception as exc:
                self._logger.warning("BiletixDetail: fetch failed url=%s attempt=%s reason=%s", url, attempt, exc)
                response = None

            if response is not None:
                if response.status_code == 200:
                    return response.text
                if response.status_code not in BILETIX_DETAIL_RETRYABLE_STATUS_CODES:
                    self._logger.info("BiletixDetail: skip url=%s status=%s", url, response.status_code)
                    return None
                self._logger.warning("BiletixDetail: retryable status url=%s status=%s attempt=%s", url, response.status_code, attempt)

            if attempt < retries:
                backoff = min(2 ** attempt, BILETIX_DETAIL_MAX_RETRY_BACKOFF_SECONDS)
                time.sleep(backoff)

        self._logger.error("BiletixDetail: all retries failed url=%s", url)
        return None

    # ------------------------------------------------------------------
    # robots.txt
    # ------------------------------------------------------------------

    def _can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        with self._robots_lock:
            parser = self._robots.get(base)
            if parser is None:
                parser = self._load_robots(base)
                self._robots[base] = parser
        agent = settings.biletix_detail_user_agent.strip() or BILETIX_DETAIL_DEFAULT_USER_AGENT
        try:
            return parser.can_fetch(agent, url)
        except Exception as exc:
            self._logger.warning("BiletixDetail: robots check failed url=%s reason=%s; allowing fetch", url, exc)
            return True

    def _load_robots(self, base: str) -> robotparser.RobotFileParser:
        parser = robotparser.RobotFileParser()
        robots_url = urljoin(base, "/robots.txt")
        timeout_val = max(settings.biletix_detail_timeout_seconds, 1)
        timeout = (min(timeout_val, 8), min(timeout_val, 8))
        agent = settings.biletix_detail_user_agent.strip() or BILETIX_DETAIL_DEFAULT_USER_AGENT
        try:
            response = requests.get(robots_url, timeout=timeout, headers={"User-Agent": agent})
            if response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                self._logger.info("BiletixDetail: robots unavailable base=%s status=%s; allowing fetch", base, response.status_code)
                parser.parse(["User-agent: *", "Allow: /"])
        except Exception as exc:
            self._logger.warning("BiletixDetail: robots fetch failed base=%s reason=%s; allowing fetch", base, exc)
            parser.parse(["User-agent: *", "Allow: /"])
        return parser

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _extract_about_description(self, html: str) -> Optional[str]:
        match = _META_DESCRIPTION_RE.search(html)
        if not match:
            return None
        plain_text = strip_html(match.group(2))
        return plain_text or None
