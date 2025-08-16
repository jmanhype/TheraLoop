import os, json
from typing import List, Dict, Tuple, Callable
from .pareto import pareto_front
from ..metrics.exact import exact_match
from ..metrics.grounding import grounding_score
from ..metrics.logprob import logprob_metric
from ..monitor.mlflow_log import log_gepa_step

class GEPA:
    def __init__(self, eval_set: List[Dict], reflect_fn: Callable, call_fn: Callable,
                 pop=8, children=2, generations=3):
        self.eval_set = eval_set
        self.reflect_fn = reflect_fn
        self.call_fn = call_fn
        self.pop, self.children, self.generations = pop, children, generations
        self.pool = []

    def score_prompt(self, prompt: str):
        results = []
        for ex in self.eval_set:
            out = self.call_fn(prompt, ex)
            em = exact_match(out.get("text",""), ex.get("gold",""))
            grd = grounding_score(out.get("text",""), ex.get("sources",""))
            lp = logprob_metric(out.get("text",""), out.get("token_logprobs",[]), ex, ex.get("negatives"))
            results.append((em, grd, lp, out))
        n = max(1, len(results))
        avg = tuple(sum(r[i] for r in results)/n for i in range(3))
        traces = {"cases":[{"ex":e,"out":o[3]} for e,o in zip(self.eval_set, results)]}
        return avg[0], avg[1], avg[2], traces

    def run(self, seed_prompt: str) -> str:
        self.pool = [{"prompt": seed_prompt, "score": None, "trace": None}]
        for g in range(self.generations):
            for p in self.pool:
                if p["score"] is None:
                    em, grd, lp, trace = self.score_prompt(p["prompt"])
                    p["score"] = (em, grd, lp); p["trace"] = trace
            scores = [p["score"] for p in self.pool]
            front_idx = pareto_front(scores)
            parents = [self.pool[i] for i in front_idx]

            log_gepa_step(g, parents)

            children = []
            for par in parents:
                muts = self.reflect_fn(par["prompt"], par["trace"]) or []
                for m in muts[:self.children]:
                    children.append({"prompt": m, "score": None, "trace": None})
            self.pool = parents + children

        champ = max(self.pool, key=lambda p: (p["score"][0], p["score"][1], p["score"][2]))
        return champ["prompt"]
