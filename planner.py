"""
planner.py — Claude Opus 4.6 pipeline architect.

Reads the dataset schema and goal, then produces a strict JSON pipeline
plan that the local Ollama executor can follow without ambiguity.
"""

import json
import anthropic
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

CLAUDE_MODEL = "claude-opus-4-6"

# Pricing: Claude Opus 4.6  ($5.00 input / $25.00 output per 1M tokens)
CLAUDE_INPUT_COST_PER_TOKEN  = 5.00  / 1_000_000
CLAUDE_OUTPUT_COST_PER_TOKEN = 25.00 / 1_000_000

SYSTEM_PROMPT = """You are a senior data pipeline architect. Your only job is to produce a
precise, machine-readable JSON pipeline plan that will be executed step-by-step
by a small local language model with limited reasoning capacity.

Each step must be:
- Self-contained: only `df` carries state between steps; do NOT reference variables from prior steps
- Specific: include a concrete pandas code hint so the executor cannot hallucinate
- Verifiable: include a clear success criterion

Output ONLY valid JSON — no markdown fences, no prose, no explanation.

Required schema:
{
  "goal": "<restate the analysis goal>",
  "dataset_summary": {
    "rows": <int>,
    "columns": ["<col>", ...],
    "key_columns": ["<most relevant columns for the goal>"]
  },
  "steps": [
    {
      "step_id": <int starting at 1>,
      "name": "<3-5 word name>",
      "description": "<one precise sentence: what this step does and why>",
      "action": "<one of: clean | transform | aggregate | analyze>",
      "pandas_hint": "<concrete pandas snippet, e.g. df['col'].fillna(df['col'].median())>",
      "expected_output": "<description of result DataFrame or value>",
      "validation": "<how to confirm the step worked>"
    }
  ],
  "insights_prompt": "<instruction for the executor to derive 5 business insights from the final DataFrame>"
}"""


def create_pipeline_plan(csv_path: str, goal: str) -> tuple[dict, dict]:
    """
    Ask Claude to architect a pipeline plan for the given CSV and goal.

    Returns:
        plan         — parsed plan dict
        token_usage  — dict with token counts and $ cost breakdown
    """
    client = anthropic.Anthropic()

    df = pd.read_csv(csv_path)
    schema = {
        "rows": len(df),
        "columns": list(df.columns),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        "null_counts": df.isnull().sum().to_dict(),
        "sample": df.head(3).to_dict(orient="records"),
        "numeric_summary": df.describe().to_dict(),
    }

    user_message = (
        f"Dataset path: {csv_path}\n"
        f"Goal: {goal}\n\n"
        f"Dataset schema:\n{json.dumps(schema, indent=2, default=str)}\n\n"
        "Produce the pipeline plan JSON."
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text.strip()
    # Strip markdown fences if Claude wraps the JSON
    if raw_text.startswith("```"):
        raw_text = "\n".join(raw_text.split("\n")[1:])
    if raw_text.endswith("```"):
        raw_text = "\n".join(raw_text.split("\n")[:-1])
    plan = json.loads(raw_text.strip())

    input_tokens  = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    token_usage = {
        "model": CLAUDE_MODEL,
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "total_tokens":  input_tokens + output_tokens,
        "input_cost":    input_tokens  * CLAUDE_INPUT_COST_PER_TOKEN,
        "output_cost":   output_tokens * CLAUDE_OUTPUT_COST_PER_TOKEN,
        "total_cost":    (input_tokens  * CLAUDE_INPUT_COST_PER_TOKEN +
                          output_tokens * CLAUDE_OUTPUT_COST_PER_TOKEN),
    }

    return plan, token_usage
