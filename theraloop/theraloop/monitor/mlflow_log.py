import mlflow

def log_gepa_step(gen, parents):
    for i, p in enumerate(parents):
        em, grd, lp = p["score"]
        mlflow.log_metric(f"gen{gen}/parent{i}/exact", float(em))
        mlflow.log_metric(f"gen{gen}/parent{i}/grounding", float(grd))
        mlflow.log_metric(f"gen{gen}/parent{i}/logprob", float(lp))
