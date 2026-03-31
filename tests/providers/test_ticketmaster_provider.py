import json
from pathlib import Path

from config import settings
from providers.ticketmaster import TicketmasterProvider
from providers.ticketmaster.event_builder import EventBuilder
from providers.ticketmaster.http_client import TicketmasterHttpClient
from providers.ticketmaster.price_extractor import PriceExtractor
from providers.ticketmaster.response_parser import ResponseParser


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
    fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "ticketmaster_events_page_0.json"
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
    settings.ticketmaster_page_delay_seconds = 0.0
    settings.ticketmaster_lookahead_days = 5000
    settings.ticketmaster_detail_price_enabled = False
    settings.ticketmaster_detail_price_limit = 0


def test_ticketmaster_parse_success():
    _set_enabled_defaults()
    parser = ResponseParser()
    builder = EventBuilder(price_extractor=PriceExtractor())
    events, total_pages = parser.parse_page_response(_load_fixture())

    assert len(events) == 2
    assert total_pages == 1
    first = builder.build(events[0])
    assert first is not None
    assert first.title == "Istanbul Jazz Night"
    assert first.type == "concert"
    assert first.occurrences[0].venue_name == "Zorlu PSM"
    price = first.occurrences[0].sources[0].price
    assert price.min_value == 250.0
    assert price.max_value == 500.0
    assert price.is_unknown is False
    assert price.resolution.legal_mode == "official_api"


def test_ticketmaster_missing_fields_skips_safely():
    _set_enabled_defaults()
    parser = ResponseParser()
    builder = EventBuilder()
    event = {
        "id": "event_without_url",
        "name": "Broken Event",
        "dates": {"start": {"dateTime": "2026-06-10T18:30:00Z"}},
    }
    parsed = parser.parse_event(event)
    assert parsed is not None
    assert builder.build(parsed) is None


def test_ticketmaster_empty_response():
    parser = ResponseParser()
    events, total_pages = parser.parse_page_response({"page": {"totalPages": 0}})
    assert events == []
    assert total_pages == 0


def test_ticketmaster_auth_error_returns_none():
    _set_enabled_defaults()
    provider = TicketmasterProvider()
    provider.session = DummySession([DummyResponse(status_code=401, payload={})])
    assert provider._fetch_page(0) is None


def test_ticketmaster_pagination_stops_on_last_page(monkeypatch):
    _set_enabled_defaults()
    client = TicketmasterHttpClient()
    pages = [
        {"events": [{"id": "e1"}, {"id": "e2"}], "total_pages": 2},
        {"events": [{"id": "e3"}], "total_pages": 2},
    ]

    def fake_fetch_page(page):
        return pages[page] if page < len(pages) else {"events": [], "total_pages": 2}

    monkeypatch.setattr(client, "fetch_page", fake_fetch_page)
    events = client.fetch_all_pages()
    assert len(events) == 3
    assert client.last_fetched_pages == 2


def test_ticketmaster_category_mapping():
    _set_enabled_defaults()
    parser = ResponseParser()
    builder = EventBuilder()
    event = {
        "id": "event_1",
        "name": "Comedy Night",
        "url": "https://www.ticketmaster.com/event/event_1",
        "dates": {"start": {"dateTime": "2026-06-10T18:30:00Z"}},
        "classifications": [{"segment": {"name": "Comedy"}}],
        "_embedded": {"venues": [{"name": "Test Venue"}]},
    }
    parsed = parser.parse_event(event)
    normalized = builder.build(parsed) if parsed is not None else None
    assert normalized is not None
    assert normalized.type == "standup"


def test_ticketmaster_normalize_event_without_session():
    _set_enabled_defaults()
    settings.ticketmaster_detail_price_enabled = True
    settings.ticketmaster_detail_price_limit = 5
    provider = TicketmasterProvider()
    payload = _load_fixture()
    event = payload["_embedded"]["events"][0]
    normalized = provider._normalize_event(event)
    assert normalized is not None
    assert normalized.title == "Istanbul Jazz Night"
