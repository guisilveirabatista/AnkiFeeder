"""ChatGPT (OpenAI) translator backend."""

from __future__ import annotations

from .base import Card, SYSTEM_PROMPT, TranslatorError


class OpenAITranslator:
    def __init__(self, model: str):
        self.model = model
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise TranslatorError(
                "The `openai` package is required for the ChatGPT translator. "
                "Install it with: pip install openai"
            ) from exc
        try:
            # Reads the OPENAI_API_KEY environment variable.
            self.client = openai.OpenAI()
        except Exception as exc:
            raise TranslatorError(
                "Could not initialize the OpenAI client. Set the OPENAI_API_KEY "
                f"environment variable. ({exc})"
            ) from exc

    def translate(self, text: str) -> Card:
        completion = self.client.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format=Card,
        )
        card = completion.choices[0].message.parsed
        if card is None:
            raise TranslatorError(f"OpenAI returned no structured result for {text!r}")
        return card
