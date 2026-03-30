"""Abstract parser contract for municipal RSS sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List

from providers.municipal_rss.models import RawRssItem, RssFeedSource


class RssFeedParser(ABC):
    """Contract implemented by all municipal RSS parsers."""

    @abstractmethod
    def parse(self, raw_content: Any, source: RssFeedSource) -> List[RawRssItem]:
        """Parse source payload into raw RSS items."""
