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

**Why this works:** Claude's plan is so precise (action type, pandas hint, validation rule) that the local model only needs to fill in the code — it never needs to reason about *what* to do, only *how* to do it. This collapses the execution quality gap between large and small models.

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
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Usage

```bash
# Default demo (SaaS customer churn analysis)
python main.py

# Custom CSV and goal
python main.py --csv path/to/data.csv --goal "Identify top performing products by region"
```

The report is written to `output/report.html` — open it in any browser.

---

## Project Structure

```
data-pipeline-agent/
├── main.py          # Orchestrator — runs the three phases
├── planner.py       # Claude Opus 4.6 — produces the JSON plan
├── executor.py      # Ollama — executes each step, tracks estimated savings
├── report.py        # Generates output/report.html
├── data/
│   └── customers.csv   # Demo dataset: 40 SaaS customers
├── output/          # Generated reports (git-ignored)
└── requirements.txt
```

---

## Cost Model

| Phase     | Model                   | Tokens        | Cost              |
|-----------|-------------------------|---------------|-------------------|
| Planning  | Claude Opus 4.6         | ~1,500        | ~$0.005           |
| Execution | qwen2.5-coder:7b (local)| —             | **$0.00**         |
| Insights  | qwen2.5-coder:7b (local)| —             | **$0.00**         |
| **Total** |                         |               | **~$0.005**       |

If Claude had executed every step instead: ~$0.02–0.04 → **70–85% savings**

The exact numbers are shown in `output/report.html` after each run.

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
