from __future__ import annotations

from utils.provider_enrichment import build_provider_payload


def test_build_provider_payload_dedups_google_tag() -> None:
    payload = build_provider_payload(
        providers=["serpapi_google_events", "serpapi_google_local"],
        source_urls=["https://www.google.com/events/example"],
        candidate_texts=["Blind"],
    )

    assert payload["providers"] == ["SerpAPIEvents", "SerpAPILocal"]
    assert payload["provider_tags"] == ["Google"]
    assert payload["provider"] == "Google"
    assert payload["provider_label"] == "Google"


def test_build_provider_payload_resolves_municipal_web_label() -> None:
    payload = build_provider_payload(
        providers=["MunicipalWeb"],
        source_urls=["https://www.kartal.bel.tr/KulturSanat/EtkinlikTakvimi"],
        candidate_texts=["Kartal Belediyesi Kultur Merkezi"],
    )

    assert payload["providers"] == ["MunicipalWeb"]
    assert "Kartal Belediyesi" in payload["provider_tags"]
    assert payload["provider"] == "Kartal Belediyesi"
