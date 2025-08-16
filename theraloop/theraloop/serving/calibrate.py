from typing import List, Tuple
from ..metrics.util import safe_sum

def best_threshold(pairs: List[Tuple[List[float], bool]]) -> float:
    # pairs: [(token_logprobs, is_correct)]
    # Simple sweep over candidate sums
    sums = [safe_sum(xs) for xs, _ in pairs]
    if not sums:
        return -50.0
    candidates = sorted(set(sums))
    best_thr, best_acc = None, -1.0
    for t in candidates:
        tp = sum(1 for s,(xs,ok) in zip(sums,pairs) if (s>=t and ok))
        tn = sum(1 for s,(xs,ok) in zip(sums,pairs) if (s<t and not ok))
        fp = sum(1 for s,(xs,ok) in zip(sums,pairs) if (s>=t and not ok))
        fn = sum(1 for s,(xs,ok) in zip(sums,pairs) if (s<t and ok))
        acc = (tp+tn)/max(1,len(pairs))
        if acc > best_acc:
            best_acc, best_thr = acc, t
    return float(best_thr)
