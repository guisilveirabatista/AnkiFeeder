"""Google Gemini translator backend."""

from __future__ import annotations

from .base import Card, TranslatorError


class GeminiTranslator:
    def __init__(self, model: str, system_prompt: str):
        self.model = model
        self.system_prompt = system_prompt
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise TranslatorError(
                "The `google-genai` package is required for the Gemini translator. "
                "Install it with: pip install google-genai"
            ) from exc
        self._genai = genai
        try:
            # Reads the GEMINI_API_KEY (or GOOGLE_API_KEY) environment variable.
            self.client = genai.Client()
        except Exception as exc:
            raise TranslatorError(
                "Could not initialize the Gemini client. Set the GEMINI_API_KEY "
                f"environment variable. ({exc})"
            ) from exc

    def translate(self, text: str) -> Card:
        response = self.client.models.generate_content(
            model=self.model,
            contents=text,
            config={
                "system_instruction": self.system_prompt,
                "response_mime_type": "application/json",
                "response_schema": Card,
            },
        )
        card = response.parsed
        if not isinstance(card, Card):
            raise TranslatorError(f"Gemini returned no structured result for {text!r}")
        return card
