import logging
import sys
import os
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO)

def test_supabase():
    url = "https://pswgebfhwojkxyunlkbu.supabase.co"
    key = "dummy_key" # The error happens DURING client creation (auth init), key doesn't need to be real for the TypeErro
    try:
        logging.info("Testing Supabase client creation...")
        client: Client = create_client(url, key)
        logging.info("Success! Client created without TypeError.")
    except TypeError as e:
        logging.error(f"FAIL: Caught expected TypeError: {e}")
    except Exception as e:
        logging.info(f"Caught other exception (fine, expected with dummy key): {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_supabase()
