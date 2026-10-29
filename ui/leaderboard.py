"""Leaderboard table with detailed per-supplier columns.

Display only: every value is read from the completed run. Nothing here changes a score or rank.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

# Recommendation bands (display rule, documented in the UI caption)
SHORTLIST_PPI_GAP = 5.0       # within 5 PPI points of the #1 supplier
NOT_RECOMMENDED_PPI = 50.0    # below this PPI


def recommendation(s: dict, top_ppi: float) -> str:
    if s["llm_status"] in ("failed", "skipped_no_text"):
        return "⛔ Not evaluated"
    if s["final_rank"] == 1:
        return "🥇 Recommended"
    if top_ppi - s["ppi"] <= SHORTLIST_PPI_GAP:
        return "🟢 Shortlist"
    if s["ppi"] < NOT_RECOMMENDED_PPI:
        return "🔴 Not recommended"
    return "🟡 Consider"


def _evaluated(s: dict) -> bool:
    return s["llm_status"] not in ("failed", "skipped_no_text")


def criteria_led(s: dict) -> str:
    led = sum(1 for c in s["criteria"] if c.get("is_benchmark_leader"))
    return f"{led} of {len(s['criteria'])}"


def weakest_area(s: dict) -> str:
    """Criterion furthest behind the best supplier; on a tie, the higher-weighted one."""
    if not _evaluated(s) or not s["criteria"]:
        return "—"
    return min(s["criteria"], key=lambda c: (c["relative_pct"], -c["weight"]))["name"]


def build_leaderboard(run: dict) -> pd.DataFrame:
    top_ppi = run["suppliers"][0]["ppi"] if run["suppliers"] else 0
    return pd.DataFrame([{
        "Rank": s["final_rank"],
        "Supplier": s["supplier_name"],
        "Recommendation": recommendation(s, top_ppi),
        "PPI": s["ppi"],
        "Gap to #1": round(s["ppi"] - top_ppi, 2),
        "Absolute score": s["absolute_score"],
        "Criteria led": criteria_led(s),
        "Weakest area": weakest_area(s),
        "Submission date": s["submission_date"],
        "Experience": s["experience_rating"],
    } for s in run["suppliers"]])


def render_table(run: dict) -> pd.DataFrame:
    """Draw the leaderboard and return the DataFrame (used by the chart below it)."""
    board = build_leaderboard(run)
    st.dataframe(board, hide_index=True, width="stretch", column_config={
        "Rank": st.column_config.NumberColumn(width="small"),
        "PPI": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=100),
        "Absolute score": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=100),
        "Gap to #1": st.column_config.NumberColumn(format="%+.2f", help="PPI points behind the #1 supplier"),
        "Criteria led": st.column_config.TextColumn(help="Criteria where this supplier has the best score in the run"),
        "Weakest area": st.column_config.TextColumn(help="Criterion where this supplier is furthest behind the best"),
        "Experience": st.column_config.NumberColumn(format="%.1f"),
    })
    st.caption(f"Recommendation is a display label only: 🥇 rank 1 · 🟢 within {SHORTLIST_PPI_GAP:g} PPI of #1 · "
               f"🟡 Consider · 🔴 PPI below {NOT_RECOMMENDED_PPI:g} · ⛔ document or LLM failed. "
               "Per-criterion scores are in the Peer comparison and Scorecards tabs.")
    return board
