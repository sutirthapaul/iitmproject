"""Orchestrator Agent: controls the workflow and calls each tool in the required order.

    Batch -> (reload criteria) -> Document Tool -> Evaluation Agent -> Validation Tool
          -> Ranking Tool -> Persist -> export

Every step is recorded in an agent trace so the run is explainable end to end.
"""
from __future__ import annotations

import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

import config
from agents.evaluation_agent import evaluate_supplier
from db import database
from domain.models import SupplierInput
from llm.client import LLMClient
from tools import pdf_tool, ranking_tool, validation_tool

APP_VERSION = "1.0.0"
ProgressFn = Callable[[float, str], None]

FORMULAS = {
    "absolute_score": "sum(score / max_score * weight) over active criteria (0-100)",
    "benchmark": "highest validated score for the criterion across all suppliers in the run",
    "gap": "supplier score - benchmark (0 for the leader, otherwise negative)",
    "relative_pct": "supplier score / benchmark * 100; 0 when the benchmark is 0",
    "ppi": "sum(relative_pct * weight) / sum(weight)",
}


class RunAborted(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def new_run_id() -> str:
    return f"RFP-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6].upper()}"


# --------------------------------------------------------------------------- input checks
def validate_weights(criteria: list[dict]) -> list[str]:
    errors = []
    if not criteria:
        errors.append("No active evaluation criteria. Activate at least one criterion.")
        return errors
    total = sum(float(c["weight"]) for c in criteria)
    if abs(total - config.WEIGHT_TOTAL) > config.WEIGHT_TOLERANCE:
        errors.append(f"Active criteria weights total {total:g}%; they must total 100%.")
    for c in criteria:
        if float(c["weight"]) <= 0:
            errors.append(f"Active criterion '{c['name']}' has weight {c['weight']}; weights must be above 0.")
        if int(c["max_score"]) <= 0:
            errors.append(f"Criterion '{c['name']}' has max_score {c['max_score']}; it must be above 0.")
    return errors


def validate_inputs(suppliers: list[SupplierInput]) -> list[str]:
    errors = []
    if not suppliers:
        return ["Upload at least one supplier PDF."]
    seen: dict[str, str] = {}
    for s in suppliers:
        label = s.file_name
        name = s.supplier_name.strip()
        if not name:
            errors.append(f"{label}: supplier name is required.")
        elif name.casefold() in seen:
            errors.append(f"{label}: supplier name '{name}' is already used by {seen[name.casefold()]}.")
        else:
            seen[name.casefold()] = label
        if not isinstance(s.submission_date, date):
            errors.append(f"{label}: submission date is invalid.")
        if not (config.EXPERIENCE_MIN <= float(s.experience_rating) <= config.EXPERIENCE_MAX):
            errors.append(f"{label}: experience rating must be between {config.EXPERIENCE_MIN:g} and "
                          f"{config.EXPERIENCE_MAX:g}.")
        if not s.file_name.lower().endswith(".pdf"):
            errors.append(f"{label}: only PDF files are accepted.")
    return errors


# --------------------------------------------------------------------------- the run
def run_evaluation(suppliers: list[SupplierInput], client: LLMClient,
                   ranking_mode: str = config.DEFAULT_RANKING_MODE,
                   db_path: Path | str | None = None,
                   progress: ProgressFn | None = None) -> dict:
    progress = progress or (lambda f, m: None)
    trace: list[dict] = []
    run_warnings: list[str] = []

    def log(actor: str, action: str, detail: str, started: float) -> None:
        trace.append({"step": len(trace) + 1, "actor": actor, "action": action, "detail": detail,
                      "duration_ms": round((time.perf_counter() - started) * 1000, 1)})

    # Step 3 - batch: validate inputs before anything is created
    t = time.perf_counter()
    input_errors = validate_inputs(suppliers)
    if input_errors:
        raise RunAborted(input_errors)

    # Step 4 - reload the latest active criteria (never trust a cached copy)
    criteria = database.get_criteria(active_only=True, db_path=db_path)
    weight_errors = validate_weights(criteria)
    if weight_errors:
        raise RunAborted(weight_errors)

    run_id = new_run_id()
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    database.create_run(run_id, created_at, ranking_mode, client.provider, client.model, criteria, db_path)
    log("Orchestrator", "Create batch",
        f"{run_id}: {len(suppliers)} supplier(s), {len(criteria)} active criteria, mode={ranking_mode}", t)
    if len(suppliers) == 1:
        run_warnings.append("Only one supplier: benchmarks equal its own scores, so PPI is 100 by definition.")

    try:
        cards = []
        n = len(suppliers)
        for i, s in enumerate(suppliers):
            base = i / n
            # Document Tool
            t = time.perf_counter()
            progress(base + 0.05 / n, f"Extracting text: {s.supplier_name}")
            ext = pdf_tool.extract_text(s.file_bytes, s.file_name)
            if not ext.ok:
                log("Document Tool", "Extract text", f"{s.supplier_name}: FAILED - {ext.error}", t)
                card = validation_tool.validate_scorecard(
                    None, criteria, s.supplier_name, "", llm_status="skipped_no_text",
                    upstream_warnings=[f"[{s.supplier_name}] {ext.error} Supplier scored 0 on every criterion."])
                cards.append(card)
                continue
            log("Document Tool", "Extract text",
                f"{s.supplier_name}: {ext.pages} page(s), {ext.chars:,} chars"
                + (" (truncated)" if ext.truncated else ""), t)

            # Evaluation Agent
            t = time.perf_counter()
            progress(base + 0.3 / n, f"Evaluating with {client.provider}: {s.supplier_name}")
            outcome = evaluate_supplier(client, s.supplier_name, criteria, ext.text)
            log("Evaluation Agent", "Score criteria",
                f"{s.supplier_name}: {outcome.status} after {outcome.attempts} attempt(s)", t)

            # Validation Tool
            t = time.perf_counter()
            progress(base + 0.9 / n, f"Validating scorecard: {s.supplier_name}")
            card = validation_tool.validate_scorecard(
                outcome.raw, criteria, s.supplier_name, ext.text, llm_status=outcome.status,
                upstream_warnings=ext.warnings + outcome.warnings)
            fixed = sum(c.normalized for c in card.criteria)
            log("Validation Tool", "Validate & normalise",
                f"{s.supplier_name}: {len(card.criteria)} criteria, {fixed} normalised, "
                f"{len(card.warnings)} warning(s)", t)
            cards.append(card)

        # Ranking Tool (deterministic)
        t = time.perf_counter()
        progress(0.95, "Scoring, benchmarking and ranking")
        meta = {s.supplier_name: {"submission_date": s.submission_date, "experience_rating": s.experience_rating}
                for s in suppliers}
        ranking = ranking_tool.rank_suppliers(cards, meta, ranking_mode)
        winner = ranking["suppliers"][0]
        log("Ranking Tool", "Score, benchmark, rank",
            f"Winner: {winner['supplier_name']} (PPI {winner['ppi']:.2f}, score {winner['absolute_score']:.2f})", t)

        all_warnings = run_warnings + ranking["warnings"] + [w for s in ranking["suppliers"] for w in s["warnings"]]
        export = {
            "rfp_run_id": run_id,
            "created_at": created_at,
            "status": "COMPLETED_WITH_WARNINGS" if all_warnings else "COMPLETED",
            "app_version": APP_VERSION,
            "llm": {"provider": client.provider, "model": client.model,
                    "temperature": config.LLM_TEMPERATURE},
            "ranking_mode": ranking["ranking_mode"],
            "ranking_rule": ranking["ranking_rule"],
            "criteria": criteria,
            "formulas": FORMULAS,
            "benchmarks": ranking["benchmarks"],
            "suppliers": ranking["suppliers"],
            "tie_break_explanation": ranking["tie_break_explanation"],
            "warnings": all_warnings,
            "agent_trace": trace,
        }

        # Persist
        t = time.perf_counter()
        database.save_run_results(export, db_path)
        log("Orchestrator", "Persist results", f"Saved {len(export['suppliers'])} supplier result(s) to SQLite", t)
        export["agent_trace"] = trace
        database.save_run_results(export, db_path)   # re-save so the stored trace includes the persist step
        progress(1.0, "Done")
        return export
    except Exception as exc:
        database.fail_run(run_id, run_warnings + [f"Run failed: {type(exc).__name__}: {exc}"], db_path)
        raise
