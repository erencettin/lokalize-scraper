import requests
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
url = 'https://etkinlik.io/etkinlik/276690/tuzbiber-6li'
r = requests.get(url, headers=headers)
with open('artifacts/probes/etkinlik_raw.html', 'w', encoding='utf-8') as f:
    f.write(r.text)
print(f"Saved {len(r.text)} bytes to artifacts/probes/etkinlik_raw.html")
