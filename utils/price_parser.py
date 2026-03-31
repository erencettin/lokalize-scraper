from __future__ import annotations

import re
from typing import Optional, Sequence, Tuple

from models.normalized_event import PriceInfo, PriceResolution
from utils.text_normalizer import TextNormalizer, clean_text


DEFAULT_PRICE_TEXT = "Fiyat bilgisi yok"
FREE_PRICE_TEXT = "Ucretsiz"
DEFAULT_CURRENCY = "TRY"

_FREE_MARKERS = {
    "ucretsiz",
    "free",
    "bedava",
    "withoutcharge",
    "nocost",
    "cretsiz",
}
_UNKNOWN_MARKERS = {
    "fiyatbilgisiyok",
    "fiyatyok",
    "priceunavailable",
    "pricenotavailable",
    "priceunknown",
    "unknown",
    "belirtilmedi",
    "tba",
    "tbd",
}


class PriceParser:
    @staticmethod
    def parse_prices(price_text: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Backward-compatible parser used by legacy sync flow.
        """
        if not price_text:
            return None, None
        normalized = PriceParser._normalize_for_match(price_text)
        if not normalized:
            return None, None
        if PriceParser._contains_unknown_marker(normalized):
            return None, None
        if PriceParser._contains_free_marker(normalized):
            return 0.0, 0.0

        values = PriceParser._extract_numeric_values(price_text)
        if not values:
            return None, None
        if len(values) == 1:
            return values[0], values[0]
        return min(values), max(values)

    @staticmethod
    def unknown_price(
        *,
        source: str,
        legal_mode: str,
        strategy: str = "unknown",
        note: Optional[str] = None,
        requires_terms_review: bool = False,
    ) -> PriceInfo:
        return PriceInfo(
            text=DEFAULT_PRICE_TEXT,
            currency=DEFAULT_CURRENCY,
            is_free=False,
            is_unknown=True,
            resolution=PriceResolution(
                strategy=strategy,
                confidence=0.0,
                legal_mode=legal_mode,
                source=source,
                is_authoritative=False,
                is_derived=False,
                requires_terms_review=requires_terms_review,
                note=note,
            ),
        )

    @staticmethod
    def resolve_structured_range(
        *,
        min_value: Optional[float],
        max_value: Optional[float],
        currency: Optional[str],
        source: str,
        legal_mode: str,
        strategy: str,
        confidence: float,
        is_authoritative: bool,
        is_derived: bool,
        note: Optional[str] = None,
    ) -> PriceInfo:
        parsed_min = PriceParser._sanitize_amount(min_value)
        parsed_max = PriceParser._sanitize_amount(max_value)
        if parsed_min is None and parsed_max is None:
            return PriceParser.unknown_price(
                source=source,
                legal_mode=legal_mode,
                strategy=f"{strategy}_missing",
                note=note,
                requires_terms_review=legal_mode == "public_web_text",
            )

        if parsed_min is None:
            parsed_min = parsed_max
        if parsed_max is None:
            parsed_max = parsed_min

        if parsed_min is None or parsed_max is None:
            return PriceParser.unknown_price(
                source=source,
                legal_mode=legal_mode,
                strategy=f"{strategy}_invalid",
                note=note,
                requires_terms_review=legal_mode == "public_web_text",
            )

        min_price = min(parsed_min, parsed_max)
        max_price = max(parsed_min, parsed_max)
        resolved_currency = clean_text(currency or DEFAULT_CURRENCY) or DEFAULT_CURRENCY
        is_free = min_price == 0.0 and max_price == 0.0
        return PriceInfo(
            min_value=min_price,
            max_value=max_price,
            text=PriceParser._format_price_text(min_price, max_price, resolved_currency),
            currency=resolved_currency,
            is_free=is_free,
            is_unknown=False,
            resolution=PriceResolution(
                strategy=strategy,
                confidence=max(0.0, min(confidence, 1.0)),
                legal_mode=legal_mode,
                source=source,
                is_authoritative=is_authoritative,
                is_derived=is_derived,
                requires_terms_review=legal_mode == "public_web_text",
                note=note,
            ),
        )

    @staticmethod
    def resolve_text_price(
        *,
        price_text: Optional[str],
        currency: Optional[str],
        source: str,
        legal_mode: str,
        strategy: str,
        confidence: float,
        is_authoritative: bool,
        is_derived: bool,
        note: Optional[str] = None,
        requires_terms_review: bool = False,
    ) -> PriceInfo:
        cleaned = clean_text(price_text or "")
        normalized = PriceParser._normalize_for_match(cleaned)
        if not cleaned or not normalized:
            return PriceParser.unknown_price(
                source=source,
                legal_mode=legal_mode,
                strategy=f"{strategy}_empty",
                note=note,
                requires_terms_review=requires_terms_review,
            )
        if PriceParser._contains_unknown_marker(normalized):
            return PriceParser.unknown_price(
                source=source,
                legal_mode=legal_mode,
                strategy=f"{strategy}_unknown_marker",
                note=note,
                requires_terms_review=requires_terms_review,
            )
        if PriceParser._contains_free_marker(normalized):
            resolved_currency = clean_text(currency or DEFAULT_CURRENCY) or DEFAULT_CURRENCY
            return PriceInfo(
                min_value=0.0,
                max_value=0.0,
                text=FREE_PRICE_TEXT,
                currency=resolved_currency,
                is_free=True,
                is_unknown=False,
                resolution=PriceResolution(
                    strategy=f"{strategy}_free_marker",
                    confidence=max(0.0, min(confidence, 1.0)),
                    legal_mode=legal_mode,
                    source=source,
                    is_authoritative=is_authoritative,
                    is_derived=is_derived,
                    requires_terms_review=requires_terms_review,
                    note=note,
                ),
            )

        values = PriceParser._extract_numeric_values(cleaned)
        if not values:
            return PriceParser.unknown_price(
                source=source,
                legal_mode=legal_mode,
                strategy=f"{strategy}_no_numeric",
                note=note,
                requires_terms_review=requires_terms_review,
            )

        min_price = min(values)
        max_price = max(values)
        resolved_currency = clean_text(currency or DEFAULT_CURRENCY) or DEFAULT_CURRENCY
        return PriceInfo(
            min_value=min_price,
            max_value=max_price,
            text=PriceParser._format_price_text(min_price, max_price, resolved_currency),
            currency=resolved_currency,
            is_free=min_price == 0.0 and max_price == 0.0,
            is_unknown=False,
            resolution=PriceResolution(
                strategy=strategy,
                confidence=max(0.0, min(confidence, 1.0)),
                legal_mode=legal_mode,
                source=source,
                is_authoritative=is_authoritative,
                is_derived=is_derived,
                requires_terms_review=requires_terms_review,
                note=note,
            ),
        )

    @staticmethod
    def resolve_from_text_candidates(
        *,
        candidates: Sequence[object],
        currency: Optional[str],
        source: str,
        legal_mode: str,
        strategy: str,
        confidence: float,
        is_authoritative: bool,
        is_derived: bool,
        note: Optional[str] = None,
        requires_terms_review: bool = False,
    ) -> PriceInfo:
        for candidate in candidates:
            text = clean_text(str(candidate or ""))
            if not text:
                continue
            resolved = PriceParser.resolve_text_price(
                price_text=text,
                currency=currency,
                source=source,
                legal_mode=legal_mode,
                strategy=strategy,
                confidence=confidence,
                is_authoritative=is_authoritative,
                is_derived=is_derived,
                note=note,
                requires_terms_review=requires_terms_review,
            )
            if not resolved.is_unknown:
                return resolved

        return PriceParser.unknown_price(
            source=source,
            legal_mode=legal_mode,
            strategy=f"{strategy}_all_candidates_unknown",
            note=note,
            requires_terms_review=requires_terms_review,
        )

    @staticmethod
    def _format_price_text(min_val: float, max_val: float, currency: str) -> str:
        if min_val == 0.0 and max_val == 0.0:
            return FREE_PRICE_TEXT
        if min_val == max_val:
            return f"{min_val:.2f} {currency}"
        return f"{min_val:.2f} - {max_val:.2f} {currency}"

    @staticmethod
    def _normalize_for_match(value: str) -> str:
        return TextNormalizer.normalize_for_match(clean_text(value or ""))

    @staticmethod
    def _contains_free_marker(normalized_text: str) -> bool:
        compact = normalized_text.replace(" ", "")
        return any(marker in compact for marker in _FREE_MARKERS)

    @staticmethod
    def _contains_unknown_marker(normalized_text: str) -> bool:
        compact = normalized_text.replace(" ", "")
        return any(marker in compact for marker in _UNKNOWN_MARKERS)

    @staticmethod
    def _extract_numeric_values(value: str) -> list[float]:
        # Filter out common ordinal prefixes in Turkish ticking to avoid extracting '1' as price from '1. Kategori - 500'.
        cleaned_val = re.sub(r"\b\d+\s*[\.,]?\s*(?:kategori|kat|faz|d[oö]nem|bilet|ad[iı]m|avantaj)\b", " ", value or "", flags=re.IGNORECASE)
        # Also filter standalone '1.', '2.', '3.' if followed by a space and capitalized word, which often are ordinals.
        cleaned_val = re.sub(r"\b\d+\s*\.\s*[A-ZÇĞİÖŞÜ]", " ", cleaned_val)
        
        tokens = re.findall(r"\d[\d.,]*", cleaned_val)
        parsed: list[float] = []
        for token in tokens:
            amount = PriceParser._to_float_token(token)
            sanitized = PriceParser._sanitize_amount(amount)
            if sanitized is None:
                continue
            parsed.append(sanitized)
        return parsed

    @staticmethod
    def _to_float_token(token: str) -> Optional[float]:
        cleaned = token.strip().strip(".,")
        if not cleaned:
            return None
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                normalized = cleaned.replace(".", "").replace(",", ".")
            else:
                normalized = cleaned.replace(",", "")
        elif "," in cleaned:
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2:
                normalized = cleaned.replace(",", ".")
            else:
                normalized = cleaned.replace(",", "")
        elif "." in cleaned:
            parts = cleaned.split(".")
            if len(parts) == 2 and len(parts[1]) <= 2:
                normalized = cleaned
            else:
                normalized = cleaned.replace(".", "")
        else:
            normalized = cleaned

        try:
            return float(normalized)
        except ValueError:
            return None

    @staticmethod
    def _sanitize_amount(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        if value < 0:
            return None
        if value > 10000000:
            return None
        return round(value, 2)
