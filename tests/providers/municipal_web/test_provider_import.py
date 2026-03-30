from datetime import datetime

import pytz

from config import settings
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo
from providers.municipal_web import MunicipalWebProvider
from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.parsing.base_strategy import SiteParser
from providers.municipal_web.provider import MunicipalWebProvider as ProviderFromModule


class DummyHttpClient:
    def setup_session(self):
        return None

    def close_session(self):
        return None

    def can_fetch(self, url: str) -> bool:
        return True

    def fetch_text(self, url: str) -> str:
        return "<html></html>"


class DummyParser(SiteParser):
    def parse_list(self, html: str, site: MunicipalSite):
        return [
            RawEventItem(title="Test Konser", link="https://example.com/e/1", date="10 Nisan 2030", time="20:00", description="Konser"),
            RawEventItem(title="Test Konser", link="https://example.com/e/2", date="10 Nisan 2030", time="20:00", description="Konser"),
        ]

    def parse_detail(self, html: str, item: RawEventItem, site: MunicipalSite) -> RawEventItem:
        return item


class DummyRegistry:
    def get_sites(self):
        parser = DummyParser()
        return [MunicipalSite(name="Dummy", base_url="https://example.com", list_urls=["https://example.com/list"], parser=parser, requires_detail=False)]


class DummyBuilder:
    def build(self, item: RawEventItem, site: MunicipalSite):
        start_at = datetime(2030, 4, 10, 17, 0, tzinfo=pytz.UTC)
        occurrence = NormalizedOccurrence(
            start_at_utc=start_at,
            local_date="2030-04-10",
            local_time="20:00",
            venue_name=site.name,
            sources=[
                NormalizedSource(
                    provider="MunicipalWeb",
                    title=item.title,
                    source_url=item.link,
                    price=PriceInfo(text="Fiyat bilgisi yok", currency="TRY"),
                )
            ],
        )
        return NormalizedEvent(title=item.title, type="concert", city_name="Istanbul", occurrences=[occurrence])


def test_import_chain():
    assert MunicipalWebProvider is ProviderFromModule


def test_disabled_provider_returns_empty():
    original = settings.municipal_web_enabled
    settings.municipal_web_enabled = False
    try:
        assert MunicipalWebProvider().fetch_and_parse() == []
    finally:
        settings.municipal_web_enabled = original


def test_provider_deduplicates_by_matching_service_key():
    enabled = settings.municipal_web_enabled
    lookahead = settings.municipal_web_lookahead_days
    max_items = settings.municipal_web_max_items_per_site
    settings.municipal_web_enabled = True
    settings.municipal_web_lookahead_days = 3650
    settings.municipal_web_max_items_per_site = 20
    try:
        provider = MunicipalWebProvider(http_client=DummyHttpClient(), site_registry=DummyRegistry(), event_builder=DummyBuilder())
        events = provider.fetch_and_parse()
    finally:
        settings.municipal_web_enabled = enabled
        settings.municipal_web_lookahead_days = lookahead
        settings.municipal_web_max_items_per_site = max_items
    assert len(events) == 1
