"""Constants for municipal web provider."""

from typing import Dict, Set

from utils.constants import CATEGORY_MAP, TURKISH_MONTHS

ISTANBUL_TIMEZONE = "Europe/Istanbul"
MAX_DESCRIPTION_LENGTH = 250
MAX_BODY_TEXT_LENGTH = 400
EXTERNAL_ID_HASH_LENGTH = 16

DEFAULT_ACCEPT_HEADER = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
DEFAULT_ACCEPT_LANGUAGE_HEADER = "tr-TR,tr;q=0.9"
DEFAULT_USER_AGENT = "LokalizeAppBot/1.0 (contact: iletisim.lokalizeapp@gmail.com)"

RETRYABLE_STATUS_CODES: Set[int] = {429, 500, 502, 503, 504}
GENERIC_TITLE_WORDS: Set[str] = {
    "belediyesi",
    "kültür",
    "kultur",
    "sanat",
    "merkezi",
    "merkez",
    "salonu",
    "salon",
    "binası",
    "bina",
    "konser",
    "tiyatro",
    "etkinlik",
    "alan",
    "alanı",
    "tesisi",
}

EVENT_KEYWORDS = (
    "konser",
    "tiyatro",
    "sergi",
    "festival",
    "gosteri",
    "gösteri",
    "sinema",
    "söyleşi",
    "soylesi",
    "etkinlik",
    "kültür",
    "kultur",
    "sanat",
    "çocuk",
    "cocuk",
)

MONTH_NAMES: Dict[int, str] = {
    1: "Ocak",
    2: "Şubat",
    3: "Mart",
    4: "Nisan",
    5: "Mayıs",
    6: "Haziran",
    7: "Temmuz",
    8: "Ağustos",
    9: "Eylül",
    10: "Ekim",
    11: "Kasım",
    12: "Aralık",
}
