from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests


class BackendClient:
    def __init__(self, base_url: Optional[str] = None):
        self._raw_backend_url = (base_url if base_url is not None else os.getenv("BACKEND_URL", "")).strip()
        self.base_url = self._raw_backend_url.rstrip("/")
        self.session = requests.Session()
        self._scraper_api_key = os.getenv("SCRAPER_API_KEY", "").strip()
        if self._scraper_api_key:
            self.session.headers.update({"X-Scraper-Key": self._scraper_api_key})
        self._is_github_actions = os.getenv("GITHUB_ACTIONS", "").strip().lower() == "true"
        self.skip_reason = self._resolve_skip_reason()
        self.enabled = self.skip_reason is None

    def _resolve_skip_reason(self) -> Optional[str]:
        if not self._raw_backend_url:
            return "[WARN] BACKEND_URL tanimli degil. Backend sync atlandi."

        parsed = urlparse(self.base_url)
        host = (parsed.hostname or "").lower()
        is_localhost = (
            host in {"localhost", "127.0.0.1"}
            or "localhost" in self.base_url.lower()
            or "127.0.0.1" in self.base_url
        )
        if self._is_github_actions and is_localhost:
            return (
                "[WARN] BACKEND_URL=localhost tespit edildi ve ortam GitHub Actions.\n"
                "[WARN] Backend sync atlandi."
            )
        return None

    def _log_skip_reason(self) -> None:
        if not self.skip_reason:
            return
        for line in self.skip_reason.splitlines():
            logging.warning(line)

    def sync_events_bulk(self, events: List[Dict], sync_run_id: str) -> bool:
        """
        Sends events to the .NET V4 Aggregator API for bulk processing.
        Skip safely when backend sync is disabled for this environment.
        """
        if not self.enabled:
            self._log_skip_reason()
            return True

        url = f"{self.base_url}/api/events/sync?syncRunId={sync_run_id}"
        try:
            parsed = urlparse(self.base_url)
            host = (parsed.hostname or "").lower()
            if host and host not in {"localhost", "127.0.0.1"}:
                logging.info("[OK] Remote backend sync deneniyor: %s", self.base_url)
            logging.info("Sending %s events to backend for sync (RunId: %s)...", len(events), sync_run_id)
            response = self.session.post(url, json=events, timeout=60)

            if 200 <= response.status_code < 300:
                logging.info("Successfully synced with backend: %s", response.json().get("message"))
                return True

            logging.error("Backend sync failed (%s) — body: %s", response.status_code, response.text[:1000])
            return False
        except Exception as exc:
            logging.error("Error connecting to backend: %s", exc)
            return False

    def deactivate_stale(self, sync_run_id: str, provider: str | None = None) -> bool:
        """
        Triggers the stale data cleanup lifecycle in the backend.
        Pass provider to scope cleanup to a single provider (recommended for
        individual-provider scripts). Pass None only when ALL providers have run.
        Skip safely when backend sync is disabled for this environment.
        """
        if not self.enabled:
            self._log_skip_reason()
            return True

        url = f"{self.base_url}/api/migration/deactivate-stale?syncRunId={sync_run_id}"
        if provider:
            url += f"&provider={provider}"
        try:
            response = self.session.post(url, timeout=30)
            return 200 <= response.status_code < 300
        except Exception as exc:
            logging.error("Error triggering stale cleanup: %s", exc)
            return False
