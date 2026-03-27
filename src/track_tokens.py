#!/usr/bin/env python3
"""Claude Code token usage tracker - Stop hook script.

Reads transcript JSONL from Stop hook stdin, extracts token usage
from assistant messages, and writes to SQLite database.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "token_usage.db"
PRICING_PATH = Path(__file__).parent / "pricing.json"


def load_pricing():
    with open(PRICING_PATH) as f:
        return json.load(f)


def get_pricing_for_model(pricing, model):
    """Get pricing for a model, falling back to _default for unknown models."""
    if model in pricing:
        return pricing[model]
    # Try prefix matching in both directions
    for key in pricing:
        if key == "_default":
            continue
        if model and (model.startswith(key) or key.startswith(model)):
            return pricing[key]
    # Try substring matching (e.g. "anthropic/claude-4.6-sonnet-..." -> match "sonnet")
    if model:
        model_lower = model.lower()
        for keyword, key in [("opus", "claude-opus-4-6"), ("sonnet", "claude-sonnet-4-6"), ("haiku", "claude-haiku-4-5-20251001")]:
            if keyword in model_lower and key in pricing:
                return pricing[key]
    return pricing.get("_default", {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_creation": 3.75})


def calc_cost(usage, rates):
    """Calculate cost in USD from token counts and rates (per million tokens)."""
    return (
        (usage.get("input_tokens") or 0) * rates["input"]
        + (usage.get("output_tokens") or 0) * rates["output"]
        + (usage.get("cache_read_input_tokens") or 0) * rates["cache_read"]
        + (usage.get("cache_creation_input_tokens") or 0) * rates["cache_creation"]
    ) / 1_000_000


def init_db(conn):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            session_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            project_dir TEXT,
            model TEXT,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read_tokens INTEGER DEFAULT 0,
            cache_creation_tokens INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0,
            UNIQUE(session_id, message_id)
        )
    """)
    conn.commit()


def parse_transcript(transcript_path, session_id, project_dir, pricing):
    """Parse transcript JSONL and yield records for insertion."""
    with open(transcript_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("type") != "assistant":
                continue

            msg = entry.get("message", {})
            usage = msg.get("usage")
            if not usage:
                continue

            message_id = msg.get("id", "")
            if not message_id:
                continue

            model = msg.get("model", "unknown")
            rates = get_pricing_for_model(pricing, model)

            timestamp = entry.get("timestamp", "")
            sid = entry.get("sessionId", session_id)
            cwd = entry.get("cwd", project_dir)

            yield {
                "timestamp": timestamp,
                "session_id": sid,
                "message_id": message_id,
                "project_dir": cwd,
                "model": model,
                "input_tokens": usage.get("input_tokens") or 0,
                "output_tokens": usage.get("output_tokens") or 0,
                "cache_read_tokens": usage.get("cache_read_input_tokens") or 0,
                "cache_creation_tokens": usage.get("cache_creation_input_tokens") or 0,
                "cost_usd": calc_cost(usage, rates),
            }


def insert_records(conn, records):
    for rec in records:
        conn.execute(
            """INSERT OR IGNORE INTO token_usage
               (timestamp, session_id, message_id, project_dir, model,
                input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens, cost_usd)
               VALUES (:timestamp, :session_id, :message_id, :project_dir, :model,
                       :input_tokens, :output_tokens, :cache_read_tokens, :cache_creation_tokens, :cost_usd)""",
            rec,
        )
    conn.commit()


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    transcript_path = hook_input.get("transcript_path", "")
    session_id = hook_input.get("session_id", "")
    project_dir = hook_input.get("cwd", "")

    if not transcript_path or not os.path.exists(transcript_path):
        sys.exit(0)

    pricing = load_pricing()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    try:
        init_db(conn)
        records = list(parse_transcript(transcript_path, session_id, project_dir, pricing))
        if records:
            insert_records(conn, records)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
