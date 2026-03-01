#!/usr/bin/env python3
"""
agent.py – Autonomous AI agent that runs inside a Debian LXC.

The agent accepts a natural-language goal from the user, uses an LLM (via
OpenRouter) to generate bash commands, executes them on the local system,
feeds the output back to the LLM, and iterates until the task is complete.

Usage:
    python agent.py

Make sure you have run setup.py first so that the .env file exists with a
valid OPENROUTER_API_KEY.
"""

import json
import os
import subprocess
import sys
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI, AuthenticationError, APIConnectionError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Load OPENROUTER_API_KEY (and any other variables) from .env
load_dotenv()

OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
MODEL: str = "openrouter/auto"

# Maximum seconds to wait for a single shell command to finish.
COMMAND_TIMEOUT: int = 60

# Maximum iterations of the agent loop to prevent infinite loops.
MAX_ITERATIONS: int = 30

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT: str = """You are an autonomous AI agent running directly inside a Debian Linux system.
Your job is to accomplish the user's goal by generating and executing bash commands one step at a time.

For EVERY response you MUST output a single, valid JSON object – nothing else.
The JSON object must contain EXACTLY these fields:

{
  "thought": "<your reasoning about what to do next>",
  "command": "<the single bash command to run, or empty string if the task is done>"
}

If the task is complete, use this format instead:

{
  "thought": "<your reasoning about why the task is done>",
  "command": "",
  "final_answer": "<a human-readable summary of what was accomplished>"
}

Rules:
- Output ONLY the JSON object. No markdown, no code fences, no extra text.
- Prefer non-interactive commands (e.g., use `apt-get install -y` not `apt-get install`).
- Never include commands that could cause irreversible system damage without explicit user instruction.
- After each command you will receive the combined stdout/stderr output as feedback.
- Use that feedback to decide your next step.
- If a command fails, diagnose the error and try a corrective command.
"""

# ---------------------------------------------------------------------------
# Execution engine
# ---------------------------------------------------------------------------


def execute_command(command: str) -> str:
    """Run *command* in a bash shell and return the combined stdout/stderr output.

    Args:
        command: The bash command string to execute.

    Returns:
        A string containing combined stdout and stderr.  If the command times
        out, a descriptive error message is returned instead of raising.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
        )
        output = result.stdout + result.stderr
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        return (
            f"[ERROR] Command timed out after {COMMAND_TIMEOUT} seconds. "
            "Consider using non-interactive flags (e.g. -y for apt-get) or "
            "breaking the task into smaller steps."
        )
    except (OSError, PermissionError, ValueError) as exc:
        return f"[ERROR] Could not execute command: {exc}"


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------


def build_client() -> OpenAI:
    """Create and return an OpenAI-compatible client pointed at OpenRouter."""
    if not OPENROUTER_API_KEY:
        print(
            "[ERROR] OPENROUTER_API_KEY is not set.\n"
            "Please run setup.py first to configure your API key."
        )
        sys.exit(1)

    return OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": "https://github.com/Ivoozz/aiagent",
            "X-Title": "Autonomous Debian AI Agent",
        },
    )


def call_llm(
    client: OpenAI,
    messages: list[dict[str, Any]],
) -> str:
    """Send *messages* to the LLM and return the raw text content of the reply.

    Args:
        client: An initialised OpenAI-compatible client.
        messages: The full conversation history in OpenAI message format.

    Returns:
        The raw text content returned by the model.

    Raises:
        SystemExit: On authentication or connection errors.
    """
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,  # type: ignore[arg-type]
        )
        content = response.choices[0].message.content
        return content if content else ""
    except AuthenticationError:
        print(
            "[ERROR] Authentication failed. Your OpenRouter API key appears to be "
            "invalid or expired.\nPlease re-run setup.py to update it."
        )
        sys.exit(1)
    except APIConnectionError as exc:
        print(f"[ERROR] Could not connect to OpenRouter: {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------


def parse_llm_response(raw: str) -> dict[str, Any]:
    """Attempt to parse the LLM's raw text as JSON.

    The LLM is instructed to return only a JSON object, but may occasionally
    wrap it in markdown code fences.  This function strips those before
    attempting to parse.

    Args:
        raw: The raw string returned by the LLM.

    Returns:
        A parsed dictionary.  On failure, returns a dict with an 'error' key
        so the agent loop can handle it gracefully.
    """
    # Strip leading/trailing whitespace
    text = raw.strip()

    # Remove markdown code fences if present (```json … ``` or ``` … ```)
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (``` or ```json) and last line (```)
        inner_lines = []
        for line in lines[1:]:
            if line.strip() == "```":
                break
            inner_lines.append(line)
        text = "\n".join(inner_lines).strip()

    try:
        return json.loads(text)  # type: ignore[return-value]
    except json.JSONDecodeError as exc:
        return {
            "error": f"JSON parse error: {exc}",
            "raw_response": raw,
            "thought": "The LLM returned a response that could not be parsed as JSON.",
            "command": "",
        }


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


def run_agent(client: OpenAI, user_goal: str) -> None:
    """Execute the ReAct-style agent loop for *user_goal*.

    Args:
        client: An initialised OpenAI-compatible client.
        user_goal: The natural-language task provided by the user.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_goal},
    ]

    print(f"\n[Agent] Starting task: {user_goal}\n{'=' * 60}")

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n[Iteration {iteration}/{MAX_ITERATIONS}]")

        # --- Call the LLM ---
        raw_response = call_llm(client, messages)

        # --- Parse the response ---
        parsed = parse_llm_response(raw_response)

        if "error" in parsed:
            print(f"[Warning] {parsed['error']}")
            print(f"  Raw response:\n{parsed.get('raw_response', '')}\n")
            # Feed the error back so the LLM can self-correct
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

        print(f"  Thought : {thought}")

        # --- Task complete ---
        if not command:
            print(f"\n[Agent] Task complete.\n{'-' * 60}")
            print(final_answer or "No final answer provided.")
            return

        # --- Execute the command ---
        print(f"  Command : {command}")
        output = execute_command(command)
        print(f"  Output  :\n{output}")

        # Append assistant turn and command output to history
        messages.append({"role": "assistant", "content": raw_response})
        messages.append(
            {
                "role": "user",
                "content": f"Command output:\n{output}",
            }
        )

    print(
        f"\n[Agent] Reached maximum iterations ({MAX_ITERATIONS}). "
        "The task may be incomplete."
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main REPL: repeatedly ask for a goal and run the agent loop."""
    client = build_client()

    print("=== Autonomous AI Agent (Debian LXC) ===")
    print(f"Model : {MODEL}")
    print(f"Timeout per command: {COMMAND_TIMEOUT}s")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            user_goal = input("Enter your goal: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Agent] Interrupted. Goodbye.")
            sys.exit(0)

        if not user_goal:
            continue
        if user_goal.lower() in {"exit", "quit"}:
            print("[Agent] Goodbye.")
            sys.exit(0)

        run_agent(client, user_goal)
        print()  # Blank line before the next prompt


if __name__ == "__main__":
    main()
