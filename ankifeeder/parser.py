"""Extract the list of words/entries from an Obsidian markdown note."""

from __future__ import annotations

import re

# Leading markdown list markers: "- ", "* ", "+ ", "1. ", "- [ ] " (tasks).
_LIST_MARKER = re.compile(r"^\s*(?:[-*+]\s+(?:\[.\]\s+)?|\d+[.)]\s+)")
# Wiki/markdown link wrappers and basic emphasis we want to strip from a word.
_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_MDLINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_EMPHASIS = re.compile(r"[*_`~]+")


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
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith(">"):
            continue
        if set(line) <= {"-", "*", "_", " "} and len(line) >= 3:
            continue  # horizontal rule like --- or ***

        line = _LIST_MARKER.sub("", line, count=1)
        line = _WIKILINK.sub(r"\1", line)
        line = _MDLINK.sub(r"\1", line)
        line = _EMPHASIS.sub("", line)
        word = line.strip()
        if not word:
            continue

        key = word.lower()
        if key in seen:
            continue
        seen.add(key)
        words.append(word)
    return words
