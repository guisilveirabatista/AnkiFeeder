"""Extract the list of words/entries from an Obsidian markdown note."""

from __future__ import annotations

import re

# Leading markdown list markers: "- ", "* ", "+ ", "1. ", "- [ ] " (tasks).
_LIST_MARKER = re.compile(r"^\s*(?:[-*+]\s+(?:\[.\]\s+)?|\d+[.)]\s+)")
# Wiki/markdown link wrappers and basic emphasis we want to strip from a word.
_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_MDLINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_EMPHASIS = re.compile(r"[*_`~]+")


def extract_words(text: str) -> list[str]:
    """Return one cleaned entry per meaningful line, preserving order and de-duping.

    Skips blank lines, markdown headings, block quotes, and horizontal rules.
    Strips list markers, links, and emphasis so "- [[ephemeral]]" -> "ephemeral".
    """
    seen: set[str] = set()
    words: list[str] = []
    for raw in text.splitlines():
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
