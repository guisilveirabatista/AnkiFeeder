"""Shared pieces for every translator backend: the card schema, prompt, and HTML rendering."""

from __future__ import annotations

from html import escape
from typing import Literal, Protocol

from pydantic import BaseModel


def same_language(a: str, b: str) -> bool:
    """Whether two language names refer to the same language (case/space-insensitive)."""
    return a.strip().lower() == b.strip().lower()


def build_system_prompt(source_language: str, target_language: str) -> str:
    """Build the system prompt for the configured language direction.

    When source and target are the same, the model acts as a monolingual
    dictionary and returns a *definition* in `result` instead of a translation.
    """
    if same_language(source_language, target_language):
        return (
            f"You are a precise {source_language} dictionary. Each input is written in "
            f"{source_language} and may be a single word, an expression or idiom, or a full "
            "sentence. Classify it as 'word', 'expression', or 'sentence'.\n"
            f"- For a 'word' or 'expression': put a clear, concise {source_language} definition "
            f"in `result`, and one natural {source_language} example sentence using it in "
            "`example_source`.\n"
            f"- For a 'sentence': put a brief {source_language} paraphrase of its meaning in "
            "`result`.\n"
            f"Always write in {source_language}, and leave `example_target` empty. "
            "Leave `part_of_speech` empty unless the input is a single word."
        )
    return (
        f"You are a precise {source_language}–{target_language} translator and bilingual "
        f"dictionary. Each input is written in {source_language} and may be a single word, an "
        "expression or idiom, or a full sentence. Classify it as 'word', 'expression', or "
        f"'sentence', and translate it naturally into {target_language}.\n"
        f"- For a 'word' or 'expression': put the concise dictionary-form {target_language} "
        f"translation in `result`, and provide one natural example sentence in {source_language} "
        f"in `example_source` plus its {target_language} equivalent in `example_target`.\n"
        f"- For a 'sentence': put the full {target_language} translation in `result`; set "
        f"`example_source` to the {source_language} sentence and `example_target` to its "
        f"{target_language} translation.\n"
        "The two example sentences must always be translations of each other. "
        "Leave `part_of_speech` empty unless the input is a single word."
    )


class Card(BaseModel):
    """Structured result a model returns for one entry. Shared across backends."""

    entry_type: Literal["word", "expression", "sentence"]
    result: str  # translation in the target language, or a definition when monolingual
    part_of_speech: str  # only meaningful for a single word; otherwise empty
    example_source: str  # example sentence in the source language
    example_target: str  # the same example in the target language; empty when monolingual


class TranslatorError(Exception):
    """Raised when a translator backend cannot be created or a translation fails."""


class Translator(Protocol):
    """Any backend that turns an entry into a Card."""

    def translate(self, text: str) -> Card: ...


def render_back(card: Card, source_language: str, target_language: str) -> str:
    """Build the HTML for the back of the card from a translated/defined Card."""
    monolingual = same_language(source_language, target_language)
    pos = (
        f' <span style="color:#888;">· {escape(card.part_of_speech)}</span>'
        if card.part_of_speech
        else ""
    )
    label = "definition" if monolingual else f"{source_language} → {target_language}"
    head = (
        f'<div><b>{escape(card.result)}</b>'
        f' <span style="color:#888;">({escape(label)})</span>'
        f"{pos}</div>"
    )
    # A full sentence's result already is the complete sentence/paraphrase, so the
    # example pair would just repeat it — show examples only for words/expressions.
    if card.entry_type == "sentence":
        return head
    examples = ""
    if card.example_source:
        examples += (
            f'<div style="margin-top:10px;">{escape(source_language)}: '
            f"{escape(card.example_source)}</div>"
        )
    if not monolingual and card.example_target:
        examples += (
            f'<div style="margin-top:4px;">{escape(target_language)}: '
            f"{escape(card.example_target)}</div>"
        )
    return head + examples
