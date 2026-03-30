import json
from pathlib import Path

from providers.municipal_web.models import MunicipalSite
from providers.municipal_web.parsing.html_card_strategy import HtmlCardStrategy
from providers.municipal_web.parsing.wp_json_strategy import WpJsonStrategy


def _fixture(name: str) -> str:
    path = Path(__file__).resolve().parents[2] / "fixtures" / "municipal_web" / name
    return path.read_text(encoding="utf-8-sig")


def _strategy() -> WpJsonStrategy:
    fallback = HtmlCardStrategy([r'href="(?P<link>[^"]+)"[^>]*>(?P<body>.*?)</a>'], require_keywords=False)
    return WpJsonStrategy(fallback_strategy=fallback)


def _site(parser) -> MunicipalSite:
    return MunicipalSite(name="Başakşehir Belediyesi", base_url="https://www.basaksehir.bel.tr", list_urls=[], parser=parser, requires_detail=False)


def test_parse_wp_json_fixture_success():
    strategy = _strategy()
    site = _site(strategy)
    payload = _fixture("sample_basaksehir_api.json")
    items = strategy.parse_list(payload, site)
    assert len(items) == 1
    assert items[0].title == "Bahar Konseri"
    assert items[0].date.endswith("2026")
    assert items[0].time == "20:00"


def test_parse_list_falls_back_to_html_strategy():
    strategy = _strategy()
    site = _site(strategy)
    html = '<a href="/etkinlik/oyun">Tiyatro Etkinlik</a>'
    items = strategy.parse_list(html, site)
    assert len(items) == 1
    assert items[0].link == "https://www.basaksehir.bel.tr/etkinlik/oyun"


def test_parse_list_handles_wrapped_json_key():
    strategy = _strategy()
    site = _site(strategy)
    payload = json.dumps({"items": [{"title": {"rendered": "Sergi"}, "link": "https://www.basaksehir.bel.tr/etkinlik/sergi"}]})
    items = strategy.parse_list(payload, site)
    assert len(items) == 1
    assert items[0].title == "Sergi"
