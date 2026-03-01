#!/usr/bin/env python3
"""
telegram_bot.py – Telegram bot interface for the autonomous AI agent.

Each Telegram message is treated as a new goal.  The bot runs the agent loop
(generate → execute → iterate) and streams status updates back to the user,
finishing with the final answer or an error summary.

Usage:
    python telegram_bot.py

Make sure you have run setup.py first so that the .env file contains both
OPENROUTER_API_KEY and TELEGRAM_BOT_TOKEN.
"""

import logging
import os
import sys
from typing import Any

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Import the core agent logic from agent.py (same directory)
from agent import (
    SYSTEM_PROMPT,
    MAX_ITERATIONS,
    build_client,
    call_llm,
    execute_command,
    parse_llm_response,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Maximum characters of command output to send in a single Telegram message.
# Telegram's message limit is 4096 characters; we leave headroom for markup.
MAX_OUTPUT_LENGTH: int = 3000

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Handler helpers
# ---------------------------------------------------------------------------


async def _run_agent_and_reply(
    update: Update,
    goal: str,
    llm_client: Any,
) -> None:
    """Run the full agent loop for *goal* and send results via *update*.

    Progress messages (thought + command + output) are sent as the loop runs
    so the user sees incremental updates rather than a long silence.

    Args:
        update: The Telegram Update object used to send replies.
        goal: The natural-language task to accomplish.
        llm_client: An initialised OpenAI-compatible client.
    """
    assert update.effective_message is not None  # type narrowing

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": goal},
    ]

    await update.effective_message.reply_text(
        f"🤖 *Starting task:* {goal}", parse_mode="Markdown"
    )

    for iteration in range(1, MAX_ITERATIONS + 1):
        raw_response = call_llm(llm_client, messages)
        parsed = parse_llm_response(raw_response)

        if "error" in parsed:
            await update.effective_message.reply_text(
                f"⚠️ *Parse error (iteration {iteration}):* {parsed['error']}\n"
                "Asking the model to self-correct…",
                parse_mode="Markdown",
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"[SYSTEM] Your last response could not be parsed as JSON. "
                        f"Error: {parsed['error']}\n"
                        "Please reply with a valid JSON object only."
                    ),
                }
            )
            continue

        thought: str = parsed.get("thought", "")
        command: str = parsed.get("command", "").strip()
        final_answer: str = parsed.get("final_answer", "")

        if not command:
            # Task complete – send the final answer
            await update.effective_message.reply_text(
                f"✅ *Task complete!*\n\n{final_answer or 'No final answer provided.'}",
                parse_mode="Markdown",
            )
            return

        # Send a status update showing what the agent is doing
        status = (
            f"🔄 *Iteration {iteration}/{MAX_ITERATIONS}*\n"
            f"💭 *Thought:* {thought}\n"
            f"💻 *Command:* `{command}`"
        )
        await update.effective_message.reply_text(status, parse_mode="Markdown")

        # Execute the command and report the output
        output = execute_command(command)
        output_preview = output[:MAX_OUTPUT_LENGTH] + ("…" if len(output) > MAX_OUTPUT_LENGTH else "")
        await update.effective_message.reply_text(
            f"📤 *Output:*\n```\n{output_preview}\n```", parse_mode="Markdown"
        )

        # Extend conversation history
        messages.append({"role": "assistant", "content": raw_response})
        messages.append(
            {"role": "user", "content": f"Command output:\n{output}"}
        )

    await update.effective_message.reply_text(
        f"⏹ *Reached maximum iterations ({MAX_ITERATIONS}).* "
        "The task may be incomplete.",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Telegram command / message handlers
# ---------------------------------------------------------------------------


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start – Welcome message."""
    assert update.effective_message is not None
    await update.effective_message.reply_text(
        "👋 Hello! I'm your autonomous AI agent.\n\n"
        "Send me any task in plain English and I'll execute it on the server.\n\n"
        "_Example:_ Install nginx and serve a Hello World page on port 8080",
        parse_mode="Markdown",
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help – Usage instructions."""
    assert update.effective_message is not None
    await update.effective_message.reply_text(
        "*Available commands:*\n"
        "/start – Show welcome message\n"
        "/help  – Show this help text\n\n"
        "Simply send any plain-text message to start a new task.",
        parse_mode="Markdown",
    )


async def message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle plain-text messages as agent goals."""
    assert update.effective_message is not None
    goal = (update.effective_message.text or "").strip()
    if not goal:
        return

    llm_client = context.bot_data.get("llm_client")
    if llm_client is None:
        await update.effective_message.reply_text(
            "❌ LLM client is not initialised. Please check your OPENROUTER_API_KEY."
        )
        return

    try:
        await _run_agent_and_reply(update, goal, llm_client)
    except Exception:  # noqa: BLE001 – log full details server-side only
        logger.exception("Unhandled error during agent run")
        await update.effective_message.reply_text(
            "❌ An unexpected error occurred while processing your request. "
            "Please try again or check the server logs for details."
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the Telegram bot (blocking)."""
    if not TELEGRAM_BOT_TOKEN:
        print(
            "[ERROR] TELEGRAM_BOT_TOKEN is not set.\n"
            "Please run setup.py first to configure your credentials."
        )
        sys.exit(1)

    # Build the shared LLM client once; store it in bot_data so handlers can
    # access it without rebuilding it on every message.
    llm_client = build_client()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.bot_data["llm_client"] = llm_client

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("Telegram bot is running. Press Ctrl-C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
