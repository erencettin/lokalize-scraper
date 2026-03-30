from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, TYPE_CHECKING
from urllib.parse import urlparse

from utils.constants import CANONICAL_PROVIDER_ALIASES, CANONICAL_PROVIDER_ORDER, PROVIDER_UI_TAG_MAP
from utils.text_normalizer import TextNormalizer, clean_text

if TYPE_CHECKING:
    from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource


_PROVIDER_ORDER_INDEX = {name: idx for idx, name in enumerate(CANONICAL_PROVIDER_ORDER)}
_PROVIDER_ALIAS_LOOKUP = {
    re.sub(r"[^a-z0-9]+", "", alias.strip().lower()): canonical
    for alias, canonical in CANONICAL_PROVIDER_ALIASES.items()
}
for canonical in CANONICAL_PROVIDER_ORDER:
    _PROVIDER_ALIAS_LOOKUP[re.sub(r"[^a-z0-9]+", "", canonical.lower())] = canonical


def _clean_string(value: Any) -> str:
    if value is None:
        return ""
    return clean_text(str(value))


def _provider_lookup_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean_string(value).lower())


def canonicalize_provider(value: Any) -> Optional[str]:
    raw = _clean_string(value)
    if not raw:
        return None
    lookup_key = _provider_lookup_key(raw)
    if lookup_key in {"unknown", "none", "null", "na", "n/a"}:
        return None
    if raw in CANONICAL_PROVIDER_ORDER:
        return raw
    return _PROVIDER_ALIAS_LOOKUP.get(lookup_key, raw)


def normalize_providers(values: Iterable[Any]) -> List[str]:
    unique: List[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, str):
            chunks = [chunk.strip() for chunk in value.split("|")]
        else:
            chunks = [value]
        for chunk in chunks:
            provider = canonicalize_provider(chunk)
            if not provider or provider in seen:
                continue
            seen.add(provider)
            unique.append(provider)
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


@lru_cache(maxsize=1)
def _load_municipal_maps() -> Tuple[List[Tuple[str, str]], Dict[str, str]]:
    domain_map: Dict[str, str] = {}
    token_map: Dict[str, str] = {}
    try:
        from providers.municipal_web.site_registry import SiteRegistry

        for site in SiteRegistry().get_sites():
            label = _clean_string(site.name)
            if not label:
                continue
            token = TextNormalizer.normalize_for_match(label.replace("Belediyesi", "")).strip()
            if token:
                token_map[token] = label
            for candidate in [site.base_url, *site.list_urls]:
                host = _extract_host(candidate)
                if host:
                    domain_map[host] = label
    except Exception:
        return [], {}

    sorted_domains = sorted(domain_map.items(), key=lambda item: len(item[0]), reverse=True)
    return sorted_domains, token_map


def resolve_municipal_labels(source_urls: Sequence[str], candidate_texts: Sequence[str]) -> List[str]:
    domain_map, token_map = _load_municipal_maps()
    labels: List[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        cleaned = _clean_string(value)
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        labels.append(cleaned)

    for url in source_urls:
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

    for text in candidate_texts:
        cleaned_text = _clean_string(text)
        if not cleaned_text:
            continue
        normalized_text = TextNormalizer.normalize_for_match(cleaned_text)
        for token, label in token_map.items():
            if token and token in normalized_text:
                add(label)
        explicit = re.search(r"([a-zA-ZçğıöşüÇĞİÖŞÜ\s-]+)\s+belediyesi", cleaned_text, flags=re.IGNORECASE)
        if explicit:
            token = TextNormalizer.normalize_for_match(explicit.group(1))
            if token in token_map:
                add(token_map[token])
            else:
                add(f"{_clean_string(explicit.group(1))} Belediyesi")

    return labels


def build_provider_payload(
    *,
    providers: Sequence[Any],
    source_urls: Sequence[Any],
    candidate_texts: Sequence[Any],
) -> Dict[str, Any]:
    canonical_providers = normalize_providers(providers)

    unique_source_urls: List[str] = []
    seen_url_keys: set[str] = set()
    for value in source_urls:
        cleaned = _clean_string(value)
        if not cleaned:
            continue
        key = _normalize_url_for_match(cleaned) or cleaned.lower()
        if key in seen_url_keys:
            continue
        seen_url_keys.add(key)
        unique_source_urls.append(cleaned)

    provider_tags: List[str] = []
    seen_tags: set[str] = set()

    def add_tag(tag: str) -> None:
        cleaned_tag = _clean_string(tag)
        if not cleaned_tag or cleaned_tag in seen_tags:
            return
        seen_tags.add(cleaned_tag)
        provider_tags.append(cleaned_tag)

    municipal_labels = resolve_municipal_labels(unique_source_urls, [_clean_string(value) for value in candidate_texts])

    for provider in canonical_providers:
        if provider == "MunicipalWeb":
            if municipal_labels:
                for label in municipal_labels:
                    add_tag(label)
            else:
                add_tag("MunicipalWeb")
            continue
        add_tag(PROVIDER_UI_TAG_MAP.get(provider, provider))

    provider_label = ", ".join(provider_tags) if provider_tags else None
    legacy_provider = provider_label or (provider_tags[0] if provider_tags else None) or (canonical_providers[0] if canonical_providers else None)

    return {
        "provider": legacy_provider,
        "providers": canonical_providers,
        "provider_tags": provider_tags,
        "provider_label": provider_label,
        "source_urls": unique_source_urls,
    }


def build_provider_payload_from_event(
    event: "NormalizedEvent",
    occurrence: "NormalizedOccurrence",
    source: "NormalizedSource",
) -> Dict[str, Any]:
    provider_inputs: List[Any] = []
    provider_inputs.extend(getattr(event, "providers", []) or [])
    provider_inputs.append(getattr(event, "provider", None))
    provider_inputs.append(getattr(event, "source", None))
    provider_inputs.append(getattr(source, "provider", None))

    source_url_inputs: List[Any] = []
    source_url_inputs.extend(getattr(event, "source_urls", []) or [])
    source_url_inputs.append(getattr(source, "source_url", None))
    source_url_inputs.append(getattr(source, "deep_link_url", None))
    source_url_inputs.append(getattr(event, "source_url", None))
    source_url_inputs.append(getattr(event, "link", None))

    candidate_texts = [
        getattr(occurrence, "venue_name", None),
        getattr(occurrence, "district", None),
        getattr(event, "venue", None),
        getattr(event, "address", None),
        getattr(event, "title", None),
        getattr(event, "description", None),
    ]

    return build_provider_payload(
        providers=provider_inputs,
        source_urls=source_url_inputs,
        candidate_texts=candidate_texts,
    )
