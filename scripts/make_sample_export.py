"""Produce samples/run_export.json (clean run) and samples/run_export_validation_case.json
(fault injection + broken PDFs) using the deterministic mock LLM.

Usage: python scripts/make_sample_export.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from agents.orchestrator import run_evaluation  # noqa: E402
from db import database  # noqa: E402
from domain.models import SupplierInput  # noqa: E402
from llm.client import build_client  # noqa: E402

SAMPLES = [
    ("Apex Systems", "apex_systems_proposal.pdf", "2026-10-05", 4.5),
    ("BrightPath Tech", "brightpath_tech_proposal.pdf", "2026-10-02", 2.0),
    ("NexaWorks", "nexaworks_proposal.pdf", "2026-10-04", 4.0),
    ("Orbit Digital", "orbit_digital_proposal.pdf", "2026-10-06", 5.0),
    ("Zenith Consulting", "zenith_consulting_proposal.pdf", "2026-10-06", 3.5),
]
EDGE = [("Corrupt Upload Ltd", "edge_cases/corrupt_file.pdf", "2026-10-07", 3.0),
        ("Scanned Docs Inc", "edge_cases/scanned_no_text.pdf", "2026-10-07", 3.0)]


def _suppliers(rows):
    return [SupplierInput(supplier_name=n, submission_date=date.fromisoformat(d), experience_rating=e,
                          file_name=Path(f).name, file_bytes=(config.SAMPLE_DIR / f).read_bytes())
            for n, f, d, e in rows]


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "samples"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "sample.db"
        database.init_db(db)
        clean = run_evaluation(_suppliers(SAMPLES), build_client("Mock (no API key)"), db_path=db)
        faulty = run_evaluation(_suppliers(SAMPLES + EDGE),
                                build_client("Mock (no API key)", fault_target="Apex Systems"), db_path=db)
    (out / "run_export.json").write_text(json.dumps(clean, indent=2))
    (out / "run_export_validation_case.json").write_text(json.dumps(faulty, indent=2))
    for name, r in (("run_export.json", clean), ("run_export_validation_case.json", faulty)):
        print(f"{name}: {r['rfp_run_id']} {r['status']} winner={r['suppliers'][0]['supplier_name']} "
              f"warnings={len(r['warnings'])}")


if __name__ == "__main__":
    main()
