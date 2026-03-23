import re

with open('artifacts/probes/etkinlik_raw.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Search for common JSON keys for events
keys = [
    '"venue_name"', '"mekan_adi"', '"start_date"', '"tarih"', 
    '"image_url"', '"resim"', '"bilet_url"', '"slug"'
]

for key in keys:
    match = re.search(key, text)
    if match:
        print(f"FOUND KEY: {key} at position {match.start()}")
        # Print surrounding context
        start = max(0, match.start() - 200)
        end = min(len(text), match.end() + 200)
        print(text[start:end])
        print("-" * 50)

# Check for large script blocks
script_matches = re.finditer(r'<script[^>]*>(.*?)</script>', text, re.DOTALL)
count = 0
for m in script_matches:
    content = m.group(1).strip()
    if len(content) > 1000:
        print(f"\nLARGE SCRIPT BLOCK {count} ({len(content)} chars):")
        print(f"Start: {content[:100]}...")
        if "JJ Pub Kanyon" in content:
            print("  -> CONTAINS 'JJ Pub Kanyon'")
        count += 1
