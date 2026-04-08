# Data Pipeline Agent

> A demo of the **Planner-Executor Pattern** — using a powerful cloud model for high-level planning and a free local model for execution, to deliver autonomy at a fraction of the token cost.

---

## The Pattern

```
┌────────────────────────────────────────────────────────────┐
│  PHASE 1 — PLANNING                      Claude Opus 4.6   │
│                                                             │
│  Input : CSV schema + analysis goal                        │
│  Output: Strict JSON pipeline spec (steps + hints)         │
│                                                             │
│  Small number of tokens — high-quality reasoning           │
└─────────────────────────────┬──────────────────────────────┘
                              │  JSON plan
                              ▼
┌────────────────────────────────────────────────────────────┐
│  PHASE 2 — EXECUTION             Ollama / qwen2.5-coder:7b │
│                                                             │
│  For each step in the plan:                                │
│    1. Generate targeted pandas code (guided by Claude's    │
│       precise spec — no ambiguity, no hallucination)       │
│    2. Execute locally                                       │
│    3. Pass result to next step                             │
│                                                             │
│  Zero API calls — runs entirely on your machine            │
└─────────────────────────────┬──────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────┐
│  PHASE 3 — REPORT                                          │
│                                                             │
│  HTML report with:                                         │
│    • Pipeline plan (Claude-authored)                       │
│    • Execution results + generated code                    │
│    • Key insights                                          │
│    • Cost comparison table  ← the demo's money slide       │
└────────────────────────────────────────────────────────────┘
```

**Why this works (in practice):** Claude's plan is precise (action type, pandas hint, validation rule), so the local model focuses on *how* to implement each step. This often narrows the quality gap, but small models can still drop columns or make subtle mistakes without extra guardrails.

---

## Prerequisites

### 1 · Anthropic API key
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 2 · Ollama + coding model
```bash
# Install Ollama: https://ollama.ai
brew install ollama       # macOS
ollama serve              # start the daemon (keep running)
ollama pull qwen2.5-coder:7b   # ~4 GB, runs well on M1 Pro 16 GB
```

### 3 · Python dependencies
```bash
poetry install
```

---

## Usage

```bash
# Default demo (SaaS customer churn analysis)
poetry run python main.py

# Custom CSV and goal
poetry run python main.py --csv path/to/data.csv --goal "Identify top performing products by region"
```

The report is written to `output/report.html` — open it in any browser.

---

## Project Structure

```
data-pipeline-agent/
├── main.py          # Orchestrator — runs the three phases
├── planner.py       # Claude Opus 4.6 — produces the JSON plan
├── executor.py      # Ollama — executes each step locally
├── report.py        # Generates output/report.html
├── data/
│   └── customers.csv   # Demo dataset: 40 SaaS customers
├── output/          # Generated reports (git-ignored)
```

---

## Cost Model

Costs vary by dataset size and plan complexity. The report shows real token usage and costs for the Claude calls, and local execution is free.

The exact numbers are shown in `output/report.html` after each run.

---

## Observed Findings and Conclusions

These observations are from real runs of the demo on the included dataset and default goal.

**What we observed**
- Total runtime is dominated by the slowest executor. In a recent run, planning took ~36s, Claude execution ~22s, and Ollama execution ~156s, leading to a total runtime around ~3 minutes.
- Ollama can fail on downstream steps when it drops columns created earlier. In the observed run, a step omitted `days_since_login`, causing a cascade of `KeyError` failures for `churn_risk_score` and `churn_risk_tier` in later steps.
- Claude Haiku did not exhibit these failures on the same plan. It preserved required columns, so dependent steps succeeded.

**Conclusions**
- Failures are primarily due to model output quality rather than bugs in the executor code.
- Smaller local models are more likely to generate code that unintentionally drops columns or violates implicit pipeline assumptions.
- If consistency is critical, add guardrails: enforce column preservation, validate required columns after each step, and retry with stricter prompts when necessary.

---

## Customising

- **Change the model:** Edit `CLAUDE_MODEL` in `planner.py` and `OLLAMA_MODEL` in `executor.py`
- **Add steps:** The plan is generated dynamically — just change the goal
- **Different dataset:** Pass `--csv` and `--goal` to `main.py`

---

## How the Plan Prevents Hallucination

Each step in Claude's plan includes:

| Field | Purpose |
|---|---|
| `description` | Exactly what the step does and why |
| `action` | Constrains the type of operation |
| `pandas_hint` | A concrete code snippet — the executor cannot stray far |
| `expected_output` | What the result should look like |
| `validation` | How to check success |

The local model's job is reduced to *completing a code template*, not *reasoning about a problem* — which is well within its capabilities.
