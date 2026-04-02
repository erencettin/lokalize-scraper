"""WordPress REST API price extractor (best-effort).

Attempts to extract price information from WordPress REST API post responses
by checking common meta and ACF field names.  Per the implementation plan,
if no price field is found the extractor returns a zero-confidence PriceInfo
(``confidence: 0.0``) — no guessing, no fabrication.

Usage
-----
    from utils.wp_rest_price_extractor import WpRestPriceExtractor

    extractor = WpRestPriceExtractor()
    price_info = extractor.extract_from_post(post_dict, source_domain="bakirkoy.bel.tr")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from models.normalized_event import PriceInfo
from utils.price_parser import PriceParser

_logger = logging.getLogger(__name__)

# Common WP meta / ACF keys that may contain price data (checked in order).
WP_PRICE_KEYS: tuple[str, ...] = (
    "event_price",
    "_event_price",
    "price",
    "_price",
    "bilet_fiyat",
    "bilet_fiyati",
    "ucret",
    "_ucret",
    "event_cost",
    "_event_cost",
    "event_fee",
    "ticket_price",
)

# Keys that explicitly signal a free event
_FREE_MARKER_KEYS: frozenset[str] = frozenset(
    {"event_free", "_event_free", "is_free", "event_is_free", "ucretsiz"}
)
_FREE_MARKER_VALUES: frozenset[str] = frozenset(
    {"1", "true", "yes", "ucretsiz", "\u00fccretsiz", "free", "bedava"}
)


class WpRestPriceExtractor:
    """Extract price from a WordPress REST API post dict.

    Checks ``post['meta']``, ``post['acf']``, and top-level keys using
    ``WP_PRICE_KEYS``.  Falls back to ``confidence: 0.0`` if nothing found.

    Currency is assumed to be TRY (standard for Turkish municipal WP sites).
    If the API response contains a ``currency`` field this is used instead.
    """

    def extract_from_post(self, post: Dict[str, Any], source_domain: str = "") -> PriceInfo:
        """Return a PriceInfo from a WP REST post dict."""
        if not isinstance(post, dict):
            return self._unknown(source_domain)

        # --- Check for explicit free markers first ---
        if self._is_explicitly_free(post):
            return PriceParser.resolve_from_text_candidates(
                candidates=["ucretsiz"],
                currency="TRY",
                source=f"wp_rest:{source_domain}",
                legal_mode="public_web_text",
                strategy="wp_rest_free_marker",
                confidence=0.80,
                is_authoritative=False,
                is_derived=True,
                note="WP meta/ACF free marker detected.",
                requires_terms_review=True,
            )

        # --- Try to find a price string ---
        raw_price = self._find_price_value(post)
        if raw_price is None:
            return self._unknown(source_domain)

        currency = self._find_currency(post)
        return PriceParser.resolve_from_text_candidates(
            candidates=[raw_price],
            currency=currency,
            source=f"wp_rest:{source_domain}",
            legal_mode="public_web_text",
            strategy="wp_rest_meta_scan",
            confidence=0.65,
            is_authoritative=False,
            is_derived=True,
            note=f"WP REST meta field value. Domain: {source_domain}",
            requires_terms_review=True,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_explicitly_free(self, post: Dict[str, Any]) -> bool:
        for key in _FREE_MARKER_KEYS:
            val = self._get_nested(post, key)
            if val is not None and str(val).strip().lower() in _FREE_MARKER_VALUES:
                return True
        # Also check if any price key contains "free" / "0"
        raw = self._find_price_value(post)
        if raw:
            lower = raw.strip().lower()
            return lower in {"free", "\u00fccretsiz", "ucretsiz", "bedava", "0", "0.00", ""}
        return False

    def _find_price_value(self, post: Dict[str, Any]) -> Optional[str]:
        for key in WP_PRICE_KEYS:
            val = self._get_nested(post, key)
            if val is not None:
                as_str = str(val).strip()
                if as_str:
                    return as_str
        return None

    def _find_currency(self, post: Dict[str, Any]) -> str:
        for key in ("currency", "event_currency", "price_currency"):
            val = self._get_nested(post, key)
            if val and isinstance(val, str):
                code = val.strip().upper()
                if code in ("TRY", "USD", "EUR"):
                    return code
        return "TRY"

    @staticmethod
    def _get_nested(post: Dict[str, Any], key: str) -> Optional[Any]:
        """Check top-level, then post['meta'], then post['acf']."""
        if key in post:
            return post[key]
        meta = post.get("meta") or {}
        if isinstance(meta, dict) and key in meta:
            return meta[key]
        acf = post.get("acf") or {}
        if isinstance(acf, dict):
            # Support dot-notation: "acf.price" → already split
            if key in acf:
                return acf[key]
        return None

    @staticmethod
    def _unknown(source_domain: str) -> PriceInfo:
        return PriceParser.resolve_from_text_candidates(
            candidates=[],
            currency="TRY",
            source=f"wp_rest:{source_domain}",
            legal_mode="public_web_text",
            strategy="wp_rest_meta_scan",
            confidence=0.0,
            is_authoritative=False,
            is_derived=False,
            note="No price field found in WP REST response.",
            requires_terms_review=False,
        )
