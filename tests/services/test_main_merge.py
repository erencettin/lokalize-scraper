from __future__ import annotations

from main_merge import merge_events


def _event(
    *,
    title: str,
    city: str,
    date: str,
    time: str,
    provider: str,
    url: str,
    source: str | None = None,
) -> dict:
    return {
        "title": title,
        "city_name": city,
        "source": source or provider,
        "occurrences": [
            {
                "local_date": date,
                "local_time": time,
                "venue_name": "Zorlu PSM",
                "sources": [
                    {
                        "provider": provider,
                        "external_id": None,
                        "title": title,
                        "source_url": url,
                    }
                ],
            }
        ],
    }


def test_merge_events_dedups_by_title_date_city_and_builds_provider_tags() -> None:
    tm_event = _event(
        title="Athena Konseri",
        city="Istanbul",
        date="2026-04-10",
        time="21:00",
        provider="Ticketmaster",
        url="https://www.biletix.com/performance/athena",
    )
    serpapi_event = _event(
        title="ATHENA  Konseri!",
        city="İstanbul",
        date="2026-04-10",
        time="21:00",
        provider="serpapi_google_events",
        source="serpapi_google_events",
        url="https://www.google.com/events/athena",
    )

    merged, overlap_count = merge_events([tm_event, serpapi_event])

    assert len(merged) == 1
    assert overlap_count == 1
    assert merged[0]["providers"] == ["Ticketmaster", "SerpAPIEvents"]
    assert merged[0]["provider_tags"] == ["Ticketmaster", "Google"]
    assert merged[0]["provider_label"] == "Ticketmaster, Google"
    assert set(merged[0]["source_urls"]) == {
        "https://www.biletix.com/performance/athena",
        "https://www.google.com/events/athena",
    }


def test_merge_events_resolves_municipal_web_to_municipality_tag() -> None:
    municipal_event = _event(
        title="Sokak Senligi",
        city="Istanbul",
        date="2026-04-12",
        time="19:00",
        provider="municipal_web",
        source="municipal_web",
        url="https://www.maltepe.bel.tr/tr/liste/etkinlikler/sokak-senligi",
    )

    merged, _ = merge_events([municipal_event])

    assert len(merged) == 1
    assert merged[0]["providers"] == ["MunicipalWeb"]
    assert "Maltepe Belediyesi" in merged[0]["provider_tags"]
    assert "MunicipalWeb" not in merged[0]["provider_tags"]


def test_merge_events_keeps_google_tag_unique_for_serpapi_pairs() -> None:
    serpapi_events = _event(
        title="Ortak Kayit",
        city="Istanbul",
        date="2026-05-01",
        time="20:00",
        provider="serpapi_google_events",
        source="serpapi_google_events",
        url="https://www.google.com/events/ortak-kayit",
    )
    serpapi_local = _event(
        title="Ortak Kayit",
        city="Istanbul",
        date="2026-05-01",
        time="20:00",
        provider="serpapi_google_local",
        source="serpapi_google_local",
        url="https://www.google.com/local/ortak-kayit",
    )

    merged, overlap_count = merge_events([serpapi_events, serpapi_local])

    assert len(merged) == 1
    assert overlap_count == 1
    assert merged[0]["providers"] == ["SerpAPIEvents", "SerpAPILocal"]
    assert merged[0]["provider_tags"] == ["Google"]
