def safe_sum(xs):
    s = 0.0
    for v in xs or []:
        try:
            s += float(v)
        except Exception:
            pass
    return s
