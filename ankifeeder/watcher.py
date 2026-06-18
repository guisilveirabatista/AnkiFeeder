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


def _log(msg: str, label: str = "") -> None:
    """Print a timestamped, optionally feed-prefixed status line."""
    prefix = f"[{label}] " if label else ""
    print(f"{time.strftime('%H:%M:%S')} {prefix}{msg}", flush=True)


def _watch_loop(feeder: Feeder, stop: threading.Event, label: str = "") -> None:
    # Sync once at startup so existing entries are caught up.
    _safe_sync(feeder, label, reason="startup")
    last_mtime = _mtime(feeder.config.note_path)
    last_sync = time.monotonic()
    retry_interval = feeder.config.retry_interval
    settle_delay = feeder.config.settle_delay
    # Monotonic time of the most recent unsynced change; None when nothing pending.
    pending_since: float | None = None
    parts = [f"checking every {feeder.config.poll_interval:g}s"]
    if settle_delay > 0:
        parts.append(f"settling {settle_delay:g}s after edits")
    if retry_interval > 0:
        parts.append(f"re-scanning every {retry_interval:g}s")
    _log(f"Watching for saves ({', '.join(parts)}).", label)
    while not stop.wait(feeder.config.poll_interval):
        current = _mtime(feeder.config.note_path)
        now = time.monotonic()
        if current != last_mtime:
            # A save landed. Don't sync yet: (re)start the settle timer so an
            # in-progress sentence — or a fast Obsidian sync mid-write — has time
            # to finish before we read it.
            last_mtime = current
            if pending_since is None and settle_delay > 0:
                _log(f"Change detected; waiting {settle_delay:g}s for edits to settle…", label)
            pending_since = now
        # Sync once edits have been quiet for settle_delay, or on the periodic
        # re-scan so words that exhausted their retries get another chance.
        settled = pending_since is not None and (now - pending_since) >= settle_delay
        due = retry_interval > 0 and (now - last_sync) >= retry_interval
        if settled or due:
            pending_since = None
            last_sync = now
            _safe_sync(feeder, label, reason="file changed" if settled else "periodic re-scan")


def _mtime(path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _safe_sync(feeder: Feeder, label: str = "", reason: str = "") -> None:
    why = f" ({reason})" if reason else ""
    _log(f"Syncing{why}…", label)
    try:
        # In multi-feed mode, suppress per-word lines (they'd interleave) and
        # just print a prefixed summary instead.
        result = feeder.sync(verbose=not label, drop_active_line=True)
        dedup = (
            f", {result.duplicates_removed} duplicates removed"
            if result.duplicates_removed
            else ""
        )
        summary = (
            f"Done: {result.added} added, {result.skipped} unchanged, "
            f"{result.failed} failed{dedup}."
        )
        _log(summary, label)
    except Exception as exc:
        # Never let a transient error (Anki closed, network blip) kill the watcher.
        _log(f"Sync error: {exc}", label)
