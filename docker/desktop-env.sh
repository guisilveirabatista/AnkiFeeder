#!/bin/bash
# Shared session environment for GUI programs (Anki, Obsidian, Openbox).
# Sourced; do not exec.

export HOME="${HOME:-/home/app}"
export USER="${USER:-app}"
export DISPLAY="${DISPLAY:-:1}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
export QT_X11_NO_MITSHM=1
export LIBGL_ALWAYS_SOFTWARE=1
export ELECTRON_DISABLE_SANDBOX=1
export ELECTRON_OZONE_PLATFORM_HINT=x11
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=${XDG_RUNTIME_DIR}/bus}"

mkdir -p "${XDG_RUNTIME_DIR}"
chmod 700 "${XDG_RUNTIME_DIR}" 2>/dev/null || true

echo "Waiting for X display ${DISPLAY}..."
for _ in $(seq 1 30); do
  if [[ -S /tmp/.X11-unix/X1 ]]; then
    echo "X socket is up"
    break
  fi
  sleep 1
done
