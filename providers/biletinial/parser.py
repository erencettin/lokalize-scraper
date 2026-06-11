"""Parses the Biletinial Google Merchant / Facebook product feed (RSS + g: namespace)."""
from __future__ import annotations

import logging
from typing import List
from xml.etree import ElementTree as ET

from providers.biletinial.constants import FEED_NAMESPACE

_NS = {"g": FEED_NAMESPACE}
_logger = logging.getLogger(__name__)


def _text(item: ET.Element, tag: str, namespaced: bool = False) -> str:
    el = item.find(tag, _NS) if namespaced else item.find(tag)
    return (el.text or "").strip() if el is not None and el.text else ""


def parse_feed_items(content: bytes) -> List[dict]:
    """Parse raw feed bytes into a list of plain dicts, one per <item>.

    Malformed feed -> raises ET.ParseError; the caller is responsible for
    catching this and skipping the feed (one bad feed must not abort others).
    """
    root = ET.fromstring(content)
    items: List[dict] = []

    for item_el in root.iter("item"):
        items.append({
            "title": _text(item_el, "title"),
            "description": _text(item_el, "description"),
            "link": _text(item_el, "link"),
            "id": _text(item_el, "g:id", namespaced=True),
            "price": _text(item_el, "g:price", namespaced=True),
            "image_link": _text(item_el, "g:image_link", namespaced=True),
            "city": _text(item_el, "g:custom_label_0", namespaced=True),
            "date": _text(item_el, "g:custom_label_1", namespaced=True),
            "subcategory": _text(item_el, "g:custom_label_2", namespaced=True),
            "category": _text(item_el, "g:custom_label_3", namespaced=True),
            "venue_slug": _text(item_el, "g:custom_label_4", namespaced=True),
            "time": _text(item_el, "g:custom_label_5", namespaced=True),
            "venue_id": _text(item_el, "g:custom_label_6", namespaced=True),
            "venue_name": _text(item_el, "g:custom_label_7", namespaced=True),
            "event_group_id": _text(item_el, "g:custom_label_8", namespaced=True),
        })

    return items
