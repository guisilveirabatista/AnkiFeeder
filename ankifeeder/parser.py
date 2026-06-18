"""Extract the list of words/entries from an Obsidian markdown note."""

from __future__ import annotations

import re

# Leading markdown list markers: "- ", "* ", "+ ", "1. ", "- [ ] " (tasks).
_LIST_MARKER = re.compile(r"^\s*(?:[-*+]\s+(?:\[.\]\s+)?|\d+[.)]\s+)")
# Wiki/markdown link wrappers and basic emphasis we want to strip from a word.
_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_MDLINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_EMPHASIS = re.compile(r"[*_`~]+")


def _clean_entry(raw: str) -> str | None:
    """Return the cleaned word for a line, or None if the line isn't an entry.

    Skips blank lines, markdown headings, block quotes, and horizontal rules.
    Strips list markers, links, and emphasis so "- [[ephemeral]]" -> "ephemeral".
    """
    line = raw.strip()
    if not line:
        return None
    if line.startswith("#") or line.startswith(">"):
        return None
    if set(line) <= {"-", "*", "_", " "} and len(line) >= 3:
        return None  # horizontal rule like --- or ***

    line = _LIST_MARKER.sub("", line, count=1)
    line = _WIKILINK.sub(r"\1", line)
    line = _MDLINK.sub(r"\1", line)
    line = _EMPHASIS.sub("", line)
    word = line.strip()
    return word or None


def extract_words(text: str, *, drop_unterminated: bool = False) -> list[str]:
    """Return one cleaned entry per meaningful line, preserving order and de-duping.

    Skips blank lines, markdown headings, block quotes, and horizontal rules.
    Strips list markers, links, and emphasis so "- [[ephemeral]]" -> "ephemeral".

    With ``drop_unterminated``, a final line not closed by a newline is treated as
    still being typed and is skipped, so a half-written entry like "This is a t"
    isn't imported before you finish it. Pressing Enter (which adds the newline)
    commits the line on the next scan.
    """
    lines = text.splitlines()
    if drop_unterminated and lines and not text.endswith(("\n", "\r")):
        lines = lines[:-1]
    seen: set[str] = set()
    words: list[str] = []
    for raw in lines:
        word = _clean_entry(raw)
        if word is None:
            continue
        key = word.lower()
        if key in seen:
            continue
        seen.add(key)
        words.append(word)
    return words


def dedup_text(text: str, *, keep_unterminated: bool = False) -> tuple[str, int]:
    """Remove duplicate entry lines from a note, keeping the first of each.

    Returns ``(new_text, removed)``. Two lines are duplicates when they clean to
    the same word (case-insensitively) — the same rule used when importing — so
    "- [[apple]]" and "apple" collapse to one. Every non-entry line (headings,
    blank lines, quotes, rules) is preserved untouched, as are the original line
    endings, so re-saving the note only drops the repeated words.

    With ``keep_unterminated``, a final line not closed by a newline is treated as
    still being typed and is never removed, matching ``extract_words``.
    """
    lines = text.splitlines(keepends=True)
    protected = len(lines) - 1 if (
        keep_unterminated and lines and not text.endswith(("\n", "\r"))
    ) else -1
    seen: set[str] = set()
    out: list[str] = []
    removed = 0
    for index, raw in enumerate(lines):
        if index == protected:
            out.append(raw)
            continue
        word = _clean_entry(raw)
        if word is None:
            out.append(raw)
            continue
        key = word.lower()
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        out.append(raw)
    return "".join(out), removed
