import requests
from bs4 import BeautifulSoup
import re

url = "https://mobilet.com/tr/event/cimri-51915/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
res = requests.get(url, headers=headers)
soup = BeautifulSoup(res.text, 'html.parser')

lines = [line.strip() for line in soup.get_text(separator='\n').split('\n') if line.strip()]
print(f"Total lines: {len(lines)}")
for i, line in enumerate(lines[:30]):
    print(f"{i}: {line}")

date_pattern = re.compile(r'\d{1,2}\s+(?:ocak|şubat|subat|mart|nisan|mayıs|mayis|haziran|temmuz|ağustos|agustos|eylül|eylul|ekim|kasım|kasim|aralık|aralik)\s+\d{4},\s+\d{2}:\d{2}', re.IGNORECASE)
for line in lines:
    if date_pattern.search(line):
         print(f"FOUND DATE MATCH: {line}")
