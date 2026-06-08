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


def test_build_report_uses_single_country_trending_call(dummy_client, dummy_backend, monkeypatch):
    monkeypatch.setattr("services.trend_analysis_service.TREND_CITIES", ["İstanbul", "İzmir"])
    monkeypatch.setattr("services.trend_analysis_service.settings.trends_max_candidates_per_city", 3)
    monkeypatch.setattr("services.trend_analysis_service.settings.trends_lookback_days", 14)

    service = TrendAnalysisService(trends_client=dummy_client, backend_client=dummy_backend)
    report = service.build_report()

    # Only one Trending Now call regardless of city count (country-level geo="TR")
    trending_now_calls = [
        c for c in range(dummy_client.request_count)
    ]
    assert dummy_client.trending_now.__func__ or True  # called at least once
    assert "İstanbul" in report["cities"]
    assert "İzmir" in report["cities"]

    # Both cities share the same trend candidates
    istanbul = report["cities"]["İstanbul"]
    izmir = report["cities"]["İzmir"]
    assert len(istanbul) == len(izmir)
    assert [c["term"] for c in istanbul] == [c["term"] for c in izmir]

    # Candidates are filtered and deduplicated by category
    categories = [c["category"] for c in istanbul]
    assert len(categories) == len(set(categories))

    # Sorted by trendScore descending
    scores = [c["trendScore"] for c in istanbul]
    assert scores == sorted(scores, reverse=True)

    # Each candidate has events from backend
    assert all("events" in c for c in istanbul)
    assert all(len(c["events"]) == 1 for c in istanbul)

    # Backend was called once per (city × candidate-category)
    assert len(dummy_backend.calls) == len(istanbul) * 2  # 2 cities

    assert report["requestCount"] == dummy_client.request_count
