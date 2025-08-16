# TheraLoop Architecture (v0.1)

**Goal:** dependable, extensible, team-scalable system for GEPA prompt evolution + confidence-aware serving using logprob surprise, with stable contracts so internals can change without breaking callers.

## 0) Core ideas (primitives & contracts)
- **Primitive:** an Evaluation Case → `{query, gold?, sources?, negatives?}` and an LM Call Result → `{text, token_logprobs[]}`.
- **Optimization Contract:** "Given a prompt P and eval set E, return champion prompt P* and a trace."
- **Serving Contract:** "Given a user question Q and prompt P*, return `{answer, token_logprobs}`, then route by a pure function of token_logprobs."

All other parts (metrics, reflection, providers) are plugins behind stable APIs.

---

## 1) Module atlas (black boxes & single-owner units)

| Module | Path | Responsibility (public API only) | Replacement strategy |
|--------|------|-----------------------------------|---------------------|
| Adapters (Providers) | `theraloop/adapters/` | `complete_with_logprobs(prompt, …) -> {text, token_logprobs[]}` | Swap provider; contract unchanged |
| Metrics | `theraloop/metrics/` | `exact_match(pred,gold)`, `grounding_score(pred,sources)`, `logprob_metric(text, token_logprobs, inputs, negatives)` | Add/replace metrics without touching GEPA |
| Pareto | `theraloop/optim/pareto.py` | `pareto_front(points) -> idx[]` | Algorithm upgrades allowed |
| GEPA Pipeline | `theraloop/optim/gepa_pipeline.py` | `GEPA.run(seed_prompt) -> champion_prompt` | Internals free; IO contract fixed |
| Evals | `theraloop/evals/` | Schema + per-case scorer utilities | Swap dataset loaders freely |
| Serving (Router) | `theraloop/serving/` | `should_escalate(token_logprobs) -> bool` (+ future: calibrated policy) | Replace routing policy safely |
| Monitor/Telemetry | `theraloop/monitor/` | `log_gepa_step(gen, parents)` | Add charts, drift checks, MLflow params |
| Safety | `theraloop/safety/` | `check_safe(text) -> bool` | Hot-swap classifiers |
| Scripts/CLIs | `scripts/` | `run_gepa.py`, `run_eval.py`, `serve_demo.py` | Tooling; no external contracts |

---

## 2) Dataflows

### 2.1 Train-time (GEPA multi-objective)

```
eval_set (JSONL) ─┬─► GEPA.run(seed)
                  │      ├─ calls→ Adapter.complete_with_logprobs
                  │      ├─ metrics: exact, grounding, logprob
                  │      ├─ Pareto select, reflect mutate
                  │      └─ MLflow: scores, artifacts (best_prompt.txt)
                  └─► outputs/best_prompt.txt
```

### 2.2 Serve-time (confidence-aware)

```
User Q ─► Prompt P* (artifact) ─► Adapter.complete_with_logprobs
                              └─► Router.should_escalate(token_logprobs)
                                   ├─ false → answer
                                   └─ true  → escalate_to_human (or hedge path)
```

---

## 3) Public Interfaces (copy-paste contracts)

Define lightweight protocols (typing-only) to make extension points explicit:

```python
# theraloop/contracts.py
from typing import Protocol, Dict, Any, List

class LMAdapter(Protocol):
    def complete_with_logprobs(self, prompt: str, max_tokens: int = 256, **kw) -> Dict[str, Any]: ...

class MetricExact(Protocol):
    def __call__(self, pred: str, gold: str) -> float: ...

class MetricGrounding(Protocol):
    def __call__(self, pred: str, sources: str) -> float: ...

class MetricLogprob(Protocol):
    def __call__(self, text: str, token_logprobs: List[float], inputs: Dict[str, Any], negatives: List[str] | None = None) -> float: ...

class ReflectFn(Protocol):
    def __call__(self, prompt: str, trace: Dict[str, Any]) -> List[str]: ...
```

**Rule:** only these interfaces are referenced across modules. Internals behind them are free to evolve.

---

## 4) Failure domains & isolation
- **Provider isolation:** all HTTP/SDKs live under `adapters/`. Rate-limits or outages degrade to mock mode (already implemented) → CI remains green.
- **Optimization isolation:** GEPA owns only prompt strings + eval traces. Metric math bugs can't corrupt artifacts; worst case = poor Pareto selection.
- **Serving isolation:** Router is pure over token_logprobs. A bad calibration file only shifts thresholds; escalation path is the safety net.
- **Telemetry isolation:** MLflow failures must never fail the run. Treat logging as best-effort.

---

## 5) SLOs, SLIs, and alerts (initial)
- **SLO-Train:** GEPA run completes ≤ 30 min (smoke runs in CI ≤ 3 min).
- **SLIs:** per-gen latency, adapter success %, eval throughput.
- **Alert:** adapter success % < 95% over 5 min window.
- **SLO-Serve:** p95 /answer latency ≤ 1.5s (provider-dependent), escalation correctness ≥ target after calibration.
- **SLIs:** logprob_sum distribution, escalation rate, safe-block rate.
- **Alert:** escalation rate jumps > +20% vs 7-day baseline or grounding score drops > 15%.

---

## 6) Deployment profiles

### 6.1 Dev
- `.env` with mock fallback; run `scripts/run_gepa.py` (generations=2), `scripts/serve_demo.py`.
- MLflow local tracking URI (file).

### 6.2 Staging
- Real provider key, short GEPA run nightly.
- MLflow to S3/backend store; retain `outputs/best_prompt.txt` artifact.

### 6.3 Production (serving)
- **Proc:** `uvicorn scripts.serve_demo:app --workers=4 --host=0.0.0.0 --port=8080`
- **Config:**
  - `THERALOOP_CONFIDENCE_THRESHOLD` (or calibration file)
  - `SAFE_MODE=1` (if you add log redaction)
- **Artifacts:** deploy `outputs/best_prompt.txt` as configmap/secret or bake into image layer.

**Minimal Dockerfile:**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -U pip && pip install -e .[all]
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "scripts.serve_demo:app", "--host=0.0.0.0", "--port=8080", "--workers=4"]
```

---

## 7) CI/CD & Nightly
- **CI:** unit tests + end-to-end smoke GEPA (mock adapter).
- **Nightly:** short GEPA with real keys (if configured) → publish MLflow links + Pareto plots; fail-open on provider errors.

**Artifacts to keep:**
- `outputs/best_prompt.txt`
- `mlruns/<experiment>/...`
- Optional: `eval_records.jsonl` for threshold calibration.

---

## 8) Observability (what to chart)
- **GEPA evolution:** per-gen scatter of (exact, grounding, logprob); count of nondominated prompts; Δsurprise histogram.
- **Serving quality:** logprob_sum vs correctness (post-hoc adjudication) → calibration curve; router confusion matrix (answer/hedge/escalate).
- **Drift:** weekly trend of mean logprob_sum and grounding score on a fixed canary set.

---

## 9) Security & compliance
- **No PHI by default:** ship with non-clinical demo data; add `SAFE_MODE=1` to disable logging raw texts.
- **Redaction layer in `monitor/`** (future): hash user IDs, strip URLs, mask entities before MLflow.
- **Guardrails:** pluggable classifier in `safety/` gate outputs; route unsafe → escalate.

---

## 10) Extension playbooks (no core edits)

1. **Add a provider**
   - New module `adapters/<provider>.py` implementing `complete_with_logprobs`.
   - No changes elsewhere.

2. **Add a metric**
   - Drop `metrics/new_metric.py` and register in GEPA scoring (or compose a `score_all` helper).
   - Update `pareto_front` caller to include the new axis (or keep 3-axis and log extra metric separately).

3. **Improve reflection**
   - Provide stronger `reflect_fn(prompt, trace)` (web-augmented, TextGrad signals).
   - Update `scripts/run_gepa.py` injection only.

4. **Hedging path**
   - Add `serving/hedge.py` with careful-mode prompt suffix and clarify-question templates; call from `/answer` when hedge policy triggers.

5. **Calibrated routing**
   - Generate `outputs/calibration.json` via `scripts/calibrate_confidence.py`.
   - Replace `should_escalate` with `calibrated_should_escalate(token_logprobs, bins)`.

---

## 11) Backward-compatibility guarantees
- **Artifacts:** `outputs/best_prompt.txt` format is stable (UTF-8 text).
- **Serving API:** `/answer` returns `{answer:str, confidence_logprob_sum:float, escalate:bool}`; additive fields only.
- **Eval schema:** demo JSONL lines keep `{query, gold?, sources?, negatives?[]}`.

---

## 12) Runbooks

### Runbook: training failure (provider 5xx / timeouts)
1. Confirm adapter health: `scripts/run_eval.py` on mock (no key).
2. Re-run with smaller generations or smaller eval set.
3. If provider down: set `TOGETHER_API_KEY` empty → mock mode to verify pipeline code.
4. Capture error logs; file an issue tagged `adapter`.

### Runbook: over-escalation in prod
1. Pull last day's `/answer` logs (counts + sums).
2. Run `scripts/calibrate_confidence.py` on adjudicated records.
3. Update `THERALOOP_CONFIDENCE_THRESHOLD` or deploy new `calibration.json`.
4. Validate against canary set; watch escalation rate SLI for 24h.

### Runbook: grounding regression
1. Compare MLflow `genN/*/grounding` trend.
2. Inspect reflection trace: ensure rules for citations included.
3. Swap `grounding_score` with your preferred checker (RAGAS/entailment).
4. Re-run 2-gen GEPA; promote if Pareto improves.

---

## 13) Roadmap (black-box safe)
- **Metrics:** swap heuristic grounding → RAGAS / entailment (no GEPA contract change).
- **Router:** move from threshold to calibrated curve; add "hedge" mode.
- **Safety:** plug Granite Guardian in `safety/` pre/post.
- **Observability:** add calibration plots; publish Pareto/Δsurprise to GH Pages.
- **Providers:** add OpenRouter/OpenAI adapters with logprobs scoring where available.

---

## 14) Ownership map (single person per module)
- `adapters/*` — Provider Engineer
- `metrics/*` — Evaluation/Quality Engineer
- `optim/*` — Optimization Engineer
- `serving/*` — Platform/Inference Engineer
- `monitor/*` — Observability Engineer
- `safety/*` — Policy/Safety Engineer
- `scripts/*` — Tooling/Release Engineer

Each owner can ship independently as long as module contracts above remain stable.

---

## Appendix A — ASCII diagram

```
                    ┌────────────────────────────────┐
                    │          GEPA Core             │
                    │ (pareto, reflect, evaluate)    │
                    └──────────────┬─────────────────┘
                                   │
                        LMAdapter.complete_with_logprobs
                                   │
                ┌──────────────────┴──────────────────┐
                │                                     │
         ┌──────▼───────┐                     ┌───────▼───────┐
         │  Metrics     │                     │  Monitor      │
         │ exact,ground │                     │ MLflow, drift │
         └──────┬───────┘                     └───────┬───────┘
                │                                       │
                └───────────────┬───────────────────────┘
                                │
                           outputs/
                           best_prompt.txt
                                │
                                ▼
                        ┌───────────────┐
                        │   Serving     │
                        │  Router (LP)  │
                        └───────┬───────┘
                                │
                                ▼
                           Escalate/Answer
```