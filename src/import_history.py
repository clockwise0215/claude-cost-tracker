#!/usr/bin/env python3
"""Import historical token usage from all transcript JSONL files.

Scans ~/.claude/projects/**/*.jsonl and imports token data into SQLite.
Safe to run multiple times - UNIQUE constraint prevents duplicates.
"""

import glob
import json
import os
import sqlite3
import sys
from pathlib import Path

# Reuse core logic from track_tokens
sys.path.insert(0, str(Path(__file__).parent))
from track_tokens import DB_PATH, init_db, insert_records, load_pricing, parse_transcript


def find_transcripts():
    """Find all transcript JSONL files under ~/.claude/projects/."""
    claude_dir = Path.home() / ".claude" / "projects"
    return glob.glob(str(claude_dir / "**" / "*.jsonl"), recursive=True)


def extract_session_id(filepath):
    """Extract session ID from transcript filename (UUID part)."""
    return Path(filepath).stem


def main():
    pricing = load_pricing()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    init_db(conn)

    transcripts = find_transcripts()
    total_files = len(transcripts)
    total_records = 0
    skipped = 0

    print(f"Found {total_files} transcript files")

    for i, filepath in enumerate(transcripts, 1):
        session_id = extract_session_id(filepath)
        try:
            records = list(parse_transcript(filepath, session_id, "", pricing))
            if records:
                # Count how many actually get inserted (not ignored)
                before = conn.execute("SELECT COUNT(*) FROM token_usage").fetchone()[0]
                insert_records(conn, records)
                after = conn.execute("SELECT COUNT(*) FROM token_usage").fetchone()[0]
                inserted = after - before
                total_records += inserted
                if inserted > 0:
                    print(f"  [{i}/{total_files}] {Path(filepath).name}: +{inserted} records")
            else:
                skipped += 1
        except Exception as e:
            print(f"  [{i}/{total_files}] {Path(filepath).name}: error - {e}", file=sys.stderr)
            skipped += 1

    conn.close()

    print(f"\nDone! Imported {total_records} new records from {total_files} files ({skipped} skipped)")
    print(f"Database: {DB_PATH}")


if __name__ == "__main__":
    main()
