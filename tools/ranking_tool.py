"""Ranking Tool - deterministic Python only. No LLM calls in this module.

Formulas (weights are percentages of 100):
    absolute_score  = sum(score / max_score * weight)                         -> 0..100
    benchmark[c]    = max(score[c]) across all suppliers in the run
    gap[c]          = score[c] - benchmark[c]                                 -> <= 0
    relative_pct[c] = score[c] / benchmark[c] * 100   (0 if benchmark is 0)
    ppi             = sum(relative_pct[c] * weight[c]) / sum(weight[c])        -> 0..100

Ranking: stable sort on an explicit key, then ranks 1..n are assigned sequentially.
Values are rounded to config.SORT_PRECISION decimals *before* sorting so that the order
always agrees with the numbers shown on screen.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

import config
from domain.models import ValidatedScorecard


def _r(x: float) -> float:
    return round(float(x) + 0.0, config.SORT_PRECISION)


def _as_date(d: date | str) -> date:
    return d if isinstance(d, date) else date.fromisoformat(str(d))


# --------------------------------------------------------------------------- formulas
def absolute_score(card: ValidatedScorecard) -> float:
    return _r(sum(c.score / c.max_score * c.weight for c in card.criteria))


def benchmarks(cards: Iterable[ValidatedScorecard]) -> dict[int, float]:
    best: dict[int, float] = {}
    for card in cards:
        for c in card.criteria:
            best[c.criterion_id] = max(best.get(c.criterion_id, 0.0), c.score)
    return best


def relative_pct(score: float, benchmark: float) -> float:
    """Safe division: when nobody scored on a criterion the benchmark is 0 and everyone gets 0%."""
    return 0.0 if benchmark <= 0 else score / benchmark * 100.0


def ppi(rel_by_criterion: dict[int, float], weights: dict[int, float]) -> float:
    total_w = sum(weights.values())
    if total_w <= 0:
        return 0.0
    return _r(sum(rel_by_criterion[cid] * w for cid, w in weights.items()) / total_w)


# --------------------------------------------------------------------------- sort keys
KEY_LABELS = {
    "ppi_first": ["PPI (higher)", "submission date (earlier)", "experience rating (higher)", "supplier name (A-Z)"],
}


def sort_key(s: dict, mode: str) -> tuple:
    base = (_as_date(s["submission_date"]).toordinal(), -float(s["experience_rating"]),
            s["supplier_name"].casefold())
    if mode == "ppi_first":
        return (-s["ppi"],) + base
    raise ValueError(f"Unknown ranking mode: {mode}")


def _display_value(s: dict, label: str):
    if label.startswith("PPI"):
        return f"{s['ppi']:.2f}"
    if label.startswith("absolute"):
        return f"{s['absolute_score']:.2f}"
    if label.startswith("submission"):
        return str(s["submission_date"])
    if label.startswith("experience"):
        return f"{float(s['experience_rating']):g}"
    return s["supplier_name"]


def explain_order(ranked: list[dict], mode: str) -> list[str]:
    """For each adjacent pair, name the first sort-key component that separated them."""
    labels = KEY_LABELS[mode]
    lines = []
    for a, b in zip(ranked, ranked[1:]):
        ka, kb = sort_key(a, mode), sort_key(b, mode)
        idx = next((i for i, (x, y) in enumerate(zip(ka, kb)) if x != y), len(labels) - 1)
        label = labels[idx]
        tied = ", ".join(f"{labels[i].split(' (')[0]} tied at {_display_value(a, labels[i])}" for i in range(idx))
        prefix = f"#{a['final_rank']} {a['supplier_name']} above #{b['final_rank']} {b['supplier_name']}: "
        decided = (f"decided by {label}: {_display_value(a, label)} vs {_display_value(b, label)}")
        lines.append(prefix + (f"{tied}; {decided}." if tied else f"{decided}."))
        a.setdefault("rank_reason", decided)
    if ranked:
        ranked[-1].setdefault("rank_reason", "lowest position after applying the sort order")
    return lines


# --------------------------------------------------------------------------- main entry point
def rank_suppliers(cards: list[ValidatedScorecard], metadata: dict[str, dict],
                   mode: str = config.DEFAULT_RANKING_MODE) -> dict:
    """Score, benchmark and rank validated scorecards.

    metadata: {supplier_name: {"submission_date": date|str, "experience_rating": float}}
    """
    if mode not in KEY_LABELS:
        raise ValueError(f"Unknown ranking mode: {mode}")
    warnings: list[str] = []
    bench = benchmarks(cards)
    names = {c.criterion_id: c.name for card in cards for c in card.criteria}
    for cid, b in bench.items():
        if b <= 0:
            warnings.append(f"Benchmark for '{names[cid]}' is 0 (no supplier scored above 0); "
                            "relative performance set to 0% for every supplier on this criterion.")

    suppliers: list[dict] = []
    for card in cards:
        meta = metadata[card.supplier_name]
        weights = {c.criterion_id: c.weight for c in card.criteria}
        rows, rel = [], {}
        for c in card.criteria:
            b = bench[c.criterion_id]
            rel[c.criterion_id] = relative_pct(c.score, b)
            rows.append({
                "criterion_id": c.criterion_id, "name": c.name, "weight": c.weight, "max_score": c.max_score,
                "score": c.score, "benchmark": b, "gap": _r(c.score - b),
                "relative_pct": _r(rel[c.criterion_id]),
                "weighted_points": _r(c.score / c.max_score * c.weight),
                "is_benchmark_leader": b > 0 and c.score == b,
                "justification": c.justification, "evidence": c.evidence,
                "evidence_verified": c.evidence_verified, "normalized": c.normalized, "notes": c.notes,
            })
        suppliers.append({
            "supplier_name": card.supplier_name,
            "submission_date": _as_date(meta["submission_date"]).isoformat(),
            "experience_rating": float(meta["experience_rating"]),
            "absolute_score": absolute_score(card),
            "ppi": ppi(rel, weights),
            "final_rank": None,
            "llm_status": card.llm_status,
            "low_confidence": card.low_confidence,
            "criteria": rows,
            "risks": card.risks,
            "overall_summary": card.overall_summary,
            "warnings": card.warnings,
        })

    ranked = sorted(suppliers, key=lambda s: sort_key(s, mode))   # Python's sort is stable
    for i, s in enumerate(ranked, start=1):
        s["final_rank"] = i
    tie_breaks = explain_order(ranked, mode)
    return {
        "ranking_mode": mode,
        "ranking_rule": config.RANKING_MODES[mode],
        "benchmarks": [{"criterion_id": cid, "name": names[cid], "benchmark": b} for cid, b in sorted(bench.items())],
        "suppliers": ranked,
        "tie_break_explanation": tie_breaks,
        "warnings": warnings,
    }
