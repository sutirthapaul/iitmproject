"""Agentic RFP Evaluation and Supplier Ranking - Streamlit entry point.

Run locally:  streamlit run app.py
"""
from __future__ import annotations

import json
import os
from datetime import date

import pandas as pd
import streamlit as st

import config
from agents.orchestrator import RunAborted, run_evaluation, validate_inputs, validate_weights
from db import database
from domain.models import SupplierInput
from llm.client import LLMError, build_client
from ui import leaderboard, peer_comparison, theme

st.set_page_config(page_title="Agentic RFP Evaluator", page_icon="📑", layout="wide")
theme.apply_theme()

SAMPLE_SUPPLIERS = [
    # file, supplier name, submission date, experience rating (1-5)
    ("apex_systems_proposal.pdf", "Apex Systems", "2026-10-05", 4.5),
    ("brightpath_tech_proposal.pdf", "BrightPath Tech", "2026-10-02", 2.0),
    ("nexaworks_proposal.pdf", "NexaWorks", "2026-10-04", 4.0),
    ("orbit_digital_proposal.pdf", "Orbit Digital", "2026-10-06", 5.0),
    ("zenith_consulting_proposal.pdf", "Zenith Consulting", "2026-10-06", 3.5),
]
SAMPLE_SET_2 = [
    ("set2/quantum_ledger_proposal.pdf", "Quantum Ledger Solutions", "2026-10-08", 4.5),
    ("set2/pinnacle_cloud_proposal.pdf", "Pinnacle Cloud Partners", "2026-10-03", 2.5),
    ("set2/swiftserve_global_proposal.pdf", "SwiftServe Global", "2026-10-05", 3.5),
    ("set2/horizon_integrators_proposal.pdf", "Horizon Integrators", "2026-10-04", 4.0),
    ("set2/lumen_analytics_proposal.pdf", "Lumen Analytics", "2026-10-09", 2.0),
]


# --------------------------------------------------------------------------- setup
@st.cache_resource
def _init_database() -> bool:
    database.init_db()          # creates + seeds on a fresh (ephemeral) container
    return True


_init_database()
ss = st.session_state
ss.setdefault("staged", {})     # file_key -> {file_name, bytes, name, date, exp}
ss.setdefault("run", None)
ss.setdefault("removed", set())  # uploader files the user removed (the uploader keeps re-sending them)
ss.setdefault("crit_version", 0)  # bumped on save/restore so the criteria table reloads from the database
ss.setdefault("crit_flash", None)
ss.setdefault("upload_version", 0)  # bumped by "Start new evaluation" so the file uploader empties
ss.setdefault("input_flash", None)


# Screen labels for providers. Internal names (config.LLM_PROVIDERS keys) stay unchanged.
PROVIDER_LABELS = {"Mock (no API key)": "Offline Demo (No API Key)"}


def display_name(provider: str) -> str:
    return PROVIDER_LABELS.get(provider, provider)


def _secret(name: str) -> str | None:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:           # no secrets.toml present
        pass
    return os.environ.get(name)


def _guess_name(file_name: str) -> str:
    stem = file_name.rsplit(".", 1)[0]
    for junk in ("_proposal", "-proposal", "_rfp", "-rfp", "_response"):
        stem = stem.replace(junk, "")
    return " ".join(w.capitalize() for w in stem.replace("-", "_").split("_") if w)


def _stage(file_name: str, data: bytes, name: str | None = None, sub_date: str | None = None,
           exp: float = 3.0) -> None:
    key = f"{file_name}:{len(data)}"
    if key not in ss.staged and key not in ss.removed:
        ss.staged[key] = {"file_name": file_name.split("/")[-1], "bytes": data,
                          "name": name or _guess_name(file_name.split("/")[-1]),
                          "date": date.fromisoformat(sub_date) if sub_date else date.today(), "exp": exp}


# --------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("⚙️ Evaluation settings")
    provider = st.selectbox("LLM provider", list(config.LLM_PROVIDERS), index=0, format_func=display_name,
                            help="Offline Demo needs no API key and is fully reproducible.")
    spec = config.LLM_PROVIDERS[provider]
    api_key, model, fault_target = None, spec["default_model"], None
    if spec["key"]:
        model = st.text_input("Model", value=_secret(f"{spec['key'].split('_')[0]}_MODEL") or spec["default_model"])
        api_key = _secret(spec["key"])
        if api_key:
            st.success(f"{spec['key']} loaded from secrets.")
        else:
            api_key = st.text_input(f"{provider} API key", type="password",
                                    help="Used for this session only; never stored.")

    ranking_mode = config.DEFAULT_RANKING_MODE
    st.caption(f"**Ranking order:** {config.RANKING_MODES[ranking_mode]}")

    st.divider()
    st.subheader("🗂️ Run history")
    runs = database.list_runs()
    if runs:
        labels = {r["rfp_run_id"]: f"{r['rfp_run_id']} · {r['suppliers']} suppliers · winner: {r['winner'] or '-'}"
                  for r in runs if r["status"] != "FAILED"}
        if labels:
            pick = st.selectbox("Previous runs", list(labels), format_func=labels.get)
            if st.button("Load selected run", width="stretch"):
                ss.run = database.load_run(pick)
                st.toast(f"Loaded {pick}")
    else:
        st.caption("No runs yet.")


# --------------------------------------------------------------------------- header
theme.header(
    "📑 Agentic RFP Evaluation & Supplier Ranking",
    "The LLM reads each proposal and scores it with evidence. Python validates, calculates, benchmarks "
    "and ranks - deterministically.",
    pills=[f"LLM: {display_name(provider).split(' (')[0]}", "PPI-based peer ranking", "Evidence-backed scores", "SQLite audit trail"])

tab_crit, tab_input, tab_board, tab_peer, tab_card, tab_run = st.tabs(
    ["① Criteria", "② Suppliers & Evaluate", "③ Leaderboard", "④ Peer comparison", "⑤ Scorecards",
     "⑥ Run details"])

# --------------------------------------------------------------------------- 1. criteria
with tab_crit:
    st.subheader("Evaluation criteria")
    st.write("Criteria are stored in SQLite and reloaded at the start of every run. Edit weights, "
             "max scores or active flags here; active weights must total 100%.")
    all_crit = database.get_criteria(active_only=False)
    df = pd.DataFrame(all_crit)[["criterion_id", "name", "description", "weight", "max_score", "is_active"]]
    df["is_active"] = df["is_active"].astype(bool)
    edited = st.data_editor(
        df, hide_index=True, width="stretch", num_rows="dynamic", key=f"crit_editor_{ss.crit_version}",
        column_config={
            "criterion_id": st.column_config.NumberColumn("ID", min_value=1, step=1, required=True),
            "name": st.column_config.TextColumn("Criterion", required=True),
            "description": st.column_config.TextColumn("What the LLM should inspect", width="large", required=True),
            "weight": st.column_config.NumberColumn("Weight %", min_value=0.0, max_value=100.0, step=1.0,
                                                    required=True),
            "max_score": st.column_config.NumberColumn("Max score", min_value=1, step=1, required=True),
            "is_active": st.column_config.CheckboxColumn("Active"),
        })
    active_total = float(edited.loc[edited["is_active"], "weight"].sum())
    c1, c2, c3 = st.columns([1, 1, 2])
    c1.metric("Active criteria", int(edited["is_active"].sum()))
    c2.metric("Active weight total", f"{active_total:g}%",
              delta="OK" if abs(active_total - 100) <= config.WEIGHT_TOLERANCE else f"{active_total - 100:+g}%",
              delta_color="normal" if abs(active_total - 100) <= config.WEIGHT_TOLERANCE else "inverse")
    b1, b2, _ = st.columns([1, 1, 3])
    if b1.button("💾 Save criteria", type="primary", width="stretch"):
        rows = edited.dropna(subset=["criterion_id", "name"]).to_dict("records")
        problems = validate_weights([r for r in rows if r["is_active"]])
        ids = [int(r["criterion_id"]) for r in rows]
        if len(ids) != len(set(ids)):
            problems.append("Criterion IDs must be unique.")
        if any(not str(r.get("description") or "").strip() for r in rows):
            problems.append("Every criterion needs a description (it is sent to the LLM).")
        if problems:
            for p in problems:
                st.error(p)
        else:
            database.save_criteria(rows)
            ss.crit_version += 1
            ss.crit_flash = "Criteria saved. The next run will use them."
            st.rerun()
    if b2.button("↺ Restore defaults", width="stretch"):
        database.reset_criteria()
        ss.crit_version += 1          # new table key = unsaved edits in the browser are discarded
        ss.crit_flash = "Default criteria restored (30 / 20 / 20 / 20 / 10)."
        st.rerun()
    if ss.crit_flash:
        st.success(ss.crit_flash)
        ss.crit_flash = None

# --------------------------------------------------------------------------- 2. input
with tab_input:
    st.subheader("Supplier proposals")
    a, b, _ = st.columns([1.3, 1.3, 3])
    if a.button("📂 Load 5 sample proposals", width="stretch"):
        ss.removed.clear()
        for f, n, d, e in SAMPLE_SUPPLIERS:
            _stage(f, (config.SAMPLE_DIR / f).read_bytes(), n, d, e)
        st.rerun()
    if b.button("🗑️ Clear current files", width="stretch", disabled=not (ss.staged or ss.run),
                help="Removes the loaded PDFs and the current results so you can start fresh. Saved runs stay in Run history."):
        ss.staged.clear()
        ss.removed.clear()
        ss.run = None
        ss.upload_version += 1                       # new uploader key = previously uploaded files are dropped
        for k in [k for k in ss if str(k).startswith(("n_", "d_", "e_", "x_"))]:
            del ss[k]                                # forget edited names/dates/ratings of removed suppliers
        ss.input_flash = "Current files and results cleared. Load the sample proposals or upload PDFs to start again."
        st.rerun()
    if ss.input_flash:
        st.success(ss.input_flash)
        ss.input_flash = None
    uploads = st.file_uploader("Or upload supplier RFP PDFs", type=["pdf"], accept_multiple_files=True,
                               key=f"uploader_{ss.upload_version}")
    for up in uploads or []:
        _stage(up.name, up.getvalue())

    if not ss.staged:
        st.info("Load the sample proposals or upload at least one PDF to begin.")
    else:
        st.markdown("**Supplier metadata** (used for tie-breaks)")
        h = st.columns([2.2, 2.2, 1.4, 1.4, 0.6])
        for col, label in zip(h, ["File", "Supplier name", "Submission date", "Experience (1-5)", ""]):
            col.caption(label)
        for key, item in list(ss.staged.items()):
            col = st.columns([2.2, 2.2, 1.4, 1.4, 0.6])
            col[0].markdown(f"`{item['file_name']}`  \n<small>{len(item['bytes']) / 1024:.0f} KB</small>",
                            unsafe_allow_html=True)
            item["name"] = col[1].text_input("Supplier name", item["name"], key=f"n_{key}",
                                             label_visibility="collapsed")
            item["date"] = col[2].date_input("Submission date", item["date"], key=f"d_{key}",
                                             label_visibility="collapsed")
            item["exp"] = col[3].number_input("Experience", config.EXPERIENCE_MIN, config.EXPERIENCE_MAX,
                                              float(item["exp"]), 0.5, key=f"e_{key}",
                                              label_visibility="collapsed")
            if col[4].button("✕", key=f"x_{key}", help="Remove"):
                del ss.staged[key]
                ss.removed.add(key)
                st.rerun()

        suppliers = [SupplierInput(supplier_name=v["name"].strip(), submission_date=v["date"],
                                   experience_rating=v["exp"], file_name=v["file_name"], file_bytes=v["bytes"])
                     for v in ss.staged.values()]
        problems = validate_inputs(suppliers) + validate_weights(database.get_criteria())
        if spec["key"] and not api_key:
            problems.append(f"Enter a {provider} API key in the sidebar, or switch to Offline Demo.")
        for p in problems:
            st.warning(p)

        go = st.button(f"🚀 Evaluate {len(suppliers)} supplier(s)", type="primary", disabled=bool(problems))
        if go:
            try:
                client = build_client(provider, api_key, model, fault_target)
                bar = st.progress(0.0, "Starting run")
                result = run_evaluation(suppliers, client, ranking_mode,
                                        progress=lambda f, m: bar.progress(min(f, 1.0), m))
                ss.run = result
                win = result["suppliers"][0]
                st.success(f"Run **{result['rfp_run_id']}** complete. Recommended supplier: "
                           f"**{win['supplier_name']}** (PPI {win['ppi']:.2f}). Open the Leaderboard tab.")
                failed = [s["supplier_name"] for s in result["suppliers"] if s["llm_status"] == "failed"]
                if failed:
                    st.error("The LLM could not evaluate: " + ", ".join(failed) +
                             ". Those suppliers were scored 0 - see Run details for the reason.")
                if result["warnings"]:
                    st.warning(f"{len(result['warnings'])} validation warning(s) recorded - see Run details.")
            except RunAborted as exc:
                for e in exc.errors:
                    st.error(e)
            except LLMError as exc:
                st.error(str(exc))

run = ss.run


def _need_run() -> bool:
    if not run:
        st.info("No results yet. Run an evaluation in tab ② or load a previous run from the sidebar.")
        return False
    return True


# --------------------------------------------------------------------------- 3. leaderboard
with tab_board:
    if _need_run():
        top = run["suppliers"][0]
        k = st.columns(4)
        k[0].metric("Recommended supplier", top["supplier_name"])
        k[1].metric("Top PPI", f"{top['ppi']:.2f}")
        k[2].metric("Top absolute score", f"{max(s['absolute_score'] for s in run['suppliers']):.2f}")
        k[3].metric("Suppliers ranked", len(run["suppliers"]))
        st.caption(f"Run `{run['rfp_run_id']}` · ranking rule: {run['ranking_rule']}")

        board = leaderboard.render_table(run)
        st.markdown("**Why this order**")
        for line in run["tie_break_explanation"]:
            st.markdown(f"- {line}")
        chart = board.set_index("Supplier")[["Absolute score", "PPI"]]
        st.bar_chart(chart, stack=False, height=320)

# --------------------------------------------------------------------------- 4. scorecards
with tab_card:
    if _need_run():
        names = [s["supplier_name"] for s in run["suppliers"]]
        name = st.selectbox("Supplier", names, format_func=lambda n: f"#{names.index(n) + 1} {n}")
        s = next(x for x in run["suppliers"] if x["supplier_name"] == name)
        m = st.columns(4)
        m[0].metric("Final rank", f"#{s['final_rank']}")
        m[1].metric("Absolute score", f"{s['absolute_score']:.2f} / 100")
        m[2].metric("PPI", f"{s['ppi']:.2f}")
        m[3].metric("LLM status", s["llm_status"])
        if s.get("rank_reason"):
            st.caption(f"Position vs next supplier: {s['rank_reason']}")

        rows = pd.DataFrame([{
            "Criterion": c["name"], "Weight %": c["weight"], "Score": c["score"], "Max": c["max_score"],
            "Benchmark": c["benchmark"], "Gap": c["gap"], "Relative %": c["relative_pct"],
            "Weighted pts": c["weighted_points"],
            "Evidence": "✓ verified" if c["evidence_verified"] else ("⚠ unverified" if c["evidence"] else "— none"),
            "Normalised": "yes" if c["normalized"] else "",
        } for c in s["criteria"]])
        st.dataframe(rows, hide_index=True, width="stretch",
                     column_config={"Relative %": st.column_config.NumberColumn(format="%.2f")})
        st.caption("Absolute score = Σ weighted pts. PPI = Σ(Relative % × Weight) / Σ Weight.")

        st.markdown("**Evidence and justification**")
        for c in s["criteria"]:
            badge = "🏆 benchmark leader" if c["is_benchmark_leader"] else f"gap {c['gap']:+g}"
            with st.expander(f"{c['name']} — {c['score']:g}/{c['max_score']} ({badge})"):
                st.write(c["justification"])
                if c["evidence"]:
                    st.markdown(f"> {c['evidence']}")
                    st.caption("✓ Quote found in the supplier document." if c["evidence_verified"]
                               else "⚠ Quote could not be matched to the document text.")
                for n in c["notes"]:
                    st.caption(f"• {n}")
        if s["overall_summary"]:
            st.markdown("**Summary**")
            st.write(s["overall_summary"])
        if s["risks"]:
            st.markdown("**Risks identified**")
            for r in s["risks"]:
                st.markdown(f"- {r}")
        if s["warnings"]:
            with st.expander(f"⚠ {len(s['warnings'])} validation warning(s) for this supplier"):
                for w in s["warnings"]:
                    st.write(w)

# --------------------------------------------------------------------------- 5. run details
with tab_peer:
    if _need_run():
        peer_comparison.render(run)

with tab_run:
    if _need_run():
        d = st.columns(4)
        d[0].metric("Suppliers evaluated", len(run["suppliers"]))
        d[1].metric("Status", run["status"].replace("_", " ").title())
        d[2].metric("LLM", display_name(run["llm"]["provider"]).split(" (")[0])
        d[3].metric("Warnings", len(run["warnings"]))
        st.markdown(f"**RFP_RUN_ID:** `{run['rfp_run_id']}`")
        st.caption(f"Created {run['created_at']} UTC · model `{run['llm']['model']}` · "
                   f"temperature {run['llm']['temperature']}")

        st.download_button("⬇️ Download complete result (JSON)", data=json.dumps(run, indent=2),
                           file_name=f"{run['rfp_run_id']}.json", mime="application/json", type="primary")

        st.markdown("**Ranking rule and tie-break explanation**")
        st.write(run["ranking_rule"])
        for line in run["tie_break_explanation"]:
            st.markdown(f"- {line}")

        left, right = st.columns(2)
        with left:
            st.markdown("**Criteria used in this run**")
            st.dataframe(pd.DataFrame(run["criteria"])[["criterion_id", "name", "weight", "max_score"]],
                         hide_index=True, width="stretch")
        with right:
            st.markdown("**Benchmarks (best score per criterion)**")
            st.dataframe(pd.DataFrame(run["benchmarks"]), hide_index=True, width="stretch")

        st.markdown("**Formulas**")
        st.table(pd.DataFrame(run["formulas"].items(), columns=["Metric", "Formula"]))

        st.markdown(f"**Warnings ({len(run['warnings'])})**")
        if run["warnings"]:
            for w in run["warnings"]:
                st.markdown(f"- {w}")
        else:
            st.write("None - every scorecard passed validation unchanged.")

        st.markdown("**Agent trace**")
        st.dataframe(pd.DataFrame(run["agent_trace"]), hide_index=True, width="stretch")
        with st.expander("Raw JSON"):
            st.json(run, expanded=False)
