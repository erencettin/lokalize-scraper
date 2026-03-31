import json
from pathlib import Path

from providers.serpapi_events import SerpApiEventsProvider


class DummySerpApiClient:
    def __init__(self, payload):
        self._payload = payload
        self.request_count = 0
        self.is_enabled = True

    def search(self, *, engine: str, query: str, location=None, hl="en", gl="us"):
        assert engine == "google_events"
        self.request_count += 1
        return self._payload


def _load_fixture() -> dict:
    fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "serpapi" / "serpapi_events_sample.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_serpapi_events_provider_maps_events():
    payload = _load_fixture()
    provider = SerpApiEventsProvider(serpapi_client=DummySerpApiClient(payload))

    events = provider.fetch_events("Istanbul")

    assert len(events) >= 2
    first = events[0]
    assert first.source == "serpapi_google_events"
    assert first.external_id is not None
    assert first.city_name == "Istanbul"
    assert first.occurrences
    source = first.occurrences[0].sources[0]
    assert source.provider == "serpapi_google_events"
    assert source.price.min_value == 500.0
    assert source.price.max_value == 500.0
    assert source.price.is_unknown is False
    assert source.price.resolution.legal_mode == "search_indexed_api"
