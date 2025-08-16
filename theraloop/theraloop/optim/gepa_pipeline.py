import os, json
from typing import List, Dict, Tuple, Callable, Set
from .pareto import pareto_front
from ..metrics.exact import exact_match
from ..metrics.grounding import grounding_score
from ..metrics.logprob import logprob_metric
from ..monitor.mlflow_log import log_gepa_step

class GEPA:
    def __init__(
        self,
        eval_set: List[Dict],
        reflect_fn: Callable,   # (prompt:str, trace:dict) -> List[str]
        call_fn: Callable,      # (prompt:str, ex:dict) -> {"text":..., "token_logprobs":[...], ...}
        pop: int = 8,
        children: int = 2,
        generations: int = 3,
        cap_pool: int | None = None,   # optional hard cap on pool size
    ):
        self.eval_set = eval_set
        self.reflect_fn = reflect_fn
        self.call_fn = call_fn
        self.pop = max(1, pop)
        self.children = max(0, children)
        self.generations = max(1, generations)
        self.cap_pool = cap_pool or (self.pop * 2)  # reasonable default
        self.pool: List[Dict] = []                  # [{prompt, score, trace}]

    def _score_prompt(self, prompt: str):
        results = []
        for ex in self.eval_set:
            out = self.call_fn(prompt, ex)
            em = exact_match(out.get("text", ""), ex.get("gold", ""))
            grd = grounding_score(out.get("text", ""), ex.get("sources", ""))
            lp = logprob_metric(out.get("text", ""), out.get("token_logprobs", []), ex, ex.get("negatives"))
            results.append((em, grd, lp, out))
        n = max(1, len(results))
        avg = tuple(sum(r[i] for r in results) / n for i in range(3))
        traces = {"cases": [{"ex": e, "out": o[3]} for e, o in zip(self.eval_set, results)]}
        return (avg[0], avg[1], avg[2]), traces

    def _score_pending(self):
        """Score any pool items with score=None (in-place)."""
        for p in self.pool:
            if p["score"] is None:
                avg, trace = self._score_prompt(p["prompt"])
                p["score"], p["trace"] = avg, trace

    def _dedupe_and_cap(self):
        """Remove duplicate prompts, keep first occurrence, and cap pool size."""
        seen: Set[str] = set()
        deduped = []
        for p in self.pool:
            key = p["prompt"]
            if key not in seen:
                seen.add(key)
                deduped.append(p)
        # Prefer keeping already-scored entries when capping
        deduped.sort(key=lambda x: (x["score"] is None, ), reverse=False)
        self.pool = deduped[: self.cap_pool]

    def run(self, seed_prompt: str) -> str:
        # Initialize population with the seed and (optionally) its simple variants
        self.pool = [{"prompt": seed_prompt, "score": None, "trace": None}]

        for g in range(self.generations):
            # 1) Ensure everything currently in the pool is scored
            self._score_pending()

            # 2) Select Pareto front among scored candidates
            scores = [p["score"] for p in self.pool]
            front_idx = pareto_front(scores)
            parents = [self.pool[i] for i in front_idx]

            # 3) Log the generation front
            log_gepa_step(g, parents)

            # 4) Generate children (except on the final generation)
            if g < self.generations - 1 and self.children > 0:
                children = []
                for par in parents:
                    muts = self.reflect_fn(par["prompt"], par["trace"]) or []
                    for m in muts[: self.children]:
                        children.append({"prompt": m, "score": None, "trace": None})

                # Reseed population: keep parents, add children, then dedupe/cap
                self.pool = parents + children
                self._dedupe_and_cap()
            else:
                # Final generation: keep only the Pareto parents; no new children
                self.pool = parents
                self._dedupe_and_cap()

        # After the loop, guarantee no None scores remain (safety net)
        self._score_pending()

        # Champion selection (lexicographic: EM, Grounding, Logprob)
        champ = max(self.pool, key=lambda p: (p["score"][0], p["score"][1], p["score"][2]))
        return champ["prompt"]