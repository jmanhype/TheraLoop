import os, json
from theraloop.serving.calibrate import best_threshold

# expects a file 'outputs/eval_records.jsonl' with lines:
# {"token_logprobs":[...], "correct": true/false}
in_path = "outputs/eval_records.jsonl"
out_path = os.getenv("THERALOOP_CALIBRATION_FILE","outputs/calibration.json")

pairs = []
if os.path.exists(in_path):
    for l in open(in_path):
        r = json.loads(l)
        pairs.append((r.get("token_logprobs",[]), bool(r.get("correct", False))))
thr = best_threshold(pairs) if pairs else -50.0
os.makedirs(os.path.dirname(out_path), exist_ok=True)
json.dump({"threshold": thr}, open(out_path,"w"))
print("Saved", out_path, "->", thr)
