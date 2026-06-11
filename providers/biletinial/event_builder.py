"""Builds NormalizedEvent objects from parsed Biletinial feed items."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pytz

from config import settings
from models.normalized_event import (
    NormalizedEvent,
    NormalizedOccurrence,
    NormalizedSource,
    PriceInfo,
    PriceResolution,
)
from providers.biletinial import category_map, city_map
from providers.biletinial.constants import (
    AFFILIATE_QUERY_PARAMS,
    ALLOWED_LINK_HOST,
    DESCRIPTION_MAX_LENGTH,
)
from utils.text_normalizer import strip_html

_TZ = pytz.timezone("Europe/Istanbul")


def _is_allowed_host(netloc: str) -> bool:
    host = netloc.lower().split("@")[-1].split(":")[0]
    return host == ALLOWED_LINK_HOST or host.endswith(f".{ALLOWED_LINK_HOST}")


def build_affiliate_url(link: str, affiliate_id: str) -> Optional[str]:
    """Append the required affiliate query params to a Biletinial event link.

    Returns None if the link is missing, malformed, or does not point at
    biletinial.com — such links must never be passed through as ticket URLs.
    """
    if not link:
        return None

    parts = urlsplit(link)
    if parts.scheme not in ("http", "https") or not _is_allowed_host(parts.netloc):
        return None

    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(AFFILIATE_QUERY_PARAMS)
    query["a_aid"] = affiliate_id

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _parse_start_dt(date_str: str, time_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        naive = datetime.strptime(f"{date_str} {time_str or '00:00'}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return _TZ.localize(naive)


def _parse_price(price_str: str) -> PriceInfo:
    try:
        value = float(price_str)
    except (TypeError, ValueError):
        return PriceInfo(is_unknown=True)

    if value < 0:
        return PriceInfo(is_unknown=True)

    return PriceInfo(
        min_value=value,
        max_value=value,
        currency="TRY",
        is_free=(value == 0),
        is_unknown=False,
        resolution=PriceResolution(
            strategy="provider",
            confidence=1.0,
            source="Biletinial",
            is_authoritative=True,
        ),
    )


class EventBuilder:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def build(self, item: dict, now_utc: datetime) -> Optional[NormalizedEvent]:
        title = (item.get("title") or "").strip()
        if not title:
            return None

        external_id = (item.get("id") or "").strip()
        if not external_id:
            self._logger.debug("Biletinial: skipping '%s' — missing g:id", title)
            return None

        type_id = category_map.resolve(item.get("category", ""), item.get("subcategory", ""))
        if type_id is None:
            self._logger.debug(
                "Biletinial: skipping '%s' — unmapped category '%s'/'%s'",
                title, item.get("category"), item.get("subcategory"),
            )
            return None

        city = city_map.resolve(item.get("city", ""))
        if city is None:
            self._logger.debug("Biletinial: skipping '%s' — unmapped city '%s'", title, item.get("city"))
            return None

        start_dt = _parse_start_dt(item.get("date", ""), item.get("time", ""))
        if start_dt is None:
            self._logger.debug("Biletinial: skipping '%s' — invalid date/time", title)
            return None

        start_utc = start_dt.astimezone(pytz.UTC)
        if start_utc < now_utc:
            return None

        link = (item.get("link") or "").strip()
        affiliate_url = build_affiliate_url(link, settings.biletinial_affiliate_id)
        if affiliate_url is None:
            self._logger.debug("Biletinial: skipping '%s' — link not on %s (%s)", title, ALLOWED_LINK_HOST, link)
            return None

        description = strip_html(item.get("description") or "")
        if description and description.casefold().startswith(title.casefold()):
            description = description[len(title):].lstrip(" \t-–—:.")
        description = description[:DESCRIPTION_MAX_LENGTH] or None
        venue_name = (item.get("venue_name") or "").strip() or title
        image_url = (item.get("image_link") or "").strip() or None
        price = _parse_price(item.get("price", ""))

        source = NormalizedSource(
            provider="Biletinial",
            external_id=external_id,
            title=title,
            description=description,
            source_url=link,
            ticket_url=affiliate_url,
            price=price,
            ticket_status="on_sale",
            brand_name="Biletinial",
            is_official_seller=True,
        )

        occurrence = NormalizedOccurrence(
            start_at_utc=start_utc,
            local_date=start_dt.strftime("%Y-%m-%d"),
            local_time=start_dt.strftime("%H:%M"),
            timezone="Europe/Istanbul",
            venue_name=venue_name,
            sources=[source],
        )

        return NormalizedEvent(
            title=title,
            description=description,
            type=type_id,
            category=type_id,
            city_name=city,
            image_url=image_url,
            occurrences=[occurrence],
            source="Biletinial",
            providers=["Biletinial"],
            provider_label="Biletinial",
            external_id=external_id,
            venue=venue_name,
        )
