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
    dictionary and returns *definitions* in each sense instead of translations.

    A word or expression can carry several distinct meanings, so the model
    returns one `Sense` per meaning, each with its own example sentence.
    """
    if same_language(source_language, target_language):
        return (
            f"You are a precise {source_language} dictionary. Each input is written in "
            f"{source_language} and may be a single word, an expression or idiom, or a full "
            "sentence. Classify it as 'word', 'expression', or 'sentence'.\n"
            f"- For a 'word' or 'expression': return EVERY distinct common meaning as a separate "
            "entry in `senses`. Do not collapse unrelated meanings into one. For each meaning, "
            f"put a clear, concise {source_language} definition in `result` and one natural "
            f"{source_language} example sentence using it in that meaning in `example_source`.\n"
            f"- For a 'sentence': return a single sense whose `result` is a brief {source_language} "
            "paraphrase of its meaning.\n"
            f"In `base_form`, give the dictionary form of the input when it is an inflected single "
            "word — the infinitive for a verb, the singular for a noun; leave it empty when the "
            "input is already in its base form or is not a single word.\n"
            f"Always write in {source_language}, and leave every `example_target` empty. "
            "Set `part_of_speech` on each sense only for a single word; otherwise leave it empty."
        )
    return (
        f"You are a precise {source_language}–{target_language} translator and bilingual "
        f"dictionary. Each input is written in {source_language} and may be a single word, an "
        "expression or idiom, or a full sentence. Classify it as 'word', 'expression', or "
        f"'sentence', and translate it into {target_language}.\n"
        f"- For a 'word' or 'expression': return EVERY distinct common meaning the {source_language} "
        "input can have as a separate entry in `senses` (for example, Dutch 'verdieping' means both "
        "'deepening' and 'floor/storey' of a building — both must appear). Do not omit meanings and "
        "do not merge unrelated ones. For each meaning, put the concise dictionary-form "
        f"{target_language} translation in `result`, set `part_of_speech`, and provide one natural "
        f"{source_language} example sentence using that meaning in `example_source` plus its "
        f"{target_language} equivalent in `example_target`.\n"
        f"- For a 'sentence': return a single sense whose `result` is the full {target_language} "
        f"translation; set `example_source` to the {source_language} sentence and `example_target` "
        "to its translation.\n"
        f"In `base_form`, give the dictionary form of the input when it is an inflected single word "
        "— the infinitive for a verb, the singular for a noun; leave it empty when the input is "
        "already in its base form or is not a single word.\n"
        "Within each sense the two example sentences must be translations of each other. "
        "Set `part_of_speech` only for a single word; otherwise leave it empty."
    )


class Sense(BaseModel):
    """One distinct meaning of an entry, with its own example sentence pair."""

    result: str  # translation in the target language, or a definition when monolingual
    part_of_speech: str  # only meaningful for a single word; otherwise empty
    example_source: str  # example sentence in the source language for this meaning
    example_target: str  # the same example in the target language; empty when monolingual


class Card(BaseModel):
    """Structured result a model returns for one entry. Shared across backends."""

    entry_type: Literal["word", "expression", "sentence"]
    base_form: str  # dictionary/infinitive form of an inflected word; otherwise empty
    senses: list[Sense]  # one entry per distinct meaning


class TranslatorError(Exception):
    """Raised when a translator backend cannot be created or a translation fails."""


class Translator(Protocol):
    """Any backend that turns an entry into a Card."""

    def translate(self, text: str) -> Card: ...


def render_back(card: Card, source_language: str, target_language: str) -> str:
    """Build the HTML for the back of the card from a translated/defined Card.

    A word/expression may have several meanings, so each `Sense` is rendered as
    its own block with its translation, part of speech, and example sentence(s).
    """
    monolingual = same_language(source_language, target_language)
    label = "definition" if monolingual else f"{source_language} → {target_language}"

    base = (
        f'<div style="color:#888;margin-bottom:8px;">base form: '
        f"<b>{escape(card.base_form)}</b></div>"
        if card.base_form
        else ""
    )

    blocks = []
    for sense in card.senses:
        pos = (
            f' <span style="color:#888;">· {escape(sense.part_of_speech)}</span>'
            if sense.part_of_speech
            else ""
        )
        head = (
            f'<div><b>{escape(sense.result)}</b>'
            f' <span style="color:#888;">({escape(label)})</span>'
            f"{pos}</div>"
        )
        # A full sentence's result already is the complete sentence/paraphrase, so the
        # example pair would just repeat it — show examples only for words/expressions.
        examples = ""
        if card.entry_type != "sentence":
            if sense.example_source:
                examples += (
                    f'<div style="margin-top:6px;">{escape(source_language)}: '
                    f"{escape(sense.example_source)}</div>"
                )
            if not monolingual and sense.example_target:
                examples += (
                    f'<div style="margin-top:4px;">{escape(target_language)}: '
                    f"{escape(sense.example_target)}</div>"
                )
        blocks.append(f'<div style="margin-bottom:12px;">{head}{examples}</div>')

    return base + "".join(blocks)
