import json
from providers.biletix import BiletixProvider

def debug():
    p = BiletixProvider()
    data = p._get_api_data('getPerformanceList/5H823/INTERNET/tr')
    if data and data.get("data"):
        # Save to file to ensure we get the full content
        with open('full_perf_raw.json', 'w', encoding='utf-8') as f:
            json.dump(data["data"][0], f, indent=2)
        print("Raw JSON saved to full_perf_raw.json")
    else:
        print(f"No data for 5H823: {data}")

if __name__ == "__main__":
    debug()
