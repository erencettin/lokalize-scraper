import logging
import sys
import os

# Emulate main.py environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from providers.passo import PassoProvider

def diagnostic():
    logging.info("Starting Passo Diagnostic (Detailed Skip Trace)...")
    provider = PassoProvider()
    raw = provider._fetch_all_raw_events()
    logging.info(f"Raw items: {len(raw)}")
    
    if raw:
        item = raw[0]
        id = item.get("id")
        name = item.get("name")
        date = item.get("date") or item.get("startDate")
        
        logging.info(f"Item 0: ID={id}, Name={name}, Date={date}")
        
        # Manually trace _parse_event
        if not id or not name:
             logging.error("Skip reason: id or name missing")
        
        parsed_date = provider._parse_date(date)
        if not parsed_date:
             logging.error(f"Skip reason: date parsing failed for '{date}'")
        else:
             logging.info(f"Parsed Date: {parsed_date}")
             
        event = provider._parse_event(item)
        logging.info(f"Final _parse_event result: {event}")

if __name__ == "__main__":
    diagnostic()
