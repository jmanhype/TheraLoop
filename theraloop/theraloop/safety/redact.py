
from __future__ import annotations
"""
PII/PHI redaction utilities.
Uses Presidio if available; falls back to regex heuristics.
"""
import re
from typing import Dict, Any, List, Tuple

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
NAME_RE = re.compile(r"\b([A-Z][a-z]+\s[A-Z][a-z]+)\b")

REDACTION_TOKEN = "[REDACTED]"

def _heuristic_detect(text: str) -> List[Tuple[str, str]]:
    findings = []
    for label, rx in (("EMAIL", EMAIL_RE), ("PHONE", PHONE_RE), ("SSN", SSN_RE), ("IP", IP_RE)):
        for m in rx.finditer(text or ""):
            findings.append((label, m.group(0)))
    for m in NAME_RE.finditer(text or ""):
        span = m.group(0)
        pre = (text[max(0, m.start()-10):m.start()] or "").lower()
        if "name is" in pre or "i'm" in pre:
            findings.append(("PERSON", span))
    seen = set(); uniq = []
    for lab,val in findings:
        if (lab,val) in seen: continue
        seen.add((lab,val)); uniq.append((lab,val))
    return uniq

def redact_text(text: str, use_presidio: bool = True) -> Dict[str, Any]:
    if not text:
        return {"text": text, "entities": [], "count": 0, "engine": "none"}
    if use_presidio:
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
            analyzer = AnalyzerEngine()
            anonymizer = AnonymizerEngine()
            res = analyzer.analyze(text=text, entities=None, language="en")
            if res:
                red = anonymizer.anonymize(
                    text=text,
                    analyzer_results=res,
                    anonymizers_config={r.entity_type: {"type":"replace","new_value":REDACTION_TOKEN} for r in res}
                )
                entities = [{"label": r.entity_type, "value": text[r.start:r.end]} for r in res]
                return {"text": red.text, "entities": entities, "count": len(res), "engine": "presidio"}
        except Exception:
            pass
    findings = _heuristic_detect(text)
    red = text
    for _, val in sorted(findings, key=lambda x: -len(x[1])):
        red = red.replace(val, REDACTION_TOKEN)
    entities = [{"label": lab, "value": val} for lab,val in findings]
    return {"text": red, "entities": entities, "count": len(findings), "engine": "heuristic"}
