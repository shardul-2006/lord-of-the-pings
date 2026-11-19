"""RAG-Shield demo UI.  Run:  streamlit run app/streamlit_app.py

Documents tab: upload (or try a sample) -> status badge -> vulnerable vs defended answers ->
alerts -> evidence overlay -> review queue -> optional decision-integrity check.
Dataset Gate tab: screen a CSV/JSONL dataset before indexing or fine-tuning.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import streamlit as st

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:  # `streamlit run` does not add the repo root
    sys.path.insert(0, str(REPO))

from rag_shield.integrity.decision_check import check as integrity_check  # noqa: E402
from rag_shield.rag.compare import answer_both  # noqa: E402
from rag_shield.rag.llm import get_llm  # noqa: E402
from rag_shield.rag.pipeline import DEFAULT_QUESTION  # noqa: E402
from rag_shield.shield import ATLAS_TAG, OWASP_TAG, Shield  # noqa: E402

FIXTURES = REPO / "data" / "fixtures"
DEMO_DATASET = REPO / "data" / "synthetic_dataset" / "poisoned.jsonl"
SAMPLES = {
    "Poisoned resume: hidden 0.5 pt white text": "smoke_poisoned.pdf",
    "Clean resume with trigger words (system override...)": "smoke_trigger_words.pdf",
    "Clean resume": "smoke_clean.pdf",
    "Visible injected instruction": "visible_injection.pdf",
    "Text placed off the page": "off_page.pdf",
    "Instruction in PDF metadata": "metadata_payload.pdf",
    "Hidden comment in Markdown": "hidden_comment.md",
    "Encrypted PDF (blocked)": "encrypted.pdf",
    "Text file named .pdf (blocked)": "not_a_pdf.pdf",
}
# status -> (colour, badge text, meaning). Colour AND text, so it reads without colour.
BADGES = {
    "clean": ("#1a7f37", "CLEAN", "Scan completed, low risk. Eligible for defended retrieval."),
    "flagged": ("#cf222e", "FLAGGED",
                "High-risk sentence(s) quarantined. Only those sentences are withheld; "
                "the facts stay available."),
    "review_required": ("#9a6700", "REVIEW REQUIRED",
                        "Ambiguous sentence(s) held back until a person reviews them."),
    "unsupported": ("#57606a", "UNSUPPORTED: BLOCKED",
                    "File type or content not supported. Never used for defended answers."),
    "scan_failed": ("#57606a", "SCAN FAILED: BLOCKED",
                    "The scan errored or timed out. Never treated as clean."),
}
BLOCKED = ("unsupported", "scan_failed")


def badge(status: str) -> str:
    colour, text, _ = BADGES.get(status, ("#57606a", status.upper(), ""))
    return (f'<span style="background:{colour};color:#fff;padding:3px 10px;border-radius:6px;'
            f'font-weight:700">{text}</span> <code>{status}</code>')


@st.cache_resource
def get_shield(tier: str, home: str) -> Shield:
    return Shield(source_tier=tier, home=home)


def ingest_bytes(shield: Shield, name: str, data: bytes) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="rag_shield_ui_"))
    try:
        path = tmp / f"upload{Path(name).suffix.lower()}"
        path.write_bytes(data)
        return shield.ingest(path, source_name=name).to_dict()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # no persistent upload storage


def screen_dataset_bytes(shield: Shield, name: str, data: bytes) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="rag_shield_ds_"))
    try:
        path = tmp / f"dataset{Path(name).suffix.lower()}"
        path.write_bytes(data)
        rep = shield.screen_dataset(path, tmp / "out")
        out = {"summary": rep.to_dict(), "report": None, "screened": ""}
        if rep.status == "completed":
            out["report"] = json.loads((tmp / "out" / "report.json").read_text(encoding="utf-8"))
            out["screened"] = (tmp / "out" / "screened.jsonl").read_text(encoding="utf-8")
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def sidebar() -> tuple[str, str, str]:
    with st.sidebar:
        st.header("Settings")
        tier = st.selectbox("Source tier", ["external_upload", "internal_kb"],
                            help="External uploads are screened more strictly than internal "
                                 "pages.")
        real_ok = bool(os.environ.get("RAG_SHIELD_LLM")
                       and os.environ.get("RAG_SHIELD_LLM_MODEL"))
        llm_choice = st.radio(
            "Language model", ["mock", "real"] if real_ok else ["mock"],
            help="mock = deterministic test double. real = the model configured with "
                 "RAG_SHIELD_LLM / RAG_SHIELD_LLM_MODEL (e.g. ollama + llama3.1:8b).")
        if not real_ok:
            st.caption("Set RAG_SHIELD_LLM=ollama and RAG_SHIELD_LLM_MODEL=llama3.1:8b to "
                       "enable a real model.")
        reviewer = st.text_input("Reviewer name", value="reviewer")
        st.subheader("Status legend")
        for status, (_, _, meaning) in BADGES.items():
            st.markdown(f"{badge(status)}<br><small>{meaning}</small>", unsafe_allow_html=True)
    return tier, llm_choice, reviewer


def dataset_tab(shield: Shield) -> None:
    st.header("Dataset Gate")
    st.write("Screen a text dataset (CSV or JSONL with a `text` column, optional `label`, "
             "`source`, `id`) before it is indexed or used for fine-tuning. Suspicious rows are "
             "quarantined, never deleted, and every decision is in the report.")
    up = st.file_uploader("Dataset", type=["csv", "jsonl"], key="dataset_upload")
    c1, c2 = st.columns(2)
    if up is not None and c1.button("Screen dataset", key="screen_dataset"):
        st.session_state.dataset = screen_dataset_bytes(shield, up.name, up.getvalue())
    if c2.button("Try the planted demo dataset", key="demo_dataset"):
        if DEMO_DATASET.exists():
            with st.spinner("Screening 1,000 rows..."):
                st.session_state.dataset = screen_dataset_bytes(
                    shield, DEMO_DATASET.name, DEMO_DATASET.read_bytes())
        else:
            st.error("Demo dataset missing: run `python scripts/make_poisoned_dataset.py`.")
    ds = st.session_state.get("dataset")
    if not ds:
        return
    s = ds["summary"]
    if s["status"] != "completed":
        st.markdown(badge("scan_failed"), unsafe_allow_html=True)
        st.warning(f"Dataset could not be screened: {s['reason']}")
        return
    m = st.columns(4)
    m[0].metric("Rows", s["total"])
    m[1].metric("Quarantined", s["quarantined"])
    m[2].metric("Exact duplicates", s["duplicates"])
    m[3].metric("Near duplicates (flagged)", s["near_duplicates"])
    st.subheader("Suspicious tokens")
    st.write(", ".join(f"`{t}`" for t in s["trigger_tokens"]) or "None found.")
    stats = [t for t in ds["report"]["trigger_token_stats"] if t["masked_disagreement"] >= 0.2]
    if stats:
        st.dataframe(stats, hide_index=True)
    st.caption("A token is flagged when almost all its rows share one label AND the rest of "
               "those rows' text points to the other label.")
    st.subheader("Flagged rows")
    st.dataframe(ds["report"]["samples"], hide_index=True)
    st.download_button("Download report.json", json.dumps(ds["report"], indent=2),
                       file_name="report.json", mime="application/json")
    st.download_button("Download screened.jsonl", ds["screened"],
                       file_name="screened.jsonl", mime="application/json")
    st.caption("Limit: statistical screening cannot guarantee a clean dataset; backdoors "
               "without an obvious trigger can pass.")


def documents_tab(shield: Shield, tier: str, llm_choice: str, reviewer: str) -> None:
    state = st.session_state
    st.header("1. Upload a document")
    st.write("PDF, Markdown or HTML. The file is checked, canonicalized and scanned sentence "
             "by sentence. Or try one of the prepared samples.")
    up_col, sample_col = st.columns(2)
    with up_col:
        uploaded = st.file_uploader("Upload", type=["pdf", "md", "markdown", "html", "htm"])
        if uploaded is not None and st.button("Scan upload", key="scan_upload"):
            state.result = ingest_bytes(shield, uploaded.name, uploaded.getvalue())
            state.filename = uploaded.name
    with sample_col:
        sample = st.selectbox("Sample", list(SAMPLES), key="sample")
        if st.button("Try this sample", key="try_sample"):
            path = FIXTURES / SAMPLES[sample]
            if path.exists():
                state.result = ingest_bytes(shield, path.name, path.read_bytes())
                state.filename = path.name
            else:
                st.error("Samples missing: run `python scripts/make_fixtures.py`.")

    result = state.get("result")
    if not result:
        st.info("No document scanned yet.")
        return
    doc_id = result["doc_id"]
    st.markdown(f"**{state.get('filename', '')}** &nbsp; {badge(result['status'])}",
                unsafe_allow_html=True)
    st.caption(BADGES.get(result["status"], ("", "", ""))[2])
    if result["status"] in BLOCKED:
        st.warning(f"Blocked from defended retrieval: {result['reason']}. "
                   "Options: retry with a supported file, reject it, or review it manually.")
        return
    doc = shield.ledger.get_document(doc_id) or {}

    st.header("2. Ask the same question to both pipelines")
    st.write("Left: an ordinary RAG pipeline that reads everything. Right: the same model and "
             "settings, but it only sees screened text.")
    question = st.text_input("Question", value=DEFAULT_QUESTION)
    spot = st.checkbox("Spotlight the defended context (Layer 3)", value=False)
    if st.button("Compare", key="compare") and doc.get("forensic_path"):
        chunks = shield.chunks_for(doc_id)
        with st.spinner("Asking both pipelines..."):
            traces = answer_both(doc["forensic_path"], chunks,
                                 f"shield:{shield.policy['version']}", get_llm(llm_choice),
                                 question, tier if spot else None)
        retrieved = [c for c in chunks if c.chunk_id in traces["defended"].retrieved_chunk_ids]
        state.answers = {k: t.to_dict() for k, t in traces.items()}
        state.output_check = shield.validate_output(traces["defended"].output,
                                                    retrieved).to_dict()
    answers = state.get("answers")
    if answers and answers["vulnerable"]["doc_sha256"] == doc.get("sha256"):
        left, right = st.columns(2)
        with left:
            st.subheader("Vulnerable pipeline")
            st.write(answers["vulnerable"]["output"])
            with st.expander("Trace"):
                st.json(answers["vulnerable"])
        with right:
            st.subheader("Defended pipeline")
            st.write(answers["defended"]["output"])
            oc = state.get("output_check") or {}
            if oc.get("canary_leak") or oc.get("stripped"):
                st.error(f"Output check: canary leak={oc.get('canary_leak')}, "
                         f"removed {len(oc.get('stripped', []))} link(s)/image(s).")
            if oc.get("ungrounded"):
                st.caption(f"{len(oc['ungrounded'])} answer sentence(s) without a valid "
                           "citation.")
            with st.expander("Trace"):
                st.json(answers["defended"])

    st.header("3. Alerts")
    st.write("Each withheld sentence, the signals that fired, its risk score and status.")
    items = [i for i in shield.review_items() if i["doc_id"] == doc_id]
    findings = {f["sentence_id"]: f for f in shield.ledger.findings_for(doc_id)}
    if not items:
        st.success("Nothing withheld in this document.")
    for it in items:
        f = findings.get(it["sentence_id"], {})
        signals = sorted({s["type"] for s in f.get("signals", [])}) or ["wording only"]
        st.markdown(f"{badge('flagged' if it['status'] == 'quarantined' else 'review_required')}"
                    f" &nbsp; **SECURITY ALERT** &nbsp; score `{it['score']}`",
                    unsafe_allow_html=True)
        st.markdown(f"> {it['text']}")
        st.caption(f"Signals: {', '.join(signals)} | Tags: {OWASP_TAG}; {ATLAS_TAG}")
        st.caption(f"Reason: {it['decision_reason']}")

    st.header("4. Evidence overlay")
    st.write("The original page with withheld sentences boxed. Hidden text is invisible on the "
             "page; the box shows where it sits.")
    if doc.get("media_type") == "application/pdf":
        page = st.number_input("Page", min_value=1, value=1, step=1)
        try:
            st.image(shield.overlay(doc_id, int(page)), caption=f"Page {page}")
        except (ValueError, FileNotFoundError) as e:
            st.warning(str(e))
    else:
        st.caption("Overlay is available for PDF documents.")

    st.header("5. Review queue")
    st.write("Release a false positive (the index is rebuilt first, then the sentence becomes "
             "available) or keep it quarantined. Every decision is logged with your name.")
    for it in items:
        c1, c2, c3 = st.columns([6, 1, 1])
        c1.write(it["text"])
        if c2.button("Release", key=f"rel_{it['sentence_id']}"):
            out = shield.release(it["sentence_id"], reviewer)
            st.toast(f"Released: index version {out['index_version']}" if out["released"]
                     else f"Not released: {out.get('reason')}")
            st.rerun()
        if c3.button("Keep quarantined", key=f"keep_{it['sentence_id']}"):
            st.toast("Kept quarantined.")
    for e in [e for e in shield.ledger.events(doc_id) if e["action"] == "release"]:
        st.caption(f"Released {e['sentence_id']} by {e['actor']} at {e['at']}")

    st.header("6. Decision-integrity check")
    st.write("Scores the candidate with and without the suspicious text. A big swing means the "
             "text may be steering the decision. Results say 'possible decision influence', "
             "not proof of an attack.")
    if st.toggle("Run decision-integrity check", key="integrity") and doc.get("forensic_path"):
        with st.spinner("Scoring with and without the suspicious text..."):
            r = integrity_check("Score this candidate for a software engineer role",
                                doc["forensic_path"], get_llm(llm_choice))
        st.metric(r.label, "yes" if r.possible_decision_influence else "no",
                  delta=f"{r.delta:+.1f} points")
        st.caption(f"{r.reason}. Status: {r.status}. Runs per condition: "
                   f"{r.variance.get('runs_per_condition', '-')}.")


st.set_page_config(page_title="RAG-Shield", layout="wide")
st.title("RAG-Shield")
st.caption("Sits between your documents and the AI: finds hidden or command-like sentences, "
           "locks away only those (reversibly), keeps the real facts, and shows its evidence.")
tier_, llm_, reviewer_ = sidebar()
home_ = os.environ.get("RAG_SHIELD_HOME") or str(Path.home() / ".rag_shield")
shield_ = get_shield(tier_, home_)
docs_tab, data_tab = st.tabs(["Documents", "Dataset Gate"])
with data_tab:
    dataset_tab(shield_)
with docs_tab:
    documents_tab(shield_, tier_, llm_, reviewer_)
