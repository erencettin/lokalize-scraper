import sys
import os
sys.path.append('c:/Lokalize/LokalizeApp/temp_scraper_repo')
from providers.municipal_web.event_builder import EventBuilder
from utils.price_parser import PriceParser

builder = EventBuilder()

class DummyItem:
    def __init__(self, desc, title):
        self.description = desc
        self.title = title

texts = [
    'ucretsiz konser',
    'biletler 150 tl',
    'Biletix - 350.00 TL',
    'Fiyat: 1. Kategori 150 ₺',
    'Biletler Biletix\'te Fiyatları: 500',
    'Bilet Fiyati: Avantajli Donem 125,00',
    'Giriş Ücretsizdir.'
]

for t in texts:
    candidates = builder._extract_price_candidates(DummyItem(t, ''))
    print(f'Text: {t} -> Candidates: {candidates}')
    price_info = PriceParser.resolve_from_text_candidates(
        candidates=candidates,
        currency='TRY',
        source='test',
        legal_mode='test',
        strategy='test',
        confidence=0.5,
        is_authoritative=False,
        is_derived=True
    )
    print(f'  Resolved: min={price_info.min_value}, max={price_info.max_value}, text={price_info.text}')
