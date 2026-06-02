"""Entry point for merging ticketmaster_municipal + serpapi datasets into data/merged/."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from services.matching_service import MatchingService
from utils.provider_enrichment import build_provider_payload

_TM_EVENTS_PATH = _ROOT / "data" / "ticketmaster_municipal" / "events.json"
_SERPAPI_EVENTS_PATH = _ROOT / "data" / "serpapi" / "events.json"
_BILETIMGO_EVENTS_PATH = _ROOT / "data" / "biletimgo" / "events.json"
_BILETCOM_EVENTS_PATH = _ROOT / "data" / "biletcom" / "events.json"
_OUT_DIR = _ROOT / "data" / "merged"


# ---------------------------------------------------------------------------
# Index helpers
# ---------------------------------------------------------------------------

def _build_indexes(
    records: List[dict],
) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, List[int]]]:
    id_index: Dict[str, int] = {}
    url_index: Dict[str, int] = {}
    title_date_city_index: Dict[str, List[int]] = defaultdict(list)

    for idx, record in enumerate(records):
        keys = MatchingService.build_event_match_keys(record)
        for key in keys.id_keys:
            id_index.setdefault(key, idx)
        for key in keys.url_keys:
            url_index.setdefault(key, idx)
        if keys.title_date_city_key:
            title_date_city_index[keys.title_date_city_key].append(idx)

    return id_index, url_index, dict(title_date_city_index)


# ---------------------------------------------------------------------------
# Source merge helpers
# ---------------------------------------------------------------------------

def _collect_source_ids(occurrence: dict) -> set:
    ids: set = set()
    for source in occurrence.get("sources") or []:
        eid = source.get("external_id")
        if eid:
            ids.add(str(eid))
    return ids


def _merge_into(base: dict, incoming: dict) -> None:
    """Fold incoming event's occurrences/sources into base in-place."""
    base_occs: List[dict] = base.setdefault("occurrences", [])
    for inc_occ in (incoming.get("occurrences") or []):
        inc_date = inc_occ.get("local_date", "")
        matched_occ = next(
            (o for o in base_occs if o.get("local_date") == inc_date), None
        )
        if matched_occ is None:
            base_occs.append(deepcopy(inc_occ))
        else:
            existing_ids = _collect_source_ids(matched_occ)
            for source in (inc_occ.get("sources") or []):
                eid = source.get("external_id")
                if eid and str(eid) in existing_ids:
                    continue
                matched_occ.setdefault("sources", []).append(deepcopy(source))


# ---------------------------------------------------------------------------
# Provider payload rebuild
# ---------------------------------------------------------------------------

def _rebuild_provider_payload(record: dict) -> None:
    """Recompute providers/provider_tags/source_urls from all sources in record."""
    providers: List[str] = []
    source_urls: List[str] = []
    candidate_texts: List[str] = []

    for occ in (record.get("occurrences") or []):
        if occ.get("venue_name"):
            candidate_texts.append(str(occ["venue_name"]))
        if occ.get("district"):
            candidate_texts.append(str(occ["district"]))
        for source in (occ.get("sources") or []):
            prov = source.get("provider")
            if prov:
                providers.append(str(prov))
            for url_field in ("source_url", "deep_link_url"):
                val = source.get(url_field)
                if val:
                    source_urls.append(str(val))

    payload = build_provider_payload(
        providers=providers,
        source_urls=source_urls,
        candidate_texts=candidate_texts,
    )
    record.update(payload)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def _provider_combo_key(record: dict) -> str:
    return "+".join(record.get("providers") or [record.get("provider", "unknown")])


def _provider_tag_combo_key(record: dict) -> str:
    tags = record.get("provider_tags") or []
    return "+".join(tags) if tags else (record.get("provider_label") or "unknown")


def _compute_stats(
    merged: List[dict],
    tm_count: int,
    serpapi_count: int,
    biletimgo_count: int,
    biletcom_count: int,
    overlap_count: int,
) -> dict:
    multi_provider = sum(1 for r in merged if len(r.get("providers") or []) > 1)

    provider_combo: Dict[str, int] = defaultdict(int)
    provider_tag_combo: Dict[str, int] = defaultdict(int)
    for r in merged:
        provider_combo[_provider_combo_key(r)] += 1
        provider_tag_combo[_provider_tag_combo_key(r)] += 1

    return {
        "total_events": len(merged),
        "total_events_before_dedup": tm_count + serpapi_count + biletimgo_count + biletcom_count,
        "total_events_after_dedup": len(merged),
        "ticketmaster_municipal_count": tm_count,
        "serpapi_count": serpapi_count,
        "biletimgo_count": biletimgo_count,
        "biletcom_count": biletcom_count,
        "overlap_count": overlap_count,
        "multi_provider_event_count": multi_provider,
        "provider_combo_counts": dict(sorted(provider_combo.items())),
        "provider_tag_combo_counts": dict(sorted(provider_tag_combo.items())),
        "last_merge": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> List[dict]:
    if not path.exists():
        print(f"[WARN] File not found, skipping: {path}")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as exc:
        print(f"[ERROR] Failed to load {path}: {exc}")
        return []


def main() -> int:
    print("=== Merge started ===")

    tm_events = _load_json(_TM_EVENTS_PATH)
    serpapi_events = _load_json(_SERPAPI_EVENTS_PATH)
    biletimgo_events = _load_json(_BILETIMGO_EVENTS_PATH)
    biletcom_events = _load_json(_BILETCOM_EVENTS_PATH)

    print(f"Loaded tm_municipal={len(tm_events)} serpapi={len(serpapi_events)} biletimgo={len(biletimgo_events)} biletcom={len(biletcom_events)}")

    # Start merged list from TM/Municipal (deep copy)
    merged: List[dict] = [deepcopy(r) for r in tm_events]

    # Build lookup indexes
    id_index, url_index, tdc_index = _build_indexes(merged)

    overlap_count = 0

    for serpapi_record in serpapi_events + biletimgo_events + biletcom_events:
        match_idx = MatchingService.find_event_match_index(
            record=serpapi_record,
            merged_records=merged,
            id_index=id_index,
            url_index=url_index,
            title_date_city_index=tdc_index,
        )
        if match_idx is not None:
            _merge_into(merged[match_idx], serpapi_record)
            overlap_count += 1
        else:
            new_idx = len(merged)
            new_record = deepcopy(serpapi_record)
            merged.append(new_record)
            # Update indexes with new record
            new_keys = MatchingService.build_event_match_keys(new_record)
            for key in new_keys.id_keys:
                id_index.setdefault(key, new_idx)
            for key in new_keys.url_keys:
                url_index.setdefault(key, new_idx)
            if new_keys.title_date_city_key:
                tdc_index.setdefault(new_keys.title_date_city_key, []).append(new_idx)

    # Rebuild provider payload for all merged records
    for record in merged:
        _rebuild_provider_payload(record)

    print(f"Merged: total={len(merged)} overlap={overlap_count}")

    # Save outputs
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    (_OUT_DIR / "final.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    stats = _compute_stats(merged, len(tm_events), len(serpapi_events), len(biletimgo_events), len(biletcom_events), overlap_count)
    (_OUT_DIR / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved {len(merged)} events → {_OUT_DIR}")
    print("=== Merge finished ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
