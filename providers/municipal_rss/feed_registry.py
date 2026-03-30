"""Feed registry and source routing for municipal RSS provider."""

from __future__ import annotations

from typing import List
from urllib.parse import urlparse

from config import settings
from providers.municipal_rss.constants import (
    PARSER_ATATURK_KITAPLIGI,
    PARSER_KULTURSANAT,
    PARSER_RSS_XML,
    PARSER_WORDPRESS,
    WP_EVENT_PER_PAGE,
    WP_POST_PER_PAGE,
)
from providers.municipal_rss.models import RssFeedSource


class FeedRegistry:
    """Convert configured feed URLs into typed source definitions."""

    def get_sources(self) -> List[RssFeedSource]:
        return [self._build_source(url) for url in self._configured_urls()]

    def _configured_urls(self) -> List[str]:
        raw = settings.municipal_rss_urls.strip()
        if not raw:
            return []
        values = [item.strip() for item in raw.split(",")]
        return [value for value in values if value.startswith("http")]

    def _build_source(self, url: str) -> RssFeedSource:
        host = (urlparse(url).hostname or "").lower()
        if "kultur.istanbul" in host:
            return RssFeedSource("kultur.istanbul", f"https://kultur.istanbul/wp-json/wp/v2/event_listing?per_page={WP_EVENT_PER_PAGE}", PARSER_WORDPRESS, fallback_url=f"https://kultur.istanbul/wp-json/wp/v2/posts?per_page={WP_POST_PER_PAGE}")
        if "orkestralar.ibb.istanbul" in host:
            return RssFeedSource("orkestralar.ibb.istanbul", f"https://orkestralar.ibb.istanbul/wp-json/wp/v2/posts?per_page={WP_POST_PER_PAGE}&categories=1", PARSER_WORDPRESS)
        if "kultursanat.istanbul" in host:
            return RssFeedSource(host, url, PARSER_KULTURSANAT)
        if "ataturkkitapligi.ibb.gov.tr" in host:
            return RssFeedSource(host, url, PARSER_ATATURK_KITAPLIGI)
        return RssFeedSource(host or url, url, PARSER_RSS_XML)
