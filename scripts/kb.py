#!/usr/bin/env python3
"""
KB Agent — runs kb_model with file-system tools so the model can
read and write wiki notes autonomously.

Usage:
    python scripts/kb.py

Requirements:
    pip install requests
"""

import json
import sys
import requests
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "kb_model"
BASE       = Path(r"C:\Users\dlpuerta\Dropbox\AREAS\NOTES\BRAIN")
WIKI       = BASE / "wiki"
RAW        = BASE / "raw"

# ---------------------------------------------------------------------------
# Tool definitions (sent to Ollama on every request)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_notes",
            "description": "List all note filenames currently in the wiki folder.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_note",
            "description": "Read the content of an existing wiki note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "kebab-case note name without .md extension",
                    }
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_note",
            "description": "Create or overwrite a wiki note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "kebab-case note name without .md extension",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full markdown content of the note",
                    },
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_raw",
            "description": "List all source files in the raw folder.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_raw",
            "description": "Read a source file from the raw folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Filename including extension",
                    }
                },
                "required": ["filename"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def list_notes() -> str:
    files = sorted(WIKI.glob("*.md"))
    return "\n".join(f.stem for f in files) if files else "(wiki is empty)"


def read_note(filename: str) -> str:
    path = WIKI / f"{filename}.md"
    if not path.exists():
        return f"Note '{filename}' not found."
    return path.read_text(encoding="utf-8")


def write_note(filename: str, content: str) -> str:
    path = WIKI / f"{filename}.md"
    existed = path.exists()
    path.write_text(content, encoding="utf-8")
    action = "updated" if existed else "created"
    print(f"  [{action}] wiki/{filename}.md")
    return f"'{filename}' {action}."


def list_raw() -> str:
    files = sorted(f.name for f in RAW.iterdir() if f.is_file())
    return "\n".join(files) if files else "(raw folder is empty)"


def read_raw(filename: str) -> str:
    path = RAW / filename
    if not path.exists():
        return f"'{filename}' not found in raw/."
    return path.read_text(encoding="utf-8")


HANDLERS = {
    "list_notes": lambda a: list_notes(),
    "read_note":  lambda a: read_note(a["filename"]),
    "write_note": lambda a: write_note(a["filename"], a["content"]),
    "list_raw":   lambda a: list_raw(),
    "read_raw":   lambda a: read_raw(a["filename"]),
}

# ---------------------------------------------------------------------------
# Ollama agent loop
# ---------------------------------------------------------------------------

def call_model(messages: list[dict]) -> dict:
    resp = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "tools": TOOLS, "stream": False},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["message"]


def agent_turn(messages: list[dict]) -> str:
    """Run the tool-calling loop until the model returns a plain text response."""
    while True:
        message = call_model(messages)
        messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            content = message.get("content", "").strip()
            if content:
                print(f"\nKB: {content}\n")
            return content

        for call in tool_calls:
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            if isinstance(args, str):
                args = json.loads(args)

            # Show tool call (hide large content args for readability)
            display = {k: v for k, v in args.items() if k != "content"}
            print(f"  [tool] {name}({display})")

            result = HANDLERS.get(name, lambda a: f"Unknown tool: {name}")(args)
            messages.append({"role": "tool", "content": result})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not WIKI.exists():
        print(f"Error: wiki folder not found: {WIKI}")
        sys.exit(1)

    print(f"KB Agent  |  model: {MODEL}")
    print(f"Wiki: {WIKI}")
    print("Ctrl+C to quit\n")

    messages: list[dict] = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        agent_turn(messages)


if __name__ == "__main__":
    main()
