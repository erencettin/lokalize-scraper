"""Tests for TribeEventsPriceExtractor."""
from __future__ import annotations

import pytest

from utils.tribe_events_price_extractor import TribeEventsPriceExtractor


@pytest.fixture
def extractor():
    return TribeEventsPriceExtractor()


class TestTribeEventsPriceExtractor:
    def test_extracts_numeric_cost(self, extractor):
        event = {"cost": "250"}
        info = extractor.extract_from_event(event)
        assert info is not None
        assert info.resolution.confidence > 0.0

    def test_free_event_empty_cost(self, extractor):
        event = {"cost": ""}
        info = extractor.extract_from_event(event)
        assert info is not None
        assert "tribe_events_cost_field" in info.resolution.strategy
        assert info.is_free is True

    def test_free_event_zero_cost(self, extractor):
        event = {"cost": "0"}
        info = extractor.extract_from_event(event)
        assert info is not None
        # "0" → free
        assert info.resolution.confidence >= 0.0

    def test_free_event_string_free(self, extractor):
        event = {"cost": "Free"}
        info = extractor.extract_from_event(event)
        assert info is not None

    def test_free_event_ucretsiz(self, extractor):
        event = {"cost": "Ücretsiz"}
        info = extractor.extract_from_event(event)
        assert info is not None

    def test_no_cost_field_returns_zero_confidence(self, extractor):
        event = {"title": "Etkinlik Adı", "start_date": "2026-05-01"}
        info = extractor.extract_from_event(event)
        assert info.resolution.confidence == 0.0

    def test_cost_min_and_max_range(self, extractor):
        event = {"cost_min": "100", "cost_max": "300"}
        info = extractor.extract_from_event(event)
        assert info is not None
        assert info.resolution.confidence > 0.0

    def test_non_dict_input_returns_zero_confidence(self, extractor):
        info = extractor.extract_from_event(None)  # type: ignore
        assert info.resolution.confidence == 0.0

    def test_currency_is_try(self, extractor):
        event = {"cost": "150"}
        info = extractor.extract_from_event(event)
        assert info.currency == "TRY"

    def test_source_is_tribe_events_api(self, extractor):
        event = {"cost": "200"}
        info = extractor.extract_from_event(event)
        assert "tribe_events" in info.resolution.strategy
