#!/usr/bin/env python3
"""
webui/app.py — Minimal Flask web UI for the aiagent autonomous agent.

Exposes:
  GET  /          → Chat interface (index.html)
  POST /chat      → Run one agent iteration and stream the response

Run directly for development:
    python webui/app.py

In production the systemd unit installed by install.sh --webui starts this
file via the project's virtual environment.
"""

import json
import os
import sys
import threading

# Allow importing agent.py from the parent directory when running as
#   python webui/app.py  (cwd = /opt/aiagent  or repository root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, Response, jsonify, render_template, request, stream_with_context
from dotenv import load_dotenv

from agent import (
    MAX_ITERATIONS,
    SYSTEM_PROMPT,
    build_client,
    call_llm,
    execute_command,
    parse_llm_response,
)

load_dotenv()

app = Flask(__name__)

# Build the LLM client once at startup (thread-safe lazy initialisation).
_llm_client = None
_llm_client_lock = threading.Lock()


def get_llm_client():
    global _llm_client
    if _llm_client is None:
        with _llm_client_lock:
            if _llm_client is None:
                _llm_client = build_client()
    return _llm_client


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """Serve the chat UI."""
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """Run the agent loop for the submitted goal and stream progress as
    newline-delimited JSON (NDJSON).

    Request body (JSON):
        { "goal": "<natural-language task>" }

    Each streamed line is a JSON object with one of these shapes:
        {"type": "thought",  "data": "<reasoning text>"}
        {"type": "command",  "data": "<bash command>"}
        {"type": "output",   "data": "<command stdout/stderr>"}
        {"type": "done",     "data": "<final answer>"}
        {"type": "error",    "data": "<error message>"}
    """
    body = request.get_json(silent=True) or {}
    goal: str = (body.get("goal") or "").strip()
    if not goal:
        return jsonify({"error": "goal is required"}), 400

    def generate():
        try:
            client = get_llm_client()
        except SystemExit:
            yield json.dumps({"type": "error", "data": "LLM client failed to initialise — check OPENROUTER_API_KEY."}) + "\n"
            return

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": goal},
        ]

        for iteration in range(1, MAX_ITERATIONS + 1):
            raw = call_llm(client, messages)
            parsed = parse_llm_response(raw)

            if "error" in parsed:
                yield json.dumps({"type": "error", "data": parsed["error"]}) + "\n"
                messages.append({
                    "role": "user",
                    "content": (
                        f"[SYSTEM] Your last response could not be parsed as JSON. "
                        f"Error: {parsed['error']}\n"
                        "Please reply with a valid JSON object only."
                    ),
                })
                continue

            thought: str = parsed.get("thought", "")
            command: str = parsed.get("command", "").strip()
            final_answer: str = parsed.get("final_answer", "")

            if thought:
                yield json.dumps({"type": "thought", "data": thought}) + "\n"

            if not command:
                yield json.dumps({"type": "done", "data": final_answer or "Task complete."}) + "\n"
                return

            yield json.dumps({"type": "command", "data": command}) + "\n"

            output = execute_command(command)
            yield json.dumps({"type": "output", "data": output}) + "\n"

            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Command output:\n{output}"})

        yield json.dumps({"type": "done", "data": f"Reached maximum iterations ({MAX_ITERATIONS}). Task may be incomplete."}) + "\n"

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson",
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Default to localhost only — place a reverse proxy (nginx/caddy) in front
    # for external access and to add authentication.
    host = os.getenv("WEBUI_HOST", "127.0.0.1")
    port = int(os.getenv("WEBUI_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
