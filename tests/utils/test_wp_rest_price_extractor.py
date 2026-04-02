"""Tests for WpRestPriceExtractor."""
from __future__ import annotations

import pytest
from unittest.mock import patch

from utils.wp_rest_price_extractor import WpRestPriceExtractor


@pytest.fixture
def extractor():
    return WpRestPriceExtractor()


class TestWpRestPriceExtractor:
    def test_extracts_from_event_price_meta(self, extractor):
        post = {"meta": {"event_price": "250"}}
        info = extractor.extract_from_post(post, source_domain="bakirkoy.bel.tr")
        assert info is not None
        # Confidence should be non-zero since a price was found
        assert info.resolution.confidence > 0.0

    def test_extracts_from_acf_price(self, extractor):
        post = {"acf": {"price": "150"}}
        info = extractor.extract_from_post(post, source_domain="beyoglu.bel.tr")
        assert info is not None
        assert info.resolution.confidence > 0.0

    def test_extracts_from_top_level_key(self, extractor):
        post = {"event_price": "300 TL"}
        info = extractor.extract_from_post(post, source_domain="test.bel.tr")
        assert info is not None
        assert info.resolution.confidence > 0.0

    def test_free_event_from_meta_marker(self, extractor):
        post = {"meta": {"event_free": "1"}}
        info = extractor.extract_from_post(post, source_domain="besiktas.bel.tr")
        assert info is not None
        assert "wp_rest_free_marker" in info.resolution.strategy
        assert info.is_free is True

    def test_no_price_field_returns_zero_confidence(self, extractor):
        post = {"meta": {"author": "Admin"}, "acf": {"map_lat": "41.0"}}
        info = extractor.extract_from_post(post, source_domain="bayramkoy.bel.tr")
        assert info is not None
        assert info.resolution.confidence == 0.0
        assert "wp_rest_meta_scan" in info.resolution.strategy

    def test_non_dict_input_returns_zero_confidence(self, extractor):
        info = extractor.extract_from_post(None, source_domain="test.bel.tr")  # type: ignore
        assert info.resolution.confidence == 0.0

    def test_acf_bilet_fiyat_key(self, extractor):
        post = {"acf": {"bilet_fiyat": "75"}}
        info = extractor.extract_from_post(post, source_domain="sisli.bel.tr")
        assert info.resolution.confidence > 0.0

    def test_try_currency_default(self, extractor):
        post = {"meta": {"event_price": "200"}}
        info = extractor.extract_from_post(post, source_domain="maltepe.bel.tr")
        assert info.currency == "TRY"
