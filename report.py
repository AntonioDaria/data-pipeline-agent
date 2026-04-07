"""
report.py — Generates the HTML demo report.

Tells a three-act story:
  1. What we analysed   (goal + dataset)
  2. What we found      (insights — front and centre)
  3. What it cost       (savings comparison — the demo's money slide)

Technical details (generated code, pandas steps) are collapsed by default.
"""

import os
from datetime import datetime

OUTPUT_DIR = "output"


def _badge(text: str, color: str) -> str:
    return f'<span class="badge" style="background:{color}">{text}</span>'


def _action_color(action: str) -> str:
    return {"clean": "#6c757d", "transform": "#0d6efd",
            "aggregate": "#6610f2", "analyze": "#198754"}.get(action, "#495057")


def generate_report(
    plan: dict,
    planner_tokens: dict,
    results: dict,
    execution_log: list,
    total_seconds: float,
    goal: str,
) -> str:

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    steps         = plan.get("steps", [])
    insights_text = results.get("insights", "")
    executor_model = execution_log[0]["model"] if execution_log else "Ollama (local)"

    # ── Cost numbers ─────────────────────────────────────────────────────────
    actual_cost   = planner_tokens["total_cost"]
    exec_est_cost = sum(s["est_claude_cost"] for s in execution_log)
    hypothetical  = actual_cost + exec_est_cost
    savings_pct   = (exec_est_cost / hypothetical * 100) if hypothetical > 0 else 0
    successes     = sum(1 for s in execution_log if s["success"])

    # ── Insights ─────────────────────────────────────────────────────────────
    insight_items = [
        line.lstrip("0123456789.-•) ").strip()
        for line in insights_text.splitlines()
        if line.strip() and not line.strip().startswith("#") and len(line.strip()) > 10
    ]
    insights_html = "".join(
        f'<div class="insight-card"><span class="insight-num">{i+1}</span>{item}</div>'
        for i, item in enumerate(insight_items[:5])
    )

    # ── Cost table rows ───────────────────────────────────────────────────────
    cost_rows = f"""
        <tr class="planning-row">
          <td><strong>Planning</strong></td>
          <td>Claude Opus 4.6 ☁️</td>
          <td class="center">{planner_tokens['input_tokens']:,} / {planner_tokens['output_tokens']:,}</td>
          <td class="cost-green center"><strong>${actual_cost:.4f}</strong></td>
          <td class="cost-red center">${actual_cost:.4f}</td>
        </tr>"""
    for log in execution_log:
        status = "✓" if log["success"] else "⚠"
        cost_rows += f"""
        <tr>
          <td>Step {log['step_id']}: {log['name']} <span class="status-{('ok' if log['success'] else 'err')}">{status}</span></td>
          <td class="local-model">{log['model']} 💻</td>
          <td class="center muted">~{log['est_claude_input_tokens']} / ~{log['est_claude_output_tokens']}</td>
          <td class="cost-green center"><strong>$0.0000</strong></td>
          <td class="cost-red center">${log['est_claude_cost']:.4f}</td>
        </tr>"""
    cost_rows += f"""
        <tr class="total-row">
          <td colspan="3"><strong>Total</strong></td>
          <td class="cost-green center"><strong>${actual_cost:.4f}</strong></td>
          <td class="cost-red center"><strong>${hypothetical:.4f}</strong></td>
        </tr>"""

    # ── How it worked (collapsed technical details) ───────────────────────────
    steps_detail = ""
    for s in steps:
        log = next((l for l in execution_log if l["step_id"] == s["step_id"]), None)
        steps_detail += f"""
        <div class="step-row">
          <div class="step-meta">
            <span class="step-num">{s['step_id']}</span>
            <div>
              <strong>{s['name']}</strong>
              <div class="muted small">{s['description']}</div>
            </div>
            {_badge(s['action'], _action_color(s['action']))}
            {'<span class="status-ok small">✓ ran</span>' if (log and log['success']) else '<span class="status-err small">⚠ error</span>' if log else ''}
          </div>
          {f'<details><summary class="show-code">View generated code</summary><pre><code>{log["code"]}</code></pre><div class="output-line">Output: {log["output"]}</div></details>' if log else ''}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Data Pipeline Agent — Report</title>
<style>
  :root {{
    --blue:#0d6efd; --green:#198754; --red:#dc3545;
    --purple:#6610f2; --gray:#6c757d; --border:#dee2e6; --light:#f8f9fa;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
          background:#f0f2f5; color:#212529; line-height:1.6; }}
  .page {{ max-width:960px; margin:0 auto; padding:2rem 1.5rem; }}

  /* ── Hero ── */
  .hero {{ background:linear-gradient(135deg,#1a1a2e,#0f3460);
           color:white; padding:2.5rem; border-radius:14px; margin-bottom:1.5rem; }}
  .hero h1 {{ font-size:1.9rem; font-weight:800; margin-bottom:.3rem; }}
  .hero .sub {{ color:#8ab4cc; margin-bottom:1.2rem; }}
  .goal-box {{ background:rgba(255,255,255,.1); border-left:4px solid #4fc3f7;
               padding:.9rem 1.1rem; border-radius:6px; font-size:.95rem; }}
  .hero-meta {{ display:flex; gap:1.5rem; margin-top:1rem;
                color:#8ab4cc; font-size:.82rem; flex-wrap:wrap; }}

  /* ── Section cards ── */
  .card {{ background:white; border-radius:12px; padding:2rem;
           margin-bottom:1.5rem; box-shadow:0 1px 4px rgba(0,0,0,.07); }}
  .card-title {{ font-size:1.15rem; font-weight:700; margin-bottom:.3rem;
                 display:flex; align-items:center; gap:.5rem; }}
  .card-sub {{ color:var(--gray); font-size:.88rem; margin-bottom:1.3rem; }}

  /* ── Insights ── */
  .insight-card {{ display:flex; align-items:flex-start; gap:1rem;
                   padding:1rem 1.2rem; border-radius:8px; background:var(--light);
                   margin-bottom:.75rem; font-size:.95rem; line-height:1.5; }}
  .insight-num {{ background:var(--blue); color:white; border-radius:50%;
                  width:1.7rem; height:1.7rem; display:flex; align-items:center;
                  justify-content:center; font-size:.75rem; font-weight:700;
                  flex-shrink:0; margin-top:.1rem; }}

  /* ── Pattern explainer ── */
  .flow {{ display:flex; align-items:stretch; gap:0; margin:1.2rem 0; }}
  .flow-box {{ flex:1; border-radius:10px; padding:1.2rem 1rem; text-align:center; }}
  .flow-box h3 {{ font-size:.85rem; font-weight:700; margin-bottom:.4rem;
                  text-transform:uppercase; letter-spacing:.05em; }}
  .flow-box p {{ font-size:.82rem; line-height:1.4; }}
  .flow-arrow {{ display:flex; align-items:center; padding:0 .4rem;
                 font-size:1.4rem; color:var(--gray); flex-shrink:0; }}
  .box-cloud {{ background:#e8f4fd; border:2px solid #90caf9; }}
  .box-local {{ background:#e8f5e9; border:2px solid #a5d6a7; }}
  .box-report {{ background:#fce4ec; border:2px solid #f48fb1; }}
  .tag {{ display:inline-block; padding:.15rem .5rem; border-radius:10px;
          font-size:.72rem; font-weight:700; margin-top:.5rem; }}
  .tag-cloud {{ background:#1565c0; color:white; }}
  .tag-local {{ background:#2e7d32; color:white; }}
  .tag-free  {{ background:#2e7d32; color:white; }}

  /* ── Cost table ── */
  table {{ width:100%; border-collapse:collapse; font-size:.88rem; }}
  th {{ background:var(--light); padding:.65rem .9rem; text-align:left;
        border-bottom:2px solid var(--border); font-weight:600; }}
  td {{ padding:.55rem .9rem; border-bottom:1px solid var(--border); vertical-align:middle; }}
  tr:last-child td {{ border-bottom:none; }}
  .planning-row td {{ background:#fffde7; }}
  .total-row td {{ background:var(--light); font-size:.95rem; }}
  .cost-green {{ color:var(--green); }}
  .cost-red   {{ color:var(--red); }}
  .local-model {{ color:var(--purple); font-size:.82rem; }}
  .center {{ text-align:center; }}

  /* ── Savings banner ── */
  .savings {{ background:linear-gradient(135deg,#1b5e20,#2e7d32);
              color:white; border-radius:12px; padding:2rem; text-align:center;
              margin-top:1.5rem; }}
  .savings-pct {{ font-size:4rem; font-weight:900; line-height:1; }}
  .savings-label {{ font-size:1rem; opacity:.85; margin-top:.25rem; }}
  .savings-stats {{ display:flex; justify-content:center; gap:3rem;
                    margin-top:1.5rem; flex-wrap:wrap; }}
  .stat-val {{ font-size:1.6rem; font-weight:800; }}
  .stat-lbl {{ font-size:.78rem; opacity:.8; margin-top:.1rem; }}

  /* ── Technical detail (collapsed) ── */
  .step-row {{ border:1px solid var(--border); border-radius:8px;
               margin-bottom:.7rem; overflow:hidden; }}
  .step-meta {{ display:flex; align-items:center; gap:.8rem; padding:.75rem 1rem;
                background:var(--light); flex-wrap:wrap; }}
  .step-num {{ background:var(--blue); color:white; border-radius:50%;
               width:1.6rem; height:1.6rem; display:flex; align-items:center;
               justify-content:center; font-size:.73rem; font-weight:700; flex-shrink:0; }}
  details {{ padding:1rem; }}
  summary.show-code {{ cursor:pointer; color:var(--blue); font-size:.84rem; }}
  pre {{ background:#1e1e2e; color:#cdd6f4; border-radius:8px; padding:1rem;
         overflow-x:auto; margin-top:.75rem; font-size:.8rem; line-height:1.5; }}
  .output-line {{ margin-top:.6rem; padding:.5rem .8rem; background:#f0fff4;
                  border-left:3px solid var(--green); border-radius:4px;
                  font-size:.83rem; color:#1a5c35; }}
  .badge {{ padding:.2rem .55rem; border-radius:10px; font-size:.72rem;
            font-weight:700; color:white; }}
  .status-ok  {{ color:var(--green); font-weight:600; }}
  .status-err {{ color:var(--red); font-weight:600; }}
  .muted {{ color:var(--gray); }}
  .small {{ font-size:.82rem; }}
  code {{ font-family:"SF Mono","Fira Code",monospace; font-size:.82rem; }}
  pre code {{ font-size:.8rem; }}

  .footer {{ text-align:center; color:var(--gray); font-size:.8rem;
             margin-top:2rem; padding-top:1rem; border-top:1px solid var(--border); }}
</style>
</head>
<body>
<div class="page">

  <!-- ① HERO -->
  <div class="hero">
    <h1>🤖 Data Pipeline Agent</h1>
    <p class="sub">Planner-Executor Pattern — AI-native data analysis demo</p>
    <div class="goal-box">🎯 <strong>Goal:</strong> {goal}</div>
    <div class="hero-meta">
      <span>📊 40 customers analysed</span>
      <span>🔢 {len(steps)} pipeline steps</span>
      <span>✅ {successes}/{len(execution_log)} steps succeeded</span>
      <span>⏱ {total_seconds:.0f}s total runtime</span>
      <span>📅 {datetime.now().strftime('%d %b %Y, %H:%M')}</span>
    </div>
  </div>

  <!-- ② HOW IT WORKS -->
  <div class="card">
    <div class="card-title">⚙️ How it works</div>
    <div class="card-sub">Two models, two jobs — each doing what it's best at.</div>
    <div class="flow">
      <div class="flow-box box-cloud">
        <h3>🧠 Planner</h3>
        <p>Claude Opus 4.6 reads the dataset and writes a precise, step-by-step plan</p>
        <span class="tag tag-cloud">Cloud API · one call</span>
      </div>
      <div class="flow-arrow">→</div>
      <div class="flow-box box-local">
        <h3>⚙️ Executor</h3>
        <p>Local model follows the plan exactly — generates and runs code for each step</p>
        <span class="tag tag-local">Runs on your machine</span>
      </div>
      <div class="flow-arrow">→</div>
      <div class="flow-box box-report">
        <h3>📊 Results</h3>
        <p>Insights and cost report — showing exactly what was saved</p>
        <span class="tag tag-free">No extra cost</span>
      </div>
    </div>
    <p class="muted small" style="margin-top:.5rem">
      Claude only reasons about <em>what to do</em>. The local model only executes <em>how to do it</em>.
      This collapses the quality gap between large and small models while keeping costs minimal.
    </p>
  </div>

  <!-- ③ INSIGHTS -->
  <div class="card">
    <div class="card-title">💡 Key Business Insights</div>
    <div class="card-sub">Derived from the customer dataset by the local model, guided by Claude's plan.</div>
    {insights_html if insights_html else '<p class="muted">No insights generated.</p>'}
  </div>

  <!-- ④ COST SAVINGS -->
  <div class="card">
    <div class="card-title">💰 Cost Comparison</div>
    <div class="card-sub">
      <strong>Actual cost</strong> = what this run cost using the planner-executor pattern. &nbsp;
      <strong>If all Claude</strong> = estimated cost if Claude had executed every step via the API.
    </div>
    <table>
      <thead>
        <tr>
          <th>Phase</th>
          <th>Model</th>
          <th class="center">Tokens (in / out)</th>
          <th class="center">Actual cost</th>
          <th class="center">If all Claude</th>
        </tr>
      </thead>
      <tbody>{cost_rows}</tbody>
    </table>

    <div class="savings">
      <div class="savings-pct">{savings_pct:.0f}%</div>
      <div class="savings-label">cost reduction with the planner-executor pattern</div>
      <div class="savings-stats">
        <div>
          <div class="stat-val">${actual_cost:.4f}</div>
          <div class="stat-lbl">Actual cost (this run)</div>
        </div>
        <div>
          <div class="stat-val">${hypothetical:.4f}</div>
          <div class="stat-lbl">If Claude ran everything</div>
        </div>
        <div>
          <div class="stat-val">${exec_est_cost:.4f}</div>
          <div class="stat-lbl">Saved by running locally</div>
        </div>
      </div>
    </div>
  </div>

  <!-- ⑤ TECHNICAL DETAIL (collapsed) -->
  <div class="card">
    <div class="card-title">🔬 Technical Detail</div>
    <div class="card-sub">The full pipeline — expand any step to see the code the local model generated.</div>
    {steps_detail}
  </div>

  <div class="footer">
    Data Pipeline Agent &nbsp;·&nbsp; Planner: Claude Opus 4.6 &nbsp;·&nbsp;
    Executor: {executor_model} &nbsp;·&nbsp; {datetime.now().strftime('%Y-%m-%d')}
  </div>

</div>
</body>
</html>"""

    path = os.path.join(OUTPUT_DIR, "report.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
