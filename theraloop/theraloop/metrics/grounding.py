def grounding_score(pred: str, sources: str) -> float:
    # Simple lexical overlap proxy (0..1)
    pred_l = (pred or "").lower()
    src_l = (sources or "").lower()
    if not src_l:
        return 0.0
    hits = 0
    for token in set(src_l.split()):
        if token and token in pred_l:
            hits += 1
    denom = max(1, len(set(src_l.split())))
    return hits / denom
