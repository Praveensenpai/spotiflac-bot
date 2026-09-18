#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# ==============================================================================
#  SpotiFLAC Bot Installer & Systemd Service Automator
# ==============================================================================

REPO_URL="https://github.com/Praveensenpai/spotiflac-bot.git"

# Terminal formatting
if [ -t 1 ]; then
    COLOR_BLUE="\033[1;34m"
    COLOR_GREEN="\033[1;32m"
    COLOR_YELLOW="\033[1;33m"
    COLOR_RED="\033[1;31m"
    COLOR_BOLD="\033[1m"
    COLOR_RESET="\033[0m"
else
    COLOR_BLUE=""
    COLOR_GREEN=""
    COLOR_YELLOW=""
    COLOR_RED=""
    COLOR_BOLD=""
    COLOR_RESET=""
fi

log_info()  { printf "%bℹ%b %s\n" "$COLOR_BLUE" "$COLOR_RESET" "$*" >&2; }
log_ok()    { printf "%b✔%b %s\n" "$COLOR_GREEN" "$COLOR_RESET" "$*" >&2; }
log_warn()  { printf "%b⚠%b %s\n" "$COLOR_YELLOW" "$COLOR_RESET" "$*" >&2; }
log_error() { printf "%b✖%b %s\n" "$COLOR_RED" "$COLOR_RESET" "$*" >&2; }

TMP_DIR="$(mktemp -d -t spotiflac_install.XXXXXXXXXX)"
cleanup() {
    local exit_code=$?
    rm -rf "$TMP_DIR"
    exit "$exit_code"
}
trap cleanup EXIT INT TERM HUP

# Determine privilege escalations
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        log_error "This installer requires root or sudo privileges to configure system packages and services."
        exit 1
    fi
fi

# Detect true non-root user and home directory
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
    REAL_USER="$SUDO_USER"
else
    REAL_USER="$(id -un)"
fi

REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"
REAL_HOME="${REAL_HOME:-$HOME}"

printf "\n%b🎵 SpotiFLAC Bot Automated Installer%b\n" "$COLOR_BOLD" "$COLOR_RESET"
printf "Target User: %b%s%b\n\n" "$COLOR_BOLD" "$REAL_USER" "$COLOR_RESET"

# 1. Detect or clone repository
INSTALL_DIR=""
if [ -f "pyproject.toml" ] && grep -q "spotiflac-bot" "pyproject.toml" 2>/dev/null; then
    INSTALL_DIR="$(pwd -P)"
    log_info "Detected local repository at: $INSTALL_DIR"
elif [ -d "$REAL_HOME/spotiflac-bot/.git" ]; then
    INSTALL_DIR="$REAL_HOME/spotiflac-bot"
    log_info "Found existing repository at: $INSTALL_DIR"
else
    INSTALL_DIR="$REAL_HOME/spotiflac-bot"
    log_info "Cloning SpotiFLAC bot repository to: $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    chown -R "$REAL_USER:$REAL_USER" "$INSTALL_DIR"
fi

# 2. Install system packages on Debian/Ubuntu
if command -v apt-get >/dev/null 2>&1; then
    log_info "Installing system dependencies via apt (xvfb, ffmpeg, chromium, git, curl)..."
    $SUDO apt-get update -qq
    $SUDO apt-get install -y -qq \
        curl \
        git \
        ffmpeg \
        xvfb \
        chromium-browser >/dev/null 2>&1 || {
            log_warn "chromium-browser package unavailable via apt, attempting alternative..."
            $SUDO apt-get install -y -qq xvfb ffmpeg curl git >/dev/null
        }
    log_ok "System dependencies installed."
else
    log_warn "Non-apt package manager detected. Please ensure curl, git, ffmpeg, and xvfb are installed."
fi

# 3. Ensure uv package manager is installed
UV_BIN="$(command -v uv || true)"
if [ -z "$UV_BIN" ] && [ -x "$REAL_HOME/.local/bin/uv" ]; then
    UV_BIN="$REAL_HOME/.local/bin/uv"
fi

if [ -z "$UV_BIN" ]; then
    log_info "uv not found. Installing uv for $REAL_USER..."
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$REAL_HOME/.local/bin" sh
    UV_BIN="$REAL_HOME/.local/bin/uv"
    chown -R "$REAL_USER:$REAL_USER" "$REAL_HOME/.local" 2>/dev/null || true
    log_ok "uv installed at $UV_BIN"
else
    log_ok "Found uv at $UV_BIN"
fi

# 4. Synchronize Python virtualenv
log_info "Installing project dependencies with uv sync..."
if [ "$(id -u)" -eq 0 ] && [ "$REAL_USER" != "root" ]; then
    su - "$REAL_USER" -c "cd '$INSTALL_DIR' && '$UV_BIN' sync"
else
    (cd "$INSTALL_DIR" && "$UV_BIN" sync)
fi
log_ok "Python environment synchronized."

# 5. Bootstrap configuration files
if [ ! -f "$INSTALL_DIR/config.toml" ]; then
    if [ -f "$INSTALL_DIR/config.example.toml" ]; then
        cp "$INSTALL_DIR/config.example.toml" "$INSTALL_DIR/config.toml"
        log_info "Created config.toml from template."
    fi
fi

# Detect controlling terminal (works even when piped via curl | bash)
HAS_TTY=false
if [ -c /dev/tty ]; then
    HAS_TTY=true
fi

# Configure allowed_user_ids in config.toml
CURRENT_USER_IDS=""
if [ -f "$INSTALL_DIR/config.toml" ]; then
    CURRENT_USER_IDS="$(grep -E '^[[:space:]]*allowed_user_ids[[:space:]]*=' "$INSTALL_DIR/config.toml" | sed -E 's/.*=[[:space:]]*//' || true)"
fi

if [ -n "${ALLOWED_USER_IDS:-}" ]; then
    formatted_ids="$(echo "$ALLOWED_USER_IDS" | awk -F',' '{for(i=1;i<=NF;i++){gsub(/[^0-9]/,"",$i); if(length($i)>0) ids=(ids?ids", ":"")$i}} END {print "["ids"]"}')"
    sed -i "s/allowed_user_ids = .*/allowed_user_ids = $formatted_ids/" "$INSTALL_DIR/config.toml"
    log_ok "Configured allowed_user_ids from environment: $formatted_ids"
elif [ "$HAS_TTY" = true ]; then
    prompt_hint=" (press Enter for all users)"
    if [ -n "$CURRENT_USER_IDS" ] && [ "$CURRENT_USER_IDS" != "[]" ]; then
        prompt_hint=" (current: $CURRENT_USER_IDS, press Enter to keep)"
    fi
    printf "\n%b👤 Enter allowed Telegram User ID(s)%s:%b " "$COLOR_BOLD" "$prompt_hint" "$COLOR_RESET"
    read -r input_user_ids < /dev/tty
    input_trimmed="$(echo "$input_user_ids" | tr -d '[:space:]')"
    if [ -n "$input_trimmed" ] && [ "$input_trimmed" != "all" ]; then
        formatted_ids="$(echo "$input_user_ids" | awk -F',' '{for(i=1;i<=NF;i++){gsub(/[^0-9]/,"",$i); if(length($i)>0) ids=(ids?ids", ":"")$i}} END {print "["ids"]"}')"
        sed -i "s/allowed_user_ids = .*/allowed_user_ids = $formatted_ids/" "$INSTALL_DIR/config.toml"
        log_ok "Configured allowed_user_ids in config.toml: $formatted_ids"
    elif [ -z "$input_trimmed" ] && [ -n "$CURRENT_USER_IDS" ]; then
        log_info "Keeping existing allowed_user_ids: $CURRENT_USER_IDS"
    else
        sed -i "s/allowed_user_ids = .*/allowed_user_ids = []/" "$INSTALL_DIR/config.toml"
        log_info "Allowing all users (allowed_user_ids = [])."
    fi
fi
chown "$REAL_USER:$REAL_USER" "$INSTALL_DIR/config.toml" 2>/dev/null || true

# Configure BOT_TOKEN in .env
CURRENT_TOKEN=""
if [ -f "$INSTALL_DIR/.env" ]; then
    CURRENT_TOKEN="$(grep -E '^BOT_TOKEN=' "$INSTALL_DIR/.env" | cut -d= -f2- | tr -d ' "' || true)"
fi

if [ -n "${BOT_TOKEN:-}" ]; then
    printf "BOT_TOKEN=%s\n" "$BOT_TOKEN" > "$INSTALL_DIR/.env"
    log_ok "Configured BOT_TOKEN from environment."
elif [ "$HAS_TTY" = true ]; then
    prompt_hint=""
    if [ -n "$CURRENT_TOKEN" ]; then
        masked_token="${CURRENT_TOKEN:0:8}...${CURRENT_TOKEN: -4}"
        prompt_hint=" (current: $masked_token, press Enter to keep)"
    fi
    printf "\n%b🔑 Enter your Telegram BOT_TOKEN from @BotFather%s:%b " "$COLOR_BOLD" "$prompt_hint" "$COLOR_RESET"
    read -r input_token < /dev/tty
    input_token="$(echo "$input_token" | tr -d '[:space:]')"
    if [ -n "$input_token" ]; then
        printf "BOT_TOKEN=%s\n" "$input_token" > "$INSTALL_DIR/.env"
        log_ok "Configured BOT_TOKEN in .env."
    elif [ -n "$CURRENT_TOKEN" ]; then
        log_info "Keeping existing BOT_TOKEN."
    else
        cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env" 2>/dev/null || echo "BOT_TOKEN=" > "$INSTALL_DIR/.env"
    fi
else
    if [ ! -f "$INSTALL_DIR/.env" ]; then
        cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env" 2>/dev/null || echo "BOT_TOKEN=" > "$INSTALL_DIR/.env"
    fi
fi
chown "$REAL_USER:$REAL_USER" "$INSTALL_DIR/.env" 2>/dev/null || true
chmod 600 "$INSTALL_DIR/.env" 2>/dev/null || true
log_ok "Configured .env file."

# 6. Configure & deploy systemd service
SERVICE_PATH="/etc/systemd/system/spotiflac-bot.service"
log_info "Deploying systemd service to $SERVICE_PATH..."

cat << EOF | $SUDO tee "$SERVICE_PATH" >/dev/null
[Unit]
Description=SpotiFLAC Telegram Lossless Music Downloader Bot
After=network.target

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
Environment=DISPLAY=:99
Environment="PATH=$REAL_HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$UV_BIN run python -m spotiflac_bot
Restart=always
RestartSec=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

$SUDO systemctl daemon-reload
$SUDO systemctl enable spotiflac-bot.service
log_ok "Systemd service enabled."

# 7. Start service if token is configured
if grep -qE '^BOT_TOKEN=[0-9]+:[A-Za-z0-9_-]+' "$INSTALL_DIR/.env" 2>/dev/null; then
    log_info "BOT_TOKEN detected. Starting spotiflac-bot service..."
    $SUDO systemctl restart spotiflac-bot.service
    log_ok "Service started! You can check logs with: journalctl -u spotiflac-bot -f"
else
    log_warn "BOT_TOKEN is not yet set in $INSTALL_DIR/.env."
    log_info "Edit your credentials and start the service:"
    printf "   nano %s/.env\n" "$INSTALL_DIR"
    printf "   sudo systemctl start spotiflac-bot\n"
fi

printf "\n%b✨ Installation Complete!%b\n" "$COLOR_GREEN" "$COLOR_RESET"
printf "Service status : sudo systemctl status spotiflac-bot\n"
printf "Live logs      : journalctl -u spotiflac-bot -f\n"
printf "Restart bot    : sudo systemctl restart spotiflac-bot\n\n"
