"""Minimal AnkiConnect client (https://foosoft.net/projects/anki-connect/)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

ANKI_CONNECT_VERSION = 6


class AnkiError(Exception):
    """Raised when AnkiConnect returns an error or cannot be reached."""


class AnkiConnect:
    def __init__(self, url: str, timeout: float = 10.0):
        self.url = url
        self.timeout = timeout

    def _invoke(self, action: str, **params):
        payload = json.dumps(
            {"action": action, "version": ANKI_CONNECT_VERSION, "params": params}
        ).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=payload, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise AnkiError(
                "Could not reach AnkiConnect at "
                f"{self.url}. Is Anki running with the AnkiConnect add-on installed? "
                f"({exc})"
            ) from exc

        if body.get("error") is not None:
            raise AnkiError(body["error"])
        return body.get("result")

    def ping(self) -> int:
        """Return the AnkiConnect API version, raising AnkiError if unreachable."""
        return self._invoke("version")

    def ensure_deck(self, deck_name: str) -> None:
        """Create the deck if it does not already exist (idempotent)."""
        self._invoke("createDeck", deck=deck_name)

    def sync(self) -> None:
        """Trigger a sync with AnkiWeb (requires the desktop app to be logged in)."""
        self._invoke("sync")

    def add_note(
        self,
        deck_name: str,
        model_name: str,
        front: str,
        back: str,
        tags: list[str],
    ) -> int | None:
        """Add a Basic note. Returns the note id, or None if it was a duplicate."""
        note = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": {"Front": front, "Back": back},
            "options": {"allowDuplicate": False, "duplicateScope": "deck"},
            "tags": tags,
        }
        try:
            return self._invoke("addNote", note=note)
        except AnkiError as exc:
            if "duplicate" in str(exc).lower():
                return None  # already in the deck; treat as success
            raise
