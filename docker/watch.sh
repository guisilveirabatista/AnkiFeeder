#!/bin/bash
# Wait for AnkiConnect, then run ankifeeder watch.
set -u

echo "Waiting for AnkiConnect on 127.0.0.1:8765..."
for _ in $(seq 1 90); do
  if python3 -c 'import urllib.request; r=urllib.request.Request("http://127.0.0.1:8765", data=b"{\"action\":\"version\",\"version\":6}", headers={"Content-Type":"application/json"}); urllib.request.urlopen(r, timeout=2)' 2>/dev/null; then
    echo "AnkiConnect is up"
    break
  fi
  sleep 2
done

exec /app/venv/bin/python -m ankifeeder -c "${ANKIFEEDER_CONFIG:-/data/ankifeeder/config.json}" watch
