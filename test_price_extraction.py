import sys
from utils.price_parser import PriceParser
import re

patterns = re.compile(
    r"(?:ucretsiz|ücretsiz|free|bedava|"
    r"₺\s*\d[\d.,]*(?:\s*-\s*₺?\s*\d[\d.,]*)?|"
    r"\d[\d.,]*(?:\s*-\s*\d[\d.,]*)?\s*(?:tl|try|₺)|"
    r"(?:fiyat|bilet).{0,40}?\b\d[\d.,]*(?:\s*-\s*\d[\d.,]*)?\b)",
    re.IGNORECASE,
)

samples = [
    "Biletix - 350.00 TL",
    "Fiyat: 1. Kategori 150 ₺",
    "Biletler Biletix'te Fiyatları: 500",
    "Bilet Fiyati: Avantajli Donem 125,00",
    "Giriş Ücretsizdir.",
    "2. Kategori - 250",
    "1. Adım - 600",
]

print("--- REGEX EXTRACTION TEST ---")
for text in samples:
    matches = patterns.findall(text)
    print(f"Text: '{text}' -> Matches: {matches}")

print("\n--- PRICE PARSER TEST ---")
for text in samples:
    # Simulating what happens in resolve_from_text_candidates
    candidates = [text]
    price = PriceParser.resolve_from_text_candidates(
        candidates=candidates,
        currency="TRY",
        source="test",
        legal_mode="test",
        strategy="test",
        confidence=1.0,
        is_authoritative=False,
        is_derived=True
    )
    print(f"Text: '{text}' -> Min: {price.min_value}, Max: {price.max_value}, IsFree: {price.is_free}, Unknown: {price.is_unknown}, OutText: '{price.text}'")

