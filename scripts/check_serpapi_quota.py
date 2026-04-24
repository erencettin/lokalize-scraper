"""Check remaining SerpAPI quota and expose it as a GitHub Actions step output."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests

_ACCOUNT_URL = "https://serpapi.com/account.json"


def _set_output(name: str, value: str) -> None:
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")
    print(f"::set-output name={name}::{value}")


def main() -> int:
    api_key = os.environ.get("SERPAPI_API_KEY", "").strip()
    if not api_key:
        print("[WARN] SERPAPI_API_KEY not set — defaulting remaining=0")
        _set_output("remaining", "0")
        return 0

    try:
        resp = requests.get(_ACCOUNT_URL, params={"api_key": api_key}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"[ERROR] SerpAPI account check failed: {exc}")
        _set_output("remaining", "0")
        return 1

    remaining = data.get("plan_searches_left", 0)
    total = data.get("plan_monthly_analytics", 0)
    used = data.get("searches_this_month", 0)

    print(f"[INFO] SerpAPI quota: remaining={remaining} used={used} total={total}")
    _set_output("remaining", str(remaining))
    return 0


if __name__ == "__main__":
    sys.exit(main())
