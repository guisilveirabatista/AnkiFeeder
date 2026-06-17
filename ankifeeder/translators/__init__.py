"""Pluggable translator backends (Claude, ChatGPT, Gemini, or a local model)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Card, Translator, TranslatorError, render_back

if TYPE_CHECKING:
    from ..config import Config

__all__ = ["Card", "Translator", "TranslatorError", "render_back", "make_translator"]


def make_translator(config: "Config") -> Translator:
    """Build the translator backend selected by `config.translator`."""
    key = config.translator.strip().lower()
    if key == "claude":
        from .claude import ClaudeTranslator

        return ClaudeTranslator(config.claude_model)
    if key in ("openai", "chatgpt", "gpt"):
        from .openai import OpenAITranslator

        return OpenAITranslator(config.openai_model)
    if key in ("gemini", "google"):
        from .gemini import GeminiTranslator

        return GeminiTranslator(config.gemini_model)
    if key in ("local", "ollama"):
        from .local import LocalTranslator

        return LocalTranslator(config.local_model, config.local_base_url, config.local_api_key)
    raise TranslatorError(
        f"Unknown translator provider {config.translator!r}. "
        "Use 'claude', 'openai', 'gemini', or 'local'."
    )
