import services.sync_service as sync_module
from services.sync_service import SyncService
from utils.change_detector import ChangeDetector


class FakeBackend:
    enabled = True

    def __init__(self, reachable=True, results=None, fatal=False):
        self.reachable = reachable
        self.results = list(results or [])
        self.last_failure_fatal = fatal
        self.calls = 0

    def is_reachable(self) -> bool:
        return self.reachable

    def sync_events_bulk(self, events, sync_run_id: str) -> bool:  # noqa: ANN001
        self.calls += 1
        return self.results.pop(0) if self.results else False


def _service(tmp_path, backend, monkeypatch, n_events):
    monkeypatch.setattr(sync_module.time, "sleep", lambda _s: None)
    monkeypatch.setattr(sync_module, "_CHUNK_SIZE", 1)
    service = SyncService(
        backend_client=backend,
        change_detector=ChangeDetector(store_path=str(tmp_path / "hashes.json")),
    )
    dtos = [
        {"provider": "P", "externalId": str(i), "title": f"t{i}", "minPrice": None, "currency": "TRY"}
        for i in range(n_events)
    ]
    monkeypatch.setattr(service, "_build_dtos", lambda _events: iter(dtos))
    return service


def test_aborts_before_any_chunk_when_backend_unreachable(tmp_path, monkeypatch):
    backend = FakeBackend(reachable=False)
    service = _service(tmp_path, backend, monkeypatch, 3)

    assert service.sync_events_to_backend_bulk([object()], "run") is False
    assert backend.calls == 0
    assert service.last_backend_sync_status == "backend_unreachable"


def test_fatal_status_skips_retries_and_remaining_chunks(tmp_path, monkeypatch):
    backend = FakeBackend(fatal=True)
    service = _service(tmp_path, backend, monkeypatch, 5)

    assert service.sync_events_to_backend_bulk([object()], "run") is False
    assert backend.calls == 1


def test_stops_after_consecutive_chunk_failures(tmp_path, monkeypatch):
    backend = FakeBackend()
    service = _service(tmp_path, backend, monkeypatch, 6)

    assert service.sync_events_to_backend_bulk([object()], "run") is False
    assert backend.calls == 2 * sync_module._CHUNK_MAX_ATTEMPTS


def test_isolated_failure_does_not_abort(tmp_path, monkeypatch):
    # chunk 1 fails 3x, chunk 2 succeeds, chunk 3 succeeds
    backend = FakeBackend(results=[False, False, False, True, True])
    service = _service(tmp_path, backend, monkeypatch, 3)

    assert service.sync_events_to_backend_bulk([object()], "run") is False
    assert backend.calls == 5
