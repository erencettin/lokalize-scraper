"""SerpAPI kalan istek kotasini kontrol eder."""

from __future__ import annotations

import os

import requests


def _write_output(remaining: int) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as file:
            file.write(f"remaining={remaining}\n")


def main() -> None:
    remaining = 0
    try:
        api_key = os.environ["SERPAPI_API_KEY"]
        response = requests.get(
            f"https://serpapi.com/account.json?api_key={api_key}",
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        remaining = int(payload.get("total_searches_left", 0))
    except Exception as exc:  # noqa: BLE001
        remaining = 0
        print(f"❌ 🔍 SerpAPI quota check hatasi: {type(exc).__name__} - {exc}")

    print(f"SerpAPI kalan istek: {remaining}")
    _write_output(remaining)

    if remaining < 10:
        print("::warning::SerpAPI quota critically low!")
    elif remaining < 30:
        print("::warning::SerpAPI quota is low!")


if __name__ == "__main__":
    main()
