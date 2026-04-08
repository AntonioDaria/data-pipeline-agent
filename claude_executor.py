"""
claude_executor.py — Claude API executor (comparison against Ollama).

Runs the exact same pipeline steps as executor.py but uses Claude
via the Anthropic API, recording real token usage per step.

Use this to:
  • Replace the estimated token counts with measured ones
  • Compare step success rate and code quality against Ollama
  • Measure the actual cost of running execution with Claude

Model: claude-haiku-4-5 — cheapest Claude model, still far larger than
       the 7B local model, giving the fairest cost/quality comparison.
"""

import io
import time
import numpy as np
import pandas as pd
import anthropic
from contextlib import redirect_stdout
from dotenv import load_dotenv

load_dotenv()

CLAUDE_EXECUTOR_MODEL        = "claude-haiku-4-5"
CLAUDE_INPUT_COST_PER_TOKEN  = 1.00 / 1_000_000   # Haiku 4.5 pricing
CLAUDE_OUTPUT_COST_PER_TOKEN = 5.00 / 1_000_000

EXECUTOR_SYSTEM = """You are a Python/pandas engineer. Write working pandas code for the step described.

STRICT RULES:
- `df` is the input DataFrame (already loaded, do not re-read CSV)
- `pd` and `np` are pre-imported — do not import anything
- Assign your result to `result` (must be a DataFrame)
- Print one short summary line at the end
- Output RAW Python code only — no markdown, no ```python, no commentary"""


def _call_claude(prompt: str) -> tuple[str, int, int]:
    """Call Claude and return (response_text, input_tokens, output_tokens)."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=CLAUDE_EXECUTOR_MODEL,
        max_tokens=1024,
        system=EXECUTOR_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip(), response.usage.input_tokens, response.usage.output_tokens


def _strip_fences(code: str) -> str:
    lines = code.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    lines = [l for l in lines if l.strip() != "```"]
    return "\n".join(lines).strip()


def _build_prompt(step: dict, df: pd.DataFrame) -> str:
    return (
        f"Step {step['step_id']}: {step['name']}\n"
        f"Description: {step['description']}\n"
        f"Action: {step['action']}\n"
        f"Hint: {step['pandas_hint']}\n"
        f"Expected output: {step['expected_output']}\n\n"
        f"DataFrame shape: {df.shape}\n"
        f"Columns: {list(df.columns)}\n"
        f"Dtypes: {dict(df.dtypes.astype(str))}\n\n"
        "Write the pandas code. Input is `df`. Output must be assigned to `result`."
    )


def _try_execute(code: str, df: pd.DataFrame) -> tuple[pd.DataFrame, str, bool]:
    buf = io.StringIO()
    local_vars = {"df": df.copy(), "pd": pd, "np": np, "result": None}
    try:
        with redirect_stdout(buf):
            exec(code, local_vars)  # noqa: S102
        output = buf.getvalue().strip() or "(no print output)"
        result = local_vars.get("result")
        if not isinstance(result, pd.DataFrame):
            for val in local_vars.values():
                if isinstance(val, pd.DataFrame) and val is not df:
                    result = val
                    break
            else:
                result = df
        return result, output, True
    except Exception as exc:
        return df, f"Execution error: {exc}", False


def execute_step(df: pd.DataFrame, step: dict) -> tuple[pd.DataFrame, str, str, bool, int, int]:
    """
    Generate and execute code for one pipeline step via Claude.

    Returns:
        result_df, code, output, success, input_tokens, output_tokens
    """
    prompt = _build_prompt(step, df)
    raw, input_tokens, output_tokens = _call_claude(prompt)
    code = _strip_fences(raw)
    result, output, success = _try_execute(code, df)
    return result, code, output, success, input_tokens, output_tokens


def generate_insights(df: pd.DataFrame, insights_prompt: str) -> tuple[str, int, int]:
    prompt = (
        f"{insights_prompt}\n\n"
        f"Data summary:\n{df.describe(include='all').to_string()}\n\n"
        f"Sample rows:\n{df.head(10).to_string()}\n\n"
        "Provide exactly 5 concise business insights as a numbered list."
    )
    return _call_claude(prompt)


def execute_pipeline(csv_path: str, plan: dict) -> tuple[dict, list]:
    """
    Execute every step in the plan using Claude.

    Returns:
        results       — dict with final_df, enriched_df, insights
        execution_log — list of per-step dicts with REAL token counts
    """
    df = pd.read_csv(csv_path)
    enriched_df = df.copy()
    execution_log = []
    steps = plan.get("steps", [])

    for step in steps:
        print(f"  [{step['step_id']}/{len(steps)}] {step['name']}...")
        t0 = time.time()

        action = step.get("action", "")
        input_df = enriched_df if action in ("aggregate", "analyze") else df

        result_df, code, output, success, input_tokens, output_tokens = execute_step(input_df, step)
        elapsed = round(time.time() - t0, 2)

        step_cost = (
            input_tokens  * CLAUDE_INPUT_COST_PER_TOKEN +
            output_tokens * CLAUDE_OUTPUT_COST_PER_TOKEN
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
            "model":     CLAUDE_EXECUTOR_MODEL,
            # Real measured values from Anthropic usage
            "claude_input_tokens":  input_tokens,
            "claude_output_tokens": output_tokens,
            "claude_cost":          step_cost,
            "tokens_are_real":      True,
            "tokens_source":        "anthropic_usage",
        })

        df = result_df
        if success and len(result_df) == len(enriched_df):
            enriched_df = result_df.copy()

    print(f"  [insights] Generating insights with {CLAUDE_EXECUTOR_MODEL}...")
    insights, _, _ = generate_insights(df, plan.get("insights_prompt", "Summarise the data."))

    return {"final_df": df, "enriched_df": enriched_df, "insights": insights}, execution_log
