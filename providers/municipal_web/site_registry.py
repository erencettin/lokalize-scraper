"""Site registry for municipal web provider."""

from __future__ import annotations

from typing import Iterable, List

from providers.municipal_web.models import MunicipalSite
from providers.municipal_web.parsing import HtmlCardStrategy, LabelDetailStrategy, NoopStrategy, PassthroughStrategy, WpJsonStrategy
from providers.municipal_web.parsing.custom import ArnavutkoyParser, AvcilarParser, BagcilarParser, BahcelievlerParser, BakirkoyParser, KartalParser, MaltepeParser, SilivriParser, SultanbeyliParser, UskudarParser


GENERIC_CARD_PATTERNS = [
    r'href="(?P<link>https?://[^"]*(?:etkinlik|etkinlikler|kultur-sanat|eventcalendar|konser|tiyatro|sergi|festival|takvim|movie|events)[^"]*)"[^>]*>(?P<body>.*?)</a>',
    r'href="(?P<link>/[^"]*(?:etkinlik|etkinlikler|kultur-sanat|eventcalendar|konser|tiyatro|sergi|festival|takvim|movie|events)[^"]*)"[^>]*>(?P<body>.*?)</a>',
]


class SiteRegistry:
    """Central source of municipal site metadata and parser assignment."""

    def get_sites(self) -> List[MunicipalSite]:
        passthrough = PassthroughStrategy()
        detail = LabelDetailStrategy()
        noop = NoopStrategy()
        wp_passthrough = WpJsonStrategy(HtmlCardStrategy(GENERIC_CARD_PATTERNS, passthrough), passthrough)
        wp_detail = WpJsonStrategy(HtmlCardStrategy(GENERIC_CARD_PATTERNS, detail), detail)

        sites = self._custom_sites()
        sites.extend(self._build_sites(self._passthrough_defs(), wp_passthrough, False))
        sites.extend(self._build_sites(self._detail_defs(), wp_detail, True))
        sites.extend(self._build_sites(self._noop_defs(), noop, False))
        return sites

    def _build_sites(self, defs: Iterable[tuple[str, str, list[str]]], parser, requires_detail: bool) -> List[MunicipalSite]:
        return [MunicipalSite(name=name, base_url=base, list_urls=urls, parser=parser, requires_detail=requires_detail) for name, base, urls in defs]

    def _custom_sites(self) -> List[MunicipalSite]:
        return [
            MunicipalSite("Arnavutköy Belediyesi", "https://www.arnavutkoy.bel.tr", ["https://www.arnavutkoy.bel.tr/tum-etkinlikler", "https://www.arnavutkoy.bel.tr/etkinlikler/egitim-etkinlikleri"], ArnavutkoyParser(), True),
            MunicipalSite("Avcılar Belediyesi", "https://www.avcilar.bel.tr", ["https://www.avcilar.bel.tr/etkinlikler", "https://www.avcilar.bel.tr/etkinlikler/konu/etkinlik"], AvcilarParser(), True),
            MunicipalSite("Bağcılar Belediyesi", "https://www.bagcilar.bel.tr", ["https://www.bagcilar.bel.tr/etkinlikler"], BagcilarParser(), True),
            MunicipalSite("Bahçelievler Belediyesi", "https://zirve.bahcelievler.bel.tr", ["https://zirve.bahcelievler.bel.tr/en/"], BahcelievlerParser(), False),
            MunicipalSite("Bakırköy Belediyesi", "https://www.bakirkoy.bel.tr", ["https://www.bakirkoy.bel.tr/tr/etkinliklerimiz", "https://bakirkoy.bel.tr/tr/"], BakirkoyParser(), False),
            MunicipalSite("Maltepe Belediyesi", "https://www.maltepe.bel.tr", ["https://www.maltepe.bel.tr/tr/liste/etkinlikler", "https://www.maltepe.bel.tr/tr/liste/etkinlikler?gnc=true"], MaltepeParser(), False),
            MunicipalSite("Kartal Belediyesi", "https://www.kartal.bel.tr", ["https://www.kartal.bel.tr/KulturSanat/EtkinlikTakvimi", "https://e-belediye.kartal.bel.tr/Etkinlik/Takvim"], KartalParser(), False),
            MunicipalSite("Sultanbeyli Belediyesi", "https://kultursanat.sultanbeyli.bel.tr", ["https://kultursanat.sultanbeyli.bel.tr/"], SultanbeyliParser(), False),
            MunicipalSite("Silivri Belediyesi", "https://kultursanat.silivri.bel.tr", ["https://kultursanat.silivri.bel.tr/", "https://kultursanat.silivri.bel.tr/?tip=4"], SilivriParser(), True),
            MunicipalSite("Üsküdar Belediyesi", "https://www.uskudar.bel.tr", ["https://www.uskudar.bel.tr/tr/sitemap/eventcalendar", "https://www.uskudar.bel.tr/tr/main/eventcalendar"], UskudarParser(), True),
        ]

    def _passthrough_defs(self) -> list[tuple[str, str, list[str]]]:
        return [
            ("Başakşehir Belediyesi", "https://www.basaksehir.bel.tr", ["https://www.basaksehir.bel.tr/kultur-sanat-ajandasi", "https://www.basaksehir.bel.tr/kultur-sanat-ve-sosyal-isler"]),
            ("Bayrampaşa Belediyesi", "https://www.bayrampasa.bel.tr", ["https://www.bayrampasa.bel.tr/wp-json/wp/v2/etkinlik?per_page=50", "https://bayrampasa.bel.tr/popular/etkinlikler"]),
            ("Beşiktaş Belediyesi", "https://www.besiktas.bel.tr", ["https://www.besiktas.bel.tr/wp-json/wp/v2/etkinlik?per_page=50", "https://www.besiktas.bel.tr/"]),
            ("Fatih Belediyesi", "https://www.fatih.bel.tr", ["https://www.fatih.bel.tr/tr/main/kultursanat/kategori/konser/2", "https://www.fatih.bel.tr/tr/main/kultursanat/"]),
            ("Gaziosmanpaşa Belediyesi", "https://kultursanat.gaziosmanpasa.bel.tr", ["https://kultursanat.gaziosmanpasa.bel.tr/menu", "https://kultursanat.gaziosmanpasa.bel.tr/ara/bolum"]),
            ("Güngören Belediyesi", "https://gungoren.bel.tr", ["https://sehirsempozyumu.gungoren.bel.tr/", "https://uoits.gungoren.bel.tr/"]),
            ("Kağıthane Belediyesi", "https://www.kagithane.bel.tr", []),
            ("Büyükçekmece Belediyesi", "https://www.buyukcekmece.bel.tr", ["https://www.buyukcekmece.bel.tr/kultur-sanat/etkinlikler", "https://www.buyukcekmece.bel.tr/kultur-sanat/", "https://www.buyukcekmece.bel.tr/"]),
        ]

    def _detail_defs(self) -> list[tuple[str, str, list[str]]]:
        return [
            ("Beylikdüzü Belediyesi", "https://www.beylikduzu.istanbul", ["https://www.beylikduzu.istanbul/etkinlikler", "https://www.beylikduzu.istanbul/etkinlikler?category=konser"]),
            ("Beyoğlu Belediyesi", "https://beyoglu.bel.tr", ["https://beyoglu.bel.tr/wp-json/wp/v2/posts?per_page=50&_embed", "https://beyoglu.bel.tr/kultur-sanat/"]),
            ("Çatalca Belediyesi", "https://etkinlik.catalca.bel.tr", ["https://etkinlik.catalca.bel.tr/"]),
            ("Esenler Belediyesi", "https://esenler.bel.tr", ["https://esenler.bel.tr/kultur-sanat/etkinlikler/", "https://esenler.bel.tr/kultur-sanat/"]),
            ("Esenyurt Belediyesi", "https://www.esenyurt.bel.tr", ["https://www.esenyurt.bel.tr/etkinlikler"]),
            ("Eyüpsultan Belediyesi", "https://www.eyupsultan.bel.tr", ["https://www.eyupsultan.bel.tr/basvuru/etkinlikler"]),
            ("Küçükçekmece Belediyesi", "https://kucukcekmecekultursanat.com", ["https://kucukcekmecekultursanat.com/wp-json/tribe/events/v1/events?per_page=50", "https://kucukcekmecekultursanat.com/tum-etkinlikler/", "https://kucukcekmecekultursanat.com/"]),
        ]

    def _noop_defs(self) -> list[tuple[str, str, list[str]]]:
        return [
            ("Sarıyer Belediyesi", "https://sariyer.bel.tr", []),
            ("Sultangazi Belediyesi", "https://sultangazi.bel.tr", []),
            ("Şişli Belediyesi", "https://www.sisli.bel.tr", []),
            ("Zeytinburnu Belediyesi", "https://www.zeytinburnu.bel.tr", []),
        ]
