import sys, os, json
from theraloop.adapters.together import complete_with_logprobs
from theraloop.evals.scorer import score_case

if __name__ == "__main__":
    prompt_path = sys.argv[1] if len(sys.argv)>1 else "outputs/best_prompt.txt"
    prompt = open(prompt_path).read() if os.path.exists(prompt_path) else "Be concise."
    eval_set = [json.loads(l) for l in open("theraloop/evals/datasets/mental_health.jsonl")]
    scores = []
    for ex in eval_set:
        out = complete_with_logprobs(f"{prompt}\n\nTask:\n{ex['query']}\nReturn only the answer.", max_tokens=128)
        sc = score_case(out, ex)
        scores.append(sc)
        print(json.dumps({"query":ex["query"],"out":out,"score":sc}))
    agg = {k: sum(s[k] for s in scores)/len(scores) for k in scores[0].keys()}
    print("AVG:", agg)
