"""Maps Biletinial feed city slugs (g:custom_label_0) to canonical DB city names."""
from __future__ import annotations

from typing import Optional

# Feed city slug -> canonical Turkish province name (as stored in Cities table).
# Covers all 81 provinces plus Biletinial-specific variants:
#   - istanbul-avrupa / istanbul-anadolu -> İstanbul (single city in DB)
#   - afyon -> Afyonkarahisar (official province name)
#   - kibris -> Kıbrıs (not a Turkish province, but kept as its own city)
_SLUG_TO_CITY: dict[str, str] = {
    "adana": "Adana",
    "adiyaman": "Adıyaman",
    "afyon": "Afyonkarahisar",
    "afyonkarahisar": "Afyonkarahisar",
    "agri": "Ağrı",
    "aksaray": "Aksaray",
    "amasya": "Amasya",
    "ankara": "Ankara",
    "antalya": "Antalya",
    "ardahan": "Ardahan",
    "artvin": "Artvin",
    "aydin": "Aydın",
    "balikesir": "Balıkesir",
    "bartin": "Bartın",
    "batman": "Batman",
    "bayburt": "Bayburt",
    "bilecik": "Bilecik",
    "bingol": "Bingöl",
    "bitlis": "Bitlis",
    "bolu": "Bolu",
    "burdur": "Burdur",
    "bursa": "Bursa",
    "canakkale": "Çanakkale",
    "cankiri": "Çankırı",
    "corum": "Çorum",
    "denizli": "Denizli",
    "diyarbakir": "Diyarbakır",
    "duzce": "Düzce",
    "edirne": "Edirne",
    "elazig": "Elazığ",
    "erzincan": "Erzincan",
    "erzurum": "Erzurum",
    "eskisehir": "Eskişehir",
    "gaziantep": "Gaziantep",
    "giresun": "Giresun",
    "gumushane": "Gümüşhane",
    "hakkari": "Hakkari",
    "hatay": "Hatay",
    "igdir": "Iğdır",
    "isparta": "Isparta",
    "istanbul": "İstanbul",
    "istanbul-avrupa": "İstanbul",
    "istanbul-anadolu": "İstanbul",
    "izmir": "İzmir",
    "kahramanmaras": "Kahramanmaraş",
    "karabuk": "Karabük",
    "karaman": "Karaman",
    "kars": "Kars",
    "kastamonu": "Kastamonu",
    "kayseri": "Kayseri",
    "kibris": "Kıbrıs",
    "kilis": "Kilis",
    "kirikkale": "Kırıkkale",
    "kirklareli": "Kırklareli",
    "kirsehir": "Kırşehir",
    "kocaeli": "Kocaeli",
    "konya": "Konya",
    "kutahya": "Kütahya",
    "malatya": "Malatya",
    "manisa": "Manisa",
    "mardin": "Mardin",
    "mersin": "Mersin",
    "mugla": "Muğla",
    "mus": "Muş",
    "nevsehir": "Nevşehir",
    "nigde": "Niğde",
    "ordu": "Ordu",
    "osmaniye": "Osmaniye",
    "rize": "Rize",
    "sakarya": "Sakarya",
    "samsun": "Samsun",
    "sanliurfa": "Şanlıurfa",
    "siirt": "Siirt",
    "sinop": "Sinop",
    "sirnak": "Şırnak",
    "sivas": "Sivas",
    "tekirdag": "Tekirdağ",
    "tokat": "Tokat",
    "trabzon": "Trabzon",
    "tunceli": "Tunceli",
    "usak": "Uşak",
    "van": "Van",
    "yalova": "Yalova",
    "yozgat": "Yozgat",
    "zonguldak": "Zonguldak",
}


def resolve(slug: str) -> Optional[str]:
    """Return the canonical city name for a feed city slug, or None if unknown.

    Trailing "-" characters are stripped to tolerate feed typos
    (e.g. "elazig-" -> "elazig" -> "Elazığ").
    """
    normalized = (slug or "").strip().lower().rstrip("-")
    return _SLUG_TO_CITY.get(normalized)
