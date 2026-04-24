"""Data contracts for municipal RSS ingestion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RawRssItem:
    """Intermediate payload parsed from RSS/API sources."""

    title: str = ""
    link: str = ""
    description: str = ""
    pub_date: str = ""
    event_date: str = ""
    venue: str = ""
    category: str = ""
    image_url: str = ""
    price_text: str = ""


@dataclass(frozen=True)
class RssFeedSource:
    """Registry model for a configured municipal RSS/API source."""

    name: str
    url: str
    parser_type: str
    fallback_url: str = ""
