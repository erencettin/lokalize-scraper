"""Bilet.com Affiliate API provider."""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from config import settings
from models.normalized_event import NormalizedEvent
from providers.base_provider import BaseProvider
from providers.biletcom.constants import DEFAULT_DETAIL_WORKERS, DETAIL_REQUEST_DELAY_SECONDS
from providers.biletcom.event_builder import EventBuilder
from providers.biletcom.http_client import BiletcomHttpClient
from providers.biletcom.models import (
    BiletcomActivity,
    BiletcomListing,
    BiletcomOption,
    BiletcomOptionDates,
    BiletcomPrice,
    BiletcomVenue,
)


def _parse_listing(raw: Dict[str, Any]) -> Optional[BiletcomListing]:
    try:
        return BiletcomListing(
            id=int(raw["id"]),
            name=(raw.get("name") or "").strip(),
            slug=(raw.get("slug") or "").strip(),
            description=raw.get("description"),
            min_price=_safe_float(raw.get("min_price")),
            max_price=_safe_float(raw.get("max_price")),
        )
    except (KeyError, ValueError, TypeError):
        return None


def _parse_venue(raw: Optional[Dict[str, Any]]) -> Optional[BiletcomVenue]:
    if not isinstance(raw, dict):
        return None
    try:
        return BiletcomVenue(
            id=int(raw.get("id", 0)),
            name=(raw.get("name") or "").strip(),
            address=raw.get("address"),
            city=raw.get("city"),
            country=raw.get("country"),
            latitude=raw.get("latitude"),
            longitude=raw.get("longitude"),
        )
    except (ValueError, TypeError):
        return None


def _parse_prices(raw_list: Any) -> List[BiletcomPrice]:
    if not isinstance(raw_list, list):
        return []
    prices: List[BiletcomPrice] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        try:
            prices.append(BiletcomPrice(
                id=int(item.get("id", 0)),
                label=(item.get("label") or "").strip(),
                type=(item.get("type") or "person"),
                amount=float(item.get("amount", 0)),
                currency=(item.get("currency") or "TRY").upper(),
            ))
        except (ValueError, TypeError):
            continue
    return prices


def _parse_option(raw: Dict[str, Any]) -> Optional[BiletcomOption]:
    if not isinstance(raw, dict):
        return None
    try:
        raw_dates = raw.get("dates") or {}
        dates = BiletcomOptionDates(
            single_date=raw_dates.get("single_date"),
            start_date=raw_dates.get("start_date"),
            end_date=raw_dates.get("end_date"),
            sale_start_date=raw_dates.get("sale_start_date"),
            sale_end_date=raw_dates.get("sale_end_date"),
        )
        return BiletcomOption(
            id=int(raw.get("id", 0)),
            name=(raw.get("name") or "").strip(),
            is_date_selectable=bool(raw.get("is_date_selectable", False)),
            is_hour_selectable=bool(raw.get("is_hour_selectable", False)),
            dates=dates,
            venue=_parse_venue(raw.get("venue")),
            prices=_parse_prices(raw.get("prices")),
        )
    except (ValueError, TypeError):
        return None


def _parse_activity(detail: Dict[str, Any]) -> Optional[BiletcomActivity]:
    raw = detail.get("activity")
    if not isinstance(raw, dict):
        return None
    try:
        photos = raw.get("photos") or []
        if not isinstance(photos, list):
            photos = []
        categories = raw.get("categories") or []
        if not isinstance(categories, list):
            categories = []
        return BiletcomActivity(
            id=int(raw.get("id", detail.get("id", 0))),
            name=(raw.get("name") or "").strip(),
            slug=(raw.get("slug") or "").strip(),
            description=raw.get("description"),
            details=raw.get("details"),
            url=raw.get("url"),
            affiliate_url=raw.get("affiliate_url"),
            logo=raw.get("logo"),
            photos=[p for p in photos if isinstance(p, str)],
            categories=[c for c in categories if isinstance(c, str)],
            min_price=_safe_float(raw.get("min_price")),
            max_price=_safe_float(raw.get("max_price")),
        )
    except (ValueError, TypeError):
        return None


def _parse_options(detail: Dict[str, Any]) -> List[BiletcomOption]:
    raw_options = detail.get("options") or []
    if not isinstance(raw_options, list):
        return []
    options: List[BiletcomOption] = []
    for raw in raw_options:
        opt = _parse_option(raw)
        if opt:
            options.append(opt)
    return options


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None


class BiletcomProvider(BaseProvider):
    """Fetches activities from Bilet.com Affiliate API and maps them to NormalizedEvent."""

    def __init__(self) -> None:
        super().__init__("bilet.com", mode="http")
        self._logger = logging.getLogger(__name__)
        self._http = BiletcomHttpClient()
        self._builder = EventBuilder()

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        if not settings.biletcom_enabled:
            self._logger.info("bilet.com: disabled by config, skipping")
            return []
        if not settings.biletcom_client_id.strip() or not settings.biletcom_client_secret.strip():
            self._logger.warning("bilet.com: credentials missing, skipping")
            return []

        self._http.setup_session()
        try:
            return self._run()
        finally:
            self._http.close_session()

    def _run(self) -> List[NormalizedEvent]:
        # Authenticate eagerly so all threads reuse the cached token.
        token = self._http.get_token()
        if not token:
            self._logger.error("bilet.com: cannot obtain token, aborting")
            return []

        raw_listings = self._http.fetch_listing()
        if not raw_listings:
            self._logger.warning("bilet.com: empty listing response")
            return []

        listings: List[BiletcomListing] = []
        for raw in raw_listings:
            listing = _parse_listing(raw)
            if listing and listing.name:
                listings.append(listing)

        self._logger.info("bilet.com: %d listings to detail-fetch", len(listings))

        workers = max(1, getattr(settings, "biletcom_detail_workers", DEFAULT_DETAIL_WORKERS))
        events: List[NormalizedEvent] = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._fetch_and_build, listing): listing
                for listing in listings
            }
            for future in as_completed(futures):
                listing = futures[future]
                try:
                    event = future.result()
                    if event:
                        events.append(event)
                except Exception as exc:
                    self._logger.debug(
                        "bilet.com: skipping id=%d name=%r reason=%s",
                        listing.id, listing.name, exc,
                    )

        self._logger.info(
            "bilet.com: parsed %d events from %d listings",
            len(events), len(listings),
        )
        return events

    def _fetch_and_build(self, listing: BiletcomListing) -> Optional[NormalizedEvent]:
        """Fetch detail for one listing and build a NormalizedEvent. Thread-safe."""
        time.sleep(DETAIL_REQUEST_DELAY_SECONDS)
        detail = self._http.fetch_activity_detail(listing.id)
        if not detail:
            self._logger.debug("bilet.com: no detail for id=%d", listing.id)
            return None

        activity = _parse_activity(detail)
        if not activity:
            self._logger.debug("bilet.com: cannot parse activity for id=%d", listing.id)
            return None

        options = _parse_options(detail)
        return self._builder.build(listing, activity, options)
