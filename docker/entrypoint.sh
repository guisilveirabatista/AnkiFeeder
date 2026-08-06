#!/usr/bin/env bash
# Prepare Anki profile, Obsidian vault/config, AnkiFeeder config, then exec CMD.
set -euo pipefail

log() { echo "[entrypoint] $*"; }

# ---------------------------------------------------------------------------
# Paths (overridable via env)
# ---------------------------------------------------------------------------
ANKI_BASE="${ANKI_BASE:-/data/anki}"
OBSIDIAN_VAULT="${OBSIDIAN_VAULT:-/vault}"
ANKIFEEDER_CONFIG="${ANKIFEEDER_CONFIG:-/data/ankifeeder/config.json}"
ANKIFEEDER_HOME="${ANKIFEEDER_HOME:-/app/ankifeeder}"
RESOLUTION="${RESOLUTION:-1920x1080}"
VNC_PASSWORD="${VNC_PASSWORD:-}"

mkdir -p \
  "$ANKI_BASE" \
  "$(dirname "$ANKIFEEDER_CONFIG")" \
  "$OBSIDIAN_VAULT" \
  "$HOME/.config/obsidian" \
  "$HOME/.vnc" \
  /tmp/.X11-unix \
  /var/log/supervisor \
  2>/dev/null || true

# Ensure supervisor env placeholders always resolve (empty string is fine).
export VNC_GEOMETRY="${VNC_GEOMETRY:-${RESOLUTION:-1920x1080}}"
export VNC_SECURITY_TYPES="${VNC_SECURITY_TYPES:-None}"
export VNC_PASSWORD_FILE="${VNC_PASSWORD_FILE:-}"
export ANKIWEB_EMAIL="${ANKIWEB_EMAIL:-}"
export ANKIWEB_PASSWORD="${ANKIWEB_PASSWORD:-}"
export ANKIWEB_SYNC_ON_LOGIN="${ANKIWEB_SYNC_ON_LOGIN:-1}"
export OBSIDIAN_EMAIL="${OBSIDIAN_EMAIL:-}"
export OBSIDIAN_PASSWORD="${OBSIDIAN_PASSWORD:-}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export GEMINI_API_KEY="${GEMINI_API_KEY:-}"

# ---------------------------------------------------------------------------
# VNC password (empty VNC_PASSWORD => no authentication)
# ---------------------------------------------------------------------------
if [[ -n "$VNC_PASSWORD" ]]; then
  log "Configuring VNC password authentication"
  printf '%s\n' "$VNC_PASSWORD" | vncpasswd -f > "$HOME/.vnc/passwd"
  chmod 600 "$HOME/.vnc/passwd"
  export VNC_SECURITY_TYPES="VncAuth"
  export VNC_PASSWORD_FILE="$HOME/.vnc/passwd"
else
  log "VNC has no password (set VNC_PASSWORD to enable auth)"
  rm -f "$HOME/.vnc/passwd"
  export VNC_SECURITY_TYPES="None"
  export VNC_PASSWORD_FILE=""
fi

# Geometry for Xvnc
export VNC_GEOMETRY="$RESOLUTION"

# ---------------------------------------------------------------------------
# Anki: ensure a default profile + install bundled add-ons
# ---------------------------------------------------------------------------
PROFILE_DIR="$ANKI_BASE/User 1"
ADDONS_DIR="$PROFILE_DIR/addons21"
mkdir -p "$ADDONS_DIR"

# Minimal prefs so Anki does not re-prompt for a new profile every boot.
# Anki rewrites these after first successful start.
if [[ ! -f "$ANKI_BASE/prefs21.db" && ! -f "$PROFILE_DIR/collection.anki2" ]]; then
  log "First-run Anki profile will be created on launch ($PROFILE_DIR)"
fi

# Symlink/copy bundled add-ons into the live profile (idempotent).
install_addon() {
  local id="$1"
  local src="/opt/anki-addons/$id"
  local dst="$ADDONS_DIR/$id"
  if [[ ! -d "$src" ]]; then
    return 0
  fi
  if [[ -L "$dst" || -d "$dst" ]]; then
    # Refresh config for AnkiConnect bind address if present
    if [[ -f "$src/config.json" && -f "$dst/config.json" ]]; then
      # Keep user config if they customized it; only ensure bind address for AnkiConnect
      if [[ "$id" == "2055492159" ]]; then
        if command -v jq >/dev/null 2>&1; then
          local tmp
          tmp="$(mktemp)"
          jq '.webBindAddress = "0.0.0.0" | .webBindPort = 8765' "$dst/config.json" > "$tmp" \
            && mv "$tmp" "$dst/config.json" || rm -f "$tmp"
        fi
      fi
    fi
    return 0
  fi
  log "Installing Anki add-on: $id"
  cp -a "$src" "$dst"
}

install_addon "2055492159"   # AnkiConnect
install_addon "ankiweb_login"

# Load AnkiConnect on first profile creation: Anki needs the profile dir.
# Create a stub so tools can find the path before Anki opens the collection.
mkdir -p "$PROFILE_DIR"

# ---------------------------------------------------------------------------
# Obsidian: vault + config so the app opens the vault on start
# ---------------------------------------------------------------------------
mkdir -p "$OBSIDIAN_VAULT"

# Sample vocab note used by the default AnkiFeeder config (only if empty vault).
DEFAULT_NOTE="$OBSIDIAN_VAULT/Vocabulary.md"
if [[ ! -f "$DEFAULT_NOTE" ]] && [[ -z "$(find "$OBSIDIAN_VAULT" -type f -name '*.md' 2>/dev/null | head -1)" ]]; then
  log "Seeding sample vault note at $DEFAULT_NOTE"
  cat > "$DEFAULT_NOTE" <<'MD'
# Vocabulary

Add one word or phrase per line. AnkiFeeder turns each into an Anki card.

- ephemeral
- serendipity
MD
fi

# Obsidian vault registry + open-on-start
OBSIDIAN_CFG="$HOME/.config/obsidian/obsidian.json"
if [[ ! -f "$OBSIDIAN_CFG" ]]; then
  log "Writing Obsidian vault config → $OBSIDIAN_VAULT"
  VAULT_ID="$(printf '%s' "$OBSIDIAN_VAULT" | md5sum | awk '{print $1}')"
  TS="$(date +%s)000"
  cat > "$OBSIDIAN_CFG" <<EOF
{
  "vaults": {
    "${VAULT_ID}": {
      "path": "${OBSIDIAN_VAULT}",
      "ts": ${TS},
      "open": true
    }
  }
}
EOF
fi

# Optional Obsidian account hints file (Sync login is interactive via the GUI).
# Credentials are NOT injected into Obsidian (no supported non-interactive API);
# we surface them as a desktop reminder and persist a marker for the user.
if [[ -n "${OBSIDIAN_EMAIL:-}" ]]; then
  cat > "$HOME/DESKTOP-SETUP.txt" <<EOF
Obsidian account
================
Email configured via OBSIDIAN_EMAIL: ${OBSIDIAN_EMAIL}
Password was provided via OBSIDIAN_PASSWORD: $([ -n "${OBSIDIAN_PASSWORD:-}" ] && echo yes || echo no)

To sign in to Obsidian Sync / Account:
  1. Open Obsidian in this desktop (already started).
  2. Settings → Account (or Settings → Sync).
  3. Sign in with the email/password above.

Your Obsidian config is persisted in the obsidian-config volume, so you only
need to do this once per volume.
EOF
else
  cat > "$HOME/DESKTOP-SETUP.txt" <<EOF
Anki + Obsidian desktop
=======================
Open http://localhost:6080/vnc.html on the host to use this desktop.

AnkiWeb login
  - Prefer env vars ANKIWEB_EMAIL + ANKIWEB_PASSWORD (auto login add-on), or
  - In Anki: Tools / Preferences → Sync, or the sync icon.

Obsidian account / Sync
  - Set OBSIDIAN_EMAIL + OBSIDIAN_PASSWORD in compose for a reminder, then
  - In Obsidian: Settings → Account / Sync (one-time; config is volume-backed).

Vault path: ${OBSIDIAN_VAULT}
Anki data:  ${ANKI_BASE}
EOF
fi

# ---------------------------------------------------------------------------
# AnkiFeeder config (generate from env if missing)
# ---------------------------------------------------------------------------
if [[ ! -f "$ANKIFEEDER_CONFIG" ]]; then
  log "Writing AnkiFeeder config → $ANKIFEEDER_CONFIG"
  NOTE_PATH="${NOTE_PATH:-$OBSIDIAN_VAULT/Vocabulary.md}"
  # Expand a leading ~ if the user passed one
  NOTE_PATH="${NOTE_PATH/#\~/$HOME}"
  cat > "$ANKIFEEDER_CONFIG" <<EOF
{
  "note_path": "${NOTE_PATH}",
  "deck_name": "${DECK_NAME:-Obsidian Vocabulary}",
  "anki_connect_url": "${ANKI_CONNECT_URL:-http://127.0.0.1:8765}",
  "model_name": "${MODEL_NAME:-Basic}",
  "translator": "${TRANSLATOR:-claude}",
  "source_language": "${SOURCE_LANGUAGE:-English}",
  "target_language": "${TARGET_LANGUAGE:-Dutch}",
  "claude_model": "${CLAUDE_MODEL:-claude-opus-4-8}",
  "openai_model": "${OPENAI_MODEL:-gpt-4o}",
  "gemini_model": "${GEMINI_MODEL:-gemini-2.5-flash}",
  "local_model": "${LOCAL_MODEL:-llama3.1}",
  "local_base_url": "${LOCAL_BASE_URL:-http://host.docker.internal:11434/v1}",
  "local_api_key": "${LOCAL_API_KEY:-ollama}",
  "poll_interval": ${POLL_INTERVAL:-1.5},
  "settle_delay": ${SETTLE_DELAY:-10.0},
  "retry_interval": ${RETRY_INTERVAL:-1800.0},
  "tag": "${TAG:-ankifeeder}",
  "sync_after_add": ${SYNC_AFTER_ADD:-true},
  "dedup_note": ${DEDUP_NOTE:-true},
  "request_delay": ${REQUEST_DELAY:-2.0},
  "max_retries": ${MAX_RETRIES:-3},
  "retry_backoff": ${RETRY_BACKOFF:-2.0}
}
EOF
else
  log "Using existing AnkiFeeder config at $ANKIFEEDER_CONFIG"
fi

# Export for child processes / supervisord programs
export ANKI_BASE OBSIDIAN_VAULT ANKIFEEDER_CONFIG ANKIFEEDER_HOME
export DISPLAY="${DISPLAY:-:1}"
export QT_X11_NO_MITSHM=1
export QT_QPA_PLATFORM=xcb
export LIBGL_ALWAYS_SOFTWARE=1
export ELECTRON_DISABLE_SANDBOX=1
export ELECTRON_OZONE_PLATFORM_HINT=x11

# AnkiWeb credentials are consumed by the ankiweb_login add-on
export ANKIWEB_EMAIL="${ANKIWEB_EMAIL:-}"
export ANKIWEB_PASSWORD="${ANKIWEB_PASSWORD:-}"
export ANKIWEB_SYNC_ON_LOGIN="${ANKIWEB_SYNC_ON_LOGIN:-1}"

# Translator API keys (already typically set via compose env)
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export GEMINI_API_KEY="${GEMINI_API_KEY:-}"

if [[ -n "$ANKIWEB_EMAIL" ]]; then
  log "AnkiWeb email is set; login add-on will attempt auth after Anki starts"
fi
if [[ -z "${ANTHROPIC_API_KEY}${OPENAI_API_KEY}${GEMINI_API_KEY}" ]]; then
  log "Warning: no translator API key set (ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY)"
fi

log "Starting: $*"
exec "$@"
