"""Build normalized events from raw municipal parser items."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Optional, Set

import pytz

from config import settings
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo
from providers.municipal_web.constants import CATEGORY_MAP, EXTERNAL_ID_HASH_LENGTH, GENERIC_TITLE_WORDS, ISTANBUL_TIMEZONE, MAX_DESCRIPTION_LENGTH, TURKISH_MONTHS
from providers.municipal_web.models import MunicipalSite, RawEventItem
from utils.date_parser import DateParser
from utils.html_extractor import extract_jsonld_price, extract_meta_price
from utils.price_parser import PriceParser
from utils.text_normalizer import clean_text


class EventBuilder:
    """Converts raw municipal events into the shared NormalizedEvent contract."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._istanbul_tz = pytz.timezone(ISTANBUL_TIMEZONE)
        self._price_pattern = re.compile(
            r"(?:ucretsiz|ücretsiz|free|bedava|"
            r"₺\s*\d[\d.,]*(?:\s*-\s*₺?\s*\d[\d.,]*)?|"
            r"\d[\d.,]*(?:\s*-\s*\d[\d.,]*)?\s*(?:tl|try|₺)|"
            r"(?:fiyat|bilet).{0,40}?\b\d[\d.,]*(?:\s*-\s*\d[\d.,]*)?\b)",
            re.IGNORECASE,
        )

    def build(self, item: RawEventItem, site: MunicipalSite) -> Optional[NormalizedEvent]:
        title = clean_text(item.title)
        link = clean_text(item.link)
        if not self._is_valid(title, link, item, site):
            return None
        description = clean_text(item.description or title)
        start_at_utc = self._parse_datetime(item.date, item.time, description)
        if start_at_utc is None:
            return None
        price = self._build_price(item, site)

        if not hasattr(self, "_logged_sites"):
            self._logged_sites = set()
        
        if site.name not in self._logged_sites:
            self._logged_sites.add(site.name)
            if "uskudar" in site.name.lower() or "üsküdar" in site.name.lower():
                html_snippet = (getattr(item, "_raw_html", None) or item.description or "")[:300]
                print(f"[USKUDAR_HTML] {html_snippet}", flush=True)
            
            print(
                f"[WEB_PRICE_DEBUG] site={site.name} "
                f"is_free={price.is_free} "
                f"min={price.min_value} "
                f"text={getattr(item, 'price_text', None)} "
                f"confidence={price.confidence}",
                flush=True
            )

        occurrence = self._build_occurrence(start_at_utc, title, link, clean_text(item.venue or site.name), price)
        return NormalizedEvent(
            title=title,
            description=self._truncate(description),
            type=self._resolve_type(f"{title} {description}"),
            city_name=settings.municipal_web_city_name.strip() or "Istanbul",
            image_url=clean_text(item.image_url) or None,
            occurrences=[occurrence],
        )

    def _is_valid(self, title: str, link: str, item: RawEventItem, site: MunicipalSite) -> bool:
        if not title or not link:
            return False
        title_lower = title.lower()
        site_name = clean_text(site.name).lower()
        venue = clean_text(item.venue).lower()
        if title_lower == site_name:
            return False
        if venue and title_lower == venue:
            return False
        return not self._is_structural_title(title_lower, site_name, venue)

    def _is_structural_title(self, title: str, site_name: str, venue: str) -> bool:
        return self._matches_generic_structure(title, site_name) or self._matches_generic_structure(title, venue)

    def _matches_generic_structure(self, title: str, phrase: str) -> bool:
        if not phrase or phrase not in title:
            return False
        remainder_words = self._remainder_words(title, phrase)
        return not remainder_words or remainder_words.issubset(GENERIC_TITLE_WORDS)

    def _remainder_words(self, title: str, phrase: str) -> Set[str]:
        remainder = clean_text(title.replace(phrase, " "))
        return set(re.findall(r"[a-zçğıöşü]+", remainder.lower()))

    def _build_source(self, title: str, link: str, price: PriceInfo) -> NormalizedSource:
        return NormalizedSource(
            provider="MunicipalWeb",
            external_id=self._build_external_id(link),
            title=title,
            source_url=link,
            price=price,
            ticket_status="unknown",
        )

    def _build_occurrence(
        self,
        start_at_utc: datetime,
        title: str,
        link: str,
        venue_name: str,
        price: PriceInfo,
    ) -> NormalizedOccurrence:
        local_date, local_time, timezone_name = DateParser.to_local_parts(start_at_utc, ISTANBUL_TIMEZONE)
        return NormalizedOccurrence(
            start_at_utc=start_at_utc,
            local_date=local_date,
            local_time=local_time,
            timezone=timezone_name,
            venue_name=venue_name,
            sources=[self._build_source(title, link, price)],
        )

    def _build_price(self, item: RawEventItem, site: MunicipalSite) -> PriceInfo:
        candidates = self._extract_price_candidates(item)
        return PriceParser.resolve_from_text_candidates(
            candidates=candidates,
            currency="TRY",
            source=f"municipal_web:{clean_text(site.base_url) or site.name}",
            legal_mode="public_web_text",
            strategy="municipal_web_text_scan",
            confidence=0.55,
            is_authoritative=False,
            is_derived=True,
            note="Public web page text parsing. Verify terms/robots per domain.",
            requires_terms_review=True,
        )

    def _extract_price_candidates(self, item: RawEventItem) -> list[str]:
        """Build a list of price string candidates from richest to plainest source.

        Order of precedence (highest confidence first):
        1. JSON-LD Event schema  (structured, most reliable)
        2. HTML meta tags        (semi-structured)
        3. Regex on description  (free text, least reliable)
        4. Regex on title        (last resort)
        """
        candidates: list[str] = []

        # --- 0. JSON cost/price (Highest priority from parser) ---
        if item.price_text:
            candidates.append(item.price_text)

        # --- 1. JSON-LD ---
        html_for_structured = getattr(item, "_raw_html", None) or item.description
        if html_for_structured:
            jsonld = extract_jsonld_price(html_for_structured)
            if jsonld:
                min_val = jsonld.get("min")
                max_val = jsonld.get("max")
                currency = str(jsonld.get("currency") or "TRY")
                if min_val is not None:
                    symbol = "₺" if currency.upper() == "TRY" else currency
                    if max_val and max_val != min_val:
                        candidates.append(f"{min_val:.0f}-{max_val:.0f} {symbol}")
                    else:
                        candidates.append(f"{min_val:.0f} {symbol}")

        # --- 2. Meta tag ---
        if html_for_structured:
            meta_price = extract_meta_price(html_for_structured)
            if meta_price:
                candidates.append(meta_price)

        # --- 3 & 4. Regex on description + title ---
        for text in (item.description, item.title):
            cleaned = clean_text(text)
            if not cleaned:
                continue
            matches = self._price_pattern.findall(cleaned)
            if matches:
                candidates.extend(clean_text(m) for m in matches if clean_text(m))

        return candidates

    def _truncate(self, value: str) -> str:
        return value if len(value) <= MAX_DESCRIPTION_LENGTH else f"{value[:MAX_DESCRIPTION_LENGTH].rstrip()}..."

    def _resolve_type(self, text: str) -> str:
        lowered = clean_text(text).lower()
        for key, mapped in CATEGORY_MAP.items():
            if key in lowered:
                return mapped
        return "experience"

    def _build_external_id(self, link: str) -> str:
        digest = hashlib.sha256(link.encode("utf-8")).hexdigest()[:EXTERNAL_ID_HASH_LENGTH]
        return f"web-{digest}"

    def _parse_datetime(self, date_text: str, time_text: str, fallback_text: str) -> Optional[datetime]:
        combined = " ".join(part for part in [clean_text(date_text), clean_text(time_text)] if part)
        return self._extract_datetime_from_text(combined) or self._extract_datetime_from_text(fallback_text)

    def _extract_datetime_from_text(self, text: str) -> Optional[datetime]:
        normalized = clean_text(text).lower()
        if not normalized:
            return None

        date_match = re.search(r"(\d{1,2})\s+([a-zçğıöşü]+)[, ]+\s*(\d{4})", normalized)
        if date_match:
            day, month_key, year = int(date_match.group(1)), date_match.group(2), int(date_match.group(3))
            month = TURKISH_MONTHS.get(month_key)
            if month:
                return self._local_datetime(year, month, day, *self._extract_time(normalized, date_match.end()))

        dotted = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", normalized)
        if dotted:
            day, month, year = int(dotted.group(1)), int(dotted.group(2)), int(dotted.group(3))
            return self._local_datetime(year, month, day, *self._extract_time(normalized, dotted.end()))
        return None

    def _extract_time(self, text: str, start_index: int = 0) -> tuple[int, int]:
        search_area = text[start_index:] if start_index > 0 else text
        match = re.search(r"(?:^|\D)(\d{1,2})[:\.](\d{2})(?:\D|$)", search_area)
        if not match:
            return (0, 0)
        hour, minute = int(match.group(1)), int(match.group(2))
        return (hour, minute) if 0 <= hour <= 23 and 0 <= minute <= 59 else (0, 0)

    def _local_datetime(self, year: int, month: int, day: int, hour: int, minute: int) -> Optional[datetime]:
        try:
            return self._istanbul_tz.localize(datetime(year, month, day, hour, minute)).astimezone(pytz.UTC)
        except Exception as exc:
            self._logger.warning(
                "MunicipalWeb: datetime parse failed year=%s month=%s day=%s hour=%s minute=%s reason=%s",
                year,
                month,
                day,
                hour,
                minute,
                exc,
            )
            return None
