from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.parsing.html_card_strategy import HtmlCardStrategy


def _site(parser) -> MunicipalSite:
    return MunicipalSite(name="Demo Belediye", base_url="https://demo.bel.tr", list_urls=[], parser=parser, requires_detail=True)


def test_html_card_strategy_extracts_unique_items():
    strategy = HtmlCardStrategy([r'href="(?P<link>[^"]+)"[^>]*>(?P<body>.*?)</a>'])
    site = _site(strategy)
    html = '<a href="/etkinlik/konser">Konser Etkinlik</a><a href="/etkinlik/konser">Konser Etkinlik</a>'
    items = strategy.parse_list(html, site)
    assert len(items) == 1
    assert items[0].title == "Konser Etkinlik"
    assert items[0].link == "https://demo.bel.tr/etkinlik/konser"


def test_html_card_strategy_parse_detail_via_label_strategy():
    strategy = HtmlCardStrategy([r'href="(?P<link>[^"]+)"[^>]*>(?P<body>.*?)</a>'])
    site = _site(strategy)
    detail_html = """
    <h1>Etkinlik Adı</h1>
    <div>Yer: Merkez Salon</div>
    <div>Tarih: 12 Nisan 2026</div>
    <div>Saat: 19:30</div>
    <p>Açıklama: Deneme metni</p>
    <img src="/poster.jpg" />
    """
    result = strategy.parse_detail(detail_html, RawEventItem(link="https://demo.bel.tr/e/1"), site)
    assert result.title == "Etkinlik Adı"
    assert result.venue == "Merkez Salon"
    assert result.date == "12 Nisan 2026"
    assert result.time == "19:30"
    assert result.image_url == "https://demo.bel.tr/poster.jpg"
