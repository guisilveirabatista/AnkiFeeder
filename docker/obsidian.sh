#!/bin/bash
set -u
# shellcheck source=/dev/null
. /usr/local/bin/desktop-env.sh
vault="${OBSIDIAN_VAULT:-/vault}"
echo "Starting Obsidian (DISPLAY=${DISPLAY} vault=${vault})"
exec /usr/local/bin/obsidian --no-sandbox --disable-gpu --disable-dev-shm-usage "${vault}"
