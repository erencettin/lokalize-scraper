from __future__ import annotations

from datetime import datetime, timezone

from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo
from services.sync_service import SyncService


class DummyBackendClient:
    def __init__(self) -> None:
        self.payload = []
        self.sync_run_id = ""

    def sync_events_bulk(self, events, sync_run_id: str) -> bool:  # noqa: ANN001
        self.payload = events
        self.sync_run_id = sync_run_id
        return True


def _build_event(provider: str, source_url: str, source_name: str) -> NormalizedEvent:
    source = NormalizedSource(
        provider=provider,
        external_id="ext-1",
        title="Test Event",
        source_url=source_url,
        price=PriceInfo(text="Fiyat bilgisi yok", currency="TRY"),
        ticket_status="unknown",
    )
    occurrence = NormalizedOccurrence(
        start_at_utc=datetime(2026, 4, 10, 18, 0, tzinfo=timezone.utc),
        local_date="2026-04-10",
        local_time="21:00",
        timezone="Europe/Istanbul",
        venue_name=source_name,
        district=None,
        sources=[source],
    )
    return NormalizedEvent(
        title="Test Event",
        description="Test description",
        type="concert",
        city_name="Istanbul",
        occurrences=[occurrence],
        source=provider,
    )


def test_sync_service_sends_google_for_serpapi_provider() -> None:
    backend = DummyBackendClient()
    service = SyncService(backend_client=backend)
    event = _build_event("serpapi_google_events", "https://www.google.com/events/abc", "Blind")

    ok = service.sync_events_to_backend_bulk([event], "run-1")

    assert ok is True
    assert backend.sync_run_id == "run-1"
    assert len(backend.payload) == 1
    dto = backend.payload[0]
    assert dto["provider"] == "Google"
    assert dto["providers"] == ["SerpAPIEvents"]
    assert dto["providerTags"] == ["Google"]
    assert dto["providerLabel"] == "Google"
    assert "priceResolution" in dto
    assert dto["priceResolution"]["legal_mode"] == "unknown"


def test_sync_service_sends_municipality_for_municipal_web_provider() -> None:
    backend = DummyBackendClient()
    service = SyncService(backend_client=backend)
    event = _build_event(
        "MunicipalWeb",
        "https://www.kartal.bel.tr/KulturSanat/EtkinlikTakvimi",
        "Kartal Belediyesi",
    )

    ok = service.sync_events_to_backend_bulk([event], "run-2")

    assert ok is True
    assert len(backend.payload) == 1
    dto = backend.payload[0]
    assert dto["provider"] == "Kartal Belediyesi"
    assert dto["providers"] == ["MunicipalWeb"]
    assert "Kartal Belediyesi" in dto["providerTags"]
    assert "priceResolution" in dto
