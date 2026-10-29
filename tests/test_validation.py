import json

from tools.validation_tool import coerce_score, evidence_in_document, parse_llm_json, validate_scorecard

DOC = ("Apex Systems holds ISO/IEC 27001:2022 certification. Data is encrypted at rest using AES-256 "
       "and in transit using TLS 1.3.")


def good_raw(criteria, score=7):
    return {"supplier_name": "Apex", "criteria": [
        {"criterion_id": c["criterion_id"], "score": score, "max_score": 10, "justification": "ok",
         "evidence": "Data is encrypted at rest using AES-256"} for c in criteria],
        "risks": ["r1"], "overall_summary": "s"}


def test_parse_plain_fenced_and_prose():
    obj = {"a": 1}
    assert parse_llm_json(json.dumps(obj))[0] == obj
    assert parse_llm_json("```json\n" + json.dumps(obj) + "\n```")[0] == obj
    assert parse_llm_json("Here you go: " + json.dumps(obj) + " thanks")[0] == obj


def test_parse_failures():
    assert parse_llm_json("")[0] is None
    assert parse_llm_json("{not json")[0] is None
    assert parse_llm_json("[1, 2]")[0] is None


def test_clean_scorecard_passes_unchanged(criteria):
    card = validate_scorecard(good_raw(criteria), criteria, "Apex", DOC)
    assert card.llm_status == "ok" and not card.low_confidence
    assert all(c.score == 7 and not c.normalized and c.evidence_verified for c in card.criteria)
    assert card.warnings == []


def test_missing_criterion_filled_with_zero(criteria):
    raw = good_raw(criteria)
    raw["criteria"] = raw["criteria"][:-1]
    card = validate_scorecard(raw, criteria, "Apex", DOC)
    last = card.criteria[-1]
    assert last.score == 0 and last.normalized
    assert any("missing" in w for w in card.warnings)
    assert card.llm_status == "repaired"


def test_out_of_range_scores_clipped(criteria):
    raw = good_raw(criteria)
    raw["criteria"][0]["score"] = 14
    raw["criteria"][1]["score"] = -3
    card = validate_scorecard(raw, criteria, "Apex", DOC)
    assert card.criteria[0].score == 10 and card.criteria[1].score == 0
    assert sum("clipped" in w for w in card.warnings) == 2


def test_text_scores_coerced(criteria):
    raw = good_raw(criteria)
    raw["criteria"][0]["score"] = "8/10"
    raw["criteria"][1]["score"] = "4/5"
    raw["criteria"][2]["score"] = "excellent"
    card = validate_scorecard(raw, criteria, "Apex", DOC)
    assert [c.score for c in card.criteria[:3]] == [8, 8, 0]
    assert card.criteria[0].normalized is False      # same scale, just parsed
    assert card.criteria[1].normalized is True       # rescaled
    assert card.criteria[2].normalized is True       # unusable -> 0


def test_unknown_and_duplicate_ids_dropped(criteria):
    raw = good_raw(criteria)
    raw["criteria"].append({"criterion_id": 99, "score": 10})
    raw["criteria"].append(dict(raw["criteria"][0], score=1))
    card = validate_scorecard(raw, criteria, "Apex", DOC)
    assert len(card.criteria) == len(criteria)
    assert card.criteria[0].score == 7
    assert any("99" in w for w in card.warnings) and any("Duplicate" in w for w in card.warnings)


def test_failed_llm_gives_low_confidence_zeros(criteria):
    card = validate_scorecard(None, criteria, "Apex", DOC, llm_status="failed")
    assert all(c.score == 0 for c in card.criteria)
    assert card.low_confidence and card.llm_status == "failed"


def test_uses_database_max_score(criteria):
    criteria[0]["max_score"] = 5
    raw = good_raw(criteria, score=7)
    card = validate_scorecard(raw, criteria, "Apex", DOC)
    assert card.criteria[0].score == 5 and card.criteria[0].max_score == 5


def test_evidence_verification():
    assert evidence_in_document("data is encrypted at   rest using AES-256", DOC)
    assert evidence_in_document("Apex Systems holds ISO/IEC 27001:2022 ... encrypted at rest using AES-256", DOC)
    assert not evidence_in_document("We guarantee a 70% cost reduction in year one.", DOC)
    assert not evidence_in_document("", DOC)


def test_coerce_rejects_bools_and_nan():
    assert coerce_score(True, 10)[0] is None
    assert coerce_score(float("nan"), 10)[0] is None
    assert coerce_score(None, 10)[0] is None
