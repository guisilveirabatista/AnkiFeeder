"""Orchestrates reading the note, translating words, and adding Anki cards."""

from __future__ import annotations

import time
from dataclasses import dataclass

from .anki import AnkiConnect
from .config import Config
from .parser import extract_words
from .state import State
from .translators import Translator, make_translator, render_back

# Substrings that mark an error as transient (worth retrying) rather than a
# permanent failure like a bad API key or malformed request. Matched case-insensitively
# against the exception text, so it works across every backend.
_TRANSIENT_MARKERS = (
    "429",
    "503",
    "529",
    "rate limit",
    "rate_limit",
    "resource_exhausted",
    "overloaded",
    "unavailable",
    "timeout",
    "timed out",
    "try again",
    "temporarily",
)


def _is_transient(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _TRANSIENT_MARKERS)


@dataclass
class SyncResult:
    added: int = 0
    skipped: int = 0  # already added in a previous run
    failed: int = 0  # translation or Anki error — will be retried next run


class Feeder:
    def __init__(self, config: Config):
        self.config = config
        self.anki = AnkiConnect(config.anki_connect_url)
        self.state = State(config.state_path)
        # Created on first sync so `init` and parsing don't require an API key.
        self._translator: Translator | None = None

    @property
    def translator(self) -> Translator:
        if self._translator is None:
            self._translator = make_translator(self.config)
        return self._translator

    def _translate(self, word: str, verbose: bool):
        """Translate one word, retrying transient (rate-limit/overload) failures with backoff."""
        attempts = self.config.max_retries + 1
        for attempt in range(attempts):
            try:
                return self.translator.translate(word)
            except Exception as exc:
                last_attempt = attempt == attempts - 1
                if last_attempt or not _is_transient(exc):
                    raise
                wait = self.config.retry_backoff * (2**attempt)
                if verbose:
                    print(
                        f"    busy, retry {attempt + 1}/{self.config.max_retries} "
                        f"for {word!r} in {wait:.0f}s"
                    )
                time.sleep(wait)

    def sync(self, verbose: bool = True) -> SyncResult:
        result = SyncResult()
        if not self.config.note_path.exists():
            raise FileNotFoundError(f"Note file not found: {self.config.note_path}")

        # Fail fast with a clear message if Anki isn't reachable.
        self.anki.ping()
        self.anki.ensure_deck(self.config.deck_name)

        text = self.config.note_path.read_text(encoding="utf-8")
        words = extract_words(text)
        new_words = [w for w in words if not self.state.has(w)]

        if verbose and new_words:
            print(f"Found {len(new_words)} new word(s) to add.")

        for index, word in enumerate(new_words):
            # Throttle between requests so we don't hammer a busy/rate-limited model.
            if index > 0 and self.config.request_delay > 0:
                time.sleep(self.config.request_delay)
            try:
                card = self._translate(word, verbose)
                self.anki.add_note(
                    deck_name=self.config.deck_name,
                    model_name=self.config.model_name,
                    front=word,
                    back=render_back(card),
                    tags=[self.config.tag],
                )
                self.state.add(word)
                result.added += 1
                if verbose:
                    print(f"  + {word} → {card.translation}")
            except Exception as exc:  # keep going; not recorded, so it retries next run
                result.failed += 1
                if verbose:
                    print(f"  ! {word}: {exc}")

        result.skipped = len(words) - len(new_words)
        self.state.save()

        # Push the new cards up to AnkiWeb (best-effort — needs the app logged in).
        if result.added and self.config.sync_after_add:
            try:
                self.anki.sync()
                if verbose:
                    print("Synced with AnkiWeb.")
            except Exception as exc:
                if verbose:
                    print(f"AnkiWeb sync failed (cards were still added locally): {exc}")

        return result
