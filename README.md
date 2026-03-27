# Claude Cost Tracker

> **Know exactly where your Claude Code tokens go.**

[English](README.md) | [中文](README_CN.md)

Claude Code's `/cost` only shows the current session — once you close the window, that data is gone. **Claude Cost Tracker** automatically records every token across all your sessions and projects, then gives you a beautiful dashboard to see the full picture.

![Dashboard Overview](assets/dashboard-overview.jpg)

## Why?

- You're on Claude Max / API and want to know your **actual usage patterns**
- You work across **multiple projects** and want to see which ones cost the most
- You want to understand the **cost impact** of different models (Opus vs Sonnet vs Haiku)
- You want to see **daily and monthly trends** to track spending over time
- You want to see how much **caching** is saving you

## Features

- **Fully automatic** — Installs as a Stop hook, records every turn silently in the background
- **Zero token cost** — Uses `command` hook type, never calls the Claude API
- **Global dashboard** — Aggregates all windows, sessions, and projects in one view
- **Cost by token type** — See exactly what Input, Output, Cache Read, and Cache Creation cost you
- **Daily & monthly trends** — Spot patterns, track spending over time
- **Model breakdown** — Compare costs across Opus, Sonnet, and Haiku
- **Project ranking** — Know which projects consume the most
- **Historical import** — Imports your existing transcript data on first install
- **Cross-platform** — macOS, Windows, Linux
- **Zero dependencies** — Pure Python 3 + SQLite, no pip install needed

## Quick Start

```bash
git clone https://github.com/clockwise0215/claude-cost-tracker.git
cd claude-cost-tracker
python install.py        # or python3 on macOS/Linux
```

That's it. Token tracking starts immediately. Your historical data is imported automatically.

## Usage

### Open the dashboard

In Claude Code, type:

```
/token-dash
```

A dashboard opens in your browser with:

| Section | What it shows |
|---------|---------------|
| **Overview cards** | Total tokens, total cost, per-type cost (Input / Output / Cache Read / Cache Creation) |
| **Daily cost** | Bar chart of spending per day |
| **Daily tokens** | Stacked bar chart by token type per day |
| **Monthly cost** | Bar chart of spending per month |
| **Model distribution** | Doughnut chart — Opus vs Sonnet vs Haiku |
| **Cost by token type** | Doughnut chart — where the money goes |
| **Project ranking** | Table sorted by cost, with session count |

<details>
<summary>More dashboard screenshots</summary>

#### Monthly Cost & Model Distribution
![Monthly and Model](assets/dashboard-monthly.jpg)

#### Monthly Tokens & Cost by Token Type
![Token Types](assets/dashboard-models.jpg)

#### Project Usage Ranking
![Project Ranking](assets/dashboard-projects.jpg)

</details>

### Quick terminal check

```
/token-cost
```

Prints this month's usage by model and project directly in the terminal.

### Direct SQL query

```bash
sqlite3 ~/.claude/token_usage.db \
  "SELECT model, SUM(cost_usd) FROM token_usage GROUP BY model"
```

> **Windows**: Replace `~/.claude/` with `%USERPROFILE%\.claude\`

## How It Works

```
Claude Code turn ends
        ↓
   Stop hook fires
        ↓
track_tokens.py reads transcript JSONL (provided via stdin)
        ↓
Extracts token usage from each assistant message
        ↓
Writes to ~/.claude/token_usage.db (SQLite, WAL mode)
        ↓
/token-dash → dashboard.py → generates HTML → opens browser
```

- Each assistant message has a unique `(session_id, message_id)` — duplicates are impossible
- SQLite WAL mode handles multiple Claude Code windows writing concurrently
- The hook exits silently on any error — it will never block your workflow

## Updating Pricing

Edit `~/.claude/hooks/pricing.json`:

```json
{
  "claude-opus-4-6": { "input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_creation": 18.75 },
  "claude-sonnet-4-6": { "input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_creation": 3.75 },
  "claude-haiku-4-5-20251001": { "input": 0.8, "output": 4.0, "cache_read": 0.08, "cache_creation": 1.0 }
}
```

Units: USD per million tokens. Unknown models fall back to Sonnet rates.

To recalculate historical costs with new rates:
```bash
rm ~/.claude/token_usage.db && python3 ~/.claude/hooks/import_history.py
```

## Requirements

- Python 3.7+
- Claude Code with hooks support

No `pip install` needed. Everything uses the Python standard library.

## Uninstall

```bash
python install.py --uninstall
```

Removes scripts, slash commands, and hook config. Your database is preserved — delete it manually if desired.

## Contributing

Issues and pull requests are welcome!

## License

MIT
