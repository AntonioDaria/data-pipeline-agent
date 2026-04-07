"""
executor.py — Local Ollama model executor.

Takes each step from the Claude-generated plan and:
  1. Asks Ollama to write pandas code for that step
  2. Executes the code locally
  3. Tracks what the step would have cost if Claude had run it

NOTE: exec() is used here intentionally for demo purposes.
      In production, use a sandboxed environment.
"""

import io
import time
import requests
import numpy as np
import pandas as pd
from contextlib import redirect_stdout

OLLAMA_MODEL    = "qwen2.5-coder:7b"
OLLAMA_BASE_URL = "http://localhost:11434"

# Conservative estimate of tokens Claude would need per execution step
# (prompt context + code generation) — used for the cost comparison report
ESTIMATED_CLAUDE_INPUT_TOKENS_PER_STEP  = 650
ESTIMATED_CLAUDE_OUTPUT_TOKENS_PER_STEP = 380
CLAUDE_INPUT_COST_PER_TOKEN  = 5.00  / 1_000_000
CLAUDE_OUTPUT_COST_PER_TOKEN = 25.00 / 1_000_000

EXECUTOR_SYSTEM = """You are a Python/pandas engineer. Write working pandas code for the step described.

STRICT RULES:
- `df` is the input DataFrame (already loaded, do not re-read CSV)
- `pd` and `np` are pre-imported — do not import anything
- Assign your result to `result` (must be a DataFrame)
- Print one short summary line at the end
- Output RAW Python code only — no markdown, no ```python, no commentary"""


def _call_ollama(prompt: str) -> str:
    """POST to Ollama /api/generate and return the response text."""
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt,
                  "system": EXECUTOR_SYSTEM, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["response"].strip()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Cannot reach Ollama at {OLLAMA_BASE_URL}. "
            "Make sure Ollama is running: `ollama serve`"
        )


def _strip_fences(code: str) -> str:
    """Remove markdown code fences if the model includes them."""
    lines = code.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def execute_step(df: pd.DataFrame, step: dict) -> tuple[pd.DataFrame, str, str, bool]:
    """
    Generate and execute code for one pipeline step via Ollama.

    Returns:
        result_df — DataFrame after the step (falls back to input df on error)
        code      — the generated Python code
        output    — stdout captured during execution
        success   — True if execution completed without exception
    """
    prompt = (
        f"Step {step['step_id']}: {step['name']}\n"
        f"Description: {step['description']}\n"
        f"Action: {step['action']}\n"
        f"Hint: {step['pandas_hint']}\n"
        f"Expected output: {step['expected_output']}\n"
        f"Validation: {step['validation']}\n\n"
        f"DataFrame shape: {df.shape}\n"
        f"Columns: {list(df.columns)}\n"
        f"Dtypes: {dict(df.dtypes.astype(str))}\n\n"
        "Write the pandas code. Input is `df`. Output must be assigned to `result`."
    )

    code = _strip_fences(_call_ollama(prompt))

    buf = io.StringIO()
    local_vars = {"df": df.copy(), "pd": pd, "np": np, "result": None}
    success = True

    try:
        with redirect_stdout(buf):
            exec(code, local_vars)  # noqa: S102
        output = buf.getvalue().strip() or "(no print output)"
        result = local_vars.get("result")
        if not isinstance(result, pd.DataFrame):
            result = df  # safe fallback
    except Exception as exc:
        output = f"Execution error: {exc}"
        result = df
        success = False

    return result, code, output, success


def generate_insights(df: pd.DataFrame, insights_prompt: str) -> str:
    """Ask Ollama to derive business insights from the final processed DataFrame."""
    prompt = (
        f"{insights_prompt}\n\n"
        f"Data summary:\n{df.describe(include='all').to_string()}\n\n"
        f"Sample rows:\n{df.head(10).to_string()}\n\n"
        "Provide exactly 5 concise business insights as a numbered list."
    )
    return _call_ollama(prompt)


def execute_pipeline(csv_path: str, plan: dict) -> tuple[dict, list]:
    """
    Execute every step in the plan using Ollama.

    Returns:
        results       — dict with final_df and insights text
        execution_log — list of per-step dicts for the report
    """
    df = pd.read_csv(csv_path)
    execution_log = []
    steps = plan.get("steps", [])

    for step in steps:
        print(f"  [{step['step_id']}/{len(steps)}] {step['name']}...")
        t0 = time.time()
        result_df, code, output, success = execute_step(df, step)
        elapsed = round(time.time() - t0, 2)

        est_cost = (
            ESTIMATED_CLAUDE_INPUT_TOKENS_PER_STEP  * CLAUDE_INPUT_COST_PER_TOKEN +
            ESTIMATED_CLAUDE_OUTPUT_TOKENS_PER_STEP * CLAUDE_OUTPUT_COST_PER_TOKEN
        )

        execution_log.append({
            "step_id":   step["step_id"],
            "name":      step["name"],
            "action":    step["action"],
            "code":      code,
            "output":    output,
            "success":   success,
            "rows_in":   len(df),
            "rows_out":  len(result_df),
            "duration":  elapsed,
            "model":     OLLAMA_MODEL,
            "est_claude_input_tokens":  ESTIMATED_CLAUDE_INPUT_TOKENS_PER_STEP,
            "est_claude_output_tokens": ESTIMATED_CLAUDE_OUTPUT_TOKENS_PER_STEP,
            "est_claude_cost":          est_cost,
        })

        df = result_df

    # Final insights — also run locally
    print("  [insights] Generating insights with Ollama...")
    insights = generate_insights(df, plan.get("insights_prompt", "Summarise the data."))

    return {"final_df": df, "insights": insights}, execution_log
