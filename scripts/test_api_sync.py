import logging
import sys
import os
import uuid
import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from clients.api_client import BackendApiClient

logging.basicConfig(level=logging.INFO)

def test_api_sync():
    client = BackendApiClient(base_url="http://localhost:5170")
    
    # We need a valid City ID and Category ID from the database for the test to work
    # For testing, we can use empty guids if the API allows, or known ones.
    # The C# MatchingService will create the occurrence/venue for us.
    
    # Let's mock the 'Kadıköy Stand Up Gecesi' exactly as the user wanted.
    city_id = "11111111-1111-1111-1111-111111111111" # We will seed this
    category_id = "22222222-2222-2222-2222-222222222222" # We will seed this
    
    start_at_1 = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)).isoformat()
    start_at_2 = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)).isoformat()

    payload = [
        # Passo - Occurrence 1 (Kadıköy Sahne)
        {
            "provider": "Passo",
            "externalId": "passo-101",
            "title": "Kadıköy Stand Up Gecesi",
            "description": "Harika bir komedi gecesi.",
            "imageUrl": "https://example.com/standup.jpg",
            "cityId": city_id,
            "categoryId": category_id,
            "venueName": "Kadıköy Sahne",
            "startAt": start_at_1,
            "sourceUrl": "https://passo.com.tr/etkinlik/101",
            "prices": [
                {"label": "Genel Satış", "amount": 150.0, "currency": "TRY"},
                {"label": "Öğrenci İndirimi", "amount": 100.0, "currency": "TRY"}
            ]
        },
        # Biletix - Occurrence 1 (Kadıköy Sahne)
        {
            "provider": "Biletix",
            "externalId": "biletix-202",
            "title": "Kadıköy Stand Up Gecesi",
            "description": "Harika bir komedi gecesi.",
            "imageUrl": "https://example.com/standup.jpg",
            "cityId": city_id,
            "categoryId": category_id,
            "venueName": "Kadıköy Sahne",
            "startAt": start_at_1,
            "sourceUrl": "https://biletix.com/etkinlik/202",
            "prices": [
                {"label": "Genel Giriş", "amount": 160.0, "currency": "TRY"},
                {"label": "Balkon", "amount": 250.0, "currency": "TRY"}
            ]
        },
        # Mobilet - Occurrence 2 (Moda Sahnesi) -> Different Venue & Date!
        {
            "provider": "Mobilet",
            "externalId": "mobilet-303",
            "title": "Kadıköy Stand Up Gecesi",
            "description": "Harika bir komedi gecesi.",
            "imageUrl": "https://example.com/standup.jpg",
            "cityId": city_id,
            "categoryId": category_id,
            "venueName": "Moda Sahnesi",
            "startAt": start_at_2,
            "sourceUrl": "https://mobilet.com/etkinlik/303",
            "prices": [
                {"label": "Tam", "amount": 140.0, "currency": "TRY"}
            ]
        }
    ]
    
    client.sync_events(payload)

if __name__ == "__main__":
    test_api_sync()
