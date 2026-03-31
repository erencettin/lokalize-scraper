from providers.municipal_web.event_builder import EventBuilder
from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.parsing.noop_strategy import NoopStrategy
from utils.text_normalizer import clean_text


def _site() -> MunicipalSite:
    return MunicipalSite(name="Test Site", base_url="https://example.com", list_urls=[], parser=NoopStrategy(), requires_detail=False)


def test_build_returns_normalized_event_when_data_is_valid():
    builder = EventBuilder()
    event = builder.build(
        RawEventItem(
            title="Bahar Konseri",
            link="https://example.com/events/1",
            venue="Test Sahne",
            date="10 Nisan 2026",
            time="20:30",
            description="Harika konser gecesi",
        ),
        _site(),
    )
    assert event is not None
    assert event.type == "concert"
    assert event.occurrences[0].venue_name == "Test Sahne"
    assert event.occurrences[0].sources[0].external_id.startswith("web-")


def test_build_uses_fallback_text_for_datetime_parse():
    builder = EventBuilder()
    event = builder.build(
        RawEventItem(
            title="Panel Gecesi",
            link="https://example.com/events/2",
            description="Panel 12 Nisan 2026 19:00",
        ),
        _site(),
    )
    assert event is not None
    assert event.type == "show"


def test_build_returns_none_when_datetime_is_missing():
    builder = EventBuilder()
    event = builder.build(
        RawEventItem(title="Tarihsiz Etkinlik", link="https://example.com/events/3", description="Yakında"),
        _site(),
    )
    assert event is None


def test_clean_text_decodes_html_entities():
    assert clean_text("Kara-&#8220;Kültür&#8221;") == 'Kara-“Kültür”'


def test_build_ignores_dotted_date_as_time():
    builder = EventBuilder()
    event = builder.build(
        RawEventItem(
            title="Güncel Etkinlik",
            link="https://example.com/events/4",
            date="30 Mart 2026",
            description="30.03.2026",
        ),
        _site(),
    )
    assert event is not None
    assert event.occurrences[0].local_time == "00:00"


def test_build_returns_none_when_title_equals_venue_or_site():
    builder = EventBuilder()
    item = RawEventItem(title="Test Site", venue="Test Site", link="https://example.com/events/5", date="12 Nisan 2026")
    assert builder.build(item, _site()) is None


def test_build_returns_none_for_generic_site_like_title():
    builder = EventBuilder()
    site = MunicipalSite(name="Silivri Belediyesi", base_url="https://example.com", list_urls=[], parser=NoopStrategy(), requires_detail=False)
    item = RawEventItem(title="Silivri Belediyesi Kültür Sanat Merkezi", link="https://example.com/events/6", date="12 Nisan 2026")
    assert builder.build(item, site) is None


def test_build_keeps_site_prefixed_real_event_title():
    builder = EventBuilder()
    site = MunicipalSite(name="Silivri Belediyesi", base_url="https://example.com", list_urls=[], parser=NoopStrategy(), requires_detail=False)
    item = RawEventItem(title="Silivri Belediyesi Bahar Şenliği", link="https://example.com/events/7", date="12 Nisan 2026")
    assert builder.build(item, site) is not None


def test_build_detects_explicit_free_price_marker() -> None:
    builder = EventBuilder()
    event = builder.build(
        RawEventItem(
            title="Acik Hava Etkinligi",
            link="https://example.com/events/8",
            date="12 Nisan 2026",
            description="Etkinlik Ucretsizdir",
        ),
        _site(),
    )
    assert event is not None
    price = event.occurrences[0].sources[0].price
    assert price.is_free is True
    assert price.min_value == 0.0
    assert price.max_value == 0.0


def test_build_keeps_price_unknown_when_not_explicit() -> None:
    builder = EventBuilder()
    event = builder.build(
        RawEventItem(
            title="Konser",
            link="https://example.com/events/9",
            date="12 Nisan 2026",
            description="Kontenjan sinirlidir",
        ),
        _site(),
    )
    assert event is not None
    price = event.occurrences[0].sources[0].price
    assert price.is_unknown is True
    assert price.min_value is None
