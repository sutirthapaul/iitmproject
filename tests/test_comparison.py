import pytest

from tests.conftest import make_card
from tools import comparison_tool as ct
from tools import ranking_tool as rt
from tests.conftest import CRITERIA

META = {n: {"submission_date": "2026-10-05", "experience_rating": 3} for n in ("A", "B", "C")}


@pytest.fixture
def run():
    cards = [make_card("A", [8, 9, 9, 8, 9]), make_card("B", [9, 7, 8, 9, 7]), make_card("C", [2, 4, 5, 4, 9])]
    out = rt.rank_suppliers(cards, META)
    out["criteria"] = CRITERIA
    return out


def test_relative_performance_matches_ranking(run):
    rows = ct.relative_performance(run)
    assert len(rows) == 15
    a_tech = next(r for r in rows if r["supplier"] == "A" and r["criterion_id"] == 1)
    assert a_tech["relative_pct"] == pytest.approx(88.89, abs=0.01) and not a_tech["is_leader"]
    # weighted average of relative % reproduces PPI
    for s in run["suppliers"]:
        mine = [r for r in rows if r["supplier"] == s["supplier_name"]]
        assert round(sum(r["relative_pct"] * r["weight"] for r in mine) / 100, 1) == round(s["ppi"], 1)


def test_ratings():
    assert ct.rating(8, 10) == "Strength"
    assert ct.rating(6, 10) == "Adequate"
    assert ct.rating(5.9, 10) == "Improvement area"
    assert ct.rating(4, 5) == "Strength"


def test_head_to_head(run):
    h = ct.head_to_head(run, "A", "B")
    assert h["ppi_gap"] == pytest.approx(run["suppliers"][0]["ppi"] - run["suppliers"][1]["ppi"], abs=0.01)
    assert {i["criterion"] for i in h["a_wins"]} == {"Implementation Plan", "Commercial Value", "Support & Experience"}
    assert {i["criterion"] for i in h["b_wins"]} == {"Technical Capability", "Security & Compliance"}
    # PPI points per criterion add up to the PPI gap
    assert sum(i["ppi_points"] for i in h["items"]) == pytest.approx(h["ppi_gap"], abs=0.05)
    with pytest.raises(ValueError):
        ct.head_to_head(run, "A", "A")


def test_to_overtake(run):
    plan = {p["criterion"]: p for p in ct.to_overtake(run, "B", "A")}
    # B is behind A; raising B's Implementation from 7 to 9 levels it with A there and should be enough
    assert plan["Implementation Plan"]["score_needed"] is not None
    assert plan["Implementation Plan"]["score_needed"] <= 10
    # C is far behind A: no single criterion closes the gap
    assert all(p["score_needed"] is None for p in ct.to_overtake(run, "C", "A"))


def test_unknown_supplier(run):
    with pytest.raises(ValueError):
        ct.relative_performance(run, ["A", "Nobody"])


def test_leaderboard_columns_and_recommendations():
    import json

    import config
    from ui.leaderboard import build_leaderboard

    run = json.loads((config.ROOT_DIR / "samples" / "run_export.json").read_text())
    board = build_leaderboard(run)
    assert len(board) == len(run["suppliers"])
    assert list(board.columns) == ["Rank", "Supplier", "Recommendation", "PPI", "Gap to #1", "Absolute score",
                                   "Criteria led", "Weakest area", "Submission date", "Experience"]
    nexa = board.iloc[0]
    assert nexa["Criteria led"] == "3 of 5" and nexa["Weakest area"] == "Technical Capability"
    assert board.iloc[0]["Recommendation"].endswith("Recommended") and board.iloc[0]["Gap to #1"] == 0
    assert list(board["Rank"]) == sorted(board["Rank"])
