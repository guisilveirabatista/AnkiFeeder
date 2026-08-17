#!/bin/bash
set -u
# shellcheck source=/dev/null
. /usr/local/bin/desktop-env.sh
export ANKI_BASE="${ANKI_BASE:-/data/anki}"
# Anki 24+ draws the main window in Qt WebEngine. Without this, the process
# stays alive (supervisor RUNNING, AnkiConnect works) but no window appears.
export QTWEBENGINE_DISABLE_SANDBOX=1
export QTWEBENGINE_CHROMIUM_FLAGS="${QTWEBENGINE_CHROMIUM_FLAGS:---no-sandbox --disable-gpu --disable-dev-shm-usage}"
export QT_OPENGL="${QT_OPENGL:-software}"
echo "Starting Anki (DISPLAY=${DISPLAY} ANKI_BASE=${ANKI_BASE})"
exec anki --base "${ANKI_BASE}"
