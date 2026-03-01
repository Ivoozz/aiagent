#!/usr/bin/env python3
"""
setup.py – One-time initialization script for the AI agent.

Run this script before starting the agent for the first time.
It will:
  1. Prompt the user for their OpenRouter API key.
  2. Write the key to a .env file so the agent can load it with python-dotenv.
  3. Install the required Python dependencies from requirements.txt.
"""

import os
import subprocess
import sys


ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
REQUIREMENTS_FILE = os.path.join(os.path.dirname(__file__), "requirements.txt")


def prompt_api_key() -> str:
    """Interactively prompt the user for their OpenRouter API key."""
    print("\n=== AI Agent – First-Time Setup ===\n")
    while True:
        key = input("Please enter your OpenRouter API Key: ").strip()
        if key:
            return key
        print("API key cannot be empty. Please try again.")


def save_env(api_key: str) -> None:
    """Write (or overwrite) the .env file with the provided API key.

    The file is created with mode 0o600 (owner read/write only) to protect
    the API key on multi-user systems.
    """
    # Open with explicit mode 0o600 so the key is only readable by the owner.
    fd = os.open(ENV_FILE, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"OPENROUTER_API_KEY={api_key}\n")
    print(f"\n✔  API key saved to {ENV_FILE}")


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
    api_key = prompt_api_key()
    save_env(api_key)
    install_dependencies()
    print(
        "\nSetup complete. You can now start the agent by running:\n"
        "    python agent.py\n"
    )


if __name__ == "__main__":
    main()
