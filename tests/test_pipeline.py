"""End-to-end tests: PDFs -> mock LLM -> validation -> ranking -> SQLite."""
from datetime import date
from pathlib import Path

import pytest

import config
from agents.orchestrator import RunAborted, run_evaluation, validate_inputs
from db import database
from domain.models import SupplierInput
from llm.client import LLMError, build_client
from tools.pdf_tool import extract_text

SAMPLES = [
    ("Apex Systems", "apex_systems_proposal.pdf", "2026-10-05", 4.5),
    ("BrightPath Tech", "brightpath_tech_proposal.pdf", "2026-10-02", 2.0),
    ("NexaWorks", "nexaworks_proposal.pdf", "2026-10-04", 4.0),
    ("Orbit Digital", "orbit_digital_proposal.pdf", "2026-10-06", 5.0),
    ("Zenith Consulting", "zenith_consulting_proposal.pdf", "2026-10-06", 3.5),
]


def suppliers(extra=()):
    rows = list(SAMPLES) + list(extra)
    return [SupplierInput(supplier_name=n, submission_date=date.fromisoformat(d), experience_rating=e,
                          file_name=Path(f).name, file_bytes=(config.SAMPLE_DIR / f).read_bytes())
            for n, f, d, e in rows]


def test_sample_pdfs_extract():
    for _, f, _, _ in SAMPLES:
        res = extract_text((config.SAMPLE_DIR / f).read_bytes(), f)
        assert res.ok and 2 <= res.pages <= 4 and res.chars > 2000


def test_broken_pdfs_rejected_cleanly():
    corrupt = extract_text((config.SAMPLE_DIR / "edge_cases/corrupt_file.pdf").read_bytes(), "c.pdf")
    scanned = extract_text((config.SAMPLE_DIR / "edge_cases/scanned_no_text.pdf").read_bytes(), "s.pdf")
    empty = extract_text(b"", "e.pdf")
    assert not corrupt.ok and "not a readable PDF" in corrupt.error
    assert not scanned.ok and "scanned" in scanned.error
    assert not empty.ok


def test_full_run_is_persisted_and_deterministic(db_path):
    client = build_client("Mock (no API key)")
    r1 = run_evaluation(suppliers(), client, db_path=db_path)
    r2 = run_evaluation(suppliers(), client, db_path=db_path)
    order = [(s["supplier_name"], s["absolute_score"], s["ppi"], s["final_rank"]) for s in r1["suppliers"]]
    assert order == [(s["supplier_name"], s["absolute_score"], s["ppi"], s["final_rank"]) for s in r2["suppliers"]]
    assert r1["status"] == "COMPLETED"
    # Orbit and Zenith are a deliberate tie on PPI and date; experience decides
    names = [s["supplier_name"] for s in r1["suppliers"]]
    assert names.index("Orbit Digital") + 1 == names.index("Zenith Consulting")
    assert any("experience rating" in line for line in r1["tie_break_explanation"])
    # persisted
    loaded = database.load_run(r1["rfp_run_id"], db_path)
    assert loaded["suppliers"] == r1["suppliers"]
    runs = database.list_runs(db_path=db_path)
    assert {r["rfp_run_id"] for r in runs} == {r1["rfp_run_id"], r2["rfp_run_id"]}
    with database.connect(db_path) as conn:
        n = conn.execute("SELECT COUNT(*) FROM criterion_assessments WHERE rfp_run_id=?",
                         (r1["rfp_run_id"],)).fetchone()[0]
    assert n == 5 * 5


def test_fault_injection_and_unreadable_pdfs(db_path):
    extra = [("Broken Co", "edge_cases/corrupt_file.pdf", "2026-10-07", 3.0)]
    client = build_client("Mock (no API key)", fault_target="Apex Systems")
    r = run_evaluation(suppliers(extra), client, db_path=db_path)
    assert r["status"] == "COMPLETED_WITH_WARNINGS"
    apex = next(s for s in r["suppliers"] if s["supplier_name"] == "Apex Systems")
    broken = next(s for s in r["suppliers"] if s["supplier_name"] == "Broken Co")
    assert apex["llm_status"] == "repaired" and apex["low_confidence"]
    assert all(c["score"] <= c["max_score"] for c in apex["criteria"])
    assert broken["llm_status"] == "skipped_no_text" and broken["absolute_score"] == 0
    assert broken["final_rank"] == len(r["suppliers"])
    text = " ".join(r["warnings"])
    for expected in ("not valid JSON", "clipped", "unknown", "missing", "not a readable PDF"):
        assert expected in text


def test_weights_must_total_100(db_path):
    rows = database.get_criteria(active_only=False, db_path=db_path)
    rows[0]["weight"] = 40
    database.save_criteria(rows, db_path)
    with pytest.raises(RunAborted) as exc:
        run_evaluation(suppliers(), build_client("Mock (no API key)"), db_path=db_path)
    assert "must total 100%" in str(exc.value)


def test_deactivated_criterion_is_excluded(db_path):
    rows = database.get_criteria(active_only=False, db_path=db_path)
    rows[4]["is_active"] = 0          # drop Support (10%)
    rows[0]["weight"] = 40            # Technical 30 -> 40 keeps total at 100
    database.save_criteria(rows, db_path)
    r = run_evaluation(suppliers(), build_client("Mock (no API key)"), db_path=db_path)
    assert all(len(s["criteria"]) == 4 for s in r["suppliers"])
    assert 5 not in {c["criterion_id"] for c in r["criteria"]}


def test_input_validation_messages():
    s = suppliers()
    s[1].supplier_name = "apex systems"         # duplicate (case-insensitive)
    s[2].supplier_name = " "
    s[3].experience_rating = 9
    errors = " ".join(validate_inputs(s))
    assert "already used" in errors and "required" in errors and "between" in errors


def test_real_provider_requires_key():
    with pytest.raises(LLMError):
        build_client("OpenAI", api_key="")
