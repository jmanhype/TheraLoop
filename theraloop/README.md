# TheraLoop v0.1 — GEPA + Logprob Surprise Loop (OSS Blueprint)

Production-ready starter for a **reflective GEPA** (prompt evolution) loop with **multi‑objective Pareto** (exact, grounding, logprob),
a **confidence‑aware router** at serve-time, and **MLflow** telemetry for surprise/drift.

## Quickstart

```bash
# 1) setup (choose your env tool)
python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e .[all]

# 2) env
cp .env.example .env
# Fill TOGETHER_API_KEY if you want live API calls.
# Without keys, offline demo uses a mock LM for smoke tests.

# 3) dry run: optimize on demo evals (mock if no key)
python scripts/run_gepa.py --generations 2

# 4) evaluate best prompt
python scripts/run_eval.py outputs/best_prompt.txt

# 5) start a confidence-aware demo server
uvicorn scripts.serve_demo:app --port 8080 --reload
# curl example:
curl -s http://localhost:8080/answer -H 'content-type: application/json'       -d '{"question":"What is 2+2?"}'
```

### What’s inside
- **adapters/** wrapper for providers (Together mockable)
- **metrics/** exact, grounding, logprob
- **optim/** GEPA pipeline + Pareto
- **evals/** schema + scorer + demo dataset
- **serving/** router + calibration
- **monitor/** MLflow logging + drift stub
- **safety/** Granite Guardian hook (optional)
- **scripts/** runnable entrypoints
- **tests/** unit + end-to-end smoke tests

### License
Apache-2.0
