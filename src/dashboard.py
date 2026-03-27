#!/usr/bin/env python3
"""Generate a static HTML dashboard for Claude Code token usage.

Reads from ~/.claude/token_usage.db and generates an interactive HTML report
with Chart.js visualizations. Opens in default browser automatically.
"""

import json
import os
import sqlite3
import webbrowser
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "token_usage.db"
OUTPUT_PATH = Path.home() / ".claude" / "token_dashboard.html"
PRICING_PATH = Path(__file__).parent / "pricing.json"


def load_pricing():
    with open(PRICING_PATH) as f:
        return json.load(f)


def get_rates(pricing, model):
    if model in pricing:
        return pricing[model]
    for key in pricing:
        if key == "_default":
            continue
        if model and (model.startswith(key) or key.startswith(model)):
            return pricing[key]
    if model:
        model_lower = model.lower()
        for keyword, key in [("opus", "claude-opus-4-6"), ("sonnet", "claude-sonnet-4-6"), ("haiku", "claude-haiku-4-5-20251001")]:
            if keyword in model_lower and key in pricing:
                return pricing[key]
    return pricing.get("_default", {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_creation": 3.75})


def query_overview(conn, pricing):
    rows = conn.execute("""
        SELECT model, input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens
        FROM token_usage
    """).fetchall()
    totals = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0,
              "input_cost": 0, "output_cost": 0, "cache_read_cost": 0, "cache_creation_cost": 0}
    for r in rows:
        model, inp, out, cr, cc = r
        rates = get_rates(pricing, model)
        totals["input_tokens"] += inp
        totals["output_tokens"] += out
        totals["cache_read_tokens"] += cr
        totals["cache_creation_tokens"] += cc
        totals["input_cost"] += inp * rates["input"] / 1_000_000
        totals["output_cost"] += out * rates["output"] / 1_000_000
        totals["cache_read_cost"] += cr * rates["cache_read"] / 1_000_000
        totals["cache_creation_cost"] += cc * rates["cache_creation"] / 1_000_000
    totals["total_tokens"] = totals["input_tokens"] + totals["output_tokens"] + totals["cache_read_tokens"] + totals["cache_creation_tokens"]
    totals["total_cost"] = totals["input_cost"] + totals["output_cost"] + totals["cache_read_cost"] + totals["cache_creation_cost"]
    return totals


def query_daily(conn):
    rows = conn.execute("""
        SELECT
            strftime('%Y-%m-%d', timestamp) as day,
            SUM(input_tokens), SUM(output_tokens),
            SUM(cache_read_tokens), SUM(cache_creation_tokens),
            SUM(cost_usd)
        FROM token_usage
        WHERE timestamp != ''
        GROUP BY day
        ORDER BY day
    """).fetchall()
    return [
        {"day": r[0], "input": r[1], "output": r[2],
         "cache_read": r[3], "cache_creation": r[4], "cost": r[5]}
        for r in rows
    ]


def query_monthly(conn):
    rows = conn.execute("""
        SELECT
            strftime('%Y-%m', timestamp) as month,
            SUM(input_tokens), SUM(output_tokens),
            SUM(cache_read_tokens), SUM(cache_creation_tokens),
            SUM(cost_usd)
        FROM token_usage
        WHERE timestamp != ''
        GROUP BY month
        ORDER BY month
    """).fetchall()
    return [
        {"month": r[0], "input": r[1], "output": r[2],
         "cache_read": r[3], "cache_creation": r[4], "cost": r[5]}
        for r in rows
    ]


def query_by_model(conn):
    rows = conn.execute("""
        SELECT model,
            SUM(input_tokens + output_tokens + cache_read_tokens + cache_creation_tokens),
            SUM(cost_usd)
        FROM token_usage
        GROUP BY model
        ORDER BY SUM(cost_usd) DESC
    """).fetchall()
    return [{"model": r[0] or "unknown", "tokens": r[1], "cost": r[2]} for r in rows]


def query_by_project(conn):
    rows = conn.execute("""
        SELECT project_dir,
            SUM(input_tokens), SUM(output_tokens),
            SUM(cache_read_tokens), SUM(cache_creation_tokens),
            SUM(cost_usd),
            COUNT(DISTINCT session_id)
        FROM token_usage
        GROUP BY project_dir
        ORDER BY SUM(cost_usd) DESC
    """).fetchall()
    return [
        {"project": r[0] or "unknown", "input": r[1], "output": r[2],
         "cache_read": r[3], "cache_creation": r[4], "cost": r[5], "sessions": r[6]}
        for r in rows
    ]


def format_tokens(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def shorten_project(path):
    if not path:
        return "unknown"
    home = str(Path.home())
    if path.startswith(home):
        path = "~" + path[len(home):]
    p = Path(path)
    parts = p.parts
    if len(parts) > 3:
        return str(Path(parts[0], parts[1], "...", parts[-1]))
    return path


def generate_html(overview, daily, monthly, by_model, by_project):
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Daily data
    daily_labels = json.dumps([d["day"] for d in daily])
    daily_costs = json.dumps([round(d["cost"], 4) for d in daily])
    daily_input = json.dumps([d["input"] for d in daily])
    daily_output = json.dumps([d["output"] for d in daily])
    daily_cache_read = json.dumps([d["cache_read"] for d in daily])
    daily_cache_creation = json.dumps([d["cache_creation"] for d in daily])

    # Monthly data
    monthly_labels = json.dumps([m["month"] for m in monthly])
    monthly_costs = json.dumps([round(m["cost"], 4) for m in monthly])
    monthly_input = json.dumps([m["input"] for m in monthly])
    monthly_output = json.dumps([m["output"] for m in monthly])
    monthly_cache_read = json.dumps([m["cache_read"] for m in monthly])
    monthly_cache_creation = json.dumps([m["cache_creation"] for m in monthly])

    model_labels = json.dumps([m["model"] for m in by_model])
    model_costs = json.dumps([round(m["cost"], 4) for m in by_model])

    project_rows = ""
    for p in by_project:
        total = p["input"] + p["output"] + p["cache_read"] + p["cache_creation"]
        project_rows += f"""
        <tr>
            <td title="{p['project']}">{shorten_project(p['project'])}</td>
            <td>{format_tokens(p['input'])}</td>
            <td>{format_tokens(p['output'])}</td>
            <td>{format_tokens(p['cache_read'])}</td>
            <td>{format_tokens(p['cache_creation'])}</td>
            <td>{format_tokens(total)}</td>
            <td>${p['cost']:.4f}</td>
            <td>{p['sessions']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Token Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f1117; color: #e1e4e8; padding: 24px; }}
h1 {{ font-size: 24px; margin-bottom: 24px; color: #f0f0f0; }}
h2 {{ font-size: 18px; margin-bottom: 16px; color: #c9d1d9; }}
.section {{ margin-bottom: 32px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }}
.card .label {{ font-size: 13px; color: #8b949e; margin-bottom: 4px; }}
.card .value {{ font-size: 28px; font-weight: 600; color: #f0f0f0; }}
.card .sub {{ font-size: 13px; color: #8b949e; margin-top: 4px; }}
.card .value.cost {{ color: #f0883e; }}
.card .value.input {{ color: #58a6ff; }}
.card .value.output {{ color: #3fb950; }}
.card .value.cache-read {{ color: #bc8cff; }}
.card .value.cache-creation {{ color: #f778ba; }}
.charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }}
.chart-box {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }}
.chart-full {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 24px; }}
@media (max-width: 900px) {{ .charts {{ grid-template-columns: 1fr; }} }}
table {{ width: 100%; border-collapse: collapse; background: #161b22; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }}
th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; font-size: 13px; }}
th {{ background: #1c2128; color: #8b949e; font-weight: 600; }}
td {{ color: #c9d1d9; }}
tr:hover {{ background: #1c2128; }}
.tab-bar {{ display: flex; gap: 8px; margin-bottom: 16px; }}
.tab-btn {{ background: #21262d; color: #8b949e; border: 1px solid #30363d; border-radius: 6px; padding: 6px 16px; cursor: pointer; font-size: 13px; }}
.tab-btn.active {{ background: #f0883e; color: #fff; border-color: #f0883e; }}
.footer {{ margin-top: 24px; text-align: center; color: #484f58; font-size: 12px; }}
</style>
</head>
<body>
<h1>Claude Token Dashboard</h1>

<div class="cards">
    <div class="card">
        <div class="label">Total Cost</div>
        <div class="value cost">${overview['total_cost']:.4f}</div>
    </div>
    <div class="card">
        <div class="label">Total Tokens</div>
        <div class="value">{format_tokens(overview['total_tokens'])}</div>
    </div>
    <div class="card">
        <div class="label">Input Tokens</div>
        <div class="value input">{format_tokens(overview['input_tokens'])}</div>
        <div class="sub">${overview['input_cost']:.4f}</div>
    </div>
    <div class="card">
        <div class="label">Output Tokens</div>
        <div class="value output">{format_tokens(overview['output_tokens'])}</div>
        <div class="sub">${overview['output_cost']:.4f}</div>
    </div>
    <div class="card">
        <div class="label">Cache Read</div>
        <div class="value cache-read">{format_tokens(overview['cache_read_tokens'])}</div>
        <div class="sub">${overview['cache_read_cost']:.4f}</div>
    </div>
    <div class="card">
        <div class="label">Cache Creation</div>
        <div class="value cache-creation">{format_tokens(overview['cache_creation_tokens'])}</div>
        <div class="sub">${overview['cache_creation_cost']:.4f}</div>
    </div>
</div>

<div class="section">
    <h2>Daily Cost (USD)</h2>
    <div class="chart-full">
        <canvas id="dailyCost" height="80"></canvas>
    </div>
</div>

<div class="section">
    <h2>Daily Tokens by Type</h2>
    <div class="chart-full">
        <canvas id="dailyTokens" height="80"></canvas>
    </div>
</div>

<div class="charts">
    <div class="chart-box">
        <h2>Monthly Cost (USD)</h2>
        <canvas id="monthlyCost"></canvas>
    </div>
    <div class="chart-box">
        <h2>Model Distribution (Cost)</h2>
        <canvas id="modelDist"></canvas>
    </div>
    <div class="chart-box">
        <h2>Monthly Tokens by Type</h2>
        <canvas id="monthlyTokens"></canvas>
    </div>
    <div class="chart-box">
        <h2>Cost by Token Type</h2>
        <canvas id="costByType"></canvas>
    </div>
</div>

<div class="section">
    <h2>Project Usage Ranking</h2>
    <table>
    <thead>
        <tr><th>Project</th><th>Input</th><th>Output</th><th>Cache Read</th><th>Cache Creation</th><th>Total</th><th>Cost</th><th>Sessions</th></tr>
    </thead>
    <tbody>{project_rows}
    </tbody>
    </table>
</div>

<div class="footer">Generated by claude-cost-tracker at {generated_at} &middot; Run <code>/token-dash</code> to refresh</div>

<script>
const chartColors = ['#f0883e', '#3fb950', '#58a6ff', '#bc8cff', '#f778ba', '#79c0ff'];
const gridColor = '#21262d';
const textColor = '#8b949e';

Chart.defaults.color = textColor;

// Daily Cost Bar Chart
new Chart(document.getElementById('dailyCost'), {{
    type: 'bar',
    data: {{
        labels: {daily_labels},
        datasets: [{{ label: 'Cost (USD)', data: {daily_costs}, backgroundColor: '#f0883e' }}]
    }},
    options: {{
        scales: {{
            y: {{ grid: {{ color: gridColor }} }},
            x: {{ grid: {{ color: gridColor }}, ticks: {{ maxRotation: 45, autoSkip: true, maxTicksLimit: 30 }} }}
        }}
    }}
}});

// Daily Tokens Stacked Bar
new Chart(document.getElementById('dailyTokens'), {{
    type: 'bar',
    data: {{
        labels: {daily_labels},
        datasets: [
            {{ label: 'Input', data: {daily_input}, backgroundColor: '#58a6ff' }},
            {{ label: 'Output', data: {daily_output}, backgroundColor: '#3fb950' }},
            {{ label: 'Cache Read', data: {daily_cache_read}, backgroundColor: '#bc8cff' }},
            {{ label: 'Cache Creation', data: {daily_cache_creation}, backgroundColor: '#f778ba' }}
        ]
    }},
    options: {{
        scales: {{
            x: {{ stacked: true, grid: {{ color: gridColor }}, ticks: {{ maxRotation: 45, autoSkip: true, maxTicksLimit: 30 }} }},
            y: {{ stacked: true, grid: {{ color: gridColor }} }}
        }}
    }}
}});

// Monthly Cost Bar Chart
new Chart(document.getElementById('monthlyCost'), {{
    type: 'bar',
    data: {{
        labels: {monthly_labels},
        datasets: [{{ label: 'Cost (USD)', data: {monthly_costs}, backgroundColor: '#f0883e' }}]
    }},
    options: {{ scales: {{ y: {{ grid: {{ color: gridColor }} }}, x: {{ grid: {{ color: gridColor }} }} }} }}
}});

// Model Distribution Pie
new Chart(document.getElementById('modelDist'), {{
    type: 'doughnut',
    data: {{
        labels: {model_labels},
        datasets: [{{ data: {model_costs}, backgroundColor: chartColors }}]
    }},
    options: {{ plugins: {{ legend: {{ position: 'bottom' }} }} }}
}});

// Monthly Tokens Stacked Bar
new Chart(document.getElementById('monthlyTokens'), {{
    type: 'bar',
    data: {{
        labels: {monthly_labels},
        datasets: [
            {{ label: 'Input', data: {monthly_input}, backgroundColor: '#58a6ff' }},
            {{ label: 'Output', data: {monthly_output}, backgroundColor: '#3fb950' }},
            {{ label: 'Cache Read', data: {monthly_cache_read}, backgroundColor: '#bc8cff' }},
            {{ label: 'Cache Creation', data: {monthly_cache_creation}, backgroundColor: '#f778ba' }}
        ]
    }},
    options: {{ scales: {{ x: {{ stacked: true, grid: {{ color: gridColor }} }}, y: {{ stacked: true, grid: {{ color: gridColor }} }} }} }}
}});

// Cost by Token Type Pie
new Chart(document.getElementById('costByType'), {{
    type: 'doughnut',
    data: {{
        labels: ['Input (${overview['input_cost']:.2f})', 'Output (${overview['output_cost']:.2f})', 'Cache Read (${overview['cache_read_cost']:.2f})', 'Cache Creation (${overview['cache_creation_cost']:.2f})'],
        datasets: [{{ data: [{overview['input_cost']:.4f}, {overview['output_cost']:.4f}, {overview['cache_read_cost']:.4f}, {overview['cache_creation_cost']:.4f}], backgroundColor: ['#58a6ff', '#3fb950', '#bc8cff', '#f778ba'] }}]
    }},
    options: {{ plugins: {{ legend: {{ position: 'bottom' }} }} }}
}});
</script>
</body>
</html>"""


def main():
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        print("Run import_history.py first or use Claude Code with the hook enabled.")
        return

    pricing = load_pricing()
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    try:
        overview = query_overview(conn, pricing)
        daily = query_daily(conn)
        monthly = query_monthly(conn)
        by_model = query_by_model(conn)
        by_project = query_by_project(conn)
    finally:
        conn.close()

    html = generate_html(overview, daily, monthly, by_model, by_project)
    OUTPUT_PATH.write_text(html)
    print(f"Dashboard generated: {OUTPUT_PATH}")

    webbrowser.open(f"file://{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
