"""Claude (Anthropic) translator backend."""

from __future__ import annotations

from .base import Card, SYSTEM_PROMPT, TranslatorError


class ClaudeTranslator:
    def __init__(self, model: str):
        self.model = model
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise TranslatorError(
                "The `anthropic` package is required for the Claude translator. "
                "Install it with: pip install anthropic"
            ) from exc
        try:
            # Reads the ANTHROPIC_API_KEY environment variable.
            self.client = anthropic.Anthropic()
        except Exception as exc:
            raise TranslatorError(
                "Could not initialize the Claude client. Set the ANTHROPIC_API_KEY "
                f"environment variable. ({exc})"
            ) from exc

    def translate(self, text: str) -> Card:
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
            output_format=Card,
        )
        card = response.parsed_output
        if card is None:
            raise TranslatorError(f"Claude returned no structured result for {text!r}")
        return card
