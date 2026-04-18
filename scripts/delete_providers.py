"""
Üsküdar Belediyesi ve Avcılar Belediyesi etkinliklerini siler.
Kullanım: python scripts/delete_providers.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.supabase_client import SupabaseClient

PROVIDERS_TO_DELETE = [
    "Üsküdar Belediyesi",
    "Avcılar Belediyesi",
]

def main():
    client = SupabaseClient().client

    for provider in PROVIDERS_TO_DELETE:
        # Count first
        count_res = client.from_("events") \
            .select("id", count="exact") \
            .eq("source_provider", provider) \
            .execute()
        count = count_res.count or 0
        print(f"{provider}: {count} etkinlik bulundu.")

        if count == 0:
            continue

        confirm = input(f"  → {count} etkinliği silmek istiyor musun? (evet/hayır): ").strip().lower()
        if confirm != "evet":
            print(f"  Atlandı: {provider}")
            continue

        # Delete in batches
        deleted = 0
        while True:
            batch_res = client.from_("events") \
                .select("id") \
                .eq("source_provider", provider) \
                .limit(100) \
                .execute()
            ids = [row["id"] for row in (batch_res.data or [])]
            if not ids:
                break
            client.from_("events").delete().in_("id", ids).execute()
            deleted += len(ids)
            print(f"  Silindi: {deleted}/{count}")

        print(f"  ✓ {provider} tamamlandı.")

if __name__ == "__main__":
    main()
