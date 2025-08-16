from typing import List, Tuple

def dominates(a: Tuple[float, ...], b: Tuple[float, ...]) -> bool:
    return all(x >= y for x, y in zip(a, b)) and any(x > y for x, y in zip(a, b))

def pareto_front(points: List[Tuple[float, ...]]) -> List[int]:
    front = []
    for i, p in enumerate(points):
        if not any(dominates(points[j], p) for j in range(len(points)) if j != i):
            front.append(i)
    return front
