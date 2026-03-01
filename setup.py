#!/usr/bin/env python3
"""
setup.py – One-time initialization script for the AI agent.

Run this script before starting the agent for the first time.
It will:
  1. Prompt the user for their OpenRouter API key.
  2. Prompt the user for their Telegram Bot Token.
  3. Write both values to a .env file so the agent can load them with
     python-dotenv.
  4. Install the required Python dependencies from requirements.txt.
"""

import os
import subprocess
import sys


ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
REQUIREMENTS_FILE = os.path.join(os.path.dirname(__file__), "requirements.txt")


def prompt_value(prompt: str) -> str:
    """Interactively prompt the user for a non-empty value."""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Value cannot be empty. Please try again.")


def save_env(openrouter_key: str, telegram_token: str) -> None:
    """Write (or overwrite) the .env file with the provided credentials.

    The file is created with mode 0o600 (owner read/write only) to protect
    the secrets from unauthorized access on multi-user systems.
    """
    # Open with explicit mode 0o600 so the keys are only readable by the owner.
    fd = os.open(ENV_FILE, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"OPENROUTER_API_KEY={openrouter_key}\n")
        f.write(f"TELEGRAM_BOT_TOKEN={telegram_token}\n")
    print(f"\n✔  Credentials saved to {ENV_FILE}")


def install_dependencies() -> None:
    """Install Python dependencies listed in requirements.txt."""
    if not os.path.isfile(REQUIREMENTS_FILE):
        print("requirements.txt not found – skipping dependency installation.")
        return
    print("\nInstalling dependencies from requirements.txt …")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_FILE],
        check=False,
    )
    if result.returncode == 0:
        print("✔  Dependencies installed successfully.")
    else:
        print(
            "⚠  Dependency installation finished with errors. "
            "Please review the output above."
        )


def main() -> None:
    print("\n=== AI Agent – First-Time Setup ===\n")
    openrouter_key = prompt_value("Please enter your OpenRouter API Key: ")
    telegram_token = prompt_value("Please enter your Telegram Bot Token: ")
    save_env(openrouter_key, telegram_token)
    install_dependencies()
    print(
        "\nSetup complete. You can now:\n"
        "  • Start the terminal agent :  python agent.py\n"
        "  • Start the Telegram bot   :  python telegram_bot.py\n"
    )


if __name__ == "__main__":
    main()
