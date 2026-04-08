"""
main.py — Planner-Executor Pipeline Demo

Architecture:
  1. Claude Opus 4.6 (planner)  — reads schema, produces a strict JSON plan
  2. Ollama + Claude Haiku run the SAME plan in parallel
  3. HTML report — side-by-side comparison: success rate, speed, cost

Usage:
    python main.py
    python main.py --csv data/customers.csv --goal "Find top revenue segments"
"""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor

from planner import create_pipeline_plan
from report import generate_report
import executor as ollama_executor
import claude_executor as claude_executor_mod

DEFAULT_CSV  = "data/customers.csv"
DEFAULT_GOAL = (
    "Identify customers at risk of churn and find the top revenue-generating "
    "segments by region and product"
)

DIVIDER = "─" * 62


def _run_timed(fn, csv_path, plan):
    """Run an execute_pipeline function and return (results, log, elapsed_seconds)."""
    t0 = time.time()
    results, log = fn(csv_path, plan)
    return results, log, round(time.time() - t0, 1)


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

    # ── PHASE 1 : PLANNING (Claude Opus) ─────────────────────────────────────
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

    # ── PHASE 2 : PARALLEL EXECUTION ─────────────────────────────────────────
    print(f"{DIVIDER}")
    print(f"  PHASE 2 — Running Ollama ({ollama_executor.OLLAMA_MODEL})"
          f" and Claude ({claude_executor_mod.CLAUDE_EXECUTOR_MODEL}) in parallel")
    print(f"{DIVIDER}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        ollama_future = pool.submit(_run_timed, ollama_executor.execute_pipeline,
                                    args.csv, plan)
        claude_future = pool.submit(_run_timed, claude_executor_mod.execute_pipeline,
                                    args.csv, plan)

        ollama_results, ollama_log, ollama_time = ollama_future.result()
        claude_results, claude_log, claude_time = claude_future.result()

    # Fill Ollama log with Claude token averages from this run (for comparison only).
    claude_in_tokens = [s["claude_input_tokens"] for s in claude_log if s.get("tokens_are_real")]
    claude_out_tokens = [s["claude_output_tokens"] for s in claude_log if s.get("tokens_are_real")]
    if claude_in_tokens and claude_out_tokens:
        avg_in = sum(claude_in_tokens) / len(claude_in_tokens)
        avg_out = sum(claude_out_tokens) / len(claude_out_tokens)
        avg_cost = (
            avg_in * claude_executor_mod.CLAUDE_INPUT_COST_PER_TOKEN +
            avg_out * claude_executor_mod.CLAUDE_OUTPUT_COST_PER_TOKEN
        )
        for s in ollama_log:
            s["claude_input_tokens"] = round(avg_in, 1)
            s["claude_output_tokens"] = round(avg_out, 1)
            s["claude_cost"] = avg_cost
            s["tokens_are_real"] = False
            s["tokens_source"] = "claude_avg_this_run"

    ollama_ok = sum(1 for s in ollama_log if s["success"])
    claude_ok = sum(1 for s in claude_log if s["success"])
    print(f"\n  ✓ Both executors done")
    print(f"    Ollama : {ollama_time:.1f}s  ({ollama_ok}/{len(ollama_log)} steps succeeded)")
    print(f"    Claude : {claude_time:.1f}s  ({claude_ok}/{len(claude_log)} steps succeeded)\n")

    # ── PHASE 3 : REPORT ─────────────────────────────────────────────────────
    print(f"{DIVIDER}")
    print("  PHASE 3 — Generating HTML report")
    print(f"{DIVIDER}")

    total_time  = time.time() - run_start
    report_path = generate_report(
        plan, planner_tokens,
        ollama_results, ollama_log, ollama_time,
        claude_results, claude_log, claude_time,
        total_time, args.goal,
    )

    # ── SUMMARY ──────────────────────────────────────────────────────────────
    planning_cost  = planner_tokens["total_cost"]
    ollama_cost    = 0.0  # local execution is free
    claude_ex_cost = sum(s["claude_cost"] for s in claude_log)   # real $

    print(f"\n{'═' * 62}")
    print("  RESULTS")
    print(f"{'═' * 62}")
    print(f"  Report     : {report_path}")
    print(f"  Total time : {total_time:.1f}s\n")
    print(f"  {'':30s}  {'OLLAMA':>10}  {'CLAUDE HAIKU':>14}")
    print(f"  {'─'*30}  {'─'*10}  {'─'*14}")
    print(f"  {'Planning (shared)':30s}  ${planning_cost:>9.4f}  ${planning_cost:>13.4f}")
    print(f"  {'Execution':30s}  {'$0.0000':>10}  ${claude_ex_cost:>13.4f}")
    print(f"  {'─'*30}  {'─'*10}  {'─'*14}")
    print(f"  {'TOTAL':30s}  ${planning_cost:>9.4f}  ${planning_cost + claude_ex_cost:>13.4f}")
    print(f"\n  Steps:  Ollama {ollama_ok}/{len(ollama_log)}  ·  "
          f"Claude {claude_ok}/{len(claude_log)}")
    print(f"  Speed:  Ollama {ollama_time:.0f}s  ·  Claude {claude_time:.0f}s\n")


if __name__ == "__main__":
    main()
