"""Tracks per-event content hashes across scraper runs.

Scraper runs happen on ephemeral GitHub Actions runners, so state is
persisted the same way other scraper output already is (see data/ticketmaster,
data/biletcom, etc.): written under data/ and committed back to the repo by
the calling workflow.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

DEFAULT_HASH_STORE_PATH = "data/sync_state/event_hashes.json"


def _dto_key(dto: dict) -> str:
    return f"{dto.get('provider')}:{dto.get('externalId')}"


def _dto_hash(dto: dict) -> str:
    payload = json.dumps(dto, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ChangeDetector:
    """Filters DTOs down to the ones whose content actually changed since
    the last successful sync, so unchanged events aren't re-sent to the
    backend on every run."""

    def __init__(self, store_path: str = DEFAULT_HASH_STORE_PATH):
        self._store_path = Path(store_path)
        self._hashes: Dict[str, str] = self._load()

    def _load(self) -> Dict[str, str]:
        if not self._store_path.exists():
            return {}
        try:
            return json.loads(self._store_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def compute_changes(self, dtos: List[dict]) -> List[Tuple[dict, str, str]]:
        """Returns (dto, key, hash) triples for DTOs whose hash differs from
        the last persisted one (or that have never been seen before)."""
        changed = []
        for dto in dtos:
            key = _dto_key(dto)
            new_hash = _dto_hash(dto)
            if self._hashes.get(key) != new_hash:
                changed.append((dto, key, new_hash))
        return changed

    def mark_synced(self, key: str, new_hash: str) -> None:
        """Records a hash as persisted. Call only after the DTO has been
        confirmed synced to the backend, so a failed sync is retried next
        run instead of being silently treated as up to date."""
        self._hashes[key] = new_hash

    def save(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._store_path.write_text(json.dumps(self._hashes, sort_keys=True), encoding="utf-8")
