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


class TicketmasterProvider(BaseProvider):
    BASE_URL = "https://app.ticketmaster.com/discovery/v2/"
    EVENTS_ENDPOINT = "events.json"
    ISTANBUL_TZ = pytz.timezone("Europe/Istanbul")

    CATEGORY_MAP = {
        "music": "concert",
        "concert": "concert",
        "theatre": "theatre",
        "theater": "theatre",
        "arts": "show",
        "family": "show",
        "sports": "match",
        "comedy": "standup",
        "film": "cinema",
        "festival": "festival",
        "miscellaneous": "experience",
    }

    def __init__(self) -> None:
        super().__init__("Ticketmaster", mode="http")
        self.logger = logging.getLogger(__name__)
        self.session: Optional[requests.Session] = None
        self._detail_price_calls = 0

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        if not settings.ticketmaster_enabled:
            self.logger.info("Ticketmaster: disabled by config, skipping provider")
            return []

        if not settings.ticketmaster_api_key.strip():
            self.logger.warning("Ticketmaster: API key missing, skipping provider safely")
            return []

        self._setup_session()
        try:
            events = self._fetch_all_events()
            self.logger.info("Ticketmaster: fetched raw events=%s", len(events))

            parsed: List[NormalizedEvent] = []
            skipped = 0
            for raw_event in events:
                try:
                    normalized = self._normalize_event(raw_event)
                    if normalized is not None:
                        parsed.append(normalized)
                    else:
                        skipped += 1
                except Exception as exc:
                    skipped += 1
                    self.logger.warning(
                        "Ticketmaster: skipped malformed record event_id=%s reason=%s",
                        raw_event.get("id"),
                        exc,
                    )

            self.logger.info(
                "Ticketmaster: summary pages=%s raw=%s parsed=%s skipped=%s",
                self._last_fetched_pages,
                len(events),
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
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
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

        for page in range(max(settings.ticketmaster_max_pages, 1)):
            result = self._fetch_page(page)
            if result is None:
                self.logger.warning("Ticketmaster: page fetch failed page=%s, stopping", page)
                break

            page_events = result.get("events", [])
            total_pages = result.get("total_pages")
            self._last_fetched_pages += 1

            if not page_events:
                self.logger.info("Ticketmaster: page=%s has no events, stopping", page)
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
                "Ticketmaster: page=%s fetched=%s new=%s total_unique=%s",
                page,
                len(page_events),
                new_count,
                len(events),
            )

            if new_count == 0:
                self.logger.info("Ticketmaster: duplicate-only page, stopping")
                break

            if isinstance(total_pages, int) and page + 1 >= total_pages:
                self.logger.info("Ticketmaster: reached remote last page=%s", total_pages - 1)
                break

        return events

    def _fetch_page(self, page: int) -> Optional[Dict[str, Any]]:
        if self.session is None:
            raise RuntimeError("Ticketmaster session is not initialized")

        params = {
            "apikey": settings.ticketmaster_api_key,
            "countryCode": settings.ticketmaster_country_code,
            "city": settings.ticketmaster_city,
            "size": max(settings.ticketmaster_size, 1),
            "page": max(page, 0),
            "sort": "date,asc",
            "include": "priceRanges",
        }

        last_error: Optional[str] = None
        url = f"{self.BASE_URL}{self.EVENTS_ENDPOINT}"

        for attempt in range(1, max(settings.ticketmaster_max_retries, 1) + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=max(settings.ticketmaster_timeout_seconds, 1),
                )

                if response.status_code in (401, 403):
                    self.logger.error(
                        "Ticketmaster: auth failed status=%s page=%s",
                        response.status_code,
                        page,
                    )
                    return None

                if response.status_code == 429:
                    backoff = float(attempt)
                    self.logger.warning(
                        "Ticketmaster: rate limited page=%s attempt=%s/%s backoff=%.1fs",
                        page,
                        attempt,
                        settings.ticketmaster_max_retries,
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
                last_error = f"Timeout at page={page}"
                self.logger.warning(
                    "Ticketmaster: timeout page=%s attempt=%s/%s",
                    page,
                    attempt,
                    settings.ticketmaster_max_retries,
                )
                time.sleep(float(attempt))
            except Exception as exc:
                last_error = self._safe_error(exc)
                self.logger.warning(
                    "Ticketmaster: request failed page=%s attempt=%s/%s error=%s",
                    page,
                    attempt,
                    settings.ticketmaster_max_retries,
                    last_error,
                )
                if attempt < settings.ticketmaster_max_retries:
                    time.sleep(float(attempt))

        self.logger.error("Ticketmaster: all retries failed page=%s last_error=%s", page, last_error)
        return None

    def _can_fetch_detail_price(self) -> bool:
        if not settings.ticketmaster_detail_price_enabled:
            return False
        limit = max(settings.ticketmaster_detail_price_limit, 0)
        if limit == 0:
            return False
        return self._detail_price_calls < limit

    def _fetch_event_detail(self, event_id: str) -> Optional[Dict[str, Any]]:
        if self.session is None:
            raise RuntimeError("Ticketmaster session is not initialized")

        url = f"{self.BASE_URL}events/{event_id}.json"
        params = {
            "apikey": settings.ticketmaster_api_key,
            "include": "priceRanges",
        }

        last_error: Optional[str] = None
        max_retries = max(settings.ticketmaster_detail_price_max_retries, 1)
        timeout_seconds = max(settings.ticketmaster_detail_price_timeout_seconds, 1)

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=timeout_seconds)

                if response.status_code in (401, 403):
                    self.logger.error(
                        "Ticketmaster: detail auth failed event_id=%s status=%s",
                        event_id,
                        response.status_code,
                    )
                    return None

                if response.status_code == 429:
                    backoff = float(attempt)
                    self.logger.warning(
                        "Ticketmaster: detail rate limited event_id=%s attempt=%s/%s backoff=%.1fs",
                        event_id,
                        attempt,
                        max_retries,
                        backoff,
                    )
                    time.sleep(backoff)
                    continue

                if response.status_code != 200:
                    preview = (response.text or "")[:200]
                    self.logger.warning(
                        "Ticketmaster: detail fetch failed event_id=%s status=%s body=%s",
                        event_id,
                        response.status_code,
                        preview,
                    )
                    return None

                self._detail_price_calls += 1
                payload = response.json()
                if isinstance(payload, dict):
                    return payload
                return None
            except Exception as exc:
                last_error = self._safe_error(exc)
                self.logger.warning(
                    "Ticketmaster: detail fetch failed event_id=%s attempt=%s/%s error=%s",
                    event_id,
                    attempt,
                    max_retries,
                    last_error,
                )

        self.logger.warning(
            "Ticketmaster: detail fetch exhausted event_id=%s error=%s",
            event_id,
            last_error,
        )
        return None

    @staticmethod
    def _needs_price_fallback(price: PriceInfo) -> bool:
        return price.min_value is None and price.max_value is None

    def _extract_page_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        embedded = payload.get("_embedded") or {}
        events = embedded.get("events") or []

        if not isinstance(events, list):
            events = []

        page_info = payload.get("page") or {}
        total_pages = page_info.get("totalPages")
        if not isinstance(total_pages, int):
            total_pages = None

        return {"events": events, "total_pages": total_pages}

    def _normalize_event(self, raw_event: Dict[str, Any]) -> Optional[NormalizedEvent]:
        event_id = str(raw_event.get("id") or "").strip()
        title = str(raw_event.get("name") or "").strip()
        if not event_id or not title:
            return None

        source_url = raw_event.get("url")
        if not isinstance(source_url, str) or not source_url.startswith("http"):
            return None

        occurrence = self._build_occurrence(raw_event, title, event_id, source_url)
        if occurrence is None:
            return None

        description = self._build_description(raw_event)
        image_url = self._extract_image_url(raw_event)
        event_type = self._resolve_category(raw_event)

        return NormalizedEvent(
            title=title,
            description=description,
            type=event_type,
            city_name=settings.ticketmaster_city,
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
        parsed_date = self._extract_datetime(raw_event)
        if parsed_date is None:
            self.logger.info(
                "Ticketmaster: skip event_id=%s reason=missing_or_invalid_date",
                event_id,
            )
            return None

        local_date, local_time, timezone_name = DateParser.to_local_parts(parsed_date)
        venue_name = self._extract_venue_name(raw_event)
        price = self._extract_price(raw_event)
        if self._needs_price_fallback(price) and self._can_fetch_detail_price():
            detail_payload = self._fetch_event_detail(event_id)
            if detail_payload is not None:
                detail_price = self._extract_price(detail_payload)
                if not self._needs_price_fallback(detail_price):
                    price = detail_price

        source = NormalizedSource(
            provider=self.name,
            external_id=event_id,
            title=title,
            source_url=source_url,
            price=price,
            ticket_status="on_sale",
        )

        return NormalizedOccurrence(
            start_at_utc=parsed_date,
            local_date=local_date,
            local_time=local_time,
            timezone=timezone_name,
            venue_name=venue_name,
            sources=[source],
        )

    def _extract_datetime(self, raw_event: Dict[str, Any]) -> Optional[datetime]:
        dates = raw_event.get("dates") or {}
        start = dates.get("start") or {}

        date_time = start.get("dateTime")
        if isinstance(date_time, str) and date_time.strip():
            parsed = DateParser.parse_iso_date(date_time.strip())
            if parsed is not None:
                return parsed

        local_date = start.get("localDate")
        local_time = start.get("localTime")
        if isinstance(local_date, str) and local_date.strip():
            time_part = "00:00:00"
            if isinstance(local_time, str) and local_time.strip():
                time_part = local_time.strip()
                if len(time_part) == 5:
                    time_part = f"{time_part}:00"

            try:
                naive = datetime.fromisoformat(f"{local_date.strip()}T{time_part}")
                localized = self.ISTANBUL_TZ.localize(naive)
                return localized.astimezone(pytz.UTC)
            except Exception:
                return None

        return None

    def _extract_image_url(self, raw_event: Dict[str, Any]) -> Optional[str]:
        images = raw_event.get("images") or []
        if not isinstance(images, list):
            return None

        selected: Optional[Tuple[int, str]] = None
        for image in images:
            if not isinstance(image, dict):
                continue
            url = image.get("url")
            if not isinstance(url, str) or not url.startswith("http"):
                continue
            width = image.get("width")
            score = int(width) if isinstance(width, int) else 0
            if selected is None or score > selected[0]:
                selected = (score, url)

        return selected[1] if selected else None

    def _extract_price(self, raw_event: Dict[str, Any]) -> PriceInfo:
        price_ranges = raw_event.get("priceRanges") or []
        if not isinstance(price_ranges, list) or not price_ranges:
            return PriceInfo(text="Fiyat bilgisi yok", currency="TRY")

        first = price_ranges[0] if isinstance(price_ranges[0], dict) else {}
        min_value = self._safe_float(first.get("min"))
        max_value = self._safe_float(first.get("max"))
        currency = first.get("currency") if isinstance(first.get("currency"), str) else "TRY"

        if min_value is None and max_value is None:
            return PriceInfo(text="Fiyat bilgisi yok", currency=currency)

        if min_value is None:
            min_value = max_value
        if max_value is None:
            max_value = min_value

        if min_value == 0 and max_value == 0:
            text = "Ucretsiz"
        elif min_value == max_value:
            text = f"{min_value:.2f} {currency}"
        else:
            text = f"{min_value:.2f} - {max_value:.2f} {currency}"

        return PriceInfo(
            min_value=min_value,
            max_value=max_value,
            text=text,
            currency=currency,
        )

    def _extract_venue_name(self, raw_event: Dict[str, Any]) -> str:
        embedded = raw_event.get("_embedded") or {}
        venues = embedded.get("venues") or []
        if isinstance(venues, list) and venues:
            first = venues[0] if isinstance(venues[0], dict) else {}
            name = first.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        return "Mekan bilgisi yok"

    def _build_description(self, raw_event: Dict[str, Any]) -> Optional[str]:
        description = raw_event.get("info") or raw_event.get("pleaseNote")
        if not isinstance(description, str):
            return None
        cleaned = description.strip()
        if not cleaned:
            return None
        return cleaned[:2000]

    def _resolve_category(self, raw_event: Dict[str, Any]) -> str:
        classifications = raw_event.get("classifications") or []
        if not isinstance(classifications, list):
            return "show"

        tokens: List[str] = []
        for item in classifications:
            if not isinstance(item, dict):
                continue
            for key in ["segment", "genre", "subGenre"]:
                node = item.get(key) or {}
                if isinstance(node, dict):
                    name = node.get("name")
                    if isinstance(name, str) and name.strip():
                        tokens.append(name.strip().lower())

        blob = " ".join(tokens)
        for keyword, mapped in self.CATEGORY_MAP.items():
            if keyword in blob:
                return mapped
        return "show"

    def _safe_float(self, value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            parsed = float(value)
            if parsed < 0:
                return None
            return round(parsed, 2)
        except (TypeError, ValueError):
            return None

    def _safe_error(self, exc: Exception) -> str:
        raw = f"{type(exc).__name__}: {exc}"
        key = settings.ticketmaster_api_key.strip()
        if key:
            raw = raw.replace(key, "***")
        return raw[:300]
