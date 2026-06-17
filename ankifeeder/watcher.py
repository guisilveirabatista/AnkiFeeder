"""Poll note file(s) for changes and sync on every save (stdlib only)."""

from __future__ import annotations

import threading
import time

from .feeder import Feeder


def watch(feeder: Feeder) -> None:
    """Watch a single feed in the foreground."""
    print(
        f"Watching {feeder.config.note_path} (deck: {feeder.config.deck_name}). "
        f"{feeder.config.language_summary()} via {feeder.config.translator} "
        f"({feeder.config.active_model()}). Press Ctrl+C to stop."
    )
    stop = threading.Event()
    try:
        _watch_loop(feeder, stop, label="")
    except KeyboardInterrupt:
        print("\nStopped watching.")


def watch_many(feeders: list[Feeder]) -> None:
    """Watch several feeds at once, each in its own thread, in one process."""
    if len(feeders) == 1:
        watch(feeders[0])
        return

    for f in feeders:
        print(
            f"Watching {f.config.note_path} → deck '{f.config.deck_name}' "
            f"[{f.config.language_summary()}, {f.config.translator}: {f.config.active_model()}]"
        )
    print(f"{len(feeders)} feeds running. Press Ctrl+C to stop.")

    stop = threading.Event()
    threads = [
        threading.Thread(
            target=_watch_loop, args=(f, stop), kwargs={"label": f.config.deck_name}, daemon=True
        )
        for f in feeders
    ]
    for t in threads:
        t.start()
    try:
        while not stop.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopped watching.")
        stop.set()


def _watch_loop(feeder: Feeder, stop: threading.Event, label: str = "") -> None:
    # Sync once at startup so existing entries are caught up.
    _safe_sync(feeder, label)
    last_mtime = _mtime(feeder.config.note_path)
    last_sync = time.monotonic()
    retry_interval = feeder.config.retry_interval
    while not stop.wait(feeder.config.poll_interval):
        current = _mtime(feeder.config.note_path)
        changed = current != last_mtime
        # Periodically re-scan even without a save, so words that exhausted their
        # retries (and so weren't recorded in state) get another chance.
        due = retry_interval > 0 and (time.monotonic() - last_sync) >= retry_interval
        if changed or due:
            last_mtime = current
            last_sync = time.monotonic()
            _safe_sync(feeder, label)


def _mtime(path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _safe_sync(feeder: Feeder, label: str = "") -> None:
    prefix = f"[{label}] " if label else ""
    try:
        # In multi-feed mode, suppress per-word lines (they'd interleave) and
        # just print a prefixed summary instead.
        result = feeder.sync(verbose=not label)
        if result.added and label:
            extra = f", {result.failed} failed" if result.failed else ""
            print(f"{prefix}Added {result.added} card(s){extra}.")
        elif result.added:
            print(f"Added {result.added} card(s).")
    except Exception as exc:
        # Never let a transient error (Anki closed, network blip) kill the watcher.
        print(f"{prefix}Sync error: {exc}")
