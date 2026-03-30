"""HTTP client wrapper for municipal web scraping."""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests
import urllib3

from config import settings
from providers.municipal_web.constants import DEFAULT_ACCEPT_HEADER, DEFAULT_ACCEPT_LANGUAGE_HEADER, DEFAULT_USER_AGENT, RETRYABLE_STATUS_CODES


class MunicipalHttpClient:
    """Encapsulates session management, retries and robots policy checks."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._session: Optional[requests.Session] = None
        self._robots: Dict[str, robotparser.RobotFileParser] = {}
        self._last_request_error = ""
        self._ssl_error_counts: Dict[str, int] = {}

    def setup_session(self) -> None:
        """Initialize requests session with project defaults."""
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": DEFAULT_ACCEPT_HEADER,
                "Accept-Language": DEFAULT_ACCEPT_LANGUAGE_HEADER,
                "User-Agent": settings.municipal_web_user_agent.strip() or DEFAULT_USER_AGENT,
            }
        )

    def close_session(self) -> None:
        """Close session safely and log cleanup failures."""
        self._log_ssl_summary()
        try:
            if self._session is not None:
                self._session.close()
        except Exception as exc:
            self._logger.warning("MunicipalWeb: session close failed reason=%s", exc)
        finally:
            self._session = None

    def fetch_text(self, url: str) -> str:
        """Fetch page text with retry and SSL fallback behavior."""
        if self._session is None:
            self._logger.error("MunicipalWeb: fetch requested without active session url=%s", url)
            return ""

        timeout = max(settings.municipal_web_timeout_seconds, 1)
        retries = max(settings.municipal_web_max_retries, 1)
        last_error = ""
        for attempt in range(1, retries + 1):
            self._last_request_error = ""
            text = self._try_fetch(url, timeout)
            if text is not None:
                return text
            last_error = self._last_request_error or f"attempt={attempt}"
            if attempt < retries:
                time.sleep(float(attempt))
        self._logger.error("MunicipalWeb: all retries failed url=%s last_error=%s", url, last_error)
        return ""

    def _try_fetch(self, url: str, timeout: int) -> Optional[str]:
        try:
            response = self._session.get(url, timeout=timeout)
            result = self._handle_response(url, response)
            if result is None:
                self._last_request_error = f"retryable status={response.status_code}"
            return result
        except requests.exceptions.SSLError as exc:
            self._record_ssl_error(url, exc, "request")
            self._last_request_error = str(exc)
            try:
                insecure_response = self._session.get(url, timeout=timeout, verify=False)
                insecure_result = self._handle_response(url, insecure_response)
                if insecure_result is None:
                    self._last_request_error = f"retryable status={insecure_response.status_code}"
                return insecure_result
            except Exception as insecure_exc:
                self._logger.warning("MunicipalWeb: insecure ssl retry failed url=%s reason=%s", url, insecure_exc)
                self._last_request_error = str(insecure_exc)
                return None
        except Exception as exc:
            self._logger.warning("MunicipalWeb: fetch failed url=%s reason=%s", url, exc)
            self._last_request_error = str(exc)
            return None

    def _handle_response(self, url: str, response: requests.Response) -> Optional[str]:
        if response.status_code == 200:
            return response.text
        if response.status_code in RETRYABLE_STATUS_CODES:
            self._logger.warning("MunicipalWeb: retryable status url=%s status=%s", url, response.status_code)
            return None
        self._logger.info("MunicipalWeb: skip url=%s status=%s", url, response.status_code)
        return ""

    def can_fetch(self, url: str) -> bool:
        """Validate robots policy for a URL with graceful fallback."""
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._robots.get(base) or self._load_robots(base)
        agent = settings.municipal_web_user_agent.strip() or "*"
        try:
            return parser.can_fetch(agent, url)
        except Exception as exc:
            self._logger.warning("MunicipalWeb: robots check failed url=%s reason=%s; allowing fetch", url, exc)
            return True

    def _load_robots(self, base: str) -> robotparser.RobotFileParser:
        parser = robotparser.RobotFileParser()
        robots_url = urljoin(base, "/robots.txt")
        try:
            response = requests.get(robots_url, timeout=max(settings.municipal_web_timeout_seconds, 1), headers={"User-Agent": settings.municipal_web_user_agent.strip() or "*"})
            if response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                self._logger.warning("MunicipalWeb: robots unavailable base=%s status=%s", base, response.status_code)
                parser.parse(["User-agent: *", "Allow: /"])
        except Exception as exc:
            if isinstance(exc, requests.exceptions.SSLError):
                self._record_ssl_error(robots_url, exc, "robots")
            else:
                self._logger.warning("MunicipalWeb: robots fetch failed base=%s reason=%s; allowing fetch", base, exc)
            parser.parse(["User-agent: *", "Allow: /"])
        self._robots[base] = parser
        return parser

    def _record_ssl_error(self, target_url: str, exc: Exception, stage: str) -> None:
        host = urlparse(target_url).netloc or target_url
        count = self._ssl_error_counts.get(host, 0) + 1
        self._ssl_error_counts[host] = count
        if count == 1:
            self._logger.warning("MunicipalWeb: ssl failed host=%s stage=%s reason=%s retry=insecure", host, stage, exc)

    def _log_ssl_summary(self) -> None:
        for host, count in self._ssl_error_counts.items():
            if count > 1:
                self._logger.warning("MunicipalWeb: ssl errors summary host=%s count=%s", host, count)
        self._ssl_error_counts = {}
