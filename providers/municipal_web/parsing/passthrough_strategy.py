"""Pass-through parser for pre-enriched list items."""

from __future__ import annotations

from typing import List

from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.parsing.base_strategy import SiteParser


class PassthroughStrategy(SiteParser):
    """Return pre-populated list item values without detail enrichment."""

    def parse_list(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        return []

    def parse_detail(self, html: str, item: RawEventItem, site: MunicipalSite) -> RawEventItem:
        item.link = item.link or site.base_url
        item.venue = item.venue or site.name
        return item
