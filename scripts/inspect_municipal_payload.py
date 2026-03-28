import os
import re
import sys
from typing import Any, Dict, List, Tuple

import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


DATE_PATTERNS = [
    re.compile(r"\d{4}-\d{2}-\d{2}"),
    re.compile(r"\d{2}\.\d{2}\.\d{4}"),
    re.compile(r"\d{1,2}/\d{1,2}/\d{4}"),
    re.compile(r"\d{1,2}\s+[A-Za-zÃ‡ÄÄ°Ã–ÅÃœÃ§ÄŸÄ±Ã¶ÅŸÃ¼]+\s+\d{4}"),
]

TIME_PATTERNS = [
    re.compile(r"\d{2}:\d{2}"),
    re.compile(r"\d{2}\.\d{2}"),
]


def _looks_like_date(text: str) -> bool:
    if not text:
        return False
    return any(pattern.search(text) for pattern in DATE_PATTERNS)


def _looks_like_time(text: str) -> bool:
    if not text:
        return False
    return any(pattern.search(text) for pattern in TIME_PATTERNS)


def _extract_candidates(value: Any, path: str = "") -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = f"{path}.{key}" if path else key
            results.extend(_extract_candidates(item, next_path))
        return results
    if isinstance(value, list):
        for index, item in enumerate(value[:20]):
            next_path = f"{path}[{index}]"
            results.extend(_extract_candidates(item, next_path))
        return results

    if isinstance(value, (int, float)):
        text = str(value)
        if _looks_like_date(text):
            results.append((path, text))
        return results

    if isinstance(value, str):
        text = value.strip()
        if _looks_like_date(text) or _looks_like_time(text):
            results.append((path, text))
        return results

    return results


def _print_entry(title: str, entry: Dict[str, Any]) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("-" * 100)
    print(f"keys: {list(entry.keys())}")
    entry_title = str(entry.get("title", {}).get("rendered", "") or entry.get("title") or "").strip()
    entry_link = str(entry.get("link") or "").strip()
    print(f"title: {entry_title}")
    print(f"link: {entry_link}")

    candidates = _extract_candidates(entry)
    if not candidates:
        print("no date/time-like fields found")
        return

    print("\nfirst 30 date/time candidates:")
    for path, value in candidates[:30]:
        print(f"- {path}: {value}")


def _fetch_json(url: str) -> Any:
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json()


def main() -> None:
    endpoints = [
        ("kultur.istanbul event_listing", "https://kultur.istanbul/wp-json/wp/v2/event_listing?per_page=3"),
        ("kultur.istanbul posts", "https://kultur.istanbul/wp-json/wp/v2/posts?per_page=3"),
        ("orkestralar.ibb.istanbul posts", "https://orkestralar.ibb.istanbul/wp-json/wp/v2/posts?per_page=3&categories=1"),
    ]

    for label, url in endpoints:
        try:
            payload = _fetch_json(url)
        except Exception as exc:
            print(f"{label} failed: {exc}")
            continue

        if not isinstance(payload, list) or not payload:
            print(f"{label} returned no list payload")
            continue

        _print_entry(f"{label} sample", payload[0])


if __name__ == "__main__":
    main()
