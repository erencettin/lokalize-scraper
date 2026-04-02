"""Tests for HTML price extraction helpers (extract_jsonld_price, extract_meta_price)."""
from __future__ import annotations

import json

import pytest

from utils.html_extractor import extract_jsonld_price, extract_meta_price


# ---------------------------------------------------------------------------
# JSON-LD fixtures
# ---------------------------------------------------------------------------

def _jsonld_html(data: dict) -> str:
    return f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>'


JSONLD_EVENT_WITH_PRICE = _jsonld_html({
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "Konser ABC",
    "offers": {
        "@type": "Offer",
        "price": "250",
        "priceCurrency": "TRY",
    }
})

JSONLD_EVENT_RANGE = _jsonld_html({
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "Festival XYZ",
    "offers": {
        "@type": "AggregateOffer",
        "lowPrice": "100",
        "highPrice": "500",
        "priceCurrency": "TRY",
    }
})

JSONLD_FREE_EVENT = _jsonld_html({
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "Ücretsiz Konser",
    "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "TRY",
    }
})

JSONLD_USD_EVENT = _jsonld_html({
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "International Show",
    "offers": {
        "@type": "Offer",
        "price": "99",
        "priceCurrency": "USD",
    }
})

JSONLD_NO_OFFERS = _jsonld_html({
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "No Price Event",
})

JSONLD_MULTIPLE_OFFERS = _jsonld_html({
    "@context": "https://schema.org",
    "@type": "Event",
    "offers": [
        {"@type": "Offer", "price": "300", "priceCurrency": "TRY"},
        {"@type": "Offer", "price": "200", "priceCurrency": "TRY"},
    ]
})


class TestExtractJsonldPrice:
    def test_single_offer_price(self):
        result = extract_jsonld_price(JSONLD_EVENT_WITH_PRICE)
        assert result is not None
        assert result["min"] == 250.0
        assert result["currency"] == "TRY"

    def test_aggregate_offer_range(self):
        result = extract_jsonld_price(JSONLD_EVENT_RANGE)
        assert result is not None
        assert result["min"] == 100.0
        assert result["max"] == 500.0

    def test_free_event_price_zero(self):
        result = extract_jsonld_price(JSONLD_FREE_EVENT)
        assert result is not None
        assert result["min"] == 0.0

    def test_usd_currency_preserved(self):
        result = extract_jsonld_price(JSONLD_USD_EVENT)
        assert result is not None
        assert result["currency"] == "USD"

    def test_no_offers_returns_none(self):
        result = extract_jsonld_price(JSONLD_NO_OFFERS)
        assert result is None

    def test_empty_html_returns_none(self):
        assert extract_jsonld_price("") is None
        assert extract_jsonld_price(None) is None  # type: ignore

    def test_multiple_offers_picks_min(self):
        result = extract_jsonld_price(JSONLD_MULTIPLE_OFFERS)
        assert result is not None
        assert result["min"] == 200.0

    def test_no_jsonld_script_returns_none(self):
        html = "<html><body><p>Fiyat yok</p></body></html>"
        assert extract_jsonld_price(html) is None

    def test_malformed_json_returns_none(self):
        html = '<script type="application/ld+json">{ bad json }</script>'
        assert extract_jsonld_price(html) is None

    def test_multiple_script_blocks_finds_first_with_price(self):
        no_price_block = '<script type="application/ld+json">{"@type":"Organization"}</script>'
        price_block = _jsonld_html({"@type": "Event", "offers": {"price": "150", "priceCurrency": "TRY"}})
        html = no_price_block + price_block
        result = extract_jsonld_price(html)
        assert result is not None
        assert result["min"] == 150.0


# ---------------------------------------------------------------------------
# Meta tag fixtures
# ---------------------------------------------------------------------------

class TestExtractMetaPrice:
    def test_event_price_property(self):
        html = '<meta property="event:price" content="350">'
        assert extract_meta_price(html) == "350"

    def test_name_price_meta(self):
        html = '<meta name="price" content="200 TL">'
        assert extract_meta_price(html) == "200 TL"

    def test_itemprop_price(self):
        html = '<meta itemprop="price" content="99.90">'
        assert extract_meta_price(html) == "99.90"

    def test_content_before_property(self):
        html = '<meta content="450" property="event:price">'
        assert extract_meta_price(html) == "450"

    def test_no_price_tag_returns_none(self):
        html = '<meta name="description" content="An event page">'
        assert extract_meta_price(html) is None

    def test_empty_html_returns_none(self):
        assert extract_meta_price("") is None
        assert extract_meta_price(None) is None  # type: ignore

    def test_free_price_text(self):
        html = '<meta property="event:price" content="Ücretsiz">'
        assert extract_meta_price(html) == "Ücretsiz"
