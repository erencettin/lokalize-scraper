"""Parser for standard RSS/XML feeds."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import List, Optional

from providers.municipal_rss.models import RawRssItem, RssFeedSource
from providers.municipal_rss.parsing.base_parser import RssFeedParser
from utils.text_normalizer import clean_text


class RssXmlParser(RssFeedParser):
    """Extract event items from RSS XML payloads."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def parse(self, raw_content: str, source: RssFeedSource) -> List[RawRssItem]:
        try:
            root = ET.fromstring(raw_content or "")
        except Exception as exc:
            self._logger.warning("MunicipalRSS: invalid XML source=%s reason=%s", source.url, exc)
            return []
        return [self._from_node(node) for node in root.findall(".//item")]

    def _from_node(self, node: ET.Element) -> RawRssItem:
        return RawRssItem(
            title=self._text(node.find("title")),
            link=self._text(node.find("link")),
            description=self._text(node.find("description")),
            pub_date=self._text(node.find("pubDate")),
            category=self._text(node.find("category")),
        )

    def _text(self, node: Optional[ET.Element]) -> str:
        return clean_text(node.text or "") if node is not None else ""
