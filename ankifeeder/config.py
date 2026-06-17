"""Configuration loading for AnkiFeeder."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config.json")

# Top-level keys that configure a feed; anything else at the top level is a
# shared default inherited by every feed in a multi-feed config.
_FEED_KEYS = frozenset(
    {"note_path", "deck_name", "state_path", "tag", "model_name", "poll_interval"}
)


@dataclass
class Config:
    # Absolute or relative path to the Obsidian note to read words from.
    note_path: Path
    # Name of the Anki deck cards are added to (created if missing).
    deck_name: str = "Obsidian Vocabulary"
    # AnkiConnect endpoint (the AnkiConnect plugin listens here by default).
    anki_connect_url: str = "http://127.0.0.1:8765"
    # Anki note type. "Basic" has Front/Back fields, which we rely on.
    model_name: str = "Basic"
    # Which translator backend to use: "claude", "openai", "gemini", or "local".
    translator: str = "claude"
    # Language of the words in the note, and the language to translate them into.
    # Set them to the same language (e.g. both "English") to get a definition
    # card instead of a translation.
    source_language: str = "English"
    target_language: str = "Dutch"
    # Claude model used when translator == "claude".
    claude_model: str = "claude-opus-4-8"
    # OpenAI model used when translator == "openai".
    openai_model: str = "gpt-4o"
    # Gemini model used when translator == "gemini".
    gemini_model: str = "gemini-2.5-flash"
    # Local model (translator == "local"): served over an OpenAI-compatible API
    # by Ollama, LM Studio, llama.cpp, vLLM, etc.
    local_model: str = "llama3.1"
    local_base_url: str = "http://localhost:11434/v1"  # Ollama's default
    local_api_key: str = "ollama"  # most local servers ignore this
    # Where the set of already-added words is persisted (relative to config dir).
    state_path: Path = Path(".ankifeeder_state.json")
    # Seconds between checks of the note file when watching.
    poll_interval: float = 1.5
    # Seconds between forced full re-scans while watching, so words that failed
    # all their attempts get retried without saving the file again. 0 disables.
    retry_interval: float = 1800.0  # 30 minutes
    # Tag applied to every card created by this tool.
    tag: str = "ankifeeder"
    # Sync the desktop app with AnkiWeb after a run that added cards.
    sync_after_add: bool = True
    # Throttling + retries — help when a remote model is rate-limited or busy.
    request_delay: float = 2.0  # seconds to wait between successive translations
    max_retries: int = 3  # extra attempts on a transient (rate-limit/overload) error
    retry_backoff: float = 2.0  # base seconds for exponential backoff (2, 4, 8, …)

    def active_model(self) -> str:
        """The model name for the currently selected translator backend."""
        return {
            "claude": self.claude_model,
            "openai": self.openai_model,
            "gemini": self.gemini_model,
            "local": self.local_model,
        }.get(self.translator, "unknown")

    def language_summary(self) -> str:
        """A short human-readable description of the language direction."""
        if self.source_language.strip().lower() == self.target_language.strip().lower():
            return f"{self.source_language} definitions"
        return f"{self.source_language} → {self.target_language}"

    @classmethod
    def load_all(cls, path: Path = DEFAULT_CONFIG_PATH) -> list["Config"]:
        """Load one Config, or several if the file has a `feeds` list.

        A multi-feed file puts shared settings at the top level and a `feeds`
        array of per-note overrides; each feed inherits the shared settings and,
        unless it sets `state_path`, gets its own state file derived from the note
        name so feeds never share dedup state.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"Config file not found: {path}\n"
                "Run `python -m ankifeeder init` to create one from the template."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        base = path.resolve().parent

        feeds = data.get("feeds")
        if feeds is not None:
            if not isinstance(feeds, list) or not feeds:
                raise ValueError(f"`feeds` in {path} must be a non-empty list.")
            shared = {k: v for k, v in data.items() if k != "feeds"}
            configs = []
            for i, feed in enumerate(feeds):
                merged = {**shared, **feed}
                if "note_path" not in merged:
                    raise ValueError(f"feed #{i + 1} in {path} is missing `note_path`.")
                default_state = f".ankifeeder_state.{_slug(merged['note_path'])}.json"
                configs.append(cls._build(merged, base, default_state))
            return configs

        if "note_path" not in data:
            raise ValueError(f"`note_path` (or a `feeds` list) is required in {path}")
        return [cls._build(data, base, str(cls.state_path))]

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> "Config":
        """Load a single Config (the first feed, if the file defines several)."""
        return cls.load_all(path)[0]

    @classmethod
    def _build(cls, data: dict, base: Path, default_state: str) -> "Config":
        return cls(
            note_path=_resolve(base, data["note_path"]),
            deck_name=data.get("deck_name", cls.deck_name),
            anki_connect_url=data.get("anki_connect_url", cls.anki_connect_url),
            model_name=data.get("model_name", cls.model_name),
            translator=data.get("translator", cls.translator),
            source_language=data.get("source_language", cls.source_language),
            target_language=data.get("target_language", cls.target_language),
            claude_model=data.get("claude_model", cls.claude_model),
            openai_model=data.get("openai_model", cls.openai_model),
            gemini_model=data.get("gemini_model", cls.gemini_model),
            local_model=data.get("local_model", cls.local_model),
            local_base_url=data.get("local_base_url", cls.local_base_url),
            local_api_key=data.get("local_api_key", cls.local_api_key),
            state_path=_resolve(base, data.get("state_path", default_state)),
            poll_interval=float(data.get("poll_interval", cls.poll_interval)),
            retry_interval=float(data.get("retry_interval", cls.retry_interval)),
            tag=data.get("tag", cls.tag),
            sync_after_add=bool(data.get("sync_after_add", cls.sync_after_add)),
            request_delay=float(data.get("request_delay", cls.request_delay)),
            max_retries=int(data.get("max_retries", cls.max_retries)),
            retry_backoff=float(data.get("retry_backoff", cls.retry_backoff)),
        )


def _resolve(base: Path, value) -> Path:
    """Resolve a path from config: absolute paths win, relative ones hang off the config dir."""
    p = Path(value).expanduser()
    return p if p.is_absolute() else (base / p)


def _slug(note_path: str) -> str:
    """A filesystem-safe slug from a note path, used to name per-feed state files."""
    stem = Path(note_path).stem
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-")
    return slug or "feed"
