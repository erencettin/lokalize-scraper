import json
from pathlib import Path

from config import settings
from providers.predicthq import PredictHQProvider


class DummyResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class DummySession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0
        self.headers = {}

    def get(self, *args, **kwargs):
        response = self.responses[self.calls]
        self.calls += 1
        return response

    def close(self):
        return None


def _load_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "predicthq_events_page_1.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _set_enabled_defaults():
    settings.predicthq_enabled = True
    settings.predicthq_access_token = "test_token"
    settings.predicthq_query = "istanbul"
    settings.predicthq_country = "TR"
    settings.predicthq_limit = 50
    settings.predicthq_max_pages = 2
    settings.predicthq_max_retries = 2
    settings.predicthq_timeout_seconds = 5


def test_predicthq_parse_success():
    _set_enabled_defaults()
    provider = PredictHQProvider()
    payload = _load_fixture()
    parsed = provider._extract_page_payload(payload)
    assert len(parsed["events"]) == 2

    first = provider._normalize_event(parsed["events"][0])
    assert first is not None
    assert first.title == "Istanbul Rock Concert"
    assert first.type == "concert"
    assert first.occurrences[0].venue_name == "Harbiye Cemil Topuzlu Acik Hava Tiyatrosu"


def test_predicthq_missing_fields_skip():
    _set_enabled_defaults()
    provider = PredictHQProvider()
    event = {"id": "no_start", "title": "Broken"}
    assert provider._normalize_event(event) is None


def test_predicthq_empty_response():
    _set_enabled_defaults()
    provider = PredictHQProvider()
    parsed = provider._extract_page_payload({"results": [], "next": None})
    assert parsed["events"] == []
    assert parsed["has_more"] is False


def test_predicthq_auth_error_returns_none():
    _set_enabled_defaults()
    provider = PredictHQProvider()
    provider.session = DummySession([DummyResponse(status_code=401, payload={})])
    result = provider._fetch_page(0)
    assert result is None


def test_predicthq_pagination_stops_without_next(monkeypatch):
    _set_enabled_defaults()
    provider = PredictHQProvider()
    pages = [
        {"events": [{"id": "e1"}, {"id": "e2"}], "has_more": True},
        {"events": [{"id": "e3"}], "has_more": False},
    ]

    def fake_fetch_page(offset):
        index = 0 if offset == 0 else 1
        return pages[index]

    monkeypatch.setattr(provider, "_fetch_page", fake_fetch_page)
    events = provider._fetch_all_events()
    assert len(events) == 3


def test_predicthq_category_mapping():
    _set_enabled_defaults()
    provider = PredictHQProvider()
    event = {
        "id": "phq_x",
        "title": "Sports Match",
        "category": "sports",
        "start": "2026-08-10T18:30:00Z",
        "entities": [{"name": "Stadium", "type": "venue"}],
    }
    normalized = provider._normalize_event(event)
    assert normalized is not None
    assert normalized.type == "match"
