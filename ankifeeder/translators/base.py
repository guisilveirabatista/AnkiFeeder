"""Shared pieces for every translator backend: the card schema, prompt, and HTML rendering."""

from __future__ import annotations

from html import escape
from typing import Literal, Protocol

from pydantic import BaseModel

# The two languages this tool works between. Each note entry is auto-detected as
# one of these and translated into the other.
LANGUAGES = ("English", "Dutch")

SYSTEM_PROMPT = (
    "You are a precise English–Dutch bilingual dictionary and translator. "
    "Each input is written in either English or Dutch and may be a single word, an "
    "expression or idiom, or a full sentence. Detect which of the two languages it is in, "
    "classify it as 'word', 'expression', or 'sentence', and translate it naturally into the "
    "other language.\n"
    "- For a 'word' or 'expression': give the concise dictionary-form translation, and provide "
    "one natural everyday example sentence in English plus its Dutch equivalent that use the "
    "input in context.\n"
    "- For a 'sentence': the translation is the whole sentence rendered in the other language; "
    "set example_english to the English version of the sentence and example_dutch to the Dutch "
    "version (whichever is the original stays as written).\n"
    "The two example sentences must always be translations of each other. "
    "Leave part_of_speech empty unless the input is a single word."
)


class Card(BaseModel):
    """Structured result a model returns for one entry. Shared across backends."""

    entry_type: Literal["word", "expression", "sentence"]
    detected_language: Literal["English", "Dutch"]
    translation: str  # the input rendered in the *other* language
    part_of_speech: str  # only meaningful for a single word; otherwise empty
    example_english: str
    example_dutch: str


class TranslatorError(Exception):
    """Raised when a translator backend cannot be created or a translation fails."""


class Translator(Protocol):
    """Any backend that turns an entry into a Card."""

    def translate(self, text: str) -> Card: ...


def render_back(card: Card) -> str:
    """Build the HTML for the back of the card from a translated Card."""
    other = "Dutch" if card.detected_language == "English" else "English"
    pos = (
        f' <span style="color:#888;">· {escape(card.part_of_speech)}</span>'
        if card.part_of_speech
        else ""
    )
    head = (
        f'<div><b>{escape(card.translation)}</b>'
        f' <span style="color:#888;">({escape(card.detected_language)} → {escape(other)})</span>'
        f"{pos}</div>"
    )
    # A full sentence's translation already is the complete sentence, so the
    # example pair would just repeat it — show examples only for words/expressions.
    if card.entry_type == "sentence":
        return head
    return (
        head
        + f'<div style="margin-top:10px;">🇬🇧 {escape(card.example_english)}</div>'
        + f'<div style="margin-top:4px;">🇳🇱 {escape(card.example_dutch)}</div>'
    )
