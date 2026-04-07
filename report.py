"""
report.py — Generates the HTML demo report.

Tells a three-act story:
  1. What we analysed   (goal + dataset)
  2. What we found      (actual computed data tables — verifiable ground truth)
  3. What it cost       (savings comparison — the demo's money slide)

Technical details (generated code, pandas steps) are collapsed by default.
"""

import os
import pandas as pd
from datetime import datetime

OUTPUT_DIR = "output"


def _badge(text: str, color: str) -> str:
    return f'<span class="badge" style="background:{color}">{text}</span>'


def _action_color(action: str) -> str:
    return {"clean": "#6c757d", "transform": "#0d6efd",
            "aggregate": "#6610f2", "analyze": "#198754"}.get(action, "#495057")


def _df_to_html(df: pd.DataFrame, highlight_col: str = None) -> str:
    """Render a DataFrame as a styled HTML table."""
    rows = ""
    for _, row in df.iterrows():
        cells = ""
        for col in df.columns:
            val = row[col]
            # Format numbers
            if isinstance(val, float):
                val = f"{val:,.1f}"
            elif isinstance(val, int):
                val = f"{val:,}"
            # Highlight the sort/key column
            style = ' style="font-weight:600;color:#0d6efd"' if col == highlight_col else ""
            cells += f"<td{style}>{val}</td>"
        rows += f"<tr>{cells}</tr>"

    headers = "".join(f"<th>{c.replace('_', ' ').title()}</th>" for c in df.columns)
    return f"""
    <div class="table-wrap">
      <table>
        <thead><tr>{headers}</tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""


def _compute_results(df: pd.DataFrame) -> dict:
    """
    Derive the three key result tables from the processed DataFrame.
    Uses verified pandas logic — not LLM-generated.
    Falls back gracefully if pipeline columns are missing.
    """
    tables = {}

    # ── At-risk customers ────────────────────────────────────────────────────
    if "churn_risk_score" in df.columns:
        # Derive at_risk if the pipeline didn't produce it (score > 50 = at risk)
        at_risk_mask = df["at_risk"] if "at_risk" in df.columns else df["churn_risk_score"] > 50

        # Keep only columns that actually exist in the DataFrame
        desired_cols = ["company_name", "region", "segment", "monthly_revenue",
                        "days_since_login", "support_tickets_last_90d", "nps_score",
                        "churn_risk_score"]
        available_cols = [c for c in desired_cols if c in df.columns]

        rename_map = {"company_name": "Company", "region": "Region",
                      "segment": "Segment", "monthly_revenue": "Monthly Revenue ($)",
                      "days_since_login": "Days Inactive",
                      "support_tickets_last_90d": "Tickets (90d)",
                      "nps_score": "NPS", "churn_risk_score": "Risk Score"}

        at_risk = (
            df[at_risk_mask]
            .sort_values("churn_risk_score", ascending=False)
            [available_cols]
            .rename(columns={k: v for k, v in rename_map.items() if k in available_cols})
        )
        tables["at_risk"] = at_risk
        tables["at_risk_revenue"] = df[at_risk_mask]["monthly_revenue"].sum()
        tables["at_risk_count"] = int(at_risk_mask.sum())

    # ── Revenue by region ─────────────────────────────────────────────────────
    rev_region = (
        df.groupby("region")["monthly_revenue"]
        .sum()
        .reset_index()
        .sort_values("monthly_revenue", ascending=False)
        .rename(columns={"region": "Region", "monthly_revenue": "Monthly Revenue ($)"})
    )
    tables["revenue_by_region"] = rev_region

    # ── Revenue by product ────────────────────────────────────────────────────
    rev_product = (
        df.groupby("product")["monthly_revenue"]
        .sum()
        .reset_index()
        .sort_values("monthly_revenue", ascending=False)
        .rename(columns={"product": "Product", "monthly_revenue": "Monthly Revenue ($)"})
    )
    tables["revenue_by_product"] = rev_product

    return tables


def generate_report(
    plan: dict,
    planner_tokens: dict,
    results: dict,
    execution_log: list,
    total_seconds: float,
    goal: str,
) -> str:

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    steps          = plan.get("steps", [])
    final_df       = results.get("final_df", pd.DataFrame())
    enriched_df    = results.get("enriched_df", final_df)
    executor_model = execution_log[0]["model"] if execution_log else "Ollama (local)"
    successes      = sum(1 for s in execution_log if s["success"])

    # ── Cost numbers ──────────────────────────────────────────────────────────
    actual_cost   = planner_tokens["total_cost"]
    exec_est_cost = sum(s["est_claude_cost"] for s in execution_log)
    hypothetical  = actual_cost + exec_est_cost
    savings_pct   = (exec_est_cost / hypothetical * 100) if hypothetical > 0 else 0

    # ── Computed result tables (ground truth) ─────────────────────────────────
    # Use enriched_df: preserves all rows + computed columns (churn_risk_score etc.)
    # even after aggregation/filter steps reduce the final_df row count.
    tables = _compute_results(enriched_df)

    # ── Results section HTML ──────────────────────────────────────────────────
    results_html = ""

    if "at_risk" in tables:
        at_risk_revenue = tables["at_risk_revenue"]
        at_risk_count   = tables["at_risk_count"]
        results_html += f"""
        <div class="result-block">
          <div class="result-header">
            <span class="result-icon">🚨</span>
            <div>
              <strong>At-Risk Customers</strong>
              <span class="result-meta">{at_risk_count} customers · ${at_risk_revenue:,.0f}/mo revenue at stake</span>
            </div>
          </div>
          {_df_to_html(tables['at_risk'], highlight_col='Risk Score')}
          <p class="table-note">Risk score 0–100 based on days inactive, support tickets, and NPS. Threshold: &gt;50.</p>
        </div>"""

    results_html += f"""
        <div class="result-grid">
          <div class="result-block">
            <div class="result-header">
              <span class="result-icon">🌍</span>
              <div><strong>Revenue by Region</strong></div>
            </div>
            {_df_to_html(tables['revenue_by_region'], highlight_col='Monthly Revenue ($)')}
          </div>
          <div class="result-block">
            <div class="result-header">
              <span class="result-icon">📦</span>
              <div><strong>Revenue by Product</strong></div>
            </div>
            {_df_to_html(tables['revenue_by_product'], highlight_col='Monthly Revenue ($)')}
          </div>
        </div>"""

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
        cost_rows += f"""
        <tr>
          <td>Step {log['step_id']}: {log['name']}
            {'<span class="ok">✓</span>' if log['success'] else '<span class="err">⚠</span>'}
          </td>
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

    # ── Technical detail rows ─────────────────────────────────────────────────
    steps_detail = ""
    for s in steps:
        log = next((l for l in execution_log if l["step_id"] == s["step_id"]), None)
        status_html = ('<span class="ok small">✓ ran</span>' if (log and log["success"])
                       else '<span class="err small">⚠ error</span>' if log else "")
        code_html = ""
        if log:
            code_html = (f'<details><summary class="show-code">View generated code</summary>'
                         f'<pre><code>{log["code"]}</code></pre>'
                         f'<div class="output-line">Output: {log["output"]}</div></details>')
        steps_detail += f"""
        <div class="step-row">
          <div class="step-meta">
            <span class="step-num">{s['step_id']}</span>
            <div><strong>{s['name']}</strong>
              <div class="muted small">{s['description']}</div>
            </div>
            {_badge(s['action'], _action_color(s['action']))}
            {status_html}
          </div>
          {code_html}
        </div>"""

    # ── Full HTML ─────────────────────────────────────────────────────────────
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
  .page {{ max-width:1000px; margin:0 auto; padding:2rem 1.5rem; }}

  /* Hero */
  .hero {{ background:linear-gradient(135deg,#1a1a2e,#0f3460); color:white;
           padding:2.5rem; border-radius:14px; margin-bottom:1.5rem; }}
  .hero h1 {{ font-size:1.9rem; font-weight:800; margin-bottom:.3rem; }}
  .hero .sub {{ color:#8ab4cc; margin-bottom:1.2rem; }}
  .goal-box {{ background:rgba(255,255,255,.1); border-left:4px solid #4fc3f7;
               padding:.9rem 1.1rem; border-radius:6px; font-size:.95rem; }}
  .hero-meta {{ display:flex; gap:1.5rem; margin-top:1rem;
                color:#8ab4cc; font-size:.82rem; flex-wrap:wrap; }}

  /* Cards */
  .card {{ background:white; border-radius:12px; padding:2rem;
           margin-bottom:1.5rem; box-shadow:0 1px 4px rgba(0,0,0,.07); }}
  .card-title {{ font-size:1.15rem; font-weight:700; margin-bottom:.3rem;
                 display:flex; align-items:center; gap:.5rem; }}
  .card-sub {{ color:var(--gray); font-size:.88rem; margin-bottom:1.3rem; }}

  /* How it works */
  .flow {{ display:flex; align-items:stretch; gap:0; margin:1.2rem 0; }}
  .flow-box {{ flex:1; border-radius:10px; padding:1.2rem 1rem; text-align:center; }}
  .flow-box h3 {{ font-size:.85rem; font-weight:700; margin-bottom:.4rem;
                  text-transform:uppercase; letter-spacing:.05em; }}
  .flow-box p {{ font-size:.82rem; line-height:1.4; }}
  .flow-arrow {{ display:flex; align-items:center; padding:0 .5rem;
                 font-size:1.4rem; color:var(--gray); flex-shrink:0; }}
  .box-cloud  {{ background:#e8f4fd; border:2px solid #90caf9; }}
  .box-local  {{ background:#e8f5e9; border:2px solid #a5d6a7; }}
  .box-report {{ background:#fce4ec; border:2px solid #f48fb1; }}
  .tag {{ display:inline-block; padding:.15rem .5rem; border-radius:10px;
          font-size:.72rem; font-weight:700; margin-top:.5rem; color:white; }}
  .tag-cloud {{ background:#1565c0; }}
  .tag-local {{ background:#2e7d32; }}

  /* Results */
  .result-block {{ margin-bottom:1.5rem; }}
  .result-header {{ display:flex; align-items:center; gap:.75rem;
                    margin-bottom:.75rem; }}
  .result-icon {{ font-size:1.4rem; }}
  .result-header strong {{ font-size:1rem; font-weight:700; display:block; }}
  .result-meta {{ font-size:.82rem; color:var(--gray); }}
  .result-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:1.5rem; }}
  @media(max-width:680px) {{ .result-grid {{ grid-template-columns:1fr; }} }}
  .table-wrap {{ overflow-x:auto; }}
  .table-note {{ font-size:.78rem; color:var(--gray); margin-top:.5rem; }}
  table {{ width:100%; border-collapse:collapse; font-size:.85rem; }}
  th {{ background:var(--light); padding:.6rem .8rem; text-align:left;
        border-bottom:2px solid var(--border); font-weight:600;
        white-space:nowrap; }}
  td {{ padding:.5rem .8rem; border-bottom:1px solid var(--border);
        vertical-align:middle; }}
  tr:last-child td {{ border-bottom:none; }}
  tr:hover td {{ background:#fafafa; }}

  /* Cost table specifics */
  .planning-row td {{ background:#fffde7; }}
  .total-row td {{ background:var(--light); }}
  .cost-green {{ color:var(--green); font-weight:600; }}
  .cost-red   {{ color:var(--red); }}
  .local-model {{ color:var(--purple); font-size:.82rem; }}
  .center {{ text-align:center; }}

  /* Savings banner */
  .savings {{ background:linear-gradient(135deg,#1b5e20,#2e7d32);
              color:white; border-radius:12px; padding:2rem;
              text-align:center; margin-top:1.5rem; }}
  .savings-pct {{ font-size:4rem; font-weight:900; line-height:1; }}
  .savings-label {{ font-size:1rem; opacity:.85; margin-top:.25rem; }}
  .savings-stats {{ display:flex; justify-content:center; gap:3rem;
                    margin-top:1.5rem; flex-wrap:wrap; }}
  .stat-val {{ font-size:1.6rem; font-weight:800; }}
  .stat-lbl {{ font-size:.78rem; opacity:.8; margin-top:.1rem; }}

  /* Technical detail */
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
         overflow-x:auto; margin-top:.75rem; font-size:.79rem; line-height:1.5; }}
  .output-line {{ margin-top:.6rem; padding:.5rem .8rem; background:#f0fff4;
                  border-left:3px solid var(--green); border-radius:4px;
                  font-size:.82rem; color:#1a5c35; }}
  .badge {{ padding:.2rem .55rem; border-radius:10px; font-size:.72rem;
            font-weight:700; color:white; }}
  .ok  {{ color:var(--green); font-weight:600; }}
  .err {{ color:var(--red); font-weight:600; }}
  .muted {{ color:var(--gray); }}
  .small {{ font-size:.82rem; }}
  code {{ font-family:"SF Mono","Fira Code",monospace; }}

  .footer {{ text-align:center; color:var(--gray); font-size:.8rem;
             margin-top:2rem; padding-top:1rem;
             border-top:1px solid var(--border); }}
</style>
</head>
<body>
<div class="page">

  <!-- HERO -->
  <div class="hero">
    <h1>🤖 Data Pipeline Agent</h1>
    <p class="sub">Planner-Executor Pattern — AI-native data analysis demo</p>
    <div class="goal-box">🎯 <strong>Goal:</strong> {goal}</div>
    <div class="hero-meta">
      <span>📊 {len(final_df)} customers analysed</span>
      <span>🔢 {len(steps)} pipeline steps</span>
      <span>✅ {successes}/{len(execution_log)} steps succeeded</span>
      <span>⏱ {total_seconds:.0f}s total runtime</span>
      <span>📅 {datetime.now().strftime('%d %b %Y, %H:%M')}</span>
    </div>
  </div>

  <!-- HOW IT WORKS -->
  <div class="card">
    <div class="card-title">⚙️ How it works</div>
    <div class="card-sub">Two models, two jobs — each doing what it's best at.</div>
    <div class="flow">
      <div class="flow-box box-cloud">
        <h3>🧠 Planner</h3>
        <p>Claude Opus 4.6 reads the dataset schema and writes a precise step-by-step plan</p>
        <span class="tag tag-cloud">Cloud API · one call</span>
      </div>
      <div class="flow-arrow">→</div>
      <div class="flow-box box-local">
        <h3>⚙️ Executor</h3>
        <p>Local model follows the plan — generates and runs pandas code for each step</p>
        <span class="tag tag-local">Runs on your machine · free</span>
      </div>
      <div class="flow-arrow">→</div>
      <div class="flow-box box-report">
        <h3>📊 Results</h3>
        <p>Actual computed data tables — verifiable numbers, not LLM interpretation</p>
        <span class="tag tag-local">Ground truth</span>
      </div>
    </div>
  </div>

  <!-- RESULTS -->
  <div class="card">
    <div class="card-title">📊 Results</div>
    <div class="card-sub">
      Computed directly from the processed data — every number is traceable back to the CSV.
    </div>
    {results_html}
  </div>

  <!-- COST SAVINGS -->
  <div class="card">
    <div class="card-title">💰 Cost Comparison</div>
    <div class="card-sub">
      <strong>Actual cost</strong> = Claude plans once, local model executes everything. &nbsp;
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
        <div><div class="stat-val">${actual_cost:.4f}</div>
             <div class="stat-lbl">Actual cost (this run)</div></div>
        <div><div class="stat-val">${hypothetical:.4f}</div>
             <div class="stat-lbl">If Claude ran everything</div></div>
        <div><div class="stat-val">${exec_est_cost:.4f}</div>
             <div class="stat-lbl">Saved by running locally</div></div>
      </div>
    </div>
  </div>

  <!-- TECHNICAL DETAIL -->
  <div class="card">
    <div class="card-title">🔬 Technical Detail</div>
    <div class="card-sub">The full pipeline — expand any step to see the code the local model generated.</div>
    {steps_detail}
  </div>

  <div class="footer">
    Data Pipeline Agent &nbsp;·&nbsp; Planner: Claude Opus 4.6
    &nbsp;·&nbsp; Executor: {executor_model}
    &nbsp;·&nbsp; {datetime.now().strftime('%Y-%m-%d')}
  </div>

</div>
</body>
</html>"""

    path = os.path.join(OUTPUT_DIR, "report.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
