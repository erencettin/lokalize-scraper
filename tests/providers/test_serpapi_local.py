import json
from pathlib import Path

from providers.serpapi_local import SerpApiLocalProvider


class DummySerpApiClient:
    def __init__(self, payload):
        self._payload = payload
        self.request_count = 0
        self.is_enabled = True

    def search(self, *, engine: str, query: str):
        assert engine == "google_local"
        self.request_count += 1
        return self._payload


def _load_fixture() -> dict:
    fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "serpapi" / "serpapi_local_sample.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_serpapi_local_provider_maps_places():
    payload = _load_fixture()
    provider = SerpApiLocalProvider(serpapi_client=DummySerpApiClient(payload))

    places = provider.fetch_places("Istanbul")

    assert len(places) >= 2
    first = places[0]
    assert first.source == "serpapi_google_local"
    assert first.external_id is not None
    assert first.title != ""
    assert first.city == "Istanbul"
    assert first.category in {"restaurant", "cafe", "bar", "game_center"}
