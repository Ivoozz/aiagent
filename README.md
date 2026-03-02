# 🤖 aiagent

An autonomous AI agent that runs inside a Debian Linux system (e.g. an LXC container). Give it a natural-language goal and it will plan, execute shell commands, observe the output, and iterate until the task is complete — all powered by an LLM via [OpenRouter](https://openrouter.ai/). Comes with both a **terminal interface** and a **Telegram bot** for remote control.

---

## ✨ Features

- **Autonomous task execution** — Describe what you want in plain English; the agent figures out the bash commands to run.
- **Iterative reasoning loop** — The agent thinks → acts → observes → repeats, self-correcting on errors.
- **OpenRouter LLM backend** — Uses `openrouter/auto` by default, giving you access to a wide range of models.
- **Telegram bot interface** — Control the agent remotely from any Telegram client with real-time progress updates.
- **Terminal interface** — Run the agent interactively from the command line.
- **Safety guardrails** — Configurable command timeout (60 s), max iteration cap (30), and non-interactive command preferences.
- **One-command installer** — Automated `install.sh` script handles system deps, Python venv, and API key configuration.

---

## 📁 Project Structure

```
aiagent/
├── agent.py            # Core autonomous agent (LLM loop + command execution)
├── telegram_bot.py     # Telegram bot interface for remote control
├── setup.py            # Interactive first-time setup (API keys + deps)
├── install.sh          # Automated deployment script for Debian systems
├── requirements.txt    # Python dependencies
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Debian-based Linux** system (tested on Debian LXC containers)
- An [OpenRouter API key](https://openrouter.ai/)
- A [Telegram Bot Token](https://core.telegram.org/bots#botfather) *(optional, for the Telegram interface)*

### Option 1 — Automated Install (recommended)

Run the installer as root on a Debian-based system:

```bash
curl -fsSL https://raw.githubusercontent.com/Ivoozz/aiagent/main/install.sh | bash
```

Or clone first and run locally:

```bash
git clone https://github.com/Ivoozz/aiagent.git
cd aiagent
sudo bash install.sh
```

The installer will:
1. Install system dependencies (`git`, `python3`, `python3-venv`, `python3-pip`)
2. Clone/update the repo to `/opt/aiagent`
3. Create a Python virtual environment and install packages
4. Prompt you for your **Telegram Bot Token** and **OpenRouter API Key**

### Option 2 — Manual Setup

```bash
git clone https://github.com/Ivoozz/aiagent.git
cd aiagent
python3 setup.py
```

The setup script will interactively ask for your API keys, save them to a `.env` file, and install Python dependencies.

---

## 🖥️ Usage

### Terminal Agent

Run the agent in your terminal for interactive, one-off tasks:

```bash
python3 agent.py
```

You will be prompted to enter a natural-language goal. The agent will then autonomously plan and execute commands to accomplish it.

**Example:**

```
🎯 Enter your goal: Install nginx and configure a basic static site on port 8080
```

### Telegram Bot

Start the Telegram bot for remote access:

```bash
python3 telegram_bot.py
```

Then open your bot in Telegram and send any message — each message is treated as a new goal. The bot streams progress updates (thoughts, commands, outputs) back to you in real time.

**Telegram Commands:**
| Command | Description |
|---------|-------------|
| `/start` | Welcome message and usage instructions |
| `/help`  | Show available commands |
| Any text | Treated as a new goal for the agent |

---

## ⚙️ Configuration

Configuration is managed via environment variables in a `.env` file:

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | ✅ | Your OpenRouter API key |
| `TELEGRAM_BOT_TOKEN` | For Telegram bot | Your Telegram Bot API token |

**Agent constants** (in `agent.py`):

| Constant | Default | Description |
|----------|---------|-------------|
| `MODEL` | `openrouter/auto` | The LLM model to use via OpenRouter |
| `COMMAND_TIMEOUT` | `60` seconds | Max time for a single shell command |
| `MAX_ITERATIONS` | `30` | Max agent loop iterations to prevent runaway execution |

---

## 🔧 Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `openai` | ≥ 1.0.0 | OpenAI-compatible client for OpenRouter API |
| `python-dotenv` | ≥ 1.0.0 | Load environment variables from `.env` |
| `python-telegram-bot` | ≥ 20.0 | Telegram Bot API wrapper |

---

## 🏗️ How It Works

1. **User provides a goal** (via terminal or Telegram).
2. **System prompt** instructs the LLM to act as an autonomous Linux agent.
3. **LLM responds** with a JSON object containing its `thought` and a `command` to execute.
4. **Agent executes** the command via `subprocess` and captures stdout/stderr.
5. **Output is fed back** to the LLM as context for the next iteration.
6. **Loop repeats** until the LLM returns a `final_answer` (empty command) or the iteration limit is reached.

```
┌──────────┐     goal      ┌──────────┐    command    ┌──────────┐
│   User   │──────────────▶│  Agent   │──────────────▶│  Shell   │
│          │               │  (LLM)   │◀──────────────│ (bash)   │
│          │◀──────────────│          │    output      │          │
│          │  final_answer │          │               │          │
└──────────┘               └──────────┘               └──────────┘
```

---

## ⚠️ Security Notice

This agent **executes shell commands as the current user**. When run as root (e.g. inside an LXC container), it has full system access. Use responsibly:

- Run in an **isolated environment** (LXC container, VM, or sandbox).
- **Never expose** the agent to untrusted input on production systems.
- API keys are stored in `.env` with `0600` permissions (owner-only read/write).

---

## 📄 License

This project is open source. See the repository for license details.

---

## 🤝 Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
