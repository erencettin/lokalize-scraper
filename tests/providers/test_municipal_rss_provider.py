from pathlib import Path

from config import settings
from providers.municipal_rss import MunicipalRssProvider


class DummyResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


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


def _load_fixture() -> str:
    fixture_path = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "municipal_rss_sample.xml"
    )
    return fixture_path.read_text(encoding="utf-8")


def _set_defaults():
    settings.municipal_rss_enabled = True
    settings.municipal_rss_urls = "https://example.ibb.gov.tr/rss.xml"
    settings.municipal_rss_city_name = "Istanbul"
    settings.municipal_rss_timeout_seconds = 5
    settings.municipal_rss_max_retries = 2


def test_parse_rss_success():
    _set_defaults()
    provider = MunicipalRssProvider()
    provider.session = DummySession([DummyResponse(status_code=200, text=_load_fixture())])
    source = provider._registry.get_sources()[0]
    items = provider._fetch_source_items(source)
    assert len(items) == 2
    event = provider._builder.build(items[0])
    assert event is not None
    assert event.type == "concert"
    assert event.city_name == "Istanbul"


def test_invalid_xml_returns_empty():
    _set_defaults()
    provider = MunicipalRssProvider()
    provider.session = DummySession([DummyResponse(status_code=200, text="<rss><broken>")])
    source = provider._registry.get_sources()[0]
    items = provider._fetch_source_items(source)
    assert items == []


def test_disabled_provider_returns_empty():
    settings.municipal_rss_enabled = False
    provider = MunicipalRssProvider()
    assert provider.fetch_and_parse() == []


def test_empty_urls_returns_empty():
    settings.municipal_rss_enabled = True
    settings.municipal_rss_urls = ""
    provider = MunicipalRssProvider()
    assert provider.fetch_and_parse() == []
