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
    "topluluklar": "social",   # topluluk buluşması = sosyal etkinlik
    "kamp": "workshop",        # kamp etkinlikleri genellikle eğitim/atölye amaçlı
    "parti": "social",         # parti = sosyal eğlence, konser değil
    "çocuk etkinlikleri": "kids",
    "cocuk etkinlikleri": "kids",
    "diğer": "social",
    "diger": "social",
}


def resolve(raw: str | None) -> str:
    if not raw:
        return "other"
    return _MAP.get(raw.strip().lower(), raw.strip().lower())
