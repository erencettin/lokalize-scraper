"""No-op parser for inactive or unsupported sites."""

from __future__ import annotations

from typing import List

from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.parsing.base_strategy import SiteParser


class NoopStrategy(SiteParser):
    """Always return empty list and preserve detail item."""

    def parse_list(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        return []

    def parse_detail(self, html: str, item: RawEventItem, site: MunicipalSite) -> RawEventItem:
        item.title = item.title or site.name
        item.link = item.link or site.base_url
        item.venue = item.venue or site.name
        return item
