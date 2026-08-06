"""Optional AnkiWeb login from environment variables.

Set:
  ANKIWEB_EMAIL
  ANKIWEB_PASSWORD
  ANKIWEB_SYNC_ON_LOGIN=1   (optional; default 1 — sync after a successful login)

Credentials are only applied when the profile does not already have a sync
username/key, so a one-time GUI login (or a previous successful env login)
wins over re-auth every start. Clear the Anki data volume to force re-login.
"""

from __future__ import annotations

import os
import traceback

from aqt import mw
from aqt.gui_hooks import main_window_did_init
from aqt.utils import tooltip


def _log(msg: str) -> None:
    print(f"[ankiweb_login] {msg}", flush=True)


def _already_configured() -> bool:
    try:
        user = mw.pm.sync_username()
        key = mw.pm.sync_key()
        return bool(user and key)
    except Exception:
        return False


def _try_login() -> None:
    email = (os.environ.get("ANKIWEB_EMAIL") or "").strip()
    password = os.environ.get("ANKIWEB_PASSWORD") or ""
    if not email or not password:
        _log("ANKIWEB_EMAIL/ANKIWEB_PASSWORD not set; skip auto-login")
        return

    if _already_configured():
        _log(f"Profile already has AnkiWeb credentials for {mw.pm.sync_username()!r}")
        return

    if mw.col is None:
        _log("Collection not ready yet; will not login")
        return

    _log(f"Attempting AnkiWeb login for {email!r}")
    try:
        endpoint = mw.pm.sync_endpoint()
        # Anki 24.11+ still exposes sync_login on the collection for this path.
        auth = mw.col.sync_login(
            username=email,
            password=password,
            endpoint=endpoint,
        )
        mw.pm.set_sync_key(auth.hkey)
        mw.pm.set_sync_username(email)
        if getattr(auth, "host_key", None):
            # Some versions return extra fields; ignore if absent.
            pass
        _log("AnkiWeb credentials stored in profile")
        try:
            tooltip(f"AnkiWeb: signed in as {email}")
        except Exception:
            pass

        if os.environ.get("ANKIWEB_SYNC_ON_LOGIN", "1").strip() not in (
            "0",
            "false",
            "False",
            "no",
        ):
            _log("Triggering initial sync…")
            try:
                # Prefer the same path the UI uses.
                from aqt import gui_hooks  # noqa: F401

                mw.on_sync_button_clicked()
            except Exception:
                try:
                    mw.col.sync()
                except Exception as exc:
                    _log(f"Sync after login failed: {exc}")
    except Exception as exc:
        _log(f"AnkiWeb login failed: {exc}")
        traceback.print_exc()
        try:
            tooltip(f"AnkiWeb login failed: {exc}")
        except Exception:
            pass


def _on_main_window() -> None:
    # Defer so the collection and UI are fully up.
    try:
        mw.progress.timer(2000, _try_login, False)
    except Exception:
        # Fallback if timer API differs
        try:
            from aqt.qt import QTimer

            QTimer.singleShot(2000, _try_login)
        except Exception as exc:
            _log(f"Could not schedule login: {exc}")


main_window_did_init.append(_on_main_window)
