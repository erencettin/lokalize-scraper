from datetime import datetime
from pathlib import Path

import pytz

from config import settings
from providers.biletinial import category_map, city_map
from providers.biletinial.event_builder import EventBuilder, build_affiliate_url
from providers.biletinial.parser import parse_feed_items
from providers.biletinial.provider import BiletinialProvider


def _load_fixture() -> bytes:
    fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "biletinial_feed_sample.xml"
    return fixture_path.read_bytes()


# ---------------------------------------------------------------------------
# category_map
# ---------------------------------------------------------------------------

def test_category_map_main_categories():
    assert category_map.resolve("tiyatro", "yetiskin-tiyatrosu") == "theatre"
    assert category_map.resolve("muzik", "Pop") == "concert"


def test_category_map_subcategory_override():
    assert category_map.resolve("tiyatro", "cocuk-tiyatrosu") == "kids"


def test_category_map_unknown_returns_none():
    assert category_map.resolve("sinema", "Film") is None
    assert category_map.resolve("", "") is None


# ---------------------------------------------------------------------------
# city_map
# ---------------------------------------------------------------------------

def test_city_map_known_slugs():
    assert city_map.resolve("samsun") == "Samsun"
    assert city_map.resolve("afyon") == "Afyonkarahisar"
    assert city_map.resolve("kibris") == "Kıbrıs"


def test_city_map_istanbul_variants_collapse():
    assert city_map.resolve("istanbul-avrupa") == "İstanbul"
    assert city_map.resolve("istanbul-anadolu") == "İstanbul"


def test_city_map_strips_trailing_dash():
    assert city_map.resolve("elazig-") == "Elazığ"


def test_city_map_unknown_returns_none():
    assert city_map.resolve("narnia") is None


# ---------------------------------------------------------------------------
# build_affiliate_url
# ---------------------------------------------------------------------------

def test_build_affiliate_url_appends_required_params():
    url = build_affiliate_url("https://biletinial.com/tr-tr/muzik/melike-sahin-konseri-bkm", "lokalize")
    assert url is not None
    assert url.startswith("https://biletinial.com/tr-tr/muzik/melike-sahin-konseri-bkm?")
    assert "utm_source=affiliate" in url
    assert "utm_medium=affiliate-partner" in url
    assert "utm_campaign=buy-ticket" in url
    assert "utm_content=lokalize" in url
    assert "a_aid=lokalize" in url


def test_build_affiliate_url_rejects_untrusted_host():
    assert build_affiliate_url("https://evil-biletinial.com/tr-tr/muzik/sahte", "lokalize") is None


def test_build_affiliate_url_rejects_lookalike_host():
    # "biletinial.com" must not match as a substring of an unrelated domain.
    assert build_affiliate_url("https://notbiletinial.com/tr-tr/muzik/sahte", "lokalize") is None


def test_build_affiliate_url_rejects_non_http_scheme():
    assert build_affiliate_url("javascript:alert(1)", "lokalize") is None


def test_build_affiliate_url_empty_link():
    assert build_affiliate_url("", "lokalize") is None


# ---------------------------------------------------------------------------
# EventBuilder
# ---------------------------------------------------------------------------

def _now_utc():
    return datetime(2026, 1, 1, tzinfo=pytz.UTC)


def _items_by_id(items, item_id):
    return next(i for i in items if i["id"] == item_id)


def test_event_builder_theatre_item():
    items = parse_feed_items(_load_fixture())
    item = _items_by_id(items, "16657813")  # Hamlet
    builder = EventBuilder()
    settings.biletinial_affiliate_id = "lokalize"

    event = builder.build(item, _now_utc())

    assert event is not None
    assert event.title == "Hamlet"
    assert event.type == "theatre"
    assert event.category == "theatre"
    assert event.city_name == "Samsun"
    assert event.external_id == "16657813"
    assert event.venue == "Samsun Ata Sahne"
    assert event.occurrences[0].local_date == "2099-09-20"
    assert event.occurrences[0].local_time == "20:00"

    source = event.occurrences[0].sources[0]
    assert source.price.min_value == 560.0
    assert source.price.is_unknown is False
    assert "a_aid=lokalize" in source.ticket_url


def test_event_builder_concert_item():
    items = parse_feed_items(_load_fixture())
    item = _items_by_id(items, "17873250")  # Melike Şahin Konseri
    builder = EventBuilder()
    settings.biletinial_affiliate_id = "lokalize"

    event = builder.build(item, _now_utc())

    assert event is not None
    assert event.type == "concert"
    assert event.city_name == "İstanbul"


def test_event_builder_kids_subcategory_override():
    items = parse_feed_items(_load_fixture())
    item = _items_by_id(items, "17900001")  # Küçük Prens (cocuk-tiyatrosu)
    builder = EventBuilder()

    event = builder.build(item, _now_utc())

    assert event is not None
    assert event.type == "kids"
    assert event.city_name == "Elazığ"  # "elazig-" trailing dash handled


def test_event_builder_kibris_city():
    items = parse_feed_items(_load_fixture())
    item = _items_by_id(items, "17900002")  # Kıbrıs Caz Festivali
    builder = EventBuilder()

    event = builder.build(item, _now_utc())

    assert event is not None
    assert event.city_name == "Kıbrıs"


def test_event_builder_skips_untrusted_link_host():
    items = parse_feed_items(_load_fixture())
    item = _items_by_id(items, "17900003")
    builder = EventBuilder()

    assert builder.build(item, _now_utc()) is None


def test_event_builder_skips_unmapped_category():
    items = parse_feed_items(_load_fixture())
    item = _items_by_id(items, "17900004")  # sinema
    builder = EventBuilder()

    assert builder.build(item, _now_utc()) is None


def test_event_builder_skips_past_event():
    items = parse_feed_items(_load_fixture())
    item = _items_by_id(items, "17900005")
    builder = EventBuilder()

    assert builder.build(item, _now_utc()) is None


# ---------------------------------------------------------------------------
# Provider end-to-end (with stubbed HTTP fetch)
# ---------------------------------------------------------------------------

def test_provider_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "biletinial_enabled", False)
    provider = BiletinialProvider()
    assert provider.fetch_and_parse() == []


def test_provider_fetch_and_parse(monkeypatch):
    monkeypatch.setattr(settings, "biletinial_enabled", True)
    monkeypatch.setattr(settings, "biletinial_feed_urls", "https://feed.biletinial.com/sitemap-facebook/2")
    monkeypatch.setattr(settings, "biletinial_affiliate_id", "lokalize")

    provider = BiletinialProvider()
    monkeypatch.setattr(provider._http, "fetch_feed", lambda url: _load_fixture())

    events = provider.fetch_and_parse()

    # 7 items total; 4 are skipped (untrusted host, unmapped category, past event)
    # plus 3 valid ones (theatre, concert, kids, Kıbrıs concert) -> 4 valid events.
    assert len(events) == 4
    titles = {e.title for e in events}
    assert "Hamlet" in titles
    assert "Melike Şahin Konseri" in titles
    assert "Küçük Prens" in titles
    assert "Kıbrıs Caz Festivali" in titles
