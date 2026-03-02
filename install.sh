#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# install.sh — Automated deployment of the aiagent Telegram bot
# Supports Debian LXC containers and any Debian-based system.
# ---------------------------------------------------------------------------

REPO_URL="https://github.com/Ivoozz/aiagent.git"
INSTALL_DIR="/opt/aiagent"
VENV_DIR="${INSTALL_DIR}/.venv"
ENV_FILE="${INSTALL_DIR}/.env"

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

# ── 5. Interactive API key prompts ──────────────────────────────────────────
echo ""
echo "[4/4] Configuring API keys..."

while true; do
    read -rsp "Enter your Telegram Bot Token: " TELEGRAM_BOT_TOKEN
    echo
    if [[ -n "${TELEGRAM_BOT_TOKEN}" ]]; then
        break
    fi
    echo "  Token cannot be empty. Please try again."
done

while true; do
    read -rsp "Enter your OpenRouter API Key: " OPENROUTER_API_KEY
    echo
    if [[ -n "${OPENROUTER_API_KEY}" ]]; then
        break
    fi
    echo "  Key cannot be empty. Please try again."
done

printf 'TELEGRAM_BOT_TOKEN=%s\nOPENROUTER_API_KEY=%s\n' \
    "${TELEGRAM_BOT_TOKEN}" "${OPENROUTER_API_KEY}" > "${ENV_FILE}"
chmod 0600 "${ENV_FILE}"

echo ""
echo "============================================================"
echo "  Installation complete!"
echo "  Config written to: ${ENV_FILE}"
echo "  To start the bot:"
echo "    ${VENV_DIR}/bin/python ${INSTALL_DIR}/telegram_bot.py"
echo "============================================================"
