"""
report.py — Generates the HTML demo report.

Produces output/report.html with:
  - Pipeline plan (Claude-authored)
  - Step-by-step execution results (Ollama-executed)
  - Key insights
  - Cost comparison table  ← the money slide for the demo
"""

import os
from datetime import datetime

OUTPUT_DIR = "output"


def _badge(text: str, color: str) -> str:
    return f'<span class="badge" style="background:{color}">{text}</span>'


def _step_action_color(action: str) -> str:
    return {
        "clean":     "#6c757d",
        "transform": "#0d6efd",
        "aggregate": "#6610f2",
        "analyze":   "#198754",
    }.get(action, "#495057")


def generate_report(
    plan: dict,
    planner_tokens: dict,
    results: dict,
    execution_log: list,
    total_seconds: float,
    goal: str,
) -> str:
    """Build the HTML report and write it to output/report.html. Returns path."""

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── Cost numbers ────────────────────────────────────────────────────────────
    actual_cost    = planner_tokens["total_cost"]
    exec_est_cost  = sum(s["est_claude_cost"] for s in execution_log)
    hypothetical   = actual_cost + exec_est_cost
    savings_pct    = (exec_est_cost / hypothetical * 100) if hypothetical > 0 else 0
    steps          = plan.get("steps", [])
    insights_text  = results.get("insights", "")

    # ── Pipeline steps HTML ──────────────────────────────────────────────────────
    steps_rows = ""
    for s in steps:
        color = _step_action_color(s["action"])
        steps_rows += f"""
        <tr>
          <td class="center">{s['step_id']}</td>
          <td><strong>{s['name']}</strong><br>
              <small class="muted">{s['description']}</small></td>
          <td>{_badge(s['action'], color)}</td>
          <td><code>{s['pandas_hint']}</code></td>
          <td class="muted small">{s['validation']}</td>
        </tr>"""

    # ── Execution log HTML ───────────────────────────────────────────────────────
    exec_rows = ""
    for log in execution_log:
        status_badge = (
            _badge("✓ success", "#198754") if log["success"]
            else _badge("⚠ error", "#dc3545")
        )
        exec_rows += f"""
        <div class="step-card">
          <div class="step-header">
            <span class="step-num">Step {log['step_id']}</span>
            <span class="step-name">{log['name']}</span>
            {status_badge}
            <span class="muted small" style="margin-left:auto">{log['duration']}s
            &nbsp;·&nbsp; {log['rows_in']} → {log['rows_out']} rows</span>
          </div>
          <details>
            <summary>View generated code <small class="muted">({log['model']})</small></summary>
            <pre><code>{log['code']}</code></pre>
            <div class="output-box"><strong>Output:</strong> {log['output']}</div>
          </details>
        </div>"""

    # ── Cost table HTML ──────────────────────────────────────────────────────────
    cost_rows = f"""
        <tr class="highlight-row">
          <td>Planning</td>
          <td>Claude Opus 4.6</td>
          <td>{planner_tokens['input_tokens']:,} in / {planner_tokens['output_tokens']:,} out</td>
          <td class="cost-actual">${actual_cost:.4f}</td>
          <td class="cost-actual">${actual_cost:.4f}</td>
        </tr>"""

    for log in execution_log:
        step_hyp = log["est_claude_cost"]
        cost_rows += f"""
        <tr>
          <td>Step {log['step_id']}: {log['name']}</td>
          <td class="model-local">{log['model']} (local)</td>
          <td class="muted">~{log['est_claude_input_tokens']} / ~{log['est_claude_output_tokens']} (est.)</td>
          <td class="cost-zero">$0.0000</td>
          <td class="cost-hyp">${step_hyp:.4f}</td>
        </tr>"""

    cost_rows += f"""
        <tr class="total-row">
          <td colspan="3"><strong>TOTAL</strong></td>
          <td class="cost-actual"><strong>${actual_cost:.4f}</strong></td>
          <td class="cost-hyp"><strong>${hypothetical:.4f}</strong></td>
        </tr>"""

    # ── Insights HTML ────────────────────────────────────────────────────────────
    insight_lines = [
        f"<li>{line.lstrip('0123456789.-) ').strip()}</li>"
        for line in insights_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    insights_html = "<ol>" + "".join(insight_lines) + "</ol>"

    # ── Full HTML ────────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data Pipeline Agent — Report</title>
<style>
  :root {{
    --blue: #0d6efd; --green: #198754; --purple: #6610f2;
    --gray: #6c757d; --light: #f8f9fa; --border: #dee2e6;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: #f0f2f5; color: #212529; line-height: 1.6; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 2rem 1.5rem; }}

  /* Header */
  .hero {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
           color: white; padding: 2.5rem 2rem; border-radius: 12px;
           margin-bottom: 2rem; }}
  .hero h1 {{ font-size: 2rem; font-weight: 700; margin-bottom: .4rem; }}
  .hero .subtitle {{ color: #a0b4cc; font-size: 1rem; margin-bottom: 1.2rem; }}
  .hero .goal-box {{ background: rgba(255,255,255,.08); border-left: 4px solid #4fc3f7;
                     padding: .8rem 1rem; border-radius: 4px; font-size: .95rem; }}
  .meta {{ display: flex; gap: 1.5rem; margin-top: 1rem; color: #a0b4cc; font-size: .85rem; }}

  /* Section cards */
  .card {{ background: white; border-radius: 10px; padding: 1.8rem;
           margin-bottom: 1.5rem; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  .card h2 {{ font-size: 1.2rem; margin-bottom: 1rem; display: flex;
              align-items: center; gap: .5rem; }}
  .card h2 .icon {{ font-size: 1.3rem; }}

  /* Tables */
  table {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
  th {{ background: var(--light); text-align: left; padding: .6rem .8rem;
        border-bottom: 2px solid var(--border); font-weight: 600; }}
  td {{ padding: .55rem .8rem; border-bottom: 1px solid var(--border); vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  .center {{ text-align: center; }}

  /* Badges */
  .badge {{ display: inline-block; padding: .2rem .55rem; border-radius: 12px;
            font-size: .75rem; font-weight: 600; color: white; }}

  /* Step execution cards */
  .step-card {{ border: 1px solid var(--border); border-radius: 8px;
                margin-bottom: 1rem; overflow: hidden; }}
  .step-header {{ display: flex; align-items: center; gap: .75rem;
                  padding: .7rem 1rem; background: var(--light); flex-wrap: wrap; }}
  .step-num {{ background: #0d6efd; color: white; border-radius: 50%;
               width: 1.6rem; height: 1.6rem; display: flex;
               align-items: center; justify-content: center; font-size: .75rem;
               font-weight: 700; flex-shrink: 0; }}
  .step-name {{ font-weight: 600; }}
  details {{ padding: 1rem; }}
  summary {{ cursor: pointer; color: var(--blue); font-size: .88rem; }}
  pre {{ background: #1e1e2e; color: #cdd6f4; border-radius: 6px;
         padding: 1rem; overflow-x: auto; margin-top: .75rem;
         font-size: .82rem; line-height: 1.5; }}
  .output-box {{ margin-top: .75rem; padding: .6rem .9rem; background: #f0fff4;
                 border-left: 3px solid var(--green); border-radius: 4px;
                 font-size: .85rem; color: #1a5c35; }}

  /* Cost section */
  .cost-actual {{ color: var(--green); font-weight: 600; }}
  .cost-zero   {{ color: var(--green); font-weight: 600; }}
  .cost-hyp    {{ color: #dc3545; }}
  .model-local {{ color: var(--purple); font-size: .82rem; }}
  .highlight-row td {{ background: #fffbea; }}
  .total-row td {{ background: var(--light); font-size: .95rem; }}

  .savings-banner {{
    background: linear-gradient(135deg, #198754, #20c997);
    color: white; border-radius: 10px; padding: 1.8rem;
    text-align: center; margin-top: 1.5rem;
  }}
  .savings-pct {{ font-size: 3.5rem; font-weight: 800; line-height: 1; }}
  .savings-label {{ font-size: 1rem; opacity: .9; margin-top: .3rem; }}
  .savings-detail {{ display: flex; justify-content: center; gap: 3rem;
                     margin-top: 1.2rem; flex-wrap: wrap; }}
  .savings-detail .item {{ text-align: center; }}
  .savings-detail .val {{ font-size: 1.5rem; font-weight: 700; }}
  .savings-detail .lbl {{ font-size: .8rem; opacity: .85; }}

  /* Insights */
  ol {{ padding-left: 1.3rem; }}
  li {{ margin-bottom: .6rem; }}

  /* Helpers */
  .muted {{ color: var(--gray); }}
  .small {{ font-size: .82rem; }}
  code {{ font-family: "SF Mono", "Fira Code", monospace; font-size: .83rem;
          background: #f0f2f5; padding: .1rem .35rem; border-radius: 3px; }}
  pre code {{ background: none; padding: 0; }}

  /* Footer */
  .footer {{ text-align: center; color: var(--gray); font-size: .82rem;
             margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border); }}
</style>
</head>
<body>
<div class="container">

  <!-- HERO -->
  <div class="hero">
    <h1>🤖 Data Pipeline Agent</h1>
    <p class="subtitle">Planner-Executor Pattern — Demo Report</p>
    <div class="goal-box">🎯 <strong>Goal:</strong> {goal}</div>
    <div class="meta">
      <span>⏱ Total runtime: {total_seconds:.1f}s</span>
      <span>📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
      <span>📊 {len(steps)} pipeline steps</span>
    </div>
  </div>

  <!-- PIPELINE PLAN -->
  <div class="card">
    <h2><span class="icon">🧠</span> Pipeline Plan — authored by Claude Opus 4.6</h2>
    <p class="muted small" style="margin-bottom:1rem">
      Claude analysed the dataset schema and produced this strict, unambiguous plan.
      The local model only needs to follow instructions — no high-level reasoning required.
    </p>
    <table>
      <thead>
        <tr>
          <th style="width:40px">#</th>
          <th>Step</th>
          <th style="width:100px">Action</th>
          <th>Pandas hint</th>
          <th>Validation</th>
        </tr>
      </thead>
      <tbody>{steps_rows}</tbody>
    </table>
  </div>

  <!-- EXECUTION LOG -->
  <div class="card">
    <h2><span class="icon">⚙️</span> Execution — powered by {execution_log[0]['model'] if execution_log else 'Ollama'} (local)</h2>
    <p class="muted small" style="margin-bottom:1rem">
      Each step: Ollama generated targeted pandas code from Claude's precise spec,
      then executed it locally. No cloud API calls — zero execution cost.
    </p>
    {exec_rows}
  </div>

  <!-- INSIGHTS -->
  <div class="card">
    <h2><span class="icon">💡</span> Key Business Insights</h2>
    <p class="muted small" style="margin-bottom:1rem">Generated by the local model from the processed data.</p>
    {insights_html}
  </div>

  <!-- COST ANALYSIS -->
  <div class="card">
    <h2><span class="icon">💰</span> Cost Analysis</h2>
    <p class="muted small" style="margin-bottom:1rem">
      <strong>Actual cost</strong>: what this run cost using the planner-executor pattern.<br>
      <strong>Hypothetical cost</strong>: estimated cost if Claude had executed every step via the API.
    </p>
    <table>
      <thead>
        <tr>
          <th>Phase</th>
          <th>Model</th>
          <th>Tokens (input / output)</th>
          <th>Actual cost</th>
          <th>Hypothetical cost</th>
        </tr>
      </thead>
      <tbody>{cost_rows}</tbody>
    </table>

    <!-- SAVINGS BANNER -->
    <div class="savings-banner">
      <div class="savings-pct">{savings_pct:.0f}%</div>
      <div class="savings-label">token cost savings with the planner-executor pattern</div>
      <div class="savings-detail">
        <div class="item">
          <div class="val">${actual_cost:.4f}</div>
          <div class="lbl">Actual cost (this run)</div>
        </div>
        <div class="item">
          <div class="val">${hypothetical:.4f}</div>
          <div class="lbl">Hypothetical (all Claude)</div>
        </div>
        <div class="item">
          <div class="val">${exec_est_cost:.4f}</div>
          <div class="lbl">Saved on execution</div>
        </div>
        <div class="item">
          <div class="val">{planner_tokens['total_tokens']:,}</div>
          <div class="lbl">Actual tokens used</div>
        </div>
      </div>
    </div>
  </div>

  <div class="footer">
    Data Pipeline Agent · Planner-Executor Pattern Demo ·
    Planner: Claude Opus 4.6 &nbsp;|&nbsp;
    Executor: {execution_log[0]['model'] if execution_log else 'Ollama (local)'}
  </div>

</div>
</body>
</html>"""

    path = os.path.join(OUTPUT_DIR, "report.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    return path
