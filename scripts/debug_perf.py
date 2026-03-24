from providers.biletix import BiletixProvider
import json

def debug():
    p = BiletixProvider()
    data = p._get_api_data('getPerformanceList/5H823/INTERNET/tr')
    if data and data.get("data"):
        print(json.dumps(data["data"][0], indent=2))
    else:
        print(f"No data for 5H823: {data}")

if __name__ == "__main__":
    debug()
