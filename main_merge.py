"""
Ticketmaster/Municipal ve SerpAPI verilerini birlestirir.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


TM_MUNI_PATH = os.path.join("data", "ticketmaster_municipal", "events.json")
SERPAPI_PATH = os.path.join("data", "serpapi", "events.json")
OUTPUT_DIR = os.path.join("data", "merged")
FINAL_PATH = os.path.join(OUTPUT_DIR, "final.json")
STATS_PATH = os.path.join(OUTPUT_DIR, "stats.json")


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def _extract_external_id(record: Dict[str, Any]) -> str:
    direct_id = record.get("external_id") or record.get("id") or record.get("event_id")
    if direct_id:
        return _normalize_text(direct_id)

    occurrences = record.get("occurrences")
    if isinstance(occurrences, list):
        for occurrence in occurrences:
            if not isinstance(occurrence, dict):
                continue
            sources = occurrence.get("sources")
            if not isinstance(sources, list):
                continue
            for source in sources:
                if not isinstance(source, dict):
                    continue
                source_id = source.get("external_id") or source.get("id")
                if source_id:
                    return _normalize_text(source_id)
    return ""


def _extract_date(record: Dict[str, Any]) -> str:
    occurrences = record.get("occurrences")
    if isinstance(occurrences, list) and occurrences:
        first_occurrence = occurrences[0]
        if isinstance(first_occurrence, dict):
            local_date = first_occurrence.get("local_date")
            if local_date:
                return _normalize_text(local_date)
            start_at = first_occurrence.get("start_at_utc")
            if start_at:
                return _normalize_text(start_at)

    direct_date = record.get("date") or record.get("local_date") or record.get("start_at")
    return _normalize_text(direct_date)


def _build_keys(record: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    external_id = _extract_external_id(record)
    id_key = f"id::{external_id}" if external_id else None

    title = _normalize_text(record.get("title"))
    event_date = _extract_date(record)
    title_date_key = f"title_date::{title}::{event_date}" if title and event_date else None
    return id_key, title_date_key


def _merge_records(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(existing)
    for key, incoming_value in incoming.items():
        if key not in merged or merged[key] in (None, "", [], {}):
            merged[key] = incoming_value
            continue

        existing_value = merged[key]
        if isinstance(existing_value, dict) and isinstance(incoming_value, dict):
            merged[key] = _merge_records(existing_value, incoming_value)
            continue

        if isinstance(existing_value, list) and isinstance(incoming_value, list):
            existing_signatures = {
                json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
                for item in existing_value
            }
            for item in incoming_value:
                signature = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
                if signature not in existing_signatures:
                    existing_value.append(item)
                    existing_signatures.add(signature)
            merged[key] = existing_value
            continue

        if key == "source" and existing_value != incoming_value:
            merged[key] = f"{existing_value}|{incoming_value}"

    return merged


def _load_list(path: str, label: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        print(f"⚠️ 🔄 {label} dosyasi bulunamadi: {path}")
        return []

    try:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 🔄 {label} okunamadi: {type(exc).__name__} - {exc}")
        return []

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    print(f"⚠️ 🔄 {label} liste formatinda degil, bos kabul edildi.")
    return []


def main() -> None:
    print("🔄 Merge basladi.")
    try:
        ticketmaster_municipal = _load_list(TM_MUNI_PATH, "TicketmasterMunicipal")
        serpapi = _load_list(SERPAPI_PATH, "SerpAPI")

        merged_records: List[Dict[str, Any]] = []
        id_index: Dict[str, int] = {}
        title_date_index: Dict[str, int] = {}
        overlap_count = 0

        for record in ticketmaster_municipal + serpapi:
            id_key, title_date_key = _build_keys(record)
            target_idx: Optional[int] = None

            if id_key and id_key in id_index:
                target_idx = id_index[id_key]
            elif title_date_key and title_date_key in title_date_index:
                target_idx = title_date_index[title_date_key]

            if target_idx is None:
                merged_records.append(dict(record))
                target_idx = len(merged_records) - 1
            else:
                merged_records[target_idx] = _merge_records(merged_records[target_idx], record)
                overlap_count += 1

            updated_id_key, updated_title_date_key = _build_keys(merged_records[target_idx])
            if updated_id_key:
                id_index[updated_id_key] = target_idx
            if updated_title_date_key:
                title_date_index[updated_title_date_key] = target_idx

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(FINAL_PATH, "w", encoding="utf-8") as final_file:
            json.dump(merged_records, final_file, ensure_ascii=False, indent=2)

        stats_payload = {
            "total_events": len(merged_records),
            "ticketmaster_municipal_count": len(ticketmaster_municipal),
            "serpapi_count": len(serpapi),
            "overlap_count": overlap_count,
            "last_merge": datetime.now(timezone.utc).isoformat(),
        }
        with open(STATS_PATH, "w", encoding="utf-8") as stats_file:
            json.dump(stats_payload, stats_file, ensure_ascii=False, indent=2)

        print(f"✅ 🔄 Merge tamamlandi. final_count={len(merged_records)} overlap={overlap_count}")
        print(f"✅ Cikti dosyalari: {FINAL_PATH}, {STATS_PATH}")
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 🔄 Merge genel hata: {type(exc).__name__} - {exc}")


if __name__ == "__main__":
    main()
