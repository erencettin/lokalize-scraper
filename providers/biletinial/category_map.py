"""Maps Biletinial feed category labels to internal event type IDs.

The feed's `g:custom_label_3` field already carries a category per item
(e.g. "tiyatro", "muzik"), so a new feed only needs a new entry here —
no per-feed registry is required.
"""
from __future__ import annotations

from typing import Optional

# g:custom_label_3 -> internal type
_MAIN_CATEGORY_MAP: dict[str, str] = {
    "tiyatro": "theatre",
    "muzik": "concert",
}

# g:custom_label_2 overrides for specific sub-categories that should not
# follow the main category mapping above.
_SUBCATEGORY_OVERRIDES: dict[str, str] = {
    "cocuk-tiyatrosu": "kids",
}


def resolve(main_category: str, sub_category: str = "") -> Optional[str]:
    """Return the internal type id for a Biletinial item, or None if unknown.

    Returning None signals the caller to skip the item rather than guess —
    new/unsupported feed categories should be added here explicitly.
    """
    sub_key = (sub_category or "").strip().lower()
    if sub_key in _SUBCATEGORY_OVERRIDES:
        return _SUBCATEGORY_OVERRIDES[sub_key]

    main_key = (main_category or "").strip().lower()
    return _MAIN_CATEGORY_MAP.get(main_key)
