"""Parsing strategy contract for municipal sites."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from providers.municipal_web.models import MunicipalSite, RawEventItem


class SiteParser(ABC):
    """Contract implemented by all municipal site parsers."""

    @abstractmethod
    def parse_list(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        """Parse list page payload and return candidate event items."""

    @abstractmethod
    def parse_detail(self, html: str, item: RawEventItem, site: MunicipalSite) -> RawEventItem:
        """Enrich item using detail page payload."""
