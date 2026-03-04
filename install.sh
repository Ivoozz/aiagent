#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# install.sh — Automated deployment of the aiagent Telegram bot
# Supports Debian LXC containers and any Debian-based system.
#
# Usage:
#   bash install.sh [--webui]
#
# Non-interactive mode (skip prompts):
#   TELEGRAM_BOT_TOKEN=<token> OPENROUTER_API_KEY=<key> bash install.sh
#
# Safe for piped installs (curl … | bash) — all prompts read from /dev/tty.
# ---------------------------------------------------------------------------

REPO_URL="https://github.com/Ivoozz/aiagent.git"
INSTALL_DIR="/opt/aiagent"
VENV_DIR="${INSTALL_DIR}/.venv"
ENV_FILE="${INSTALL_DIR}/.env"
INSTALL_WEBUI=false

# ── Parse arguments ─────────────────────────────────────────────────────────
for arg in "$@"; do
    case "${arg}" in
        --webui) INSTALL_WEBUI=true ;;
        *) echo "Unknown option: ${arg}" >&2; exit 1 ;;
    esac
done

# ── 1. Pre-flight checks ────────────────────────────────────────────────────
echo "============================================================"
echo "  aiagent Telegram Bot — Automated Installer"
echo "============================================================"

if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: This script must be run as root." >&2
    exit 1
fi

# ── 2. Install system dependencies ─────────────────────────────────────────
echo ""
echo "[1/4] Installing system dependencies..."
apt-get update -qq
apt-get install -y git python3 python3-venv python3-pip

# ── 3. Clone or update the repository ──────────────────────────────────────
echo ""
echo "[2/4] Setting up repository at ${INSTALL_DIR}..."
if [[ -d "${INSTALL_DIR}/.git" ]]; then
    echo "  Directory already exists — pulling latest changes."
    git -C "${INSTALL_DIR}" pull
else
    git clone "${REPO_URL}" "${INSTALL_DIR}"
fi

# ── 4. Python virtual environment & dependencies ───────────────────────────
echo ""
echo "[3/4] Creating Python virtual environment and installing dependencies..."
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip -q
"${VENV_DIR}/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

# ── 5. API key configuration ────────────────────────────────────────────────
echo ""
echo "[4/4] Configuring API keys..."

# Accept credentials from environment variables for non-interactive / piped installs.
# If the variables are already set, skip the interactive prompts entirely.

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
    while true; do
        # Read from /dev/tty so the prompt works even when stdin is a pipe
        # (e.g. curl … | bash).
        # NOTE: disable shell history (HISTFILE) before sensitive input if
        # you are concerned about credentials appearing in ~/.bash_history.
        IFS= read -rsp "Enter your Telegram Bot Token: " TELEGRAM_BOT_TOKEN </dev/tty
        echo
        if [[ -n "${TELEGRAM_BOT_TOKEN}" ]]; then
            break
        fi
        echo "  Token cannot be empty. Please try again."
    done
fi

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
    while true; do
        IFS= read -rsp "Enter your OpenRouter API Key: " OPENROUTER_API_KEY </dev/tty
        echo
        if [[ -n "${OPENROUTER_API_KEY}" ]]; then
            break
        fi
        echo "  Key cannot be empty. Please try again."
    done
fi

# Write credentials with mode 0600 atomically via a subshell + redirect so
# the file is never world-readable even for a moment.
(umask 177; printf 'TELEGRAM_BOT_TOKEN=%s\nOPENROUTER_API_KEY=%s\n' \
    "${TELEGRAM_BOT_TOKEN}" "${OPENROUTER_API_KEY}" > "${ENV_FILE}")

echo ""
echo "============================================================"
echo "  Installation complete!"
echo "  Config written to: ${ENV_FILE}"
echo "  To start the bot:"
echo "    ${VENV_DIR}/bin/python ${INSTALL_DIR}/telegram_bot.py"

# ── 6. Optional web UI scaffold ─────────────────────────────────────────────
if [[ "${INSTALL_WEBUI}" == "true" ]]; then
    echo ""
    echo "[+] Installing optional web UI..."
    "${VENV_DIR}/bin/pip" install -r "${INSTALL_DIR}/webui/requirements.txt" -q

    # Install systemd service for the web UI
    # NOTE: The web UI binds to 127.0.0.1 by default and has no built-in
    # authentication.  For external access, place a reverse proxy (e.g.
    # nginx, Caddy) in front and add authentication there.
    cat > /etc/systemd/system/aiagent-webui.service <<'SERVICE'
[Unit]
Description=aiagent Web UI (Flask)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/aiagent
EnvironmentFile=/opt/aiagent/.env
ExecStart=/opt/aiagent/.venv/bin/python /opt/aiagent/webui/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload
    systemctl enable --now aiagent-webui.service
    echo "  Web UI service installed and started."
    echo "  Access it at: http://localhost:5000"
fi

echo "============================================================"
