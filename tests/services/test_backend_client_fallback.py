from __future__ import annotations

from clients.backend_client import BackendClient


def test_backend_client_skips_when_backend_url_missing(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("BACKEND_URL", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    client = BackendClient()

    assert client.enabled is False
    assert "BACKEND_URL tanimli degil" in (client.skip_reason or "")
    assert client.sync_events_bulk([], "run-1") is True


def test_backend_client_skips_localhost_on_github_actions(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("BACKEND_URL", "http://localhost:5170")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    client = BackendClient()

    assert client.enabled is False
    assert "GitHub Actions" in (client.skip_reason or "")


def test_backend_client_allows_remote_backend_on_github_actions(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("BACKEND_URL", "https://my-backend.example.com")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    client = BackendClient()

    assert client.enabled is True
    assert client.skip_reason is None
