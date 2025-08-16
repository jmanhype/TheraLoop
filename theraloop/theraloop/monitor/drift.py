# Placeholder for logprob drift / surprise deltas over time.
def surprise_delta(curr_lp_mean: float, prev_lp_mean: float) -> float:
    return float(curr_lp_mean - prev_lp_mean)
