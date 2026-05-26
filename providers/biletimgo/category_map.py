_MAP: dict[str, str] = {
    # BiletimGO canonical categories → internal type
    "konser": "concert",
    "festival": "festival",
    "sahne": "theatre",
    "tiyatro": "theatre",
    "stand-up": "standup",
    "workshop": "workshop",
    "eğitim": "workshop",
    "egitim": "workshop",
    "topluluklar": "workshop",
    "kamp": "festival",
    "parti": "concert",
    "çocuk etkinlikleri": "kids",
    "cocuk etkinlikleri": "kids",
    "diğer": "social",
    "diger": "social",
}


def resolve(raw: str | None) -> str:
    if not raw:
        return "other"
    return _MAP.get(raw.strip().lower(), raw.strip().lower())
