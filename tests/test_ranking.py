import random

import pytest

from tests.conftest import make_card
from tools import ranking_tool as rt

META = {
    "A": {"submission_date": "2026-10-05", "experience_rating": 4.0},
    "B": {"submission_date": "2026-10-05", "experience_rating": 4.0},
    "C": {"submission_date": "2026-10-05", "experience_rating": 4.0},
}


def test_weighted_score_matches_build_guide_example():
    # Build guide: scores 8,7,9,8,6 with weights 30/20/20/20/10 -> 7.80 on a 10-point scale = 78 on 0-100
    assert rt.absolute_score(make_card("A", [8, 7, 9, 8, 6])) == 78.0


def test_benchmark_gap_relative_and_ppi():
    cards = [make_card("A", [8, 7, 9, 8, 6]), make_card("B", [10, 5, 6, 8, 3])]
    out = rt.rank_suppliers(cards, META, "ppi_first")
    bench = {b["criterion_id"]: b["benchmark"] for b in out["benchmarks"]}
    assert bench == {1: 10, 2: 7, 3: 9, 4: 8, 5: 6}
    a = next(s for s in out["suppliers"] if s["supplier_name"] == "A")
    rows = {c["criterion_id"]: c for c in a["criteria"]}
    assert rows[1]["gap"] == -2 and rows[1]["relative_pct"] == 80.0
    assert rows[2]["gap"] == 0 and rows[2]["is_benchmark_leader"]
    # PPI(A) = (80*30 + 100*20 + 100*20 + 100*20 + 100*10) / 100 = 94
    assert a["ppi"] == 94.0
    b = next(s for s in out["suppliers"] if s["supplier_name"] == "B")
    # PPI(B) = (100*30 + 71.428..*20 + 66.66..*20 + 100*20 + 50*10)/100 = 82.62
    assert b["ppi"] == pytest.approx(82.62, abs=0.01)
    assert [s["supplier_name"] for s in out["suppliers"]] == ["A", "B"]


def test_zero_benchmark_is_safe_and_warned():
    cards = [make_card("A", [5, 0, 5, 5, 5]), make_card("B", [4, 0, 4, 4, 4])]
    out = rt.rank_suppliers(cards, META, "ppi_first")
    assert any("Implementation Plan" in w and "is 0" in w for w in out["warnings"])
    for s in out["suppliers"]:
        assert next(c for c in s["criteria"] if c["criterion_id"] == 2)["relative_pct"] == 0.0


def test_tie_break_submission_date():
    cards = [make_card("A", [8] * 5), make_card("B", [8] * 5)]
    meta = {"A": {"submission_date": "2026-10-06", "experience_rating": 5},
            "B": {"submission_date": "2026-10-02", "experience_rating": 1}}
    out = rt.rank_suppliers(cards, meta, "ppi_first")
    assert [s["supplier_name"] for s in out["suppliers"]] == ["B", "A"]
    assert "submission date" in out["tie_break_explanation"][0]


def test_tie_break_experience_then_name():
    cards = [make_card("Zeta", [8] * 5), make_card("Alpha", [8] * 5), make_card("Mid", [8] * 5)]
    meta = {"Zeta": {"submission_date": "2026-10-02", "experience_rating": 4.5},
            "Alpha": {"submission_date": "2026-10-02", "experience_rating": 3.0},
            "Mid": {"submission_date": "2026-10-02", "experience_rating": 3.0}}
    out = rt.rank_suppliers(cards, meta, "ppi_first")
    assert [s["supplier_name"] for s in out["suppliers"]] == ["Zeta", "Alpha", "Mid"]
    assert "experience rating" in out["tie_break_explanation"][0]
    assert "supplier name" in out["tie_break_explanation"][1]
    assert [s["final_rank"] for s in out["suppliers"]] == [1, 2, 3]


def test_name_tie_break_is_case_insensitive():
    cards = [make_card("beta", [8] * 5), make_card("Alpha", [8] * 5)]
    meta = {n: {"submission_date": "2026-10-02", "experience_rating": 3} for n in ("beta", "Alpha")}
    out = rt.rank_suppliers(cards, meta, "ppi_first")
    assert [s["supplier_name"] for s in out["suppliers"]] == ["Alpha", "beta"]


def test_ppi_can_beat_higher_absolute_score():
    # Example from the README: A has the higher absolute score, but B wins because ranking is PPI first.
    crit = [{"criterion_id": 1, "name": "C1", "description": "", "weight": 50, "max_score": 10},
            {"criterion_id": 2, "name": "C2", "description": "", "weight": 50, "max_score": 10}]
    cards = [make_card("A", [10, 2], crit), make_card("B", [6, 4], crit)]
    meta = {n: {"submission_date": "2026-10-02", "experience_rating": 3} for n in ("A", "B")}
    out = rt.rank_suppliers(cards, meta, "ppi_first")
    a, b = sorted(out["suppliers"], key=lambda s: s["supplier_name"])
    assert a["absolute_score"] > b["absolute_score"] and b["ppi"] > a["ppi"]
    assert [s["supplier_name"] for s in out["suppliers"]] == ["B", "A"]


def test_order_is_independent_of_input_order():
    names = [f"S{i}" for i in range(8)]
    meta = {n: {"submission_date": f"2026-10-0{1 + i % 3}", "experience_rating": 1 + i % 4} for i, n in enumerate(names)}
    base = [make_card(n, [(i * 3) % 7 + 3, 6, (i * 5) % 9 + 1, 7, 5]) for i, n in enumerate(names)]
    expected = [s["supplier_name"] for s in rt.rank_suppliers(base, meta)["suppliers"]]
    for seed in range(10):
        shuffled = base[:]
        random.Random(seed).shuffle(shuffled)
        assert [s["supplier_name"] for s in rt.rank_suppliers(shuffled, meta)["suppliers"]] == expected


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        rt.rank_suppliers([make_card("A", [1] * 5)], META, "random")
