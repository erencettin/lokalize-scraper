"""
Merge Ticketmaster/Municipal and SerpAPI event outputs into one de-duplicated feed.
"""

from __future__ import annotations

import copy
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from services.matching_service import MatchingService, build_occurrence_dedup_key
from utils.constants import CANONICAL_PROVIDER_ALIASES, CANONICAL_PROVIDER_ORDER, PROVIDER_UI_TAG_MAP
from utils.text_normalizer import TextNormalizer, clean_text


TM_MUNI_PATH = os.path.join("data", "ticketmaster_municipal", "events.json")
SERPAPI_PATH = os.path.join("data", "serpapi", "events.json")
OUTPUT_DIR = os.path.join("data", "merged")
FINAL_PATH = os.path.join(OUTPUT_DIR, "final.json")
STATS_PATH = os.path.join(OUTPUT_DIR, "stats.json")

_PROVIDER_ORDER_INDEX = {name: idx for idx, name in enumerate(CANONICAL_PROVIDER_ORDER)}
_PROVIDER_ALIAS_LOOKUP = {
    re.sub(r"[^a-z0-9]+", "", alias.strip().lower()): canonical
    for alias, canonical in CANONICAL_PROVIDER_ALIASES.items()
}
for canonical in CANONICAL_PROVIDER_ORDER:
    _PROVIDER_ALIAS_LOOKUP[re.sub(r"[^a-z0-9]+", "", canonical.lower())] = canonical

_MUNICIPAL_DOMAIN_LABELS: Optional[List[Tuple[str, str]]] = None
_MUNICIPAL_TOKEN_LABELS: Optional[Dict[str, str]] = None


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _is_missing(value: Any) -> bool:
    return value in (None, "", [], {})


def _clean_string(value: Any) -> str:
    if value is None:
        return ""
    return clean_text(str(value))


def _provider_lookup_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean_string(value).lower())


def _canonicalize_provider(value: Any) -> Optional[str]:
    raw = _clean_string(value)
    if not raw:
        return None
    lookup_key = _provider_lookup_key(raw)
    if lookup_key in {"unknown", "none", "null", "na", "n/a"}:
        return None
    if raw in CANONICAL_PROVIDER_ORDER:
        return raw
    return _PROVIDER_ALIAS_LOOKUP.get(lookup_key, raw)


def _sort_unique_providers(values: Iterable[str]) -> List[str]:
    unique: List[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _canonicalize_provider(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return sorted(unique, key=lambda item: (_PROVIDER_ORDER_INDEX.get(item, 999), item))


def _normalize_url_for_match(value: Any) -> str:
    raw = _clean_string(value)
    if not raw:
        return ""
    parsed = urlparse(raw)
    if not parsed.scheme and not parsed.netloc and "." in raw and "/" not in raw:
        parsed = urlparse(f"https://{raw}")

    host = (parsed.netloc or "").lower()
    if "@" in host:
        host = host.split("@", 1)[-1]
    if ":" in host:
        host = host.split(":", 1)[0]
    host = host.removeprefix("www.")
    path = parsed.path or ""
    if path != "/":
        path = path.rstrip("/")
    return f"{host}{path}".strip()


def _extract_host(value: Any) -> str:
    raw = _clean_string(value)
    if not raw:
        return ""
    parsed = urlparse(raw)
    if not parsed.netloc and "." in raw:
        parsed = urlparse(f"https://{raw}")
    host = (parsed.netloc or "").lower()
    if "@" in host:
        host = host.split("@", 1)[-1]
    if ":" in host:
        host = host.split(":", 1)[0]
    return host.removeprefix("www.")


def _normalize_date_key(value: Any) -> str:
    raw = _clean_string(value)
    if not raw:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw
    if re.match(r"^\d{4}-\d{2}-\d{2}[tT]", raw):
        return raw[:10]
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.date().isoformat()
    except ValueError:
        return TextNormalizer.normalize_for_match(raw)


def _extract_record_date(record: Dict[str, Any]) -> str:
    occurrences = record.get("occurrences")
    if isinstance(occurrences, list):
        for occurrence in occurrences:
            if not isinstance(occurrence, dict):
                continue
            for key in ("local_date", "date", "start_at_utc", "start_at"):
                normalized = _normalize_date_key(occurrence.get(key))
                if normalized:
                    return normalized
    for key in ("date", "local_date", "start_at_utc", "start_at"):
        normalized = _normalize_date_key(record.get(key))
        if normalized:
            return normalized
    return ""


def _is_event_record(record: Dict[str, Any]) -> bool:
    if not isinstance(record, dict):
        return False

    record_type = _provider_lookup_key(record.get("_record_type"))
    if record_type == "serpapilocal":
        return False
    if record_type == "serpapievents":
        return True

    source_key = _provider_lookup_key(record.get("source"))
    if source_key == "serpapigooglelocal":
        return False
    if source_key in {"serpapigoogleevents", "serpapievents"}:
        return True

    occurrences = record.get("occurrences")
    if isinstance(occurrences, list) and any(isinstance(item, dict) for item in occurrences):
        return True

    title = _clean_string(record.get("title") or record.get("name"))
    has_date = any(
        _clean_string(record.get(key)) for key in ("date", "local_date", "start_at", "start_at_utc")
    )
    return bool(title and has_date)


def _merge_unique_values(existing: List[Any], incoming: List[Any]) -> List[Any]:
    merged = list(existing)
    signatures = {
        json.dumps(item, ensure_ascii=False, sort_keys=True, default=_json_default)
        for item in merged
    }
    for item in incoming:
        signature = json.dumps(item, ensure_ascii=False, sort_keys=True, default=_json_default)
        if signature in signatures:
            continue
        merged.append(item)
        signatures.add(signature)
    return merged


def _merge_pipe_values(existing: Any, incoming: Any) -> str:
    parts: List[str] = []
    seen: set[str] = set()
    for raw_value in (existing, incoming):
        for chunk in _clean_string(raw_value).split("|"):
            cleaned = chunk.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            parts.append(cleaned)
    return "|".join(parts)


def _merge_dict_values(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing)
    for key, incoming_value in incoming.items():
        existing_value = merged.get(key)
        if isinstance(existing_value, dict) and isinstance(incoming_value, dict):
            merged[key] = _merge_dict_values(existing_value, incoming_value)
            continue
        if isinstance(existing_value, list) and isinstance(incoming_value, list):
            merged[key] = _merge_unique_values(existing_value, incoming_value)
            continue
        if _is_missing(existing_value) and not _is_missing(incoming_value):
            merged[key] = incoming_value
    return merged


def _extract_source_urls(record: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        cleaned = _clean_string(value)
        if not cleaned:
            return
        normalized = _normalize_url_for_match(cleaned) or cleaned.lower()
        if normalized in seen:
            return
        seen.add(normalized)
        urls.append(cleaned)

    for value in record.get("source_urls", []) if isinstance(record.get("source_urls"), list) else []:
        add(value)

    for key in ("source_url", "url", "link"):
        add(record.get(key))

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
                add(source.get("source_url"))
                add(source.get("deep_link_url"))
                add(source.get("url"))

    return urls


def _extract_providers(record: Dict[str, Any]) -> List[str]:
    found: List[str] = []
    for value in record.get("providers", []) if isinstance(record.get("providers"), list) else []:
        provider = _canonicalize_provider(value)
        if provider:
            found.append(provider)

    for key in ("provider", "source", "_record_type"):
        raw_value = record.get(key)
        if isinstance(raw_value, str):
            chunks = [chunk.strip() for chunk in raw_value.split("|")]
        else:
            chunks = [raw_value]
        for chunk in chunks:
            provider = _canonicalize_provider(chunk)
            if provider:
                found.append(provider)

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
                provider = _canonicalize_provider(source.get("provider"))
                if provider:
                    found.append(provider)

    return _sort_unique_providers(found)


def _load_municipal_maps() -> Tuple[List[Tuple[str, str]], Dict[str, str]]:
    global _MUNICIPAL_DOMAIN_LABELS, _MUNICIPAL_TOKEN_LABELS
    if _MUNICIPAL_DOMAIN_LABELS is not None and _MUNICIPAL_TOKEN_LABELS is not None:
        return _MUNICIPAL_DOMAIN_LABELS, _MUNICIPAL_TOKEN_LABELS

    domain_map: Dict[str, str] = {}
    token_map: Dict[str, str] = {}
    try:
        from providers.municipal_web.site_registry import SiteRegistry

        for site in SiteRegistry().get_sites():
            label = _clean_string(site.name)
            if not label:
                continue

            token = TextNormalizer.normalize_for_match(label.replace("Belediyesi", ""))
            token = token.strip()
            if token:
                token_map[token] = label

            for candidate in [site.base_url, *site.list_urls]:
                host = _extract_host(candidate)
                if host:
                    domain_map[host] = label
    except Exception:
        domain_map = {}
        token_map = {}

    _MUNICIPAL_DOMAIN_LABELS = sorted(domain_map.items(), key=lambda item: len(item[0]), reverse=True)
    _MUNICIPAL_TOKEN_LABELS = token_map
    return _MUNICIPAL_DOMAIN_LABELS, _MUNICIPAL_TOKEN_LABELS


def _resolve_municipal_labels(record: Dict[str, Any]) -> List[str]:
    domain_map, token_map = _load_municipal_maps()
    labels: List[str] = []
    seen: set[str] = set()

    def add(label: str) -> None:
        cleaned = _clean_string(label)
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        labels.append(cleaned)

    for url in _extract_source_urls(record):
        host = _extract_host(url)
        if not host:
            continue
        for domain, label in domain_map:
            if host == domain or host.endswith(f".{domain}"):
                add(label)
                break
        else:
            district_match = re.search(r"([a-z0-9-]+)\.bel\.tr$", host)
            if district_match:
                token = TextNormalizer.normalize_for_match(district_match.group(1))
                if token in token_map:
                    add(token_map[token])

    text_sources: List[str] = []
    for key in ("district", "municipality", "venue", "venue_name", "address", "title", "description"):
        text = _clean_string(record.get(key))
        if text:
            text_sources.append(text)

    occurrences = record.get("occurrences")
    if isinstance(occurrences, list):
        for occurrence in occurrences:
            if not isinstance(occurrence, dict):
                continue
            for key in ("district", "venue", "venue_name"):
                text = _clean_string(occurrence.get(key))
                if text:
                    text_sources.append(text)

    for text in text_sources:
        normalized_text = TextNormalizer.normalize_for_match(text)
        for token, label in token_map.items():
            if token and token in normalized_text:
                add(label)
        explicit = re.search(r"([a-zA-ZçğıöşüÇĞİÖŞÜ\s-]+)\s+belediyesi", text, flags=re.IGNORECASE)
        if explicit:
            token = TextNormalizer.normalize_for_match(explicit.group(1))
            if token in token_map:
                add(token_map[token])
            else:
                add(f"{_clean_string(explicit.group(1))} Belediyesi")

    return labels


def _build_provider_tags(record: Dict[str, Any], providers: Sequence[str]) -> List[str]:
    tags: List[str] = []
    seen: set[str] = set()

    def add(tag_value: str) -> None:
        tag = _clean_string(tag_value)
        if not tag or tag in seen:
            return
        seen.add(tag)
        tags.append(tag)

    for provider in providers:
        if provider == "MunicipalWeb":
            municipal_labels = _resolve_municipal_labels(record)
            if municipal_labels:
                for label in municipal_labels:
                    add(label)
            else:
                add("MunicipalWeb")
            continue
        add(PROVIDER_UI_TAG_MAP.get(provider, provider))

    return tags


def _sanitize_source(source: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = dict(source)
    provider = _canonicalize_provider(cleaned.get("provider"))
    if provider:
        cleaned["provider"] = provider
    return cleaned


def _extract_occurrence_date_time(occurrence: Dict[str, Any]) -> Tuple[str, str]:
    local_date = _clean_string(occurrence.get("local_date") or occurrence.get("date"))
    local_time = _clean_string(occurrence.get("local_time") or occurrence.get("time"))

    start_at = _clean_string(occurrence.get("start_at_utc") or occurrence.get("start_at"))
    if not local_date:
        local_date = _normalize_date_key(start_at)
    if not local_time and start_at and re.match(r"^\d{4}-\d{2}-\d{2}[tT]\d{2}:\d{2}", start_at):
        local_time = start_at[11:16]
    if len(local_time) >= 5:
        local_time = local_time[:5]
    return local_date, local_time


def _build_occurrence_key(event_title: str, occurrence: Dict[str, Any]) -> str:
    local_date, local_time = _extract_occurrence_date_time(occurrence)
    if local_date or local_time:
        return build_occurrence_dedup_key(event_title, local_date, local_time)
    venue = TextNormalizer.normalize_for_match(_clean_string(occurrence.get("venue_name") or occurrence.get("venue")))
    start_at = TextNormalizer.normalize_for_match(_clean_string(occurrence.get("start_at_utc") or occurrence.get("start_at")))
    return f"{TextNormalizer.normalize_for_match(event_title)}|{venue}|{start_at}"


def _merge_sources(existing_sources: List[Dict[str, Any]], incoming_sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()

    def build_key(source: Dict[str, Any]) -> str:
        provider = _canonicalize_provider(source.get("provider")) or _clean_string(source.get("provider"))
        external_id = TextNormalizer.normalize_for_match(_clean_string(source.get("external_id") or source.get("id")))
        url_key = _normalize_url_for_match(source.get("source_url") or source.get("url") or source.get("deep_link_url"))
        fallback_signature = json.dumps(source, ensure_ascii=False, sort_keys=True, default=_json_default)
        return f"{provider}|{external_id}|{url_key}|{fallback_signature if not (provider or external_id or url_key) else ''}"

    for source in [*existing_sources, *incoming_sources]:
        if not isinstance(source, dict):
            continue
        normalized = _sanitize_source(source)
        key = build_key(normalized)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(normalized)

    return merged


def _merge_occurrence(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing)
    for key in ("start_at_utc", "local_date", "local_time", "timezone", "venue_name", "district"):
        if _is_missing(merged.get(key)) and not _is_missing(incoming.get(key)):
            merged[key] = incoming.get(key)

    existing_sources = merged.get("sources") if isinstance(merged.get("sources"), list) else []
    incoming_sources = incoming.get("sources") if isinstance(incoming.get("sources"), list) else []
    merged["sources"] = _merge_sources(existing_sources, incoming_sources)
    return merged


def _merge_occurrences(event_title: str, existing: Any, incoming: Any) -> List[Dict[str, Any]]:
    existing_list = [item for item in existing if isinstance(item, dict)] if isinstance(existing, list) else []
    incoming_list = [item for item in incoming if isinstance(item, dict)] if isinstance(incoming, list) else []

    merged = [dict(item) for item in existing_list]
    occurrence_index: Dict[str, int] = {}
    for idx, occurrence in enumerate(merged):
        occurrence_index[_build_occurrence_key(event_title, occurrence)] = idx
        if isinstance(occurrence.get("sources"), list):
            occurrence["sources"] = _merge_sources([], occurrence["sources"])

    for occurrence in incoming_list:
        normalized = dict(occurrence)
        if isinstance(normalized.get("sources"), list):
            normalized["sources"] = _merge_sources([], normalized["sources"])
        key = _build_occurrence_key(event_title, normalized)
        existing_idx = occurrence_index.get(key)
        if existing_idx is None:
            merged.append(normalized)
            occurrence_index[key] = len(merged) - 1
        else:
            merged[existing_idx] = _merge_occurrence(merged[existing_idx], normalized)

    return merged


def _pick_best_description(existing_value: Any, incoming_value: Any) -> Any:
    existing_text = _clean_string(existing_value)
    incoming_text = _clean_string(incoming_value)
    if not incoming_text:
        return existing_value
    if not existing_text:
        return incoming_value
    return incoming_value if len(incoming_text) > len(existing_text) else existing_value


def _prepare_record(record: Dict[str, Any]) -> Dict[str, Any]:
    prepared: Dict[str, Any] = copy.deepcopy(record)
    occurrences = prepared.get("occurrences")
    if isinstance(occurrences, list):
        for occurrence in occurrences:
            if not isinstance(occurrence, dict):
                continue
            if isinstance(occurrence.get("sources"), list):
                occurrence["sources"] = _merge_sources([], occurrence["sources"])
    return _enrich_provider_fields(prepared)


def _enrich_provider_fields(record: Dict[str, Any]) -> Dict[str, Any]:
    providers = _extract_providers(record)
    provider_tags = _build_provider_tags(record, providers)
    source_urls = _extract_source_urls(record)

    record["providers"] = providers
    record["provider_tags"] = provider_tags
    record["provider_label"] = ", ".join(provider_tags) if provider_tags else None
    record["source_urls"] = source_urls
    if providers:
        record["provider"] = providers[0]
    return record


def _merge_records(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(existing)

    event_title = _clean_string(merged.get("title") or incoming.get("title") or merged.get("name") or incoming.get("name"))
    merged["occurrences"] = _merge_occurrences(event_title, merged.get("occurrences"), incoming.get("occurrences"))

    for key, incoming_value in incoming.items():
        if key in {"providers", "provider_tags", "provider_label", "source_urls", "provider", "occurrences"}:
            continue

        existing_value = merged.get(key)
        if key == "description":
            merged[key] = _pick_best_description(existing_value, incoming_value)
            continue

        if key in {"latitude", "longitude"}:
            if existing_value is None and incoming_value is not None:
                merged[key] = incoming_value
            continue

        if key in {"image", "image_url", "thumbnail_url", "venue_name", "venue", "place_name", "price_min", "price_max"}:
            if _is_missing(existing_value) and not _is_missing(incoming_value):
                merged[key] = incoming_value
            continue

        if key == "source" and not _is_missing(existing_value) and not _is_missing(incoming_value):
            if _clean_string(existing_value) != _clean_string(incoming_value):
                merged[key] = _merge_pipe_values(existing_value, incoming_value)
            continue

        if isinstance(existing_value, dict) and isinstance(incoming_value, dict):
            merged[key] = _merge_dict_values(existing_value, incoming_value)
            continue

        if isinstance(existing_value, list) and isinstance(incoming_value, list):
            merged[key] = _merge_unique_values(existing_value, incoming_value)
            continue

        if _is_missing(existing_value) and not _is_missing(incoming_value):
            merged[key] = incoming_value

    return _enrich_provider_fields(merged)


def merge_events(records: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    merged_records: List[Dict[str, Any]] = []
    id_index: Dict[str, int] = {}
    url_index: Dict[str, int] = {}
    title_date_city_index: Dict[str, List[int]] = defaultdict(list)
    overlap_count = 0

    for raw_record in records:
        if not isinstance(raw_record, dict):
            continue
        record = _prepare_record(raw_record)

        match_idx = MatchingService.find_event_match_index(
            record=record,
            merged_records=merged_records,
            id_index=id_index,
            url_index=url_index,
            title_date_city_index=title_date_city_index,
        )

        if match_idx is None:
            merged_records.append(record)
            target_idx = len(merged_records) - 1
        else:
            merged_records[match_idx] = _merge_records(merged_records[match_idx], record)
            target_idx = match_idx
            overlap_count += 1

        keys = MatchingService.build_event_match_keys(merged_records[target_idx])
        for id_key in keys.id_keys:
            id_index[id_key] = target_idx
        for url_key in keys.url_keys:
            url_index[url_key] = target_idx
        if keys.title_date_city_key:
            indexes = title_date_city_index[keys.title_date_city_key]
            if target_idx not in indexes:
                indexes.append(target_idx)

    return merged_records, overlap_count


def _build_stats(
    *,
    total_before: int,
    merged_records: Sequence[Dict[str, Any]],
    overlap_count: int,
    ticketmaster_municipal_count: int,
    serpapi_count: int,
) -> Dict[str, Any]:
    provider_combo_counts: Counter[str] = Counter()
    provider_tag_combo_counts: Counter[str] = Counter()
    multi_provider_event_count = 0

    for record in merged_records:
        providers = record.get("providers") if isinstance(record.get("providers"), list) else []
        provider_tags = record.get("provider_tags") if isinstance(record.get("provider_tags"), list) else []

        if providers:
            provider_combo_counts["+".join(providers)] += 1
            if len(providers) > 1:
                multi_provider_event_count += 1
        if provider_tags:
            provider_tag_combo_counts["+".join(provider_tags)] += 1

    return {
        "total_events": len(merged_records),
        "total_events_before_dedup": total_before,
        "total_events_after_dedup": len(merged_records),
        "ticketmaster_municipal_count": ticketmaster_municipal_count,
        "serpapi_count": serpapi_count,
        "overlap_count": overlap_count,
        "multi_provider_event_count": multi_provider_event_count,
        "provider_combo_counts": dict(sorted(provider_combo_counts.items())),
        "provider_tag_combo_counts": dict(sorted(provider_tag_combo_counts.items())),
        "last_merge": datetime.now(timezone.utc).isoformat(),
    }


def _load_list(path: str, label: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        print(f"WARN {label} file not found: {path}")
        return []
    try:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {label} read failed: {type(exc).__name__} - {exc}")
        return []

    if not isinstance(payload, list):
        print(f"WARN {label} payload is not a list, ignored.")
        return []

    return [item for item in payload if isinstance(item, dict)]


def main() -> None:
    print("Merge started.")
    try:
        ticketmaster_municipal_raw = _load_list(TM_MUNI_PATH, "TicketmasterMunicipal")
        serpapi_raw = _load_list(SERPAPI_PATH, "SerpAPI")

        ticketmaster_municipal = [item for item in ticketmaster_municipal_raw if _is_event_record(item)]
        serpapi = [item for item in serpapi_raw if _is_event_record(item)]
        all_events = [*ticketmaster_municipal, *serpapi]

        merged_records, overlap_count = merge_events(all_events)
        stats_payload = _build_stats(
            total_before=len(all_events),
            merged_records=merged_records,
            overlap_count=overlap_count,
            ticketmaster_municipal_count=len(ticketmaster_municipal),
            serpapi_count=len(serpapi),
        )

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(FINAL_PATH, "w", encoding="utf-8") as final_file:
            json.dump(merged_records, final_file, ensure_ascii=False, indent=2, default=_json_default)
        with open(STATS_PATH, "w", encoding="utf-8") as stats_file:
            json.dump(stats_payload, stats_file, ensure_ascii=False, indent=2, default=_json_default)

        print(
            "Merge completed. "
            f"before={stats_payload['total_events_before_dedup']} "
            f"after={stats_payload['total_events_after_dedup']} "
            f"overlap={stats_payload['overlap_count']}"
        )
        print(f"Output files: {FINAL_PATH}, {STATS_PATH}")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR Merge failed: {type(exc).__name__} - {exc}")


if __name__ == "__main__":
    main()
