"""Peer Comparison Tool - deterministic Python, no LLM.

Works only on a completed run's export (the same dict the app shows and saves), so a
comparison never changes any score or rank. Display thresholds are relative to each
criterion's max_score: >= 80% of max is a strength, < 60% is an improvement area.
"""
from __future__ import annotations

STRENGTH_RATIO = 0.8        # 8/10 and above
IMPROVEMENT_RATIO = 0.6     # below 6/10


def rating(score: float, max_score: float) -> str:
    ratio = score / max_score if max_score else 0
    if ratio >= STRENGTH_RATIO:
        return "Strength"
    if ratio < IMPROVEMENT_RATIO:
        return "Improvement area"
    return "Adequate"


def _pick(run: dict, names: list[str]) -> list[dict]:
    by_name = {s["supplier_name"]: s for s in run["suppliers"]}
    missing = [n for n in names if n not in by_name]
    if missing:
        raise ValueError(f"Not in this run: {', '.join(missing)}")
    return sorted((by_name[n] for n in names), key=lambda s: s["final_rank"])


def relative_performance(run: dict, names: list[str] | None = None) -> list[dict]:
    """Long-format rows: one per supplier x criterion with relative % (score / benchmark x 100).

    100% means the supplier is the best in the run on that criterion. Suppliers are in rank
    order, criteria in criterion_id order.
    """
    names = names or [s["supplier_name"] for s in run["suppliers"]]
    rows = []
    for s in _pick(run, names):
        for c in s["criteria"]:
            rows.append({
                "rank": s["final_rank"], "supplier": s["supplier_name"],
                "criterion_id": c["criterion_id"], "criterion": c["name"], "weight": c["weight"],
                "score": c["score"], "max_score": c["max_score"], "benchmark": c["benchmark"],
                "gap": c["gap"], "relative_pct": c["relative_pct"],
                "is_leader": bool(c.get("is_benchmark_leader")),
                "rating": rating(c["score"], c["max_score"]),
            })
    return rows


def criterion_matrix(run: dict, names: list[str]) -> list[dict]:
    """One row per criterion: each supplier's score + rating, and who leads among the selection."""
    picked = _pick(run, names)
    rows = []
    for crit in run["criteria"]:
        cid = crit["criterion_id"]
        cells = {s["supplier_name"]: next(c for c in s["criteria"] if c["criterion_id"] == cid) for s in picked}
        top = max(c["score"] for c in cells.values())
        leaders = [n for n, c in cells.items() if c["score"] == top]
        rows.append({
            "criterion_id": cid,
            "criterion": crit["name"],
            "weight": crit["weight"],
            "max_score": crit["max_score"],
            "benchmark": next(c["benchmark"] for c in cells.values()),
            "scores": {n: c["score"] for n, c in cells.items()},
            "ratings": {n: rating(c["score"], c["max_score"]) for n, c in cells.items()},
            "leaders": leaders if top > 0 else [],
            "spread": round(top - min(c["score"] for c in cells.values()), 2),
        })
    return rows


def head_to_head(run: dict, a: str, b: str) -> dict:
    """Where A beats B, where B beats A, and the weighted points each difference is worth."""
    if a == b:
        raise ValueError("Choose two different suppliers.")
    picked = {s["supplier_name"]: s for s in _pick(run, [a, b])}
    sa, sb = picked[a], picked[b]
    items = []
    for ca in sa["criteria"]:
        cb = next(c for c in sb["criteria"] if c["criterion_id"] == ca["criterion_id"])
        diff = round(ca["score"] - cb["score"], 2)
        items.append({
            "criterion": ca["name"], "weight": ca["weight"],
            "score_a": ca["score"], "score_b": cb["score"], "difference": diff,
            # absolute-score points this criterion contributes to the gap between A and B
            "weighted_points": round(ca["weighted_points"] - cb["weighted_points"], 2),
            # PPI points this criterion contributes to the gap
            "ppi_points": round((ca["relative_pct"] - cb["relative_pct"]) * ca["weight"] / 100, 2),
        })
    a_wins = sorted([i for i in items if i["difference"] > 0], key=lambda i: -i["ppi_points"])
    b_wins = sorted([i for i in items if i["difference"] < 0], key=lambda i: i["ppi_points"])
    ties = [i for i in items if i["difference"] == 0]
    ppi_gap = round(sa["ppi"] - sb["ppi"], 2)
    score_gap = round(sa["absolute_score"] - sb["absolute_score"], 2)

    if ppi_gap > 0:
        verdict = f"{a} leads {b} by {ppi_gap:.2f} PPI points"
    elif ppi_gap < 0:
        verdict = f"{b} leads {a} by {-ppi_gap:.2f} PPI points"
    else:
        verdict = f"{a} and {b} are level on PPI; the tie-break rules decide their order"
    if a_wins:
        verdict += f". {a}'s biggest advantage: {a_wins[0]['criterion']} (+{a_wins[0]['ppi_points']:.2f} PPI)"
    if b_wins:
        verdict += f". {b}'s biggest advantage: {b_wins[0]['criterion']} (+{-b_wins[0]['ppi_points']:.2f} PPI)"
    return {
        "a": a, "b": b, "rank_a": sa["final_rank"], "rank_b": sb["final_rank"],
        "ppi_a": sa["ppi"], "ppi_b": sb["ppi"], "score_a": sa["absolute_score"], "score_b": sb["absolute_score"],
        "ppi_gap": ppi_gap, "score_gap": score_gap,
        "items": items, "a_wins": a_wins, "b_wins": b_wins, "ties": ties,
        "verdict": verdict + ".",
    }


def to_overtake(run: dict, challenger: str, leader: str) -> list[dict]:
    """For each criterion: how many score points the challenger alone would need on that
    criterion (other scores unchanged) to reach the leader's PPI. None = not possible on that
    criterion alone. Benchmarks are recomputed because raising a score can raise the benchmark.
    """
    picked = {s["supplier_name"]: s for s in _pick(run, [challenger, leader])}
    ch, ld = picked[challenger], picked[leader]
    others = [s for s in run["suppliers"] if s["supplier_name"] != challenger]
    weights = {c["criterion_id"]: c["weight"] for c in ch["criteria"]}
    total_w = sum(weights.values()) or 1

    def ppi_with(cid: int, new_score: float) -> tuple[float, float]:
        """Return (challenger PPI, leader PPI) if the challenger scored new_score on cid."""
        def rel(score, bench):
            return 0.0 if bench <= 0 else score / bench * 100
        ch_scores = {c["criterion_id"]: c["score"] for c in ch["criteria"]}
        ch_scores[cid] = new_score
        bench = {k: max([ch_scores[k]] + [next(c["score"] for c in o["criteria"] if c["criterion_id"] == k)
                                          for o in others]) for k in ch_scores}
        ld_scores = {c["criterion_id"]: c["score"] for c in ld["criteria"]}
        p_ch = sum(rel(ch_scores[k], bench[k]) * w for k, w in weights.items()) / total_w
        p_ld = sum(rel(ld_scores[k], bench[k]) * w for k, w in weights.items()) / total_w
        return round(p_ch, 2), round(p_ld, 2)

    out = []
    for c in ch["criteria"]:
        needed = None
        steps = int(round((c["max_score"] - c["score"]) * 2))           # half-point steps
        for i in range(1, steps + 1):
            trial = c["score"] + i / 2
            p_ch, p_ld = ppi_with(c["criterion_id"], trial)
            if p_ch > p_ld:
                needed = trial
                break
        out.append({"criterion": c["name"], "weight": c["weight"], "current": c["score"],
                    "max_score": c["max_score"], "score_needed": needed,
                    "increase": None if needed is None else round(needed - c["score"], 1)})
    return sorted(out, key=lambda r: (r["increase"] is None, r["increase"] or 0))
