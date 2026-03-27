# Claude Cost Tracker

Claude Code token usage tracker with dashboard visualization.

## Project Structure

- `src/track_tokens.py` — Stop hook script, parses transcript JSONL and writes to SQLite
- `src/dashboard.py` — Generates static HTML dashboard with Chart.js
- `src/import_history.py` — Bulk imports historical transcript data
- `src/pricing.json` — Model pricing rates (USD per million tokens)
- `commands/token-dash.md` — Slash command to open dashboard
- `commands/token-cost.md` — Slash command for terminal summary
- `install.py` — Cross-platform installer (also supports `--uninstall`)

## Key Design Decisions

- SQLite with WAL mode for concurrent multi-window writes
- `(session_id, message_id)` as unique key for deduplication
- Hook type is `command` (not `prompt`) — zero token consumption
- All errors are silent (stderr only) to never block Claude Code
- Pricing in separate JSON file for easy updates without code changes
- Static HTML report (no web server, no port needed)
- Per-token-type cost calculated at query time using pricing.json (not stored in DB)
- Model matching supports exact, prefix, and keyword fallback (e.g. "anthropic/claude-4.6-sonnet-..." → Sonnet rates)
- `or 0` pattern for all usage fields to handle null values from API
- Cross-platform: all paths use `pathlib.Path`, installer auto-detects Python command

## Database

Location: `~/.claude/token_usage.db` (all platforms, resolved via `Path.home()`)

Table `token_usage`: timestamp, session_id, message_id, project_dir, model, input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens, cost_usd

## Testing

After install, verify with:
```bash
sqlite3 ~/.claude/token_usage.db "SELECT COUNT(*) FROM token_usage"
python3 ~/.claude/hooks/dashboard.py
```
