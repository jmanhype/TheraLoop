import os, json, argparse, mlflow
from theraloop.optim.gepa_pipeline import GEPA
from theraloop.adapters.together import complete_with_logprobs

def call_fn(prompt, item, model=None):
    text = f"{prompt}\n\nTask:\n{item['query']}\nReturn only the answer."
    out = complete_with_logprobs(text, max_tokens=128, model=model or os.getenv("THERALOOP_MODEL"))
    return out

def reflect_fn(prompt, trace):
    failures = []
    for c in trace.get("cases", []):
        txt = (c["out"].get("text","") or "").strip()
        gold = (c["ex"].get("gold","") or "").strip()
        if gold and gold != txt:
            failures.append(f"- Prefer exact string: `{gold}` when unambiguous.")
    rules = "\n".join(sorted(set(failures))) or "- Keep successes; tighten formatting."
    mutated = f"{prompt}\n\nRefinements:\n{rules}\n"
    return [mutated]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--generations", type=int, default=2)
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    eval_set = [json.loads(l) for l in open("theraloop/evals/datasets/demo.jsonl")]
    seed = "You are a careful, citation-aware assistant. Answer exactly; if unsure, say 'insufficient evidence'."
    mlflow.set_experiment(os.getenv("THERALOOP_EXPERIMENT", "theraloop"))
    os.makedirs("outputs", exist_ok=True)
    with mlflow.start_run(run_name="gepa-demo"):
        champ = GEPA(eval_set, reflect_fn, lambda p,it: call_fn(p,it,args.model), generations=args.generations).run(seed)
        open("outputs/best_prompt.txt","w").write(champ)
        mlflow.log_artifact("outputs/best_prompt.txt")
        print("Champion prompt saved to outputs/best_prompt.txt")
