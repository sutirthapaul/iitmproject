"""SQLite persistence layer. The only module that writes SQL."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import config

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

DEFAULT_CRITERIA = [
    (1, "Technical Capability",
     "Architecture, integrations, scalability and technical fit with the requirement.", 30, 10),
    (2, "Implementation Plan",
     "Timeline, milestones, staffing, delivery approach and risk plan.", 20, 10),
    (3, "Commercial Value",
     "Pricing clarity, total cost of ownership, assumptions and value for money.", 20, 10),
    (4, "Security & Compliance",
     "Security controls, certifications, data privacy and auditability.", 20, 10),
    (5, "Support & Experience",
     "Support model, SLAs, similar past projects and client references.", 10, 10),
]


@contextmanager
def connect(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------- setup
def init_db(db_path: Path | str | None = None) -> None:
    """Create tables and seed default criteria if the table is empty. Idempotent."""
    with connect(db_path) as conn:
        conn.executescript(SCHEMA_PATH.read_text())
        count = conn.execute("SELECT COUNT(*) FROM evaluation_criteria").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO evaluation_criteria (criterion_id, name, description, weight, max_score, is_active) "
                "VALUES (?, ?, ?, ?, ?, 1)",
                DEFAULT_CRITERIA,
            )


def reset_criteria(db_path: Path | str | None = None) -> None:
    with connect(db_path) as conn:
        conn.execute("DELETE FROM evaluation_criteria")
        conn.executemany(
            "INSERT INTO evaluation_criteria (criterion_id, name, description, weight, max_score, is_active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            DEFAULT_CRITERIA,
        )


# ---------------------------------------------------------------- criteria
def get_criteria(active_only: bool = True, db_path: Path | str | None = None) -> list[dict]:
    sql = "SELECT * FROM evaluation_criteria"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY criterion_id"
    with connect(db_path) as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def save_criteria(rows: list[dict], db_path: Path | str | None = None) -> None:
    """Upsert the full criteria table (used by the Criteria editor)."""
    with connect(db_path) as conn:
        ids = []
        for r in rows:
            ids.append(int(r["criterion_id"]))
            conn.execute(
                """INSERT INTO evaluation_criteria (criterion_id, name, description, weight, max_score, is_active)
                   VALUES (:criterion_id, :name, :description, :weight, :max_score, :is_active)
                   ON CONFLICT(criterion_id) DO UPDATE SET
                     name=excluded.name, description=excluded.description, weight=excluded.weight,
                     max_score=excluded.max_score, is_active=excluded.is_active""",
                {
                    "criterion_id": int(r["criterion_id"]),
                    "name": str(r["name"]).strip(),
                    "description": str(r["description"]).strip(),
                    "weight": float(r["weight"]),
                    "max_score": int(r["max_score"]),
                    "is_active": 1 if r["is_active"] else 0,
                },
            )
        if ids:
            placeholders = ",".join("?" * len(ids))
            conn.execute(f"DELETE FROM evaluation_criteria WHERE criterion_id NOT IN ({placeholders})", ids)


# ---------------------------------------------------------------- runs
def create_run(run_id: str, created_at: str, ranking_mode: str, provider: str, model: str,
               criteria: list[dict], db_path: Path | str | None = None) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO rfp_runs (rfp_run_id, created_at, status, ranking_mode, llm_provider, llm_model, "
            "criteria_snapshot) VALUES (?, ?, 'RUNNING', ?, ?, ?, ?)",
            (run_id, created_at, ranking_mode, provider, model, json.dumps(criteria)),
        )


def fail_run(run_id: str, warnings: list[str], db_path: Path | str | None = None) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE rfp_runs SET status='FAILED', run_warnings=? WHERE rfp_run_id=?",
            (json.dumps(warnings), run_id),
        )


def save_run_results(export: dict, db_path: Path | str | None = None) -> None:
    """Persist the complete run atomically under one RFP_RUN_ID."""
    run_id = export["rfp_run_id"]
    with connect(db_path) as conn:
        conn.execute("DELETE FROM supplier_results WHERE rfp_run_id=?", (run_id,))
        conn.execute("DELETE FROM criterion_assessments WHERE rfp_run_id=?", (run_id,))
        for s in export["suppliers"]:
            conn.execute(
                "INSERT INTO supplier_results (rfp_run_id, supplier_name, submission_date, experience_rating, "
                "absolute_score, ppi, final_rank, result_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, s["supplier_name"], s["submission_date"], s["experience_rating"],
                 s["absolute_score"], s["ppi"], s["final_rank"], json.dumps(s)),
            )
            for c in s["criteria"]:
                conn.execute(
                    "INSERT INTO criterion_assessments (rfp_run_id, supplier_name, criterion_id, criterion_name, "
                    "weight, max_score, score, benchmark, gap, relative_pct, weighted_points, justification, "
                    "evidence, evidence_verified, normalized) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (run_id, s["supplier_name"], c["criterion_id"], c["name"], c["weight"], c["max_score"],
                     c["score"], c["benchmark"], c["gap"], c["relative_pct"], c["weighted_points"],
                     c["justification"], c["evidence"], int(c["evidence_verified"]), int(c["normalized"])),
                )
        conn.execute(
            "UPDATE rfp_runs SET status=?, run_warnings=?, export_json=? WHERE rfp_run_id=?",
            (export["status"], json.dumps(export["warnings"]), json.dumps(export), run_id),
        )


def list_runs(limit: int = 50, db_path: Path | str | None = None) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT r.rfp_run_id, r.created_at, r.status, r.ranking_mode, r.llm_provider,
                      COUNT(s.id) AS suppliers,
                      (SELECT supplier_name FROM supplier_results WHERE rfp_run_id=r.rfp_run_id AND final_rank=1)
                        AS winner
               FROM rfp_runs r LEFT JOIN supplier_results s ON s.rfp_run_id = r.rfp_run_id
               GROUP BY r.rfp_run_id ORDER BY r.created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def load_run(run_id: str, db_path: Path | str | None = None) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT export_json FROM rfp_runs WHERE rfp_run_id=?", (run_id,)).fetchone()
        if row and row["export_json"]:
            return json.loads(row["export_json"])
    return None
