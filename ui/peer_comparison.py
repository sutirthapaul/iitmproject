"""Peer comparison tab: relative performance % by criterion, plus a head-to-head view.

Read-only: everything is computed from the completed run, nothing is re-scored or re-ranked.
"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from tools import comparison_tool as ct

# Categorical palette (fixed order, colour follows the supplier's rank in the run, never cycled).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
TEXT = "#0F172A"
MUTED = "#64748B"
GRID = "#E2E8F0"
CHART_PADDING = {"left": 12, "right": 12, "top": 12, "bottom": 12}
# Break long criterion names onto lines at spaces, keeping "&" with the following word.
LABEL_EXPR = "split(replace(datum.label, ' & ', ' &\u00a0'), ' ')"


def _supplier_colors(run: dict) -> tuple[list[str], list[str]]:
    names = [s["supplier_name"] for s in run["suppliers"]][:len(SERIES)]
    return names, SERIES[:len(names)]


def heatmap_height(n_suppliers: int) -> int:
    return max(48 * n_suppliers, 140)


def _heatmap(df: pd.DataFrame, suppliers: list[str], criteria: list[str]) -> alt.Chart:
    base = alt.Chart(df).encode(
        x=alt.X("criterion:N", sort=criteria, title=None,
                axis=alt.Axis(labelAngle=0, labelLimit=140, labelColor=TEXT, ticks=False, domain=False,
                              orient="bottom", labelExpr=LABEL_EXPR, labelPadding=8)),
        y=alt.Y("supplier:N", sort=suppliers, title=None,
                axis=alt.Axis(labelColor=TEXT, ticks=False, domain=False, labelLimit=180)),
        tooltip=[alt.Tooltip("supplier:N", title="Supplier"), alt.Tooltip("criterion:N", title="Criterion"),
                 alt.Tooltip("relative_pct:Q", title="Relative %", format=".1f"),
                 alt.Tooltip("score:Q", title="Score"), alt.Tooltip("benchmark:Q", title="Benchmark"),
                 alt.Tooltip("gap:Q", title="Gap", format="+.1f"), alt.Tooltip("weight:Q", title="Weight %")],
    )
    cells = base.mark_rect(cornerRadius=4, stroke="white", strokeWidth=2).encode(
        color=alt.Color("relative_pct:Q", title="Relative %",
                        scale=alt.Scale(domain=[0, 100], range=["#eef5fd", "#86b6ef", "#2a78d6", "#0d366b"]),
                        legend=alt.Legend(orient="bottom", gradientLength=220, titleColor=MUTED,
                                          labelColor=MUTED)))
    labels = base.mark_text(fontSize=13, fontWeight=500).encode(
        text=alt.Text("label:N"),
        color=alt.condition("datum.relative_pct >= 55", alt.value("white"), alt.value(TEXT)))
    return (cells + labels).properties(height=heatmap_height(len(suppliers)), padding=CHART_PADDING)


def _grouped_bars(df: pd.DataFrame, suppliers: list[str], colors: list[str], criteria: list[str],
                  color_domain: list[str]) -> alt.Chart:
    rule = alt.Chart(pd.DataFrame({"y": [100]})).mark_rule(color=MUTED, strokeDash=[4, 4]).encode(y="y:Q")
    bars = alt.Chart(df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, stroke="white",
                                  strokeWidth=2).encode(
        x=alt.X("criterion:N", sort=criteria, title=None,
                axis=alt.Axis(labelAngle=0, labelColor=TEXT, ticks=False, labelExpr=LABEL_EXPR)),
        xOffset=alt.XOffset("supplier:N", sort=suppliers),
        y=alt.Y("relative_pct:Q", title="Relative performance %", scale=alt.Scale(domain=[0, 105]),
                axis=alt.Axis(values=[0, 25, 50, 75, 100], gridColor=GRID, titleColor=MUTED,
                              labelColor=MUTED, domain=False, ticks=False)),
        color=alt.Color("supplier:N", sort=suppliers, title=None,
                        scale=alt.Scale(domain=color_domain, range=colors),
                        legend=alt.Legend(orient="top", labelColor=TEXT, symbolType="square")),
        tooltip=[alt.Tooltip("supplier:N", title="Supplier"), alt.Tooltip("criterion:N", title="Criterion"),
                 alt.Tooltip("relative_pct:Q", title="Relative %", format=".1f"),
                 alt.Tooltip("score:Q", title="Score"), alt.Tooltip("benchmark:Q", title="Benchmark")],
    )
    return (bars + rule).properties(height=340, padding=CHART_PADDING)


def render(run: dict) -> None:
    st.subheader("Peer comparison: relative performance % by criterion")
    st.caption("Relative % = supplier score ÷ best score in this run × 100. 100% means best in class on that "
               "criterion; lower values show how far behind the leader a supplier is.")

    all_names = [s["supplier_name"] for s in run["suppliers"]]
    picked = st.multiselect("Suppliers to compare", all_names, default=all_names[:min(5, len(all_names))],
                            help="Shown in rank order. Colours stay with the supplier whatever you select.")
    if len(picked) < 2:
        st.info("Select at least two suppliers.")
        return
    if len(picked) > len(SERIES):
        st.warning(f"Showing the first {len(SERIES)} selected suppliers.")
        picked = picked[:len(SERIES)]

    rows = ct.relative_performance(run, picked)
    df = pd.DataFrame(rows)
    df["label"] = df["relative_pct"].map(lambda v: f"{v:.0f}%") + df["is_leader"].map(lambda b: " ★" if b else "")
    suppliers = list(dict.fromkeys(df["supplier"]))                  # rank order
    criteria = [c["name"] for c in run["criteria"]]
    color_domain, color_range = _supplier_colors(run)
    colors = [color_range[color_domain.index(n)] for n in suppliers]

    view = st.radio("View", ["Heatmap", "Bar chart", "Table"], horizontal=True, label_visibility="collapsed")
    if view == "Heatmap":
        # explicit height: newer Streamlit versions otherwise shrink layered charts with a discrete y axis
        st.altair_chart(_heatmap(df, suppliers, criteria), width="stretch",
                        height=heatmap_height(len(suppliers)) + 140)
        st.caption("★ = benchmark leader for that criterion. Hover a cell for score, benchmark and gap.")
    elif view == "Bar chart":
        st.altair_chart(_grouped_bars(df, suppliers, colors, criteria, suppliers), height=440,
                        width="stretch")
        st.caption("Dashed line = benchmark (100%).")
    else:
        table = df.pivot(index="supplier", columns="criterion", values="relative_pct").reindex(suppliers)[criteria]
        ppi = {s["supplier_name"]: s["ppi"] for s in run["suppliers"]}
        table["PPI"] = [ppi[n] for n in table.index]
        st.dataframe(table, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="%.1f%%") for c in criteria}
                     | {"PPI": st.column_config.NumberColumn(format="%.2f")})
        st.caption("PPI is the weighted average of these percentages.")

    # ---------------- strengths / improvement areas
    st.markdown("#### Strengths and improvement areas")
    st.caption("Display rule only (does not change scores): ≥ 80% of max score = strength, < 60% = improvement area.")
    cols = st.columns(min(len(suppliers), 4))
    for i, name in enumerate(suppliers):
        sub = df[df["supplier"] == name]
        with cols[i % len(cols)]:
            st.markdown(f"**#{int(sub['rank'].iloc[0])} {name}**")
            strengths = sub[sub["rating"] == "Strength"]["criterion"].tolist()
            weak = sub[sub["rating"] == "Improvement area"]["criterion"].tolist()
            st.markdown("✅ " + (", ".join(strengths) if strengths else "_none_"))
            st.markdown("⚠️ " + (", ".join(weak) if weak else "_none_"))

    # ---------------- head to head
    st.divider()
    st.markdown("#### Head-to-head")
    c1, c2 = st.columns(2)
    a = c1.selectbox("Supplier A", suppliers, index=0)
    b = c2.selectbox("Supplier B", suppliers, index=1 if len(suppliers) > 1 else 0)
    if a == b:
        st.info("Choose two different suppliers.")
        return
    h = ct.head_to_head(run, a, b)
    m = st.columns(4)
    m[0].metric(f"{a} PPI", f"{h['ppi_a']:.2f}", f"{h['ppi_gap']:+.2f} vs {b}")
    m[1].metric(f"{b} PPI", f"{h['ppi_b']:.2f}")
    m[2].metric(f"{a} score", f"{h['score_a']:.2f}", f"{h['score_gap']:+.2f}")
    m[3].metric(f"{b} score", f"{h['score_b']:.2f}")
    st.info(h["verdict"])
    st.dataframe(pd.DataFrame([{
        "Criterion": i["criterion"], "Weight %": i["weight"], a: i["score_a"], b: i["score_b"],
        "Difference": i["difference"], "PPI points": i["ppi_points"],
        "Advantage": a if i["difference"] > 0 else (b if i["difference"] < 0 else "Level"),
    } for i in h["items"]]), hide_index=True, width="stretch",
        column_config={"Difference": st.column_config.NumberColumn(format="%+.1f"),
                       "PPI points": st.column_config.NumberColumn(
                           format="%+.2f", help="How much this criterion adds to (or subtracts from) A's PPI lead")})

    lower, upper = (b, a) if h["rank_a"] < h["rank_b"] else (a, b)
    with st.expander(f"What would {lower} need to overtake {upper}?"):
        st.caption(f"Improvement on ONE criterion only, other scores unchanged. Benchmarks are recalculated, so "
                   f"raising {lower}'s score can also lower {upper}'s relative %.")
        plan = ct.to_overtake(run, lower, upper)
        st.dataframe(pd.DataFrame([{
            "Criterion": p["criterion"], "Weight %": p["weight"], "Current": p["current"],
            "Score needed": f"{p['score_needed']:g} / {p['max_score']}" if p["score_needed"] is not None
            else "not enough on its own",
            "Increase": f"+{p['increase']:g}" if p["increase"] is not None else "—",
        } for p in plan]), hide_index=True, width="stretch")
