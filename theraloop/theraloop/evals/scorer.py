from typing import Dict, Any
from ..metrics.exact import exact_match
from ..metrics.grounding import grounding_score
from ..metrics.logprob import logprob_metric

def score_case(out: Dict[str,Any], ex: Dict[str,Any]) -> Dict[str,float]:
    em = exact_match(out.get("text",""), ex.get("gold",""))
    grd = grounding_score(out.get("text",""), ex.get("sources",""))
    lp = logprob_metric(out.get("text",""), out.get("token_logprobs",[]), ex, ex.get("negatives"))
    return {"exact": em, "grounding": grd, "logprob": lp}
