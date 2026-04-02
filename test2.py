import sys
import logging
logging.basicConfig(level=logging.ERROR)
sys.path.append('c:/Lokalize/LokalizeApp/temp_scraper_repo')
from providers.municipal_web.provider import MunicipalWebProvider
from providers.municipal_web.models import MunicipalSite
from providers.municipal_web.parsing.custom import AvcilarParser

site = MunicipalSite('Avcılar Belediyesi', 'https://www.avcilar.bel.tr', ['https://www.avcilar.bel.tr/etkinlikler'], AvcilarParser(), True)

prov = MunicipalWebProvider()
prov._registry.get_sites = lambda: [site]

events = prov.fetch_and_parse()
print(f'Extracted {len(events)} events')
for e in events[:3]:
    print('Event:', e.title)
    for o in e.occurrences:
        for s in o.sources:
            print('  Price:', s.price.text, s.price.min_value)
