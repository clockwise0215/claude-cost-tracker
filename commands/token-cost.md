Show a quick summary of this month's Claude token usage in the terminal.

Run `python3 -c "
import sqlite3
from pathlib import Path
from datetime import datetime

db = Path.home() / '.claude' / 'token_usage.db'
if not db.exists():
    print('No usage data found. Run import_history.py or enable the hook first.')
    exit()

conn = sqlite3.connect(str(db))
month = datetime.now().strftime('%Y-%m')

print(f'=== Claude Token Usage: {month} ===\n')

print('By Model:')
for r in conn.execute('''SELECT model, SUM(input_tokens), SUM(output_tokens), SUM(cache_read_tokens), SUM(cache_creation_tokens), SUM(cost_usd) FROM token_usage WHERE strftime(\"%Y-%m\", timestamp) = ? GROUP BY model ORDER BY SUM(cost_usd) DESC''', (month,)):
    total = r[1]+r[2]+r[3]+r[4]
    print(f'  {r[0]:30s}  tokens: {total:>12,}  cost: \${r[5]:.4f}')

print('\nBy Project:')
for r in conn.execute('''SELECT project_dir, SUM(input_tokens+output_tokens+cache_read_tokens+cache_creation_tokens), SUM(cost_usd) FROM token_usage WHERE strftime(\"%Y-%m\", timestamp) = ? GROUP BY project_dir ORDER BY SUM(cost_usd) DESC LIMIT 10''', (month,)):
    proj = r[0] or 'unknown'
    if len(proj) > 40: proj = '...' + proj[-37:]
    print(f'  {proj:40s}  tokens: {r[1]:>12,}  cost: \${r[2]:.4f}')

row = conn.execute('''SELECT SUM(input_tokens+output_tokens+cache_read_tokens+cache_creation_tokens), SUM(cost_usd) FROM token_usage WHERE strftime(\"%Y-%m\", timestamp) = ?''', (month,)).fetchone()
print(f'\nTotal: {row[0] or 0:,} tokens, \${row[1] or 0:.4f}')
conn.close()
"
