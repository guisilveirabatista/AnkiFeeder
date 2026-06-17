"""Command-line entry point for AnkiFeeder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, Config
from .feeder import Feeder
from .watcher import watch_many

CONFIG_TEMPLATE = """{
  "note_path": "~/Obsidian/Vault/Vocabulary.md",
  "deck_name": "Obsidian Vocabulary",
  "anki_connect_url": "http://127.0.0.1:8765",
  "model_name": "Basic",
  "translator": "claude",
  "source_language": "English",
  "target_language": "Dutch",
  "claude_model": "claude-opus-4-8",
  "openai_model": "gpt-4o",
  "gemini_model": "gemini-2.5-flash",
  "local_model": "llama3.1",
  "local_base_url": "http://localhost:11434/v1",
  "local_api_key": "ollama",
  "poll_interval": 1.5,
  "settle_delay": 10.0,
  "retry_interval": 1800.0,
  "tag": "ankifeeder",
  "sync_after_add": true,
  "request_delay": 2.0,
  "max_retries": 3,
  "retry_backoff": 2.0
}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ankifeeder",
        description="Watch an Obsidian note and feed its words into Anki as cards.",
    )
    parser.add_argument(
        "-c", "--config", type=Path, default=DEFAULT_CONFIG_PATH,
        help=f"Path to config file (default: {DEFAULT_CONFIG_PATH}).",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("watch", help="Watch the note and add words as you save (default).")
    sub.add_parser("sync", help="Add any new words once, then exit.")
    sub.add_parser("init", help="Write a config.json template to get started.")
    args = parser.parse_args(argv)

    command = args.command or "watch"

    if command == "init":
        return _init(args.config)

    try:
        configs = Config.load_all(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    feeders = [Feeder(c) for c in configs]

    if command == "sync":
        for feeder in feeders:
            label = f"[{feeder.config.deck_name}] " if len(feeders) > 1 else ""
            print(
                f"{label}{feeder.config.language_summary()} via "
                f"{feeder.config.translator} ({feeder.config.active_model()})."
            )
            try:
                result = feeder.sync()
            except Exception as exc:
                print(f"{label}Error: {exc}", file=sys.stderr)
                continue
            print(
                f"{label}Done. added={result.added} skipped={result.skipped} "
                f"failed={result.failed}"
            )
        return 0

    if command == "watch":
        watch_many(feeders)
        return 0

    parser.print_help()
    return 1


def _init(path: Path) -> int:
    if path.exists():
        print(f"{path} already exists; not overwriting.", file=sys.stderr)
        return 1
    path.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    print(f"Wrote {path}. Edit `note_path` to point at your Obsidian note, then run "
          "`python -m ankifeeder watch`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
