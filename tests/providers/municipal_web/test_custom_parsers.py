from pathlib import Path

from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.parsing.custom import (
    ArnavutkoyParser,
    AvcilarParser,
    BagcilarParser,
    BahcelievlerParser,
    BakirkoyParser,
    KartalParser,
    MaltepeParser,
    SilivriParser,
    SultanbeyliParser,
    UskudarParser,
)


def _fixture(name: str) -> str:
    path = Path(__file__).resolve().parents[2] / "fixtures" / "municipal_web" / name
    return path.read_text(encoding="utf-8-sig")


def _site(name: str, base_url: str, parser, detail: bool = True) -> MunicipalSite:
    return MunicipalSite(name=name, base_url=base_url, list_urls=[], parser=parser, requires_detail=detail)


def test_arnavutkoy_parser_with_fixture():
    parser = ArnavutkoyParser()
    site = _site("Arnavutköy", "https://www.arnavutkoy.bel.tr", parser)
    html = _fixture("sample_arnavutkoy.html")
    items = parser.parse_list(html, site)
    detail = parser.parse_detail(html, items[0], site)
    assert len(items) == 2
    assert detail.date == "12 Nisan 2026"


def test_avcilar_parser_list_and_detail():
    parser = AvcilarParser()
    site = _site("Avcılar", "https://www.avcilar.bel.tr", parser)
    list_html = '<a href="/etkinlikler/test">Etkinlik</a>'
    detail_html = "<h1>Avcılar Etkinliği</h1><div>Etkinlik Tarihi: 10 Nisan 2026</div><div>Etkinlik Saati: 18:30</div>"
    items = parser.parse_list(list_html, site)
    detail = parser.parse_detail(detail_html, items[0], site)
    assert len(items) == 1
    assert detail.title == "Avcılar Etkinliği"


def test_bagcilar_parser_list_and_detail():
    parser = BagcilarParser()
    site = _site("Bağcılar", "https://www.bagcilar.bel.tr", parser)
    list_html = '<a href="/Activity/Detail/15">Detay</a>'
    detail_html = "<h1>Bağcılar Etkinliği</h1><div>Seans Tarihi: 11 Nisan 2026</div><div>Seans: 20:00</div>"
    item = parser.parse_list(list_html, site)[0]
    detail = parser.parse_detail(detail_html, item, site)
    assert detail.date == "11 Nisan 2026"


def test_bahcelievler_parser_single_page():
    parser = BahcelievlerParser()
    site = _site("Bahçelievler", "https://zirve.bahcelievler.bel.tr", parser, detail=False)
    html = "<h1>Bahar Konseri</h1><div>10 Nisan 2026 19:00</div><div>Yer: Kongre Merkezi</div>"
    items = parser.parse_list(html, site)
    assert len(items) == 1
    assert items[0].venue == "Kongre Merkezi"


def test_bakirkoy_parser_line_based_extraction():
    parser = BakirkoyParser()
    site = _site("Bakırköy", "https://www.bakirkoy.bel.tr", parser, detail=False)
    html = """
    Konser | 12 Nisan 2026 20:00
    Yıldızlar Gecesi
    """
    items = parser.parse_list(html, site)
    assert len(items) == 1
    assert items[0].title == "Yıldızlar Gecesi"


def test_kartal_parser_with_table_fixture():
    parser = KartalParser()
    site = _site("Kartal", "https://www.kartal.bel.tr", parser, detail=False)
    html = _fixture("sample_kartal_table.html")
    items = parser.parse_list(html, site)
    assert len(items) == 1
    assert items[0].title == "Konser Gecesi"


def test_maltepe_parser_news_box():
    parser = MaltepeParser()
    site = _site("Maltepe", "https://www.maltepe.bel.tr", parser, detail=False)
    html = ' <div class="newsBox"><a href="/tr/guncel/etkinlikler/a"><small>13 Nisan 2026</small><h3>Maltepe Etkinliği</h3><p class="newsDescription">Açıklama</p></a></div>'
    items = parser.parse_list(html, site)
    assert len(items) == 1
    assert items[0].title == "Maltepe Etkinliği"


def test_sultanbeyli_parser_uses_dynamic_year_from_block():
    parser = SultanbeyliParser()
    site = _site("Sultanbeyli", "https://kultursanat.sultanbeyli.bel.tr", parser, detail=False)
    html = _fixture("sample_sultanbeyli.html")
    items = parser.parse_list(html, site)
    assert len(items) == 1
    assert items[0].date.endswith("2027")


def test_silivri_parser_list_and_detail():
    parser = SilivriParser()
    site = _site("Silivri", "https://kultursanat.silivri.bel.tr", parser)
    list_html = '<a href="/etkinlik/12/34">Detay</a>'
    detail_html = "<h1>Silivri Etkinlik</h1><div>Etkinlik Tarihi: 15 Nisan 2026</div><div>Etkinlik Saati: 21:00</div>"
    item = parser.parse_list(list_html, site)[0]
    detail = parser.parse_detail(detail_html, item, site)
    assert detail.date == "15 Nisan 2026"


def test_uskudar_parser_sitemap_fixture_and_detail():
    parser = UskudarParser()
    site = _site("Üsküdar", "https://www.uskudar.bel.tr", parser)
    xml = _fixture("sample_uskudar_sitemap.xml")
    detail_html = "<div>Adı: Üsküdar Etkinliği</div><div>Tarih: 16 Nisan 2026</div><div>Saat: 18:00</div>"
    items = parser.parse_list(xml, site)
    detailed = parser.parse_detail(detail_html, RawEventItem(link=items[0].link), site)
    assert len(items) == 2
    assert detailed.title == "Üsküdar Etkinliği"
