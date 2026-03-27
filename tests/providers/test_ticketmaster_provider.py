import json
from pathlib import Path

from config import settings
from providers.ticketmaster import TicketmasterProvider


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
        / "ticketmaster_events_page_0.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _set_enabled_defaults():
    settings.ticketmaster_enabled = True
    settings.ticketmaster_api_key = "test_key"
    settings.ticketmaster_country_code = "TR"
    settings.ticketmaster_city = "Istanbul"
    settings.ticketmaster_size = 50
    settings.ticketmaster_max_pages = 2
    settings.ticketmaster_max_retries = 2
    settings.ticketmaster_timeout_seconds = 5


def test_ticketmaster_parse_success():
    _set_enabled_defaults()
    provider = TicketmasterProvider()

    payload = _load_fixture()
    parsed = provider._extract_page_payload(payload)
    assert len(parsed["events"]) == 2

    first = provider._normalize_event(parsed["events"][0])
    assert first is not None
    assert first.title == "Istanbul Jazz Night"
    assert first.type == "concert"
    assert first.occurrences[0].venue_name == "Zorlu PSM"


def test_ticketmaster_missing_fields_skips_safely():
    _set_enabled_defaults()
    provider = TicketmasterProvider()

    event = {
        "id": "event_without_url",
        "name": "Broken Event",
        "dates": {"start": {"dateTime": "2026-06-10T18:30:00Z"}},
    }
    assert provider._normalize_event(event) is None


def test_ticketmaster_empty_response():
    _set_enabled_defaults()
    provider = TicketmasterProvider()

    parsed = provider._extract_page_payload({"page": {"totalPages": 0}})
    assert parsed["events"] == []
    assert parsed["total_pages"] == 0


def test_ticketmaster_auth_error_returns_none():
    _set_enabled_defaults()
    provider = TicketmasterProvider()
    provider.session = DummySession([DummyResponse(status_code=401, payload={})])

    result = provider._fetch_page(0)
    assert result is None


def test_ticketmaster_pagination_stops_on_last_page(monkeypatch):
    _set_enabled_defaults()
    provider = TicketmasterProvider()

    pages = [
        {"events": [{"id": "e1"}, {"id": "e2"}], "total_pages": 2},
        {"events": [{"id": "e3"}], "total_pages": 2},
    ]

    def fake_fetch_page(page):
        return pages[page] if page < len(pages) else {"events": [], "total_pages": 2}

    provider._last_fetched_pages = 0
    monkeypatch.setattr(provider, "_fetch_page", fake_fetch_page)
    events = provider._fetch_all_events()

    assert len(events) == 3
    assert provider._last_fetched_pages == 2


def test_ticketmaster_category_mapping():
    _set_enabled_defaults()
    provider = TicketmasterProvider()

    event = {
        "id": "event_1",
        "name": "Comedy Night",
        "url": "https://www.ticketmaster.com/event/event_1",
        "dates": {"start": {"dateTime": "2026-06-10T18:30:00Z"}},
        "classifications": [{"segment": {"name": "Comedy"}}],
        "_embedded": {"venues": [{"name": "Test Venue"}]},
    }

    normalized = provider._normalize_event(event)
    assert normalized is not None
    assert normalized.type == "standup"
