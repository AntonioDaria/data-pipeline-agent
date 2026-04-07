"""
main.py — Planner-Executor Pipeline Demo

Architecture:
  1. Claude Opus 4.6 (planner)  — reads schema, produces a strict JSON plan
  2. Ollama / qwen2.5-coder:7b (executor) — follows the plan step-by-step
  3. HTML report — shows results + exact cost comparison

Usage:
    python main.py
    python main.py --csv data/customers.csv --goal "Find top revenue segments"
"""

import argparse
import time

from planner import create_pipeline_plan
from executor import execute_pipeline, OLLAMA_MODEL
from report import generate_report

DEFAULT_CSV  = "data/customers.csv"
DEFAULT_GOAL = (
    "Identify customers at risk of churn and find the top revenue-generating "
    "segments by region and product"
)

DIVIDER = "─" * 62


def main():
    parser = argparse.ArgumentParser(description="Data Pipeline Agent Demo")
    parser.add_argument("--csv",  default=DEFAULT_CSV,  help="Path to input CSV")
    parser.add_argument("--goal", default=DEFAULT_GOAL, help="Analysis goal")
    args = parser.parse_args()

    print(f"\n{'═' * 62}")
    print("  DATA PIPELINE AGENT — Planner / Executor Pattern")
    print(f"{'═' * 62}\n")
    print(f"  CSV  : {args.csv}")
    print(f"  Goal : {args.goal[:70]}...")
    print()

    run_start = time.time()

    # ── PHASE 1 : PLANNING (Claude) ──────────────────────────────────────────
    print(f"{DIVIDER}")
    print("  PHASE 1 — Planning with Claude Opus 4.6")
    print(f"{DIVIDER}")
    phase1_start = time.time()

    plan, planner_tokens = create_pipeline_plan(args.csv, args.goal)

    phase1_time = time.time() - phase1_start
    print(f"  ✓ Plan ready in {phase1_time:.1f}s")
    print(f"    Steps:   {len(plan['steps'])}")
    print(f"    Tokens:  {planner_tokens['total_tokens']:,}  "
          f"({planner_tokens['input_tokens']:,} in / {planner_tokens['output_tokens']:,} out)")
    print(f"    Cost:    ${planner_tokens['total_cost']:.4f}")
    print()

    for step in plan["steps"]:
        print(f"    [{step['step_id']}] {step['name']}")
    print()

    # ── PHASE 2 : EXECUTION (Ollama) ─────────────────────────────────────────
    print(f"{DIVIDER}")
    print(f"  PHASE 2 — Executing with Ollama ({OLLAMA_MODEL})")
    print(f"{DIVIDER}")
    phase2_start = time.time()

    results, execution_log = execute_pipeline(args.csv, plan)

    phase2_time = time.time() - phase2_start
    successes = sum(1 for s in execution_log if s["success"])
    print(f"\n  ✓ Execution done in {phase2_time:.1f}s  "
          f"({successes}/{len(execution_log)} steps succeeded)\n")

    # ── PHASE 3 : REPORT ─────────────────────────────────────────────────────
    print(f"{DIVIDER}")
    print("  PHASE 3 — Generating HTML report")
    print(f"{DIVIDER}")

    total_time  = time.time() - run_start
    report_path = generate_report(
        plan, planner_tokens, results, execution_log, total_time, args.goal
    )

    # ── SUMMARY ──────────────────────────────────────────────────────────────
    exec_est   = sum(s["est_claude_cost"] for s in execution_log)
    actual     = planner_tokens["total_cost"]
    hypo       = actual + exec_est
    savings_pc = exec_est / hypo * 100 if hypo > 0 else 0

    print(f"\n{'═' * 62}")
    print("  RESULTS")
    print(f"{'═' * 62}")
    print(f"  Report       : {report_path}")
    print(f"  Total time   : {total_time:.1f}s\n")
    print(f"  {'COST BREAKDOWN':30s}  {'ACTUAL':>10}  {'IF ALL CLAUDE':>14}")
    print(f"  {'─'*30}  {'─'*10}  {'─'*14}")
    print(f"  {'Planning (Claude Opus 4.6)':30s}  ${actual:>9.4f}  ${actual:>13.4f}")
    for log in execution_log:
        label = f"Step {log['step_id']}: {log['name']}"[:30]
        print(f"  {label:30s}  {'$0.0000':>10}  ${log['est_claude_cost']:>13.4f}")
    print(f"  {'─'*30}  {'─'*10}  {'─'*14}")
    print(f"  {'TOTAL':30s}  ${actual:>9.4f}  ${hypo:>13.4f}")
    print(f"\n  🎉 Savings: {savings_pc:.0f}%  (${exec_est:.4f} kept local)\n")


if __name__ == "__main__":
    main()
