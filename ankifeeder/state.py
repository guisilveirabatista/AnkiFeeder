"""Persist which words have already been added so re-runs don't duplicate cards."""

from __future__ import annotations

import json
from pathlib import Path


class State:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._added: set[str] = set()
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._added = {str(w).lower() for w in data.get("added", [])}
            except (json.JSONDecodeError, OSError):
                self._added = set()

    def has(self, word: str) -> bool:
        return word.lower() in self._added

    def add(self, word: str) -> None:
        self._added.add(word.lower())

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"added": sorted(self._added)}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
