"""Tribe Events (The Events Calendar) API price extractor.

Handles the Tribe Events REST API v1 response format used by sites like
K\u00fc\u00e7\u00fck\u00e7ekmece Belediyesi.  The API endpoint is typically:
    GET /wp-json/tribe/events/v1/events

Each event object may contain ``cost``, ``cost_min``, ``cost_max`` fields.
A value of ``"0"`` or empty string typically means the event is free.

Usage
-----
    from utils.tribe_events_price_extractor import TribeEventsPriceExtractor

    extractor = TribeEventsPriceExtractor()
    price_info = extractor.extract_from_event(event_dict)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from models.normalized_event import PriceInfo
from utils.price_parser import PriceParser

_logger = logging.getLogger(__name__)

# Tribe Events cost field names (checked in priority order)
_COST_FIELDS: tuple[str, ...] = ("cost", "cost_min", "cost_max")

# Strings that signal a free event (case-insensitive after strip)
_FREE_VALUES: frozenset[str] = frozenset(
    {"", "0", "free", "ucretsiz", "\u00fccretsiz", "bedava", "0.00", "0,00"}
)

# Remove currency symbols / separators to get a raw numeric string
_CLEANUP_PATTERN = re.compile(r"[\u20ba$\u20ac,\s]")


class TribeEventsPriceExtractor:
    """Extract price from a Tribe Events v1 API event dict.

    Checks ``event['cost']``, ``event['cost_min']``, ``event['cost_max']``.
    Returns free PriceInfo when value is empty/zero, unknown (confidence 0.0)
    when no field present, or a parsed PriceInfo with confidence 0.70 otherwise.

    Currency is assumed to be TRY (Tribe Events on Turkish municipal sites
    typically does not expose a currency field).
    """

    def extract_from_event(self, event: Dict[str, Any]) -> PriceInfo:
        """Return a PriceInfo from a Tribe Events v1 event dict."""
        print(f"[TRIBE_PRICE] Called. cost={event.get('cost') if isinstance(event, dict) else None}", flush=True)
        if not isinstance(event, dict):
            return self._unknown()

        # Collect all cost field values (skip missing)
        raw_values: list[str] = []
        for field in _COST_FIELDS:
            val = event.get(field)
            if val is not None:
                raw_values.append(str(val).strip())

        if not raw_values:
            _logger.debug("TribeEvents Raw Cost: [] -> Parsed: Unknown (0.0)")
            return self._unknown()

        # Check explicit free: cost field present but empty / zero
        if all(v.lower() in _FREE_VALUES for v in raw_values):
            return PriceParser.resolve_from_text_candidates(
                candidates=["ucretsiz"],
                currency="TRY",
                source="tribe_events_api",
                legal_mode="public_api",
                strategy="tribe_events_cost_field",
                confidence=0.75,
                is_authoritative=False,
                is_derived=True,
                note="Tribe Events cost field is empty/zero — event is free.",
                requires_terms_review=True,
            )

        # Use the most useful value (cost_min preferred over cost)
        primary = raw_values[0]

        # Build candidate list: use cost_min + cost_max range if both numeric
        candidates: list[str] = []
        min_raw = _CLEANUP_PATTERN.sub("", raw_values[0]) if len(raw_values) > 0 else ""
        max_raw = _CLEANUP_PATTERN.sub("", raw_values[-1]) if len(raw_values) > 1 else ""

        if min_raw and max_raw and min_raw != max_raw:
            candidates.append(f"{min_raw}-{max_raw} \u20ba")
        elif primary:
            candidates.append(primary)

        result = PriceParser.resolve_from_text_candidates(
            candidates=candidates,
            currency="TRY",
            source="tribe_events_api",
            legal_mode="public_api",
            strategy="tribe_events_cost_field",
            confidence=0.70,
            is_authoritative=False,
            is_derived=True,
            note="Tribe Events API cost field. Verify ToS for public use.",
            requires_terms_review=True,
        )
        _logger.debug("Tribe (Küçükçekmece) Raw Cost: %s -> Parsed: %s", raw_values, result)
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _unknown() -> PriceInfo:
        return PriceParser.resolve_from_text_candidates(
            candidates=[],
            currency="TRY",
            source="tribe_events_api",
            legal_mode="public_api",
            strategy="tribe_events_cost_field",
            confidence=0.0,
            is_authoritative=False,
            is_derived=False,
            note="No cost field found in Tribe Events response.",
            requires_terms_review=False,
        )
