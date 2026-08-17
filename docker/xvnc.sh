#!/bin/bash
# Start TigerVNC's X server on display :1 / RFB port 5900.
set -u

mkdir -p /tmp/.X11-unix "${HOME:-/home/app}/.vnc"
chmod 1777 /tmp/.X11-unix 2>/dev/null || true
# Stale locks from a previous crash prevent Xvnc from binding the display.
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1

geom="${VNC_GEOMETRY:-1920x1080}"
auth_args=( -SecurityTypes None )
if [[ -n "${VNC_PASSWORD_FILE:-}" && -f "${VNC_PASSWORD_FILE}" ]]; then
  auth_args=( -SecurityTypes VncAuth -PasswordFile "${VNC_PASSWORD_FILE}" )
fi

# TigerVNC 1.13+: boolean params are -name=0/1, not "-name no".
# -ac lets Openbox/Anki/Obsidian attach without an Xauthority file.
exec Xvnc :1 \
  -geometry "${geom}" \
  -depth 24 \
  -rfbport 5900 \
  -localhost=0 \
  -AlwaysShared \
  -ac \
  "${auth_args[@]}"
