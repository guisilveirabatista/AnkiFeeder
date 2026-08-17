#!/bin/bash
set -u
# shellcheck source=/dev/null
. /usr/local/bin/desktop-env.sh
export ANKI_BASE="${ANKI_BASE:-/data/anki}"
echo "Starting Anki (DISPLAY=${DISPLAY} ANKI_BASE=${ANKI_BASE})"
exec anki
