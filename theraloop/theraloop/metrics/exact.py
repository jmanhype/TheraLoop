def exact_match(pred: str, gold: str) -> float:
    pred = (pred or "").strip()
    gold = (gold or "").strip()
    return 1.0 if pred == gold else 0.0
