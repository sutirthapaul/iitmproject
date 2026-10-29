"""Validation Tool.

Turns whatever the LLM returned into a complete, in-range scorecard:
  * parses JSON (tolerates code fences / leading prose)
  * keeps exactly one result per *active* criterion (drops unknown ids and duplicates)
  * coerces non-numeric scores ("8/10", "7.5") and clips out-of-range values
  * fills missing criteria with score 0
  * checks that cited evidence actually appears in the supplier document
Every change is recorded as a warning so the final score stays explainable.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

import config
from domain.models import ValidatedCriterion, ValidatedScorecard

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)
_SCORE_STR = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(?:/\s*(\d+(?:\.\d+)?))?")


# --------------------------------------------------------------------------- JSON parsing
def parse_llm_json(raw: str | None) -> tuple[dict | None, str | None]:
    """Return (object, None) on success or (None, error_message)."""
    if raw is None or not str(raw).strip():
        return None, "Empty response from model."
    text = _FENCE.sub("", str(raw).strip()).strip()
    for candidate in (text, _outer_braces(text)):
        if not candidate:
            continue
        try:
            obj = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            return obj, None
        return None, f"Model returned JSON {type(obj).__name__}, expected an object."
    return None, "Response is not valid JSON."


def _outer_braces(text: str) -> str | None:
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if 0 <= start < end else None


# --------------------------------------------------------------------------- score coercion
def coerce_score(value: Any, max_score: int) -> tuple[float | None, str | None]:
    """Return (score, note). score None means unusable."""
    if isinstance(value, bool) or value is None:
        return None, f"score {value!r} is not numeric"
    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return None, f"score {value!r} is not a finite number"
        return float(value), None
    if isinstance(value, str):
        m = _SCORE_STR.match(value)
        if not m:
            return None, f"score {value!r} is not numeric"
        num = float(m.group(1))
        if m.group(2):
            denom = float(m.group(2))
            if denom <= 0:
                return None, f"score {value!r} has an invalid denominator"
            if denom != max_score:
                return num / denom * max_score, f"score {value!r} rescaled to a {max_score}-point scale"
            return num, f"score {value!r} parsed from text"
        return num, f"score {value!r} parsed from text"
    return None, f"score of type {type(value).__name__} is not numeric"


# --------------------------------------------------------------------------- evidence check
def _norm(s: str) -> str:
    s = s.lower()
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def evidence_in_document(evidence: str, document: str) -> bool:
    """True if the quoted evidence can be found in the document (whitespace/quote tolerant)."""
    ev = _norm(evidence).strip(" \"'")
    if len(ev) < 8:
        return False
    doc = _norm(document)
    if ev in doc:
        return True
    fragments = [f.strip(" \"'.,;") for f in re.split(r"\.\.\.|…", ev)]
    fragments = [f for f in fragments if len(f) >= 15]
    if fragments and all(f in doc for f in fragments):
        return True
    words = ev.split()
    if len(words) < 6:
        return False
    grams = [" ".join(words[i:i + 6]) for i in range(len(words) - 5)]
    return sum(g in doc for g in grams) / len(grams) >= 0.7


# --------------------------------------------------------------------------- main entry point
def validate_scorecard(raw: dict | None, criteria: list[dict], supplier_name: str,
                       document_text: str = "", llm_status: str = "ok",
                       upstream_warnings: list[str] | None = None) -> ValidatedScorecard:
    warnings: list[str] = list(upstream_warnings or [])
    tag = f"[{supplier_name}]"
    by_id = {int(c["criterion_id"]): c for c in criteria}

    if raw is None:
        raw = {}
        if llm_status not in ("skipped_no_text",):
            llm_status = "failed"

    returned_name = raw.get("supplier_name")
    if returned_name and str(returned_name).strip().casefold() != supplier_name.casefold():
        warnings.append(f"{tag} Model returned supplier_name {returned_name!r}; using the entered name.")

    items = raw.get("criteria", [])
    if not isinstance(items, list):
        warnings.append(f"{tag} 'criteria' is not a list; treating all criteria as missing.")
        items = []

    accepted: dict[int, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            warnings.append(f"{tag} Ignored a criteria entry that is not an object.")
            continue
        try:
            cid = int(item.get("criterion_id"))
        except (TypeError, ValueError):
            warnings.append(f"{tag} Ignored entry with invalid criterion_id {item.get('criterion_id')!r}.")
            continue
        if cid not in by_id:
            warnings.append(f"{tag} Ignored unknown or inactive criterion_id {cid}.")
            continue
        if cid in accepted:
            warnings.append(f"{tag} Duplicate result for criterion {cid}; kept the first.")
            continue
        accepted[cid] = item

    results: list[ValidatedCriterion] = []
    for cid, crit in by_id.items():
        max_score = int(crit["max_score"])
        name = crit["name"]
        notes: list[str] = []
        item = accepted.get(cid)

        if item is None:
            reason = "no model output" if llm_status in ("failed", "skipped_no_text") else "missing from model output"
            notes.append(f"{reason}; score set to 0")
            results.append(ValidatedCriterion(
                criterion_id=cid, name=name, weight=float(crit["weight"]), max_score=max_score, score=0.0,
                justification=f"Not assessed ({reason}).", evidence="", normalized=True, notes=notes))
            warnings.append(f"{tag} {name}: {reason}; score set to 0.")
            continue

        changed = False
        score, note = coerce_score(item.get("score"), max_score)
        if note:
            notes.append(note)
            changed = "rescaled" in note
        if score is None:
            score = 0.0
            notes.append("score set to 0")
            changed = True
        if score < 0 or score > max_score:
            clipped = min(max(score, 0.0), float(max_score))
            notes.append(f"score {score:g} clipped to {clipped:g} (range 0-{max_score})")
            score = clipped
            changed = True
        score = round(score, 1)

        model_max = item.get("max_score")
        if model_max is not None and str(model_max) != str(max_score):
            notes.append(f"model used max_score {model_max!r}; database value {max_score} applied")

        justification = str(item.get("justification") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        if not justification:
            notes.append("justification missing")
            justification = "No justification provided by the model."
        verified = bool(evidence) and evidence_in_document(evidence, document_text)
        if not evidence:
            notes.append("no evidence cited")
        elif not verified:
            notes.append("evidence could not be found verbatim in the document")

        # Only changes to the score itself count as normalisation; evidence notes are informational.
        normalized = changed
        for n in notes:
            warnings.append(f"{tag} {name}: {n}.")
        results.append(ValidatedCriterion(
            criterion_id=cid, name=name, weight=float(crit["weight"]), max_score=max_score, score=score,
            justification=justification, evidence=evidence, evidence_verified=verified,
            normalized=normalized, notes=notes))

    risks = raw.get("risks", [])
    if not isinstance(risks, list):
        risks = [str(risks)] if risks else []
    risks = [str(r).strip() for r in risks if str(r).strip()]
    summary = str(raw.get("overall_summary") or "").strip()

    normalized_count = sum(r.normalized for r in results)
    low_conf = bool(results) and normalized_count / len(results) > config.LOW_CONFIDENCE_THRESHOLD
    if low_conf:
        warnings.append(f"{tag} Low-confidence scorecard: {normalized_count} of {len(results)} criteria "
                        "had to be normalised.")
    if normalized_count and llm_status == "ok":
        llm_status = "repaired"

    return ValidatedScorecard(
        supplier_name=supplier_name, criteria=results, risks=risks, overall_summary=summary,
        warnings=warnings, llm_status=llm_status, low_confidence=low_conf)
