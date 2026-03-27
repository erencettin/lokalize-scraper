import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import pytz
import requests

from config import settings
from models.normalized_event import (
    NormalizedEvent,
    NormalizedOccurrence,
    NormalizedSource,
    PriceInfo,
)
from providers.base_provider import BaseProvider
from utils.date_parser import DateParser


class PredictHQProvider(BaseProvider):
    BASE_URL = "https://api.predicthq.com/v1/events/"
    ISTANBUL_TZ = pytz.timezone("Europe/Istanbul")

    CATEGORY_MAP = {
        "concerts": "concert",
        "conferences": "experience",
        "sports": "match",
        "festivals": "festival",
        "performing-arts": "theatre",
        "community": "show",
        "expos": "experience",
        "school-holidays": "show",
        "public-holidays": "show",
    }

    def __init__(self) -> None:
        super().__init__("PredictHQ", mode="http")
        self.logger = logging.getLogger(__name__)
        self.session: Optional[requests.Session] = None
        self._last_fetched_pages = 0

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        if not settings.predicthq_enabled:
            self.logger.info("PredictHQ: disabled by config, skipping provider")
            return []

        if not settings.predicthq_access_token.strip():
            self.logger.warning("PredictHQ: access token missing, skipping provider safely")
            return []

        self._setup_session()
        try:
            raw_events = self._fetch_all_events()
            self.logger.info("PredictHQ: fetched raw events=%s", len(raw_events))

            parsed: List[NormalizedEvent] = []
            skipped = 0
            for raw_event in raw_events:
                try:
                    normalized = self._normalize_event(raw_event)
                    if normalized is not None:
                        parsed.append(normalized)
                    else:
                        skipped += 1
                except Exception as exc:
                    skipped += 1
                    self.logger.warning(
                        "PredictHQ: skipped malformed record event_id=%s reason=%s",
                        raw_event.get("id"),
                        self._safe_error(exc),
                    )

            self.logger.info(
                "PredictHQ: summary pages=%s raw=%s parsed=%s skipped=%s",
                self._last_fetched_pages,
                len(raw_events),
                len(parsed),
                skipped,
            )
            return parsed
        finally:
            self._close_session()

    def _setup_session(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {settings.predicthq_access_token.strip()}",
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }
        )
        self._last_fetched_pages = 0

    def _close_session(self) -> None:
        try:
            if self.session is not None:
                self.session.close()
        except Exception:
            pass
        finally:
            self.session = None

    def _fetch_all_events(self) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set()
        offset = 0

        for page in range(1, max(settings.predicthq_max_pages, 1) + 1):
            result = self._fetch_page(offset)
            if result is None:
                self.logger.warning("PredictHQ: page fetch failed page=%s, stopping", page)
                break

            page_events = result.get("events", [])
            has_more = bool(result.get("has_more", False))
            self._last_fetched_pages += 1

            if not page_events:
                self.logger.info("PredictHQ: page=%s has no events, stopping", page)
                break

            new_count = 0
            for item in page_events:
                event_id = str(item.get("id") or "")
                if not event_id or event_id in seen_ids:
                    continue
                seen_ids.add(event_id)
                events.append(item)
                new_count += 1

            self.logger.info(
                "PredictHQ: page=%s fetched=%s new=%s total_unique=%s",
                page,
                len(page_events),
                new_count,
                len(events),
            )

            if new_count == 0:
                self.logger.info("PredictHQ: duplicate-only page, stopping")
                break

            if not has_more:
                self.logger.info("PredictHQ: no next page, stopping")
                break

            offset += max(settings.predicthq_limit, 1)

        return events

    def _fetch_page(self, offset: int) -> Optional[Dict[str, Any]]:
        if self.session is None:
            raise RuntimeError("PredictHQ session is not initialized")

        params = {
            "q": settings.predicthq_query,
            "country": settings.predicthq_country,
            "limit": max(settings.predicthq_limit, 1),
            "offset": max(offset, 0),
            "sort": "start",
        }

        last_error: Optional[str] = None
        for attempt in range(1, max(settings.predicthq_max_retries, 1) + 1):
            try:
                response = self.session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=max(settings.predicthq_timeout_seconds, 1),
                )

                if response.status_code in (401, 403):
                    self.logger.error(
                        "PredictHQ: auth failed status=%s offset=%s",
                        response.status_code,
                        offset,
                    )
                    return None

                if response.status_code == 429:
                    backoff = float(attempt)
                    self.logger.warning(
                        "PredictHQ: rate limited offset=%s attempt=%s/%s backoff=%.1fs",
                        offset,
                        attempt,
                        settings.predicthq_max_retries,
                        backoff,
                    )
                    time.sleep(backoff)
                    continue

                if response.status_code != 200:
                    preview = (response.text or "")[:300]
                    raise RuntimeError(f"Unexpected status={response.status_code} preview={preview}")

                payload = response.json()
                return self._extract_page_payload(payload)
            except requests.exceptions.Timeout:
                last_error = f"Timeout at offset={offset}"
                self.logger.warning(
                    "PredictHQ: timeout offset=%s attempt=%s/%s",
                    offset,
                    attempt,
                    settings.predicthq_max_retries,
                )
                time.sleep(float(attempt))
            except Exception as exc:
                last_error = self._safe_error(exc)
                self.logger.warning(
                    "PredictHQ: request failed offset=%s attempt=%s/%s error=%s",
                    offset,
                    attempt,
                    settings.predicthq_max_retries,
                    last_error,
                )
                if attempt < settings.predicthq_max_retries:
                    time.sleep(float(attempt))

        self.logger.error("PredictHQ: all retries failed offset=%s last_error=%s", offset, last_error)
        return None

    def _extract_page_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        events = payload.get("results") or []
        if not isinstance(events, list):
            events = []
        has_more = bool(payload.get("next"))
        return {"events": events, "has_more": has_more}

    def _normalize_event(self, raw_event: Dict[str, Any]) -> Optional[NormalizedEvent]:
        event_id = str(raw_event.get("id") or "").strip()
        title = str(raw_event.get("title") or "").strip()
        if not event_id or not title:
            return None

        source_url = raw_event.get("local_rank_url") or raw_event.get("phq_attendance_url")
        if not isinstance(source_url, str) or not source_url.startswith("http"):
            # PredictHQ kaynak URL yoksa kendi event linkini üret
            source_url = f"https://control.predicthq.com/events/{event_id}"

        occurrence = self._build_occurrence(raw_event, title, event_id, source_url)
        if occurrence is None:
            return None

        category = self._resolve_category(raw_event)
        description = self._build_description(raw_event)
        image_url = None

        return NormalizedEvent(
            title=title,
            description=description,
            type=category,
            city_name="Istanbul",
            image_url=image_url,
            occurrences=[occurrence],
        )

    def _build_occurrence(
        self,
        raw_event: Dict[str, Any],
        title: str,
        event_id: str,
        source_url: str,
    ) -> Optional[NormalizedOccurrence]:
        start_at = self._extract_datetime(raw_event)
        if start_at is None:
            self.logger.info("PredictHQ: skip event_id=%s reason=missing_or_invalid_date", event_id)
            return None

        local_date, local_time, timezone_name = DateParser.to_local_parts(start_at)
        venue_name = self._extract_venue_name(raw_event)
        source = NormalizedSource(
            provider=self.name,
            external_id=event_id,
            title=title,
            source_url=source_url,
            price=PriceInfo(text="Fiyat bilgisi yok", currency="TRY"),
            ticket_status="unknown",
        )

        return NormalizedOccurrence(
            start_at_utc=start_at,
            local_date=local_date,
            local_time=local_time,
            timezone=timezone_name,
            venue_name=venue_name,
            sources=[source],
        )

    def _extract_datetime(self, raw_event: Dict[str, Any]) -> Optional[datetime]:
        start = raw_event.get("start")
        if isinstance(start, str) and start.strip():
            parsed = DateParser.parse_iso_date(start.strip())
            if parsed is not None:
                return parsed
        return None

    def _extract_venue_name(self, raw_event: Dict[str, Any]) -> str:
        entities = raw_event.get("entities") or []
        if isinstance(entities, list):
            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                name = entity.get("name")
                entity_type = str(entity.get("type") or "").lower()
                if isinstance(name, str) and name.strip() and entity_type in {"venue", "performer"}:
                    return name.strip()
        return "Mekan bilgisi yok"

    def _resolve_category(self, raw_event: Dict[str, Any]) -> str:
        category = str(raw_event.get("category") or "").strip().lower()
        return self.CATEGORY_MAP.get(category, "show")

    def _build_description(self, raw_event: Dict[str, Any]) -> Optional[str]:
        labels = raw_event.get("labels") or []
        if isinstance(labels, list) and labels:
            joined = ", ".join(str(item) for item in labels if item)
            return joined[:2000] if joined else None
        return None

    def _safe_error(self, exc: Exception) -> str:
        raw = f"{type(exc).__name__}: {exc}"
        token = settings.predicthq_access_token.strip()
        if token:
            raw = raw.replace(token, "***")
        return raw[:300]
