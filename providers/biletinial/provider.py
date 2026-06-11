"""Biletinial affiliate feed provider."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List
from xml.etree import ElementTree as ET

import pytz

from config import settings
from models.normalized_event import NormalizedEvent
from providers.base_provider import BaseProvider
from providers.biletinial.event_builder import EventBuilder
from providers.biletinial.http_client import BiletinialHttpClient
from providers.biletinial.parser import parse_feed_items


class BiletinialProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("Biletinial", mode="http")
        self._logger = logging.getLogger(__name__)
        self._http = BiletinialHttpClient()
        self._builder = EventBuilder()

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        if not settings.biletinial_enabled:
            self._logger.info("Biletinial: disabled by config, skipping")
            return []

        feed_urls = [u.strip() for u in settings.biletinial_feed_urls.split(",") if u.strip()]
        if not feed_urls:
            self._logger.warning("Biletinial: no feed URLs configured, skipping")
            return []

        now_utc = datetime.now(pytz.UTC)
        events: List[NormalizedEvent] = []

        for url in feed_urls:
            content = self._http.fetch_feed(url)
            if content is None:
                self._logger.error("Biletinial: failed to fetch feed %s", url)
                continue

            try:
                items = parse_feed_items(content)
            except ET.ParseError as exc:
                self._logger.error("Biletinial: failed to parse feed %s: %s", url, exc)
                continue

            self._logger.info("Biletinial: %d items in feed %s", len(items), url)

            for item in items:
                try:
                    event = self._builder.build(item, now_utc)
                    if event is not None:
                        events.append(event)
                except Exception as exc:
                    self._logger.debug(
                        "Biletinial: skipping item id=%s (%s: %s)",
                        item.get("id"), type(exc).__name__, exc,
                    )

        self._logger.info("Biletinial: parsed %d events total", len(events))
        return events
