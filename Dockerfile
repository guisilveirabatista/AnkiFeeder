# AnkiFeeder stack: Anki (+ AnkiConnect) + Obsidian + AnkiFeeder
# Desktop GUIs are reachable via noVNC in a browser.
#
# Build:  docker compose build
# Run:    docker compose up -d
# UI:     http://localhost:6080/vnc.html

FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG ANKI_VERSION=26.08
ARG OBSIDIAN_VERSION=1.13.4
ARG TARGETARCH

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    # Desktop
    DISPLAY=:1 \
    RESOLUTION=1920x1080 \
    VNC_PORT=5900 \
    NOVNC_PORT=6080 \
    # Anki
    ANKI_BASE=/data/anki \
    # Obsidian
    OBSIDIAN_VAULT=/vault \
    # AnkiFeeder
    ANKIFEEDER_HOME=/app/ankifeeder \
    ANKIFEEDER_CONFIG=/data/ankifeeder/config.json \
    PYTHONUNBUFFERED=1

# ---------------------------------------------------------------------------
# System packages
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl wget gnupg \
        python3 python3-pip python3-venv \
        zstd xz-utils unzip jq \
        # Desktop / VNC
        tigervnc-standalone-server tigervnc-common \
        openbox xterm fonts-dejavu-core \
        novnc websockify \
        dbus-x11 \
        supervisor \
        # Shared GUI / Chromium-Electron / Qt runtime deps
        libnss3 libnspr4 libatk-bridge2.0-0 libatk1.0-0 libcups2 \
        libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
        libxrandr2 libgbm1 libasound2t64 libpango-1.0-0 libcairo2 \
        libx11-xcb1 libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 \
        libxcb-keysyms1 libxcb-render-util0 libxcb-shape0 libxcb-shm0 \
        libxshmfence1 libglu1-mesa libgl1 libegl1 \
        libxtst6 libxi6 libxrender1 libsm6 libice6 \
        libgtk-3-0 libnotify4 libxss1 xdg-utils \
        # Audio optional for Anki
        mpv \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Anki desktop (official Linux bundle)
# ---------------------------------------------------------------------------
RUN set -eux; \
    case "${TARGETARCH:-amd64}" in \
      amd64|x86_64) ANKI_ARCH=x86_64 ;; \
      arm64|aarch64) ANKI_ARCH=aarch64 ;; \
      *) echo "Unsupported arch: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fL -o /tmp/anki.tar.zst \
      "https://github.com/ankitects/anki/releases/download/${ANKI_VERSION}/anki-${ANKI_VERSION}-linux-${ANKI_ARCH}.tar.zst"; \
    mkdir -p /tmp/anki; \
    tar -x --zstd -f /tmp/anki.tar.zst -C /tmp/anki --strip-components=1; \
    # install.sh wants to register MIME types; skip those lines in containers
    (cd /tmp/anki && sed -E 's/^(xdg-mime|update-desktop-database)/# \1/' install.sh | bash); \
    rm -rf /tmp/anki /tmp/anki.tar.zst

# ---------------------------------------------------------------------------
# AnkiConnect add-on (bundled into the image; wired into the profile at runtime)
# ---------------------------------------------------------------------------
RUN set -eux; \
    mkdir -p /opt/anki-addons/2055492159; \
    curl -fL "https://github.com/FooSoft/anki-connect/archive/refs/heads/master.tar.gz" \
      | tar -xz -C /tmp; \
    cp -a /tmp/anki-connect-master/plugin/. /opt/anki-addons/2055492159/; \
    # Allow connections from outside localhost (other containers / host)
    if [ -f /opt/anki-addons/2055492159/config.json ]; then \
      jq '.webBindAddress = "0.0.0.0" | .webBindPort = 8765' \
        /opt/anki-addons/2055492159/config.json > /tmp/ac.json \
        && mv /tmp/ac.json /opt/anki-addons/2055492159/config.json; \
    else \
      printf '%s\n' '{"apiKey":null,"apiLogPath":null,"ignoreOriginList":[],"webBindAddress":"0.0.0.0","webBindPort":8765,"webCorsOriginList":["http://localhost"]}' \
        > /opt/anki-addons/2055492159/config.json; \
    fi; \
    printf '%s\n' '{"name":"AnkiConnect","mod":0,"disabled":false,"max_level":0,"min_point_version":0,"max_point_version":0,"branch_index":0,"config":{}}' \
      > /opt/anki-addons/2055492159/meta.json; \
    rm -rf /tmp/anki-connect-master

# Small add-on: optional AnkiWeb login from ANKIWEB_EMAIL / ANKIWEB_PASSWORD
COPY docker/addons/ankiweb_login /opt/anki-addons/ankiweb_login

# ---------------------------------------------------------------------------
# Obsidian (AppImage extracted — no FUSE required)
# ---------------------------------------------------------------------------
RUN set -eux; \
    case "${TARGETARCH:-amd64}" in \
      amd64|x86_64) OBS_ASSET="Obsidian-${OBSIDIAN_VERSION}.AppImage" ;; \
      arm64|aarch64) OBS_ASSET="Obsidian-${OBSIDIAN_VERSION}-arm64.AppImage" ;; \
      *) echo "Unsupported arch for Obsidian: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fL -o /tmp/Obsidian.AppImage \
      "https://github.com/obsidianmd/obsidian-releases/releases/download/v${OBSIDIAN_VERSION}/${OBS_ASSET}"; \
    chmod +x /tmp/Obsidian.AppImage; \
    cd /tmp && ./Obsidian.AppImage --appimage-extract; \
    mv /tmp/squashfs-root /opt/obsidian; \
    # Convenience launcher
    printf '%s\n' '#!/bin/sh' \
      'exec /opt/obsidian/obsidian --no-sandbox --disable-gpu "$@"' \
      > /usr/local/bin/obsidian; \
    chmod +x /usr/local/bin/obsidian; \
    rm -f /tmp/Obsidian.AppImage

# ---------------------------------------------------------------------------
# AnkiFeeder application
# ---------------------------------------------------------------------------
WORKDIR /app/ankifeeder
COPY requirements.txt ./
RUN python3 -m venv /app/venv \
    && /app/venv/bin/pip install --no-cache-dir -U pip \
    && /app/venv/bin/pip install --no-cache-dir -r requirements.txt

COPY ankifeeder ./ankifeeder
COPY bin ./bin
COPY config.json ./

# ---------------------------------------------------------------------------
# Runtime user, dirs, supervisor + entrypoint
# ---------------------------------------------------------------------------
# ubuntu:24.04 already ships UID/GID 1000 as "ubuntu". Recreate as "app".
# Stay root so the entrypoint can chown named volumes; supervisord then
# drops privileges to app.
RUN if getent passwd ubuntu >/dev/null; then userdel -r ubuntu || userdel ubuntu; fi \
    && if getent group ubuntu >/dev/null; then groupdel ubuntu || true; fi \
    && if getent group 1000 >/dev/null; then groupmod -n app "$(getent group 1000 | cut -d: -f1)"; \
       else groupadd -g 1000 app; fi \
    && useradd -m -u 1000 -g app -s /bin/bash app \
    && mkdir -p \
         /data/anki \
         /data/ankifeeder \
         /vault \
         /home/app/.config/obsidian \
         /home/app/.vnc \
         /var/log/supervisor \
         /var/run \
    && chown -R app:app /app /data /vault /home/app /var/log/supervisor

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY docker/watch.sh /usr/local/bin/ankifeeder-watch.sh
COPY docker/xvnc.sh /usr/local/bin/xvnc.sh
COPY docker/supervisord.conf /etc/supervisor/conf.d/ankifeeder.conf
COPY docker/config/openbox-rc.xml /etc/xdg/openbox/rc.xml

RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/ankifeeder-watch.sh /usr/local/bin/xvnc.sh \
    && mkdir -p /etc/supervisor \
    && chown app:app /etc/supervisor/conf.d/ankifeeder.conf

WORKDIR /home/app

EXPOSE 5900 6080 8765

VOLUME ["/data/anki", "/data/ankifeeder", "/vault", "/home/app/.config/obsidian"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/ankifeeder.conf"]
