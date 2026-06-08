import json
from pathlib import Path

import pytest

from services.trend_analysis_service import TrendAnalysisService
from utils.constants import TREND_CATEGORIES

_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "serpapi"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES_DIR / name).read_text(encoding="utf-8"))


class DummyTrendsClient:
    """Stands in for SerpApiTrendsClient — returns fixture data without live calls."""

    def __init__(self, trends_payload: dict):
        self._trends_payload = trends_payload
        self.is_enabled = True
        self.request_count = 0
        self.queries_called: list[str] = []

    def interest_over_time(self, *, query: str, geo: str, lookback_days: int = 14):
        self.request_count += 1
        self.queries_called.append(query)
        return self._trends_payload.get("interest_over_time", {}).get("timeline_data", [])


class DummyBackendClient:
    """Stands in for BackendClient — returns a canned event list for any city/category."""

    def __init__(self):
        self.calls: list[dict] = []

    def get_trend_candidates(self, *, city: str, category: str, limit: int = 5):
        self.calls.append({"city": city, "category": category})
        return [{"id": "evt-1", "title": "Sample Event", "imageUrl": None, "sourceUrl": "https://example.com/evt-1"}]


@pytest.fixture
def dummy_client():
    return DummyTrendsClient(trends_payload=_load_fixture("google_trends_sample.json"))


@pytest.fixture
def dummy_backend():
    return DummyBackendClient()


def test_all_categories_are_scored(dummy_client, dummy_backend, monkeypatch):
    monkeypatch.setattr("services.trend_analysis_service.TREND_CITIES", ["İstanbul"])
    monkeypatch.setattr("services.trend_analysis_service.settings.trends_lookback_days", 14)

    service = TrendAnalysisService(trends_client=dummy_client, backend_client=dummy_backend)
    report = service.build_report()

    # One interest_over_time call per category
    assert dummy_client.request_count == len(TREND_CATEGORIES)

    # All categories appear in the city report
    istanbul = report["cities"]["İstanbul"]
    returned_ids = {c["category"] for c in istanbul}
    expected_ids = {c["id"] for c in TREND_CATEGORIES}
    assert returned_ids == expected_ids


def test_categories_sorted_by_trend_score(dummy_client, dummy_backend, monkeypatch):
    monkeypatch.setattr("services.trend_analysis_service.TREND_CITIES", ["İstanbul"])
    monkeypatch.setattr("services.trend_analysis_service.settings.trends_lookback_days", 14)

    service = TrendAnalysisService(trends_client=dummy_client, backend_client=dummy_backend)
    report = service.build_report()

    scores = [c["trendScore"] for c in report["cities"]["İstanbul"]]
    assert scores == sorted(scores, reverse=True)


def test_all_cities_get_all_categories(dummy_client, dummy_backend, monkeypatch):
    cities = ["İstanbul", "İzmir", "Ankara"]
    monkeypatch.setattr("services.trend_analysis_service.TREND_CITIES", cities)
    monkeypatch.setattr("services.trend_analysis_service.settings.trends_lookback_days", 14)

    service = TrendAnalysisService(trends_client=dummy_client, backend_client=dummy_backend)
    report = service.build_report()

    assert set(report["cities"].keys()) == set(cities)
    for city in cities:
        assert len(report["cities"][city]) == len(TREND_CATEGORIES)

    # Backend called once per city × category
    assert len(dummy_backend.calls) == len(cities) * len(TREND_CATEGORIES)
