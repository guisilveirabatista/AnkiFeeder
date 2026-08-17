#!/bin/bash
# Serve noVNC and proxy WebSockets to the Xvnc RFB port.
set -u

echo "Waiting for Xvnc on 127.0.0.1:5900..."
for _ in $(seq 1 30); do
  if bash -c 'echo >/dev/tcp/127.0.0.1/5900' 2>/dev/null; then
    echo "Xvnc is up"
    break
  fi
  sleep 1
done

# Bind on all interfaces so Docker port publishing can reach us.
# novnc_proxy is flaky on Ubuntu 24.04 (often looks for a git checkout of
# websockify); the packaged websockify is the reliable path.
exec websockify --web /usr/share/novnc/ 0.0.0.0:6080 127.0.0.1:5900
