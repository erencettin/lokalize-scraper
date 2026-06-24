from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional

import pytz

from clients.serpapi_client import SerpApiClient
from config import build_serpapi_events_queries, settings
from models.normalized_event import (
    NormalizedEvent,
    NormalizedOccurrence,
    NormalizedSource,
    PriceInfo,
)
from utils.date_parser import DateParser
from utils.performer_extractor import extract_performer_from_title
from utils.price_parser import PriceParser
from utils.text_normalizer import clean_text

_ISTANBUL_TZ = pytz.timezone("Europe/Istanbul")


class SerpApiEventsProvider:
    def __init__(self, serpapi_client: Optional[SerpApiClient] = None) -> None:
        self._logger = logging.getLogger(__name__)
        self._client = serpapi_client or SerpApiClient()

    @property
    def request_count(self) -> int:
        return self._client.request_count

    def fetch_events(self, city: Optional[str] = None) -> List[NormalizedEvent]:
        if not self._client.is_enabled:
            self._logger.warning("SerpApiEventsProvider: SERPAPI_API_KEY missing, provider is skipped.")
            return []

        resolved_city = (city or settings.serpapi_city).strip()
        location_hint = self._build_location_hint(resolved_city)
        now = datetime.now(timezone.utc)
        events: List[NormalizedEvent] = []
        dedup_keys: set[str] = set()

        for query in build_serpapi_events_queries(resolved_city):
            payload = self._client.search(
                engine="google_events",
                query=query["q"],
                location=location_hint,
                hl="en",
                gl="us",
            )
            payload_error = payload.get("error")
            if isinstance(payload_error, str) and payload_error.strip():
                self._logger.warning(
                    "SerpApiEventsProvider: query failed city=%s query=%s error=%s",
                    resolved_city,
                    query["q"],
                    payload_error,
                )
                continue
            event_results = payload.get("events_results")
            if not isinstance(event_results, list):
                self._logger.info(
                    "SerpApiEventsProvider: no events_results city=%s query=%s keys=%s",
                    resolved_city,
                    query["q"],
                    ",".join(sorted(payload.keys())),
                )
                continue



            for raw in event_results:
                if not isinstance(raw, dict):
                    continue
                event = self._map_event(
                    raw=raw,
                    category=query["category"],
                    city=resolved_city,
                    fetched_at=now,
                )
                if event is None:
                    continue
                dedup_key = f"{event.external_id}|{event.city_name}".lower()
                if dedup_key in dedup_keys:
                    continue
                dedup_keys.add(dedup_key)
                events.append(event)

        self._logger.info(
            "SerpApiEventsProvider: fetched=%s city=%s requests=%s",
            len(events),
            resolved_city,
            self.request_count,
        )
        return events

    def _map_event(
        self,
        *,
        raw: dict,
        category: str,
        city: str,
        fetched_at: datetime,
    ) -> Optional[NormalizedEvent]:
        self._logger.info("SerpAPI Raw Event (category=%s): %s", category, raw)
        title = clean_text(str(raw.get("title") or ""))
        if not title:
            return None

        link = self._clean_optional(raw.get("link")) or "https://www.google.com"
        date_payload = raw.get("date") if isinstance(raw.get("date"), dict) else {}
        event_start_at = self._parse_event_start(date_payload, fallback=fetched_at)
        local_date, local_time, tz_name = DateParser.to_local_parts(event_start_at, "Europe/Istanbul")
        venue = self._extract_venue(raw)
        address = self._extract_address(raw)
        ticket_info = self._extract_ticket_info(raw)
        price = self._extract_price(raw, ticket_info)
        external_id = (
            self._clean_optional(raw.get("event_id"))
            or self._clean_optional(raw.get("id"))
            or self._build_fallback_id(title=title, link=link, city=city)
        )

        source = NormalizedSource(
            provider="serpapi_google_events",
            external_id=external_id,
            title=title,
            source_url=link,
            ticket_url=self._extract_ticket_url(raw),
            price=price,
            ticket_status="unknown",
        )

        occurrence = NormalizedOccurrence(
            start_at_utc=event_start_at,
            local_date=local_date,
            local_time=local_time,
            timezone=tz_name,
            venue_name=venue or "Belirtilmedi",
            district=None,
            sources=[source],
        )

        description = self._clean_optional(raw.get("description"))
        event_type = self._infer_type_from_content(title, description, category)
        return NormalizedEvent(
            title=title,
            description=description,
            type=event_type,
            city_name=city,
            occurrences=[occurrence],
            source="serpapi_google_events",
            external_id=external_id,
            category=category,
            address=address,
            venue=venue,
            link=link,
            ticket_info=ticket_info,
            thumbnail_url=self._clean_optional(raw.get("thumbnail")),
            fetched_at=fetched_at,
            source_url=link,
            performer_name=extract_performer_from_title(title, event_type),
        )

    # Keywords that confirm an event is genuinely a sport event (not a concert at a sports venue)
    _SPORT_TITLE_KEYWORDS = (
        "maç", "futbol", "basketbol", "voleybol", "tenis", "formula",
        "mma", "boks", " lig", "derbi", "esport", "maraton", "marathon",
        "kupa", "turnuva", "playoff", "championship", " vs ",
    )

    def _infer_type_from_content(self, title: str, description: Optional[str], query_category: str) -> str:
        """Infer event type from title/description signals, falling back to query category.

        Prevents events from being mis-categorised when they appear in a query result
        for a different category (e.g. a concert at a sports venue in a sports query).
        Order matters: more specific signals are checked first.
        """
        content = (title + " " + (description or "")).lower()
        lower_title = title.lower()

        _SIGNALS: list[tuple[str, list[str]]] = [
            ("standup",    ["stand up", "stand-up", "standup", "komedi show"]),
            ("concert",    ["konser", "concert", " tour", "canlı müzik", "canli muzik",
                            "gig", "live müzik", "live performance", "tickets for"]),
            ("theatre",    ["tiyatro", "müzikal", "opera ", "opera'", "bale "]),
            ("cinema",     ["sinema", "film göster", "belgesel göster", "özel gösterim"]),
            ("exhibition", ["sergi ", "sergisin", "sanat galerisi", "fotoğraf sergisi"]),
            ("festival",   ["festival", " fest "]),
            ("workshop",   ["workshop", "atölye", "masterclass", "bootcamp"]),
            ("kids",       ["çocuk etkinlik", "aile etkinlik", "çocuklar için"]),
            # "match" only when genuine sport keywords are present — venue name alone is not enough
            ("match",      ["maç", "futbol maç", "basketbol maç", "voleybol maç",
                            "lig maçı", "deplasman", " vs ", "karşılaşması",
                            "playoff", "derbi maç"]),
        ]

        for event_type, keywords in _SIGNALS:
            if any(k in content for k in keywords):
                return event_type

        # Query-category fallback — refuse "match" unless title confirms it's a sport event.
        # This prevents concerts at sports arenas (e.g. Manifest at Ülker Sports Arena)
        # from being stored as sports events.
        mapped = self._map_type(query_category)
        if mapped == "match" and not any(kw in lower_title for kw in self._SPORT_TITLE_KEYWORDS):
            return "festival"
        return mapped

    @staticmethod
    def _map_type(category: str) -> str:
        mapping = {
            "concert":    "concert",
            "theater":    "theatre",
            "cinema":     "cinema",
            "art":        "exhibition",
            "standup":    "standup",
            "festival":   "festival",
            "sports":     "match",
            "workshop":   "workshop",
            "experience": "festival",
            "family":     "kids",
        }
        return mapping.get(category, "festival")

    def _parse_event_start(self, payload: dict, fallback: datetime) -> datetime:
        start_date = self._clean_optional(payload.get("start_date"))
        when_text = self._clean_optional(payload.get("when"))
        candidate = when_text or start_date
        if not candidate:
            return fallback

        english_text_match = re.search(
            r"(?:[A-Za-z]{3},\s*)?([A-Za-z]{3})\s+(\d{1,2})(?:,\s*(\d{1,2}:\d{2})\s*(AM|PM))?",
            candidate,
        )
        if english_text_match:
            month_abbr, day_text, time_text, ampm = english_text_match.groups()
            month = self._english_month(month_abbr)
            if month is not None:
                day = int(day_text)
                hour = 20
                minute = 0
                if time_text and ampm:
                    hour_text, minute_text = time_text.split(":")
                    hour = int(hour_text)
                    minute = int(minute_text)
                    if ampm.upper() == "PM" and hour != 12:
                        hour += 12
                    if ampm.upper() == "AM" and hour == 12:
                        hour = 0

                fallback_local = fallback.astimezone(_ISTANBUL_TZ)
                year = fallback_local.year
                try:
                    local_dt = _ISTANBUL_TZ.localize(
                        datetime(year, month, day, hour, minute, 0)
                    )
                except ValueError:
                    return fallback

                # If parsed date is far in the past relative to run date, roll to next year.
                if local_dt < fallback_local and (fallback_local - local_dt).days > 30:
                    local_dt = _ISTANBUL_TZ.localize(
                        datetime(year + 1, month, day, hour, minute, 0)
                    )
                return local_dt.astimezone(timezone.utc)

        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
            year, month, day = candidate.split("-")
            local_dt = _ISTANBUL_TZ.localize(
                datetime(int(year), int(month), int(day), 20, 0, 0)
            )
            return local_dt.astimezone(timezone.utc)

        parsed = DateParser.parse_iso_date(candidate)
        if parsed is not None:
            return parsed

        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", candidate)
        if match:
            year, month, day = match.groups()
            local_dt = _ISTANBUL_TZ.localize(
                datetime(int(year), int(month), int(day), 20, 0, 0)
            )
            return local_dt.astimezone(timezone.utc)

        return fallback

    def _extract_address(self, raw: dict) -> Optional[str]:
        address = raw.get("address")
        if isinstance(address, list):
            values = [clean_text(str(item)) for item in address if clean_text(str(item))]
            return ", ".join(values) if values else None
        return self._clean_optional(address)

    def _extract_venue(self, raw: dict) -> Optional[str]:
        venue = raw.get("venue")
        if isinstance(venue, dict):
            return self._clean_optional(venue.get("name"))
        return self._clean_optional(venue)

    def _extract_ticket_info(self, raw: dict) -> Optional[str]:
        ticket_info = raw.get("ticket_info")
        if isinstance(ticket_info, list) and ticket_info and isinstance(ticket_info[0], dict):
            chunks = []
            for item in ticket_info:
                if not isinstance(item, dict):
                    continue
                source = self._clean_optional(item.get("source"))
                price = self._clean_optional(item.get("price")) or self._clean_optional(item.get("ticket_price"))
                link_type = self._clean_optional(item.get("link_type"))
                if source and price:
                    chunks.append(f"{source} - {price}")
                elif source and link_type:
                    chunks.append(f"{source} ({link_type})")
                elif source:
                    chunks.append(source)
            return " | ".join(chunks) if chunks else None
        if isinstance(ticket_info, list):
            chunks = []
            for item in ticket_info:
                if not isinstance(item, list):
                    continue
                parts = [clean_text(str(piece)) for piece in item if clean_text(str(piece))]
                if parts:
                    chunks.append(" - ".join(parts))
            return " | ".join(chunks) if chunks else None
        return self._clean_optional(ticket_info)

    def _extract_ticket_url(self, raw: dict) -> Optional[str]:
        ticket_info = raw.get("ticket_info")
        if not isinstance(ticket_info, list):
            return None
        candidates = []
        for item in ticket_info:
            if not isinstance(item, dict):
                continue
            if str(item.get("link_type")).lower() == "tickets":
                source = self._clean_optional(item.get("source")) or "Bilinmeyen Sağlayıcı"
                link = self._clean_optional(item.get("link"))
                if link:
                    candidates.append((source, link))
        if not candidates:
            return None
        for source, link in candidates:
            if "biletix" in source.lower():
                return f"{source}|{link}"
        return f"{candidates[0][0]}|{candidates[0][1]}"

    def _extract_price(self, raw: dict, ticket_info_text: Optional[str]) -> PriceInfo:
        extracted_price = self._safe_float(raw.get("extracted_price"))
        if extracted_price is not None:
            return PriceParser.resolve_structured_range(
                min_value=extracted_price,
                max_value=extracted_price,
                currency=self._clean_optional(raw.get("currency")) or "TRY",
                source="serpapi_google_events_api",
                legal_mode="search_indexed_api",
                strategy="serpapi_extracted_price",
                confidence=0.8,
                is_authoritative=False,
                is_derived=True,
            )

        price_text = self._clean_optional(raw.get("price"))
        if price_text:
            resolved = PriceParser.resolve_text_price(
                price_text=price_text,
                currency=self._clean_optional(raw.get("currency")) or "TRY",
                source="serpapi_google_events_api",
                legal_mode="search_indexed_api",
                strategy="serpapi_price_text",
                confidence=0.74,
                is_authoritative=False,
                is_derived=True,
                note="Search-indexed price; verify with ticketing provider before purchase.",
            )
            if not resolved.is_unknown:
                return resolved

        ticket_price_candidates = self._extract_ticket_price_candidates(raw)
        if ticket_info_text:
            ticket_price_candidates.append(ticket_info_text)

        # P1 Debug: log raw ticket_info structure to diagnose missing prices
        raw_ticket_info = raw.get("ticket_info")
        if raw_ticket_info and not ticket_price_candidates:
            self._logger.debug(
                "SerpAPI: ticket_info has no price candidates title='%s' ticket_info=%s",
                raw.get("title", "?"),
                str(raw_ticket_info)[:200],
            )

        return PriceParser.resolve_from_text_candidates(
            candidates=ticket_price_candidates,
            currency=self._clean_optional(raw.get("currency")) or "TRY",
            source="serpapi_google_events_ticket_info",
            legal_mode="search_indexed_api",
            strategy="serpapi_ticket_info_scan",
            confidence=0.68,
            is_authoritative=False,
            is_derived=True,
            note="Search-indexed ticket info. Prefer direct provider API when available.",
        )

    def _extract_ticket_price_candidates(self, raw: dict) -> List[str]:
        candidates: List[str] = []
        ticket_info = raw.get("ticket_info")
        if not isinstance(ticket_info, list):
            return candidates
        for item in ticket_info:
            if isinstance(item, dict):
                for key in ("price", "ticket_price", "display_price"):
                    value = self._clean_optional(item.get(key))
                    if value:
                        candidates.append(value)
            elif isinstance(item, list):
                parts = [self._clean_optional(piece) for piece in item]
                for part in parts:
                    if part:
                        candidates.append(part)
            else:
                value = self._clean_optional(item)
                if value:
                    candidates.append(value)
        return candidates

    @staticmethod
    def _safe_float(value: object) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(str(value))
        except (TypeError, ValueError):
            return None

    def _build_fallback_id(self, *, title: str, link: str, city: str) -> str:
        text = f"{title}|{link}|{city}".lower()
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
        return f"serpapi-event-{digest[:20]}"

    @staticmethod
    def _build_location_hint(city: str) -> str:
        normalized = city.strip()
        lowered = normalized.lower()
        if "turkey" in lowered or "türkiye" in lowered:
            return normalized
        return f"{normalized}, Turkey"

    @staticmethod
    def _english_month(value: str) -> Optional[int]:
        mapping = {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
        }
        return mapping.get(value.lower())

    @staticmethod
    def _clean_optional(value: object) -> Optional[str]:
        if value is None:
            return None
        text = clean_text(str(value))
        return text or None
