import json
from pathlib import Path

import pytest

from services.trend_analysis_service import TrendAnalysisService, _fold, _match_category

_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "serpapi"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES_DIR / name).read_text(encoding="utf-8"))


class DummyTrendsClient:
    """Stands in for SerpApiTrendsClient using static fixtures (no live SerpAPI calls)."""

    def __init__(self, trending_payload: dict, trends_payload: dict):
        self._trending_payload = trending_payload
        self._trends_payload = trends_payload
        self.is_enabled = True
        self.request_count = 0

    def trending_now(self, *, geo: str):
        self.request_count += 1
        return self._trending_payload.get("trending_searches", [])

    def interest_over_time(self, *, query: str, geo: str, lookback_days: int = 14):
        self.request_count += 1
        return self._trends_payload.get("interest_over_time", {}).get("timeline_data", [])


class DummyBackendClient:
    """Stands in for BackendClient — returns a canned event list for any city/category."""

    def __init__(self):
        self.calls = []

    def get_trend_candidates(self, *, city: str, category: str, limit: int = 5):
        self.calls.append({"city": city, "category": category, "limit": limit})
        return [{
            "id": "evt-1",
            "title": "Sample Event",
            "imageUrl": "https://example.com/poster.jpg",
            "sourceUrl": "https://example.com/events/sample-event",
        }]


@pytest.fixture
def dummy_client():
    return DummyTrendsClient(
        trending_payload=_load_fixture("trending_now_sample.json"),
        trends_payload=_load_fixture("google_trends_sample.json"),
    )


@pytest.fixture
def dummy_backend():
    return DummyBackendClient()


def test_fold_strips_turkish_accents():
    assert _fold("İstanbul Tiyatro Oyunları") == "istanbul tiyatro oyunlari"


def test_match_category_recognizes_keywords():
    assert _match_category("Tarkan İstanbul konseri") == "concert"
    assert _match_category("Galatasaray maç biletleri") == "sports"
    assert _match_category("İstanbul tiyatro oyunları haziran") == "theatre"
    assert _match_category("İstanbul stand-up gösterileri") == "standup"
    assert _match_category("döviz kuru bugün") is None


def test_build_report_filters_and_ranks_by_trend_score(dummy_client, dummy_backend, monkeypatch):
    monkeypatch.setattr("services.trend_analysis_service.TREND_CITIES", ["İstanbul"])
    monkeypatch.setattr("services.trend_analysis_service.TREND_CITY_GEO", {"İstanbul": "TR-34"})
    monkeypatch.setattr("services.trend_analysis_service.settings.trends_max_candidates_per_city", 3)
    monkeypatch.setattr("services.trend_analysis_service.settings.trends_lookback_days", 14)

    service = TrendAnalysisService(trends_client=dummy_client, backend_client=dummy_backend)
    report = service.build_report()

    assert set(report["cities"].keys()) == {"İstanbul"}
    candidates = report["cities"]["İstanbul"]

    # Only category-matching terms survive ("döviz kuru bugün" is filtered out)
    assert len(candidates) == 3
    assert all(c["category"] in {"concert", "sports", "theatre", "standup"} for c in candidates)

    # All candidates use the same fixture timeline, so they share the max score (87)
    # and stay sorted in non-increasing order.
    scores = [c["trendScore"] for c in candidates]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 87

    assert report["requestCount"] == dummy_client.request_count

    # Each candidate's matched events came from the backend, mapped through
    # TREND_CATEGORY_TO_BACKEND_TYPE (e.g. "sports" -> "match", "standup" -> "standup").
    expected_event = {
        "id": "evt-1",
        "title": "Sample Event",
        "imageUrl": "https://example.com/poster.jpg",
        "sourceUrl": "https://example.com/events/sample-event",
    }
    assert all(c["events"] == [expected_event] for c in candidates)
    # Only 3 candidates survive (trends_max_candidates_per_city=3), each mapped
    # through TREND_CATEGORY_TO_BACKEND_TYPE (e.g. "sports" -> "match").
    called_categories = {call["category"] for call in dummy_backend.calls}
    assert len(dummy_backend.calls) == 3
    assert called_categories <= {"concert", "match", "theatre", "standup"}
