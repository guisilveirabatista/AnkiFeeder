"""Local-model translator backend (Ollama, LM Studio, llama.cpp, vLLM, …).

These runners expose an OpenAI-compatible HTTP API, so we reuse the OpenAI SDK
pointed at a local `base_url`. No data leaves your machine.
"""

from __future__ import annotations

from .base import Card, TranslatorError


class LocalTranslator:
    def __init__(self, model: str, base_url: str, system_prompt: str, api_key: str = "ollama"):
        self.model = model
        self.system_prompt = system_prompt
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise TranslatorError(
                "The `openai` package is required for the local translator (it speaks the "
                "OpenAI-compatible API local servers expose). Install it with: pip install openai"
            ) from exc
        try:
            # Local servers usually ignore the key, but the SDK requires a non-empty one.
            self.client = openai.OpenAI(base_url=base_url, api_key=api_key or "not-needed")
        except Exception as exc:
            raise TranslatorError(
                f"Could not initialize the local OpenAI-compatible client at {base_url}. ({exc})"
            ) from exc

    def translate(self, text: str) -> Card:
        completion = self.client.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": text},
            ],
            response_format=Card,
        )
        card = completion.choices[0].message.parsed
        if card is None:
            raise TranslatorError(f"Local model returned no structured result for {text!r}")
        return card
