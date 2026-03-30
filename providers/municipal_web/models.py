"""Data contracts for municipal web scraping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from providers.municipal_web.parsing.base_strategy import SiteParser


@dataclass
class RawEventItem:
    """Intermediate event payload used between parser and event builder."""

    title: str = ""
    link: str = ""
    venue: str = ""
    date: str = ""
    time: str = ""
    description: str = ""
    image_url: str = ""


@dataclass(frozen=True)
class MunicipalSite:
    """Registry model for each municipal website source."""

    name: str
    base_url: str
    list_urls: List[str]
    parser: "SiteParser"
    requires_detail: bool = True
    city_name: Optional[str] = None
