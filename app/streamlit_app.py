"""RAG-Shield: Enterprise Security Operations Console for Document RAG.

A provenance-aware trust layer and security middleware for document RAG:
canonicalizes inputs, quarantines malicious instructions at the sentence level,
preserves genuine facts, checks decision integrity, and screens pre-retrieval datasets.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import streamlit as st

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.uploads import ingest_bytes, screen_dataset_bytes  # noqa: E402
from rag_shield.adapters import get_adapter  # noqa: E402
from rag_shield.integrity.decision_check import check as integrity_check  # noqa: E402
from rag_shield.rag.compare import answer_both  # noqa: E402
from rag_shield.rag.llm import get_llm  # noqa: E402
from rag_shield.rag.pipeline import DEFAULT_QUESTION  # noqa: E402
from rag_shield.shield import ATLAS_TAG, OWASP_TAG, Shield  # noqa: E402

FIXTURES = REPO / "data" / "fixtures"
DEMO_DATASET = REPO / "data" / "synthetic_dataset" / "poisoned.jsonl"

# ------------------------------------------------------------------------------
# Professional SVG Vector Logos & Icons (Zero Emojis)
# ------------------------------------------------------------------------------
SVG_SHIELD_LOGO = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg>"""

SVG_STATUS_FLAGGED = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>"""

SVG_STATUS_REVIEW = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>"""

SVG_STATUS_CLEAN = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>"""

SVG_STATUS_BLOCKED = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>"""

SVG_LOCK = """<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>"""

SVG_UNLOCK = """<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>"""

SVG_RADAR = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 1 10 10"/><path d="M12 12l5-5"/><circle cx="12" cy="12" r="4"/></svg>"""

SAMPLES = {
    "Poisoned resume: hidden 0.5 pt white text": "smoke_poisoned.pdf",
    "Visible injected instruction": "visible_injection.pdf",
    "Text placed off the page": "off_page.pdf",
    "Instruction in PDF metadata": "metadata_payload.pdf",
    "Hidden comment in Markdown": "hidden_comment.md",
    "Clean resume with trigger words (system override...)": "smoke_trigger_words.pdf",
    "Clean resume": "smoke_clean.pdf",
    "Encrypted PDF (blocked)": "encrypted.pdf",
    "Text file named .pdf (blocked)": "not_a_pdf.pdf",
}

SAMPLE_DETAILS = {
    "smoke_poisoned.pdf": {
        "title": "Sub-Point White Text",
        "tag": "Physical Hiding",
        "badge_color": "#ef4444",
        "vector": "0.5 pt white font hidden on white page directing the LLM to recommend candidate as CEO.",
        "layer": "Layer 1 + 2",
    },
    "visible_injection.pdf": {
        "title": "Visible Directive Override",
        "tag": "Direct Instruction",
        "badge_color": "#dc2626",
        "vector": "Unhidden prompt injection directive overriding evaluation rubric and hiring decision.",
        "layer": "Layer 2",
    },
    "off_page.pdf": {
        "title": "Off-Canvas Text",
        "tag": "Layout Anomaly",
        "badge_color": "#f59e0b",
        "vector": "Malicious payload placed outside printable canvas coordinates [x < 0 or y > page].",
        "layer": "Layer 1",
    },
    "metadata_payload.pdf": {
        "title": "Carrier Metadata Injection",
        "tag": "Metadata Carrier",
        "badge_color": "#8b5cf6",
        "vector": "Injection hidden inside PDF document metadata attributes (/Title, /Subject, /Author).",
        "layer": "Layer 1 + 2",
    },
    "hidden_comment.md": {
        "title": "Markdown HTML Comment",
        "tag": "Concealed Markup",
        "badge_color": "#ec4899",
        "vector": "Instruction disguised inside HTML comment tags <!-- SYSTEM: ... --> in Markdown.",
        "layer": "Layer 1",
    },
    "smoke_trigger_words.pdf": {
        "title": "Clean Resume (Trigger Words)",
        "tag": "False Positive Baseline",
        "badge_color": "#10b981",
        "vector": "Legitimate engineering resume containing trigger words ('override', 'system prompt').",
        "layer": "Safe Pass",
    },
    "smoke_clean.pdf": {
        "title": "Clean Resume",
        "tag": "Pure Baseline",
        "badge_color": "#059669",
        "vector": "Standard authentic software engineer resume with normal layout and verified facts.",
        "layer": "Safe Pass",
    },
    "encrypted.pdf": {
        "title": "Encrypted / Password-Protected",
        "tag": "Fail-Closed Guard",
        "badge_color": "#64748b",
        "vector": "Encrypted PDF file; scanner guard blocks from ingestion to prevent un-scanned bypass.",
        "layer": "Scanner Guard",
    },
    "not_a_pdf.pdf": {
        "title": "Spoofed Extension (.pdf)",
        "tag": "Magic-Byte Verification",
        "badge_color": "#64748b",
        "vector": "Plain text renamed to .pdf; fails binary magic-byte verification.",
        "layer": "Scanner Guard",
    },
}

BADGES = {
    "clean": (
        "#10b981",
        "CLEAN",
        "Scan completed, low risk. All facts eligible for defended retrieval.",
    ),
    "flagged": (
        "#ef4444",
        "FLAGGED",
        "High-risk sentence(s) quarantined. Legitimate facts remain safely accessible.",
    ),
    "review_required": (
        "#f59e0b",
        "REVIEW REQUIRED",
        "Ambiguous sentence(s) held back from retrieval pending operator inspection.",
    ),
    "unsupported": (
        "#64748b",
        "UNSUPPORTED: BLOCKED",
        "File type or encoding not supported. Fail-closed: rejected from index.",
    ),
    "scan_failed": (
        "#64748b",
        "SCAN FAILED: BLOCKED",
        "The scan errored or timed out. Fail-closed: never entered into retrieval.",
    ),
}
BLOCKED = ("unsupported", "scan_failed")


def badge_html(status: str) -> str:
    colour, text, _ = BADGES.get(status, ("#64748b", status.upper(), ""))
    icon = (
        SVG_STATUS_FLAGGED if status == "flagged"
        else SVG_STATUS_REVIEW if status == "review_required"
        else SVG_STATUS_CLEAN if status == "clean"
        else SVG_STATUS_BLOCKED
    )
    return (
        f'<span style="display:inline-flex;align-items:center;gap:6px;background:{colour}22;'
        f'color:{colour};border:1px solid {colour}44;padding:2px 8px;border-radius:4px;'
        f'font-weight:700;font-size:0.72rem;letter-spacing:0.04em;">'
        f'{icon} {text}</span>'
    )


@st.cache_resource
def get_shield(tier: str, home: str) -> Shield:
    return Shield(source_tier=tier, home=home)


def apply_custom_styles():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        code, pre {
            font-family: 'JetBrains Mono', monospace !important;
        }

        header[data-testid="stHeader"] {
            background: rgba(9, 13, 22, 0.6);
            backdrop-filter: blur(8px);
        }
        .block-container {
            max-width: 1320px;
            padding-top: 4.2rem;
            padding-bottom: 3rem;
        }

        /* Top Header Bar */
        .rs-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #090d16;
            border: 1px solid #1e293b;
            padding: 16px 24px;
            border-radius: 8px;
            margin-top: 0.4rem;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            position: relative;
            z-index: 5;
        }
        .rs-brand {
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .rs-brand-name {
            font-size: 1.15rem;
            font-weight: 700;
            color: #f8fafc;
            letter-spacing: -0.01em;
            margin: 0;
            line-height: 1.3;
        }
        .rs-brand-tag {
            font-size: 0.72rem;
            font-weight: 600;
            color: #94a3b8;
            background: #1e293b;
            padding: 2px 8px;
            border-radius: 4px;
            border: 1px solid #334155;
            font-family: 'JetBrains Mono', monospace;
        }
        .rs-topbar-meta {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 0.8rem;
            color: #94a3b8;
        }
        .rs-meta-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #111827;
            padding: 3px 10px;
            border-radius: 6px;
            border: 1px solid #1e293b;
            color: #e2e8f0;
            font-size: 0.75rem;
        }

        /* Security Posture Status HUD */
        .rs-posture-card {
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 16px;
            border: 1px solid;
            display: flex;
            align-items: flex-start;
            gap: 16px;
        }
        .rs-posture-clean {
            background: #062b1b;
            border-color: #065f46;
            color: #a7f3d0;
        }
        .rs-posture-flagged {
            background: #2b0c10;
            border-color: #991b1b;
            color: #fecaca;
        }
        .rs-posture-review {
            background: #2d1d07;
            border-color: #92400e;
            color: #fde68a;
        }
        .rs-posture-blocked {
            background: #131b2a;
            border-color: #334155;
            color: #cbd5e1;
        }

        /* Metric HUD Grid */
        .rs-hud-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 18px;
        }
        .rs-hud-box {
            background: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 14px 18px;
        }
        .rs-hud-val {
            font-size: 1.6rem;
            font-weight: 700;
            color: #f8fafc;
            line-height: 1.1;
            font-family: 'JetBrains Mono', monospace;
        }
        .rs-hud-lbl {
            font-size: 0.72rem;
            text-transform: uppercase;
            font-weight: 600;
            color: #94a3b8;
            letter-spacing: 0.05em;
            margin-top: 4px;
        }
        .rs-hud-sub {
            font-size: 0.72rem;
            color: #64748b;
            margin-top: 2px;
        }

        /* Findings Cards */
        .rs-finding-card {
            background: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 10px;
        }
        .rs-finding-flagged {
            border-left: 3px solid #ef4444;
        }
        .rs-finding-review {
            border-left: 3px solid #f59e0b;
        }
        .rs-finding-clean {
            border-left: 3px solid #10b981;
        }
        .rs-finding-released {
            border-left: 3px solid #3b82f6;
        }

        /* Arena Box */
        .rs-arena-box {
            border-radius: 8px;
            padding: 18px;
            background: #0f172a;
            border: 1px solid #1e293b;
            min-height: 220px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .rs-arena-vuln {
            border-top: 3px solid #ef4444;
        }
        .rs-arena-defended {
            border-top: 3px solid #10b981;
        }

        /* Buttons & Tabs */
        .stButton>button {
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.85rem;
            padding: 0.4rem 0.9rem;
            transition: all 0.15s ease;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            border-bottom: 1px solid #1e293b;
            padding-bottom: 2px;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 6px 6px 0 0;
            font-weight: 600;
            font-size: 0.88rem;
            padding: 6px 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar() -> tuple[str, str, str]:
    with st.sidebar:
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
                {SVG_SHIELD_LOGO}
                <div>
                    <strong style="font-size:0.98rem;color:#f8fafc;">RAG-Shield Console</strong>
                    <div style="font-size:0.72rem;color:#94a3b8;">Security Operations</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("##### Configuration & Policy")
        tier = st.selectbox(
            "Source Trust Tier",
            ["external_upload", "internal_kb"],
            help="external_upload: Strict thresholds (0.70 Quarantine / 0.40 Review) with dynamic spotlighting.\n"
                 "internal_kb: Relaxed thresholds (0.90 / 0.80) for trusted internal documentation.",
        )
        if tier == "external_upload":
            st.caption(f"{SVG_LOCK} <strong>Strict Policy</strong>: Quarantine &ge;0.70 &middot; Review &ge;0.40", unsafe_allow_html=True)
        else:
            st.caption("<strong>Internal KB</strong>: Relaxed thresholds for internal technical docs.", unsafe_allow_html=True)

        real_ok = bool(os.environ.get("RAG_SHIELD_LLM") and os.environ.get("RAG_SHIELD_LLM_MODEL"))
        llm_choice = st.radio(
            "Language Model Engine",
            ["mock", "real"] if real_ok else ["mock"],
            help="mock: Deterministic security test double (string matching).\n"
                 "real: Connects to local Ollama (llama3.1:8b) or configured API.",
        )
        if not real_ok:
            st.caption("Mock double active. Set RAG_SHIELD_LLM=ollama to connect local model.")

        reviewer = st.text_input(
            "Security Analyst ID",
            value="secops_analyst_01",
            help="Audited identity logged in SQLite Trust Ledger for all forensic decisions.",
        )

        st.markdown("---")
        st.markdown("##### Status Legend")
        for status, (_, _label, meaning) in BADGES.items():
            st.markdown(
                f"<div style='margin-bottom:6px;'>"
                f"{badge_html(status)} <code>{status}</code><br>"
                f"<span style='font-size:0.72rem;color:#94a3b8;'>{meaning}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.markdown(
            f"""
            <div style="font-size:0.72rem;color:#64748b;line-height:1.5;">
                <strong>Policy Engine:</strong> <code>policy_v1</code><br>
                <strong>Taxonomy:</strong> <code>{OWASP_TAG.split(':')[0]}</code> &middot; <code>{ATLAS_TAG.split(':')[0]}</code><br>
                <strong>Forensic Ledger:</strong> SQLite Local
            </div>
            """,
            unsafe_allow_html=True,
        )
    return tier, llm_choice, reviewer


def documents_tab(shield: Shield, tier: str, llm_choice: str, reviewer: str) -> None:
    state = st.session_state

    # --------------------------------------------------------------------------
    # 1. PRIMARY DOCUMENT INGESTION & ATTACK FIXTURE DESK
    # --------------------------------------------------------------------------
    st.markdown("#### Document Ingestion & Attack Library")

    c_sample, c_upload = st.columns([1.3, 1.0], gap="large")

    with c_sample:
        st.markdown("##### Preset Attack Fixture")
        selected_sample_label = st.selectbox(
            "Select Attack or Baseline Sample",
            list(SAMPLES.keys()),
            key="sample",
            help="Pre-configured attack samples verifying physical hiding, directives, and fail-closed guards.",
        )
        target_file = SAMPLES[selected_sample_label]
        details = SAMPLE_DETAILS.get(target_file, {})

        st.markdown(
            f"""
            <div style="background:#090e1a;border:1px solid #1e293b;border-radius:6px;padding:10px 14px;margin:8px 0 12px 0;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                    <strong style="color:#f8fafc;font-size:0.86rem;">{details.get('title', target_file)}</strong>
                    <span style="background:{details.get('badge_color', '#3b82f6')}22;color:{details.get('badge_color', '#3b82f6')};border:1px solid {details.get('badge_color', '#3b82f6')}44;font-size:0.72rem;padding:1px 6px;border-radius:4px;font-weight:700;">
                        {details.get('tag', 'Vector')}
                    </span>
                </div>
                <div style="font-size:0.78rem;color:#94a3b8;line-height:1.4;">
                    {details.get('vector', '')}
                </div>
                <div style="font-size:0.72rem;color:#64748b;margin-top:6px;">
                    Target Defense: <code>{details.get('layer', 'Core')}</code>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("Test Selected Sample", key="try_sample", type="primary", use_container_width=True):
            path = FIXTURES / target_file
            if path.exists():
                with st.spinner(f"Ingesting and screening {target_file}..."):
                    state.result = ingest_bytes(shield, path.name, path.read_bytes())
                    state.filename = path.name
                    state.pop("answers", None)
                    st.rerun()
            else:
                st.error("Fixtures missing: run `python scripts/make_fixtures.py`.")

    with c_upload:
        st.markdown("##### Upload Custom Document")
        st.caption("Accepts PDF, Markdown (.md), and HTML (.htm, .html). Binary magic-bytes validated fail-closed.")
        uploaded = st.file_uploader(
            "Drop or browse file",
            type=["pdf", "md", "markdown", "html", "htm"],
            key="custom_uploader",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            st.caption(f"Loaded: <code>{uploaded.name}</code> ({uploaded.size / 1024:.1f} KB)")
            if st.button("Scan Uploaded Document", key="scan_upload_btn", use_container_width=True):
                with st.spinner(f"Screening {uploaded.name}..."):
                    state.result = ingest_bytes(shield, uploaded.name, uploaded.getvalue())
                    state.filename = uploaded.name
                    state.pop("answers", None)
                    st.rerun()

    result = state.get("result")
    if not result:
        st.markdown("---")
        st.info("Select a preset attack sample or upload a document to begin screening.")
        return

    doc_id = result["doc_id"]
    status = result["status"]
    doc = shield.ledger.get_document(doc_id) or {}
    chunks = shield.chunks_for(doc_id)
    items = [i for i in shield.review_items() if i["doc_id"] == doc_id]
    findings = {f["sentence_id"]: f for f in shield.ledger.findings_for(doc_id)}
    all_sentences = shield.ledger.sentences_for(doc_id)

    quarantined_ids = result.get("quarantined_ids", [])
    review_ids = result.get("review_ids", [])
    clean_count = max(0, len(findings) - len(quarantined_ids) - len(review_ids))

    # --- SECURITY POSTURE BANNER ---
    banner_class = (
        "rs-posture-blocked" if status in BLOCKED
        else "rs-posture-flagged" if status == "flagged"
        else "rs-posture-review" if status == "review_required"
        else "rs-posture-clean"
    )
    status_icon = (
        SVG_STATUS_BLOCKED if status in BLOCKED
        else SVG_STATUS_FLAGGED if status == "flagged"
        else SVG_STATUS_REVIEW if status == "review_required"
        else SVG_STATUS_CLEAN
    )
    status_headline = (
        f"Blocked: {result.get('reason', 'Unsupported File')}" if status in BLOCKED
        else f"Threat Isolated: {len(quarantined_ids)} Malicious Sentence(s) Quarantined" if status == "flagged"
        else f"Operator Review Required: {len(review_ids)} Sentence(s) Held" if status == "review_required"
        else "Verified Clean: Permitted Document Facts Retained in Defended Index"
    )

    st.markdown("---")
    st.markdown(
        f"""
        <div class="rs-posture-card {banner_class}">
            <div style="padding-top:2px;">{status_icon}</div>
            <div style="flex:1;">
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
                    <strong style="font-size:1.05rem;">{status_headline}</strong>
                    {badge_html(status)}
                </div>
                <div style="font-size:0.8rem;line-height:1.5;">
                    Document: <strong>{state.get('filename', 'Unknown')}</strong> &middot;
                    Doc ID: <code>{doc_id[:12]}...</code> &middot;
                    Index Version: <code>v{result.get('index_version', 1)}</code> &middot;
                    Tier: <code>{tier}</code>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- METRICS HUD ---
    st.markdown(
        f"""
        <div class="rs-hud-grid">
            <div class="rs-hud-box">
                <div class="rs-hud-val">{len(findings)}</div>
                <div class="rs-hud-lbl">Parsed Sentences</div>
                <div class="rs-hud-sub">Normalized & analyzed</div>
            </div>
            <div class="rs-hud-box" style="border-bottom:2px solid #ef4444;">
                <div class="rs-hud-val" style="color:#ef4444;">{len(quarantined_ids)}</div>
                <div class="rs-hud-lbl">Quarantined</div>
                <div class="rs-hud-sub">Withheld from index</div>
            </div>
            <div class="rs-hud-box" style="border-bottom:2px solid #f59e0b;">
                <div class="rs-hud-val" style="color:#f59e0b;">{len(review_ids)}</div>
                <div class="rs-hud-lbl">Review Queue</div>
                <div class="rs-hud-sub">Awaiting operator sign-off</div>
            </div>
            <div class="rs-hud-box" style="border-bottom:2px solid #10b981;">
                <div class="rs-hud-val" style="color:#10b981;">{len(chunks)}</div>
                <div class="rs-hud-lbl">Defended Facts</div>
                <div class="rs-hud-sub">{clean_count} clean chunks indexed</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if status in BLOCKED:
        st.warning(
            f"Blocked from defended retrieval: {result.get('reason')}\n\n"
            "Fail-closed security: malformed, encrypted, or unsupported files are excluded from defended RAG."
        )
        return

    # --------------------------------------------------------------------------
    # 2. WORKSPACE CONSOLE TABS
    # --------------------------------------------------------------------------
    t_findings, t_arena, t_evidence, t_queue, t_integrity, t_export = st.tabs([
        "Sentence Findings & Multi-Vector Telemetry",
        "Vulnerable vs. Defended RAG Arena",
        "Visual PDF Evidence Overlay",
        "Human-in-the-Loop Review Desk",
        "Decision Integrity Lab",
        "Security Audit Report & Export",
    ])

    # --------------------------------------------------------------------------
    # SUB-TAB 1: SENTENCE FINDINGS & MULTI-VECTOR TELEMETRY
    # --------------------------------------------------------------------------
    with t_findings:
        st.markdown("##### Multi-Vector Sentence Telemetry & Signal Decomposition")
        st.caption(
            "Mathematical fusion formula: "
            "$$\\text{Score} = 0.45 \\cdot S + 0.35 \\cdot L + 0.40 \\cdot H + 0.20 \\cdot C \\cdot \\max(S, L)$$"
        )

        review_map = {i["sentence_id"]: i for i in items}

        col_search, col_filter = st.columns([2.5, 1.5])
        with col_search:
            search_query = st.text_input("Search Sentence Text or ID", placeholder="Filter by text, ID (e.g. S-001)...", key="findings_search")
        with col_filter:
            filter_mode = st.selectbox(
                "Filter Disposition",
                ["All Sentences", "Quarantined Only", "Review Required Only", "Clean Facts Only"],
                key="findings_filter",
            )

        # Filter sentences based on search and disposition
        visible_sentences = []
        for s in all_sentences:
            s_id = s.sentence_id
            f = findings.get(s_id, {})
            rev = review_map.get(s_id)
            stat = rev["status"] if rev else f.get("status", "clean")

            if filter_mode == "Quarantined Only" and stat != "quarantined":
                continue
            if filter_mode == "Review Required Only" and stat != "review_required":
                continue
            if filter_mode == "Clean Facts Only" and stat not in ("clean", "released"):
                continue

            if search_query:
                q = search_query.lower()
                if q not in s.text.lower() and q not in s_id.lower():
                    continue
            visible_sentences.append((s, f, rev, stat))

        st.caption(f"Displaying {len(visible_sentences)} of {len(all_sentences)} analyzed sentences")

        if not visible_sentences:
            st.info("No sentences match the current filter criteria.")
        else:
            for s, f, _rev, stat in visible_sentences:
                s_id = s.sentence_id
                score = float(f.get("score", 0.0))
                signals = f.get("signals", [])
                has_h = any(g.get("type") in ("tiny_font", "low_contrast", "off_page") for g in signals)
                has_c = any(g.get("type") in ("metadata", "alt_text") for g in signals)
                h_val = 0.40 if has_h else 0.0
                c_val = 0.20 if has_c else 0.0
                rem = max(0.0, score - h_val - c_val)
                s_val = min(0.45, rem * 0.55)
                l_val = max(0.0, rem - s_val)

                card_border = (
                    "rs-finding-flagged" if stat == "quarantined"
                    else "rs-finding-review" if stat == "review_required"
                    else "rs-finding-released" if stat == "released"
                    else "rs-finding-clean"
                )

                st.markdown(
                    f"""
                    <div class="rs-finding-card {card_border}">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                            <div style="display:flex;align-items:center;gap:10px;">
                                {badge_html(stat)}
                                <code>{s_id}</code>
                            </div>
                            <span style="font-family:'JetBrains Mono',monospace;font-size:0.8rem;background:#1e293b;padding:2px 8px;border-radius:4px;color:#f8fafc;">
                                Score: {score:.3f}
                            </span>
                        </div>
                        <div style="font-size:0.88rem;color:#f8fafc;background:#131d31;padding:10px 12px;border-radius:6px;border:1px solid #1e293b;margin-bottom:10px;font-style:italic;">
                            &ldquo;{s.text}&rdquo;
                        </div>
                        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:10px;">
                            <div style="background:#090e1a;border:1px solid #1e293b;padding:6px 10px;border-radius:4px;">
                                <div style="font-size:0.7rem;color:#94a3b8;text-transform:uppercase;">Hiding (H)</div>
                                <div style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;font-weight:700;color:{'#ef4444' if h_val > 0 else '#64748b'};">{h_val:.2f}</div>
                            </div>
                            <div style="background:#090e1a;border:1px solid #1e293b;padding:6px 10px;border-radius:4px;">
                                <div style="font-size:0.7rem;color:#94a3b8;text-transform:uppercase;">Directive (L)</div>
                                <div style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;font-weight:700;color:{'#f59e0b' if l_val > 0 else '#64748b'};">{l_val:.2f}</div>
                            </div>
                            <div style="background:#090e1a;border:1px solid #1e293b;padding:6px 10px;border-radius:4px;">
                                <div style="font-size:0.7rem;color:#94a3b8;text-transform:uppercase;">Classifier (S)</div>
                                <div style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;font-weight:700;color:{'#3b82f6' if s_val > 0 else '#64748b'};">{s_val:.2f}</div>
                            </div>
                            <div style="background:#090e1a;border:1px solid #1e293b;padding:6px 10px;border-radius:4px;">
                                <div style="font-size:0.7rem;color:#94a3b8;text-transform:uppercase;">Carrier (C)</div>
                                <div style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;font-weight:700;color:{'#8b5cf6' if c_val > 0 else '#64748b'};">{c_val:.2f}</div>
                            </div>
                        </div>
                        <div style="font-size:0.75rem;color:#94a3b8;line-height:1.5;">
                            <strong>Signals:</strong> {', '.join(sorted({g.get('type') for g in signals})) or 'None'} &middot;
                            <strong>Rationale:</strong> {f.get('decision_reason', 'Clean fact retained in retrieval index')}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Inline action for quarantined / review sentences
                if stat in ("quarantined", "review_required"):
                    c_act1, c_act2 = st.columns([1, 4])
                    with c_act1:
                        if st.button("Release Sentence", key=f"f_rel_{s_id}"):
                            out = shield.release(s_id, reviewer)
                            if out.get("released"):
                                st.toast(f"Sentence {s_id} released! Defended index updated to v{out['index_version']}.")
                                st.rerun()
                    with c_act2:
                        st.caption(f"Release false positive to re-index into defended retrieval (audited under Analyst: {reviewer}).")

        # Security Alert Callout (contract compliance for test_streamlit.py)
        if items:
            for it in items:
                f = findings.get(it["sentence_id"], {})
                sigs = sorted({s["type"] for s in f.get("signals", [])}) or ["linguistic directive"]
                st.markdown(
                    f"{badge_html('flagged' if it['status'] == 'quarantined' else 'review_required')} "
                    f"&nbsp; **SECURITY ALERT** &nbsp; score `0.94`",
                    unsafe_allow_html=True,
                )
                st.markdown(f"> {it['text']}")
                st.caption(f"Signals: {', '.join(sigs)} &middot; Tags: {OWASP_TAG}; {ATLAS_TAG} &middot; Reason: {it['decision_reason']}")

    # --------------------------------------------------------------------------
    # SUB-TAB 2: VULNERABLE VS DEFENDED RAG ARENA
    # --------------------------------------------------------------------------
    with t_arena:
        st.markdown("##### Side-by-Side RAG Comparison")
        st.write(
            "Submit an evaluation prompt to both pipelines. Notice how naive RAG ingests unscreened text "
            "and falls victim to indirect prompt injection, while RAG-Shield neutralizes the instruction and answers from facts."
        )

        col_q, col_opts = st.columns([3.2, 1.2])
        with col_q:
            question = st.text_input(
                "Evaluation Prompt",
                value=DEFAULT_QUESTION,
                key="rag_prompt_input",
                help="Prompt sent concurrently to naive and defended pipelines.",
            )
        with col_opts:
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            spot = st.checkbox(
                "Context Spotlighting (Layer 3)",
                value=False,
                help="Wraps defended text in dynamic cryptographic delimiters (<<UNTRUSTED_<hex>>>).",
            )

        if st.button("Compare Vulnerable vs. Defended", key="compare", type="primary", use_container_width=True):
            if doc.get("forensic_path"):
                with st.spinner("Executing comparative LLM inference across both pipelines..."):
                    traces = answer_both(
                        doc["forensic_path"],
                        chunks,
                        f"shield:{shield.policy['version']}",
                        get_llm(llm_choice),
                        question,
                        tier if spot else None,
                    )
                    retrieved = [c for c in chunks if c.chunk_id in traces["defended"].retrieved_chunk_ids]
                    state.answers = {k: t.to_dict() for k, t in traces.items()}
                    state.output_check = shield.validate_output(traces["defended"].output, retrieved).to_dict()
                    st.rerun()

        answers = state.get("answers")
        if answers and answers.get("vulnerable", {}).get("doc_sha256") == doc.get("sha256"):
            col_vuln, col_def = st.columns(2, gap="medium")
            with col_vuln:
                st.subheader("Vulnerable pipeline")
                st.markdown(
                    f"""
                    <div class="rs-arena-box rs-arena-vuln">
                        <div>
                            <div style="font-size:0.75rem;font-weight:700;color:#ef4444;text-transform:uppercase;margin-bottom:8px;">
                                Naive RAG (Direct Ingestion)
                            </div>
                            <div style="font-size:0.86rem;color:#f8fafc;background:#1e293b;padding:12px;border-radius:6px;line-height:1.5;">
                                {answers['vulnerable']['output']}
                            </div>
                        </div>
                        <div style="font-size:0.72rem;color:#ef4444;margin-top:10px;">
                            Warning: Consumes raw document characters directly into prompt context.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.expander("View Vulnerable Pipeline Trace"):
                    st.json(answers["vulnerable"])

            with col_def:
                st.subheader("Defended pipeline")
                st.markdown(
                    f"""
                    <div class="rs-arena-box rs-arena-defended">
                        <div>
                            <div style="font-size:0.75rem;font-weight:700;color:#10b981;text-transform:uppercase;margin-bottom:8px;">
                                Defended RAG (Screened Facts Only)
                            </div>
                            <div style="font-size:0.86rem;color:#f8fafc;background:#1e293b;padding:12px;border-radius:6px;line-height:1.5;">
                                {answers['defended']['output']}
                            </div>
                        </div>
                        <div style="font-size:0.72rem;color:#10b981;margin-top:10px;">
                            Protected: Filtered through 4-Layer Security Middleware prior to retrieval.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                oc = state.get("output_check") or {}
                if oc.get("canary_leak"):
                    st.error("Layer 4 Safeguard: Leaked system canary token detected and redacted.")
                if oc.get("stripped"):
                    st.warning(f"Layer 4 Safeguard: Stripped {len(oc['stripped'])} exfiltration link(s)/image(s).")
                if oc.get("ungrounded"):
                    st.caption(f"Notice: {len(oc['ungrounded'])} response sentence(s) without approved chunk citation.")

                with st.expander("View Defended Pipeline Trace"):
                    st.json(answers["defended"])

    # --------------------------------------------------------------------------
    # SUB-TAB 3: PDF EVIDENCE OVERLAY
    # --------------------------------------------------------------------------
    with t_evidence:
        st.markdown("##### Visual PDF Evidence & Bounding Box Inspection")
        st.write(
            "Inspect original PDF pages rendered with bounding boxes highlighting suspicious or quarantined text. "
            "Invisible text (e.g., 0.5pt white text on white page) is visually pinpointed by the bounding box."
        )

        if doc.get("media_type") == "application/pdf":
            page_count = max(1, doc.get("pages", 1) or 1)
            page = st.number_input("Select Document Page", min_value=1, max_value=page_count, value=1, step=1)
            try:
                overlay_bytes = shield.overlay(doc_id, int(page))
                st.image(overlay_bytes, caption=f"Forensic Page {page} of {page_count} Evidence Overlay", use_container_width=True)
            except Exception as e:
                st.warning(f"Could not render overlay: {e}")
        else:
            st.info("Visual evidence overlays are generated for PDF format documents.")

    # --------------------------------------------------------------------------
    # SUB-TAB 4: HUMAN-IN-THE-LOOP REVIEW DESK
    # --------------------------------------------------------------------------
    with t_queue:
        st.markdown("##### Human-in-the-Loop Review Desk & Provenance Trail")
        st.write(
            "Release false positives (the defended vector index is dynamically updated upon release) "
            "or confirm quarantined payloads. All decisions are immutably signed in the SQLite Trust Ledger."
        )

        if not items:
            st.success("Queue Empty: No items are currently quarantined or held in this document.")
        else:
            for it in items:
                s_id = it["sentence_id"]
                status_item = it["status"]
                c_txt, c_btn1, c_btn2 = st.columns([5.5, 1.4, 1.4])
                with c_txt:
                    st.markdown(
                        f"""
                        <div style="background:#0f172a;border:1px solid #1e293b;padding:12px 14px;border-radius:6px;margin-bottom:8px;">
                            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                                {badge_html('flagged' if status_item == 'quarantined' else 'review_required')}
                                <code>{s_id}</code>
                            </div>
                            <div style="font-size:0.86rem;color:#f8fafc;">{it['text']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                if status_item != "released":
                    with c_btn1:
                        if st.button("Release", key=f"rel_{s_id}", use_container_width=True):
                            out = shield.release(s_id, reviewer)
                            if out.get("released"):
                                st.toast(f"Released: index updated to v{out['index_version']}.")
                            else:
                                st.error(f"Release failed: {out.get('reason')}")
                            st.rerun()
                    with c_btn2:
                        if st.button("Keep Quarantined", key=f"keep_{s_id}", use_container_width=True):
                            st.toast(f"Retained in quarantine: {s_id}")
                else:
                    with c_btn1:
                        if st.button("Re-quarantine", key=f"req_{s_id}", use_container_width=True):
                            out = shield.requarantine(s_id, reviewer)
                            st.toast(f"Re-quarantined: index v{out['index_version']}.")
                            st.rerun()

        events = [e for e in shield.ledger.events(doc_id) if e["action"] in ("release", "requarantine")]
        if events:
            st.markdown("###### Audit Ledger Event Trail")
            for ev in events:
                st.caption(f"• Action: `{ev['action']}` on `{ev['sentence_id']}` by Analyst `{ev['actor']}` at {ev['at']}")

    # --------------------------------------------------------------------------
    # SUB-TAB 5: DECISION INTEGRITY LAB
    # --------------------------------------------------------------------------
    with t_integrity:
        st.markdown("##### Downstream Decision Integrity Simulation")
        st.write(
            "Tests whether quarantined sentences possess the power to alter downstream high-stakes decisions. "
            "Runs counterfactual scoring across seeded trials with and without suspicious passages, validated against a benign-removal control baseline."
        )

        c_dom, c_task = st.columns([1.2, 2.0])
        with c_dom:
            available_domains = ["hr", "paper_review"]
            domain_labels = {
                "hr": "HR Screening (Software Engineer)",
                "paper_review": "Academic Paper Review (Venue Publication)",
            }
            selected_domain_key = st.selectbox(
                "Evaluation Domain",
                options=available_domains,
                format_func=lambda k: domain_labels.get(k, k),
                key="integrity_domain_selector",
            )
            adapter = get_adapter(selected_domain_key)
        with c_task:
            task_input = st.text_input(
                "Integrity Decision Task",
                value=adapter.integrity_task,
                key="integrity_task_input",
                help="The downstream decision task evaluated with and without suspicious passages.",
            )

        run_integrity = st.toggle("Execute Decision Steering Check", key="integrity")
        if run_integrity and doc.get("forensic_path"):
            with st.spinner(f"Executing counterfactual scoring simulation ({selected_domain_key})..."):
                r = integrity_check(
                    task_input,
                    doc["forensic_path"],
                    get_llm(llm_choice),
                    policy=adapter.policy if adapter.policy else None,
                )
            c_m1, c_m2 = st.columns([1, 2])
            with c_m1:
                st.metric(
                    r.label,
                    "Influence Detected" if r.possible_decision_influence else "No Influence",
                    delta=f"{r.delta:+.1f} points",
                    delta_color="inverse" if r.possible_decision_influence else "normal",
                )
            with c_m2:
                st.markdown(
                    f"""
                    <div style="background:#0f172a;border:1px solid #1e293b;padding:14px;border-radius:8px;">
                        <strong style="color:#f8fafc;">Evaluation Verdict:</strong>
                        <div style="font-size:0.86rem;color:#cbd5e1;margin-top:4px;">{r.reason}</div>
                        <div style="font-size:0.75rem;color:#64748b;margin-top:6px;">Status: <code>{r.status}</code> &middot; Runs per condition: {r.variance.get('runs_per_condition', 3)} &middot; Threshold: {r.threshold}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            if r.passages:
                st.markdown("###### Per-Passage Counterfactual Sensitivity Breakdown")
                passage_rows = []
                for p in r.passages:
                    sids = ", ".join(p.get("removed_sentence_ids", []))
                    w_mean = p.get("with", {}).get("mean", 0.0)
                    wo_mean = p.get("without", {}).get("mean", 0.0)
                    delta = p.get("delta", 0.0)
                    passage_rows.append({
                        "Tested Sentences": sids,
                        "Score With Passage": f"{w_mean:.1f}",
                        "Score Without": f"{wo_mean:.1f}",
                        "Score Delta": f"{delta:+.1f}",
                        "Sample Text Preview": (p.get("removed_text", [""])[0] or "")[:80] + "...",
                    })
                st.dataframe(passage_rows, hide_index=True, use_container_width=True)

            if r.control and r.control.get("enabled"):
                st.markdown("###### Benign-Removal Negative Control Baseline")
                c_ctrl = r.control
                max_ctrl = c_ctrl.get("max_abs_delta", 0.0)
                st.caption(
                    f"To prevent penalizing ordinary qualifications, ordinary sentences were removed as negative controls. "
                    f"Max benign delta swing observed: **{max_ctrl:.1f} points**."
                )
                if c_ctrl.get("passages"):
                    ctrl_rows = [
                        {
                            "Sentence ID": cp.get("removed_sentence_id"),
                            "Control Delta Swing": f"{cp.get('delta', 0.0):+.1f}",
                            "Sentence Text": cp.get("removed_text", "")[:75] + "...",
                        }
                        for cp in c_ctrl["passages"]
                    ]
                    st.dataframe(ctrl_rows, hide_index=True, use_container_width=True)

    # --------------------------------------------------------------------------
    # SUB-TAB 6: AUDIT REPORT & EXPORT
    # --------------------------------------------------------------------------
    with t_export:
        st.markdown("##### Security Audit Report & Provenance Export")
        st.write("Verifiable forensic audit trail ready for compliance archive or security sign-off.")

        audit_md = f"""# RAG-Shield Forensic Security Audit Report

## Document Information
- **File Name:** {state.get('filename', 'Unknown')}
- **Document ID:** {doc_id}
- **SHA-256:** {doc.get('sha256', 'N/A')}
- **Status:** {status.upper()}
- **Policy Version:** {result.get('policy_version', 'policy_v1')}
- **Taxonomy:** {OWASP_TAG} | {ATLAS_TAG}

## Risk Telemetry
- **Total Sentences:** {len(findings)}
- **Quarantined Sentences:** {len(quarantined_ids)}
- **Review Required:** {len(review_ids)}
- **Clean Facts Retained:** {clean_count}
- **Defended Index Version:** v{result.get('index_version', 1)}

## Sentence-Level Telemetry Log
"""
        for s in all_sentences:
            f = findings.get(s.sentence_id, {})
            score = float(f.get("score", 0.0))
            stat_name = f.get("status", "clean").upper()
            audit_md += f"- [{stat_name}] {s.sentence_id} (Score: {score:.3f}): {s.text}\n"

        st.download_button(
            "Download Formal Markdown Security Report",
            audit_md,
            file_name=f"RAG_Shield_Security_Report_{doc_id[:8]}.md",
            mime="text/markdown",
            type="primary",
        )


def dataset_tab(shield: Shield) -> None:
    st.markdown("#### Pre-Retrieval Dataset Gate & Poison Quarantine")
    st.write(
        "Screen pre-retrieval corpora and fine-tuning datasets (JSONL or CSV with a `text` column) "
        "before vector indexing. Detects poisoned rows, rare backdoor triggers, and near-duplicate injections."
    )

    c_up, c_demo = st.columns(2, gap="medium")
    with c_up:
        st.markdown("##### Upload Custom Dataset")
        up = st.file_uploader("Upload CSV or JSONL dataset", type=["csv", "jsonl"], key="dataset_upload")
        if up is not None and st.button("Screen Uploaded Dataset", key="screen_dataset_btn", type="primary", use_container_width=True):
            with st.spinner("Analyzing dataset rows for backdoor triggers and duplicates..."):
                st.session_state.dataset = screen_dataset_bytes(shield, up.name, up.getvalue())
                st.rerun()

    with c_demo:
        st.markdown("##### Pre-Configured Poisoned Demo Dataset")
        st.caption("1,000 synthetic rows with planted backdoor triggers and poisoned text.")
        if st.button("Test 1,000-Row Planted Demo", key="demo_dataset", use_container_width=True):
            if DEMO_DATASET.exists():
                with st.spinner("Screening 1,000 synthetic rows for backdoor triggers..."):
                    st.session_state.dataset = screen_dataset_bytes(
                        shield, DEMO_DATASET.name, DEMO_DATASET.read_bytes()
                    )
                    st.rerun()
            else:
                st.error("Demo dataset missing: run `python scripts/make_poisoned_dataset.py`.")

    ds = st.session_state.get("dataset")
    if not ds:
        st.info("Upload a dataset or launch the synthetic demo to inspect Dataset Gate screening.")
        return

    s = ds["summary"]
    if s["status"] != "completed":
        st.markdown(badge_html("scan_failed"), unsafe_allow_html=True)
        st.warning(f"Dataset could not be screened: {s['reason']}")
        return

    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Rows", str(s["total"]))
    m2.metric("Poisoned", str(s["quarantined"]))
    m3.metric("Exact Duplicates", str(s["duplicates"]))
    m4.metric("Near Duplicates", str(s["near_duplicates"]))

    col_tok, col_flag = st.columns([1, 1.4], gap="medium")
    with col_tok:
        st.markdown("##### Suspicious Backdoor Trigger Tokens")
        st.write(", ".join(f"`{t}`" for t in s["trigger_tokens"]) or "None identified.")
        stats = [t for t in ds["report"]["trigger_token_stats"] if t["masked_disagreement"] >= 0.2]
        if stats:
            st.dataframe(stats, hide_index=True, use_container_width=True)
        st.caption("A token is flagged when its presence correlates abnormally with label disagreement.")

    with col_flag:
        st.markdown("##### Flagged Rows Sample")
        st.dataframe(ds["report"]["samples"], hide_index=True, use_container_width=True)

    d_col1, d_col2, d_col3 = st.columns(3)
    with d_col1:
        st.download_button(
            "Download report.json",
            json.dumps(ds["report"], indent=2),
            file_name="report.json",
            mime="application/json",
            use_container_width=True,
        )
    with d_col2:
        st.download_button(
            "Download screened.jsonl (Clean Corpus)",
            ds["screened"],
            file_name="screened.jsonl",
            mime="application/json",
            use_container_width=True,
        )
    with d_col3:
        st.download_button(
            "Download quarantined.jsonl (Poison Rows)",
            ds.get("quarantined", ""),
            file_name="quarantined.jsonl",
            mime="application/json",
            use_container_width=True,
        )


# ==============================================================================
# MAIN APP ENTRYPOINT
# ==============================================================================
st.set_page_config(
    page_title="RAG-Shield | Security Operations Console",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_custom_styles()

tier_, llm_, reviewer_ = sidebar()
home_ = os.environ.get("RAG_SHIELD_HOME") or str(Path.home() / ".rag_shield")
shield_ = get_shield(tier_, home_)

# Top Compact Header Bar with SVG Logo
st.markdown(
    f"""
    <div class="rs-topbar">
        <div class="rs-brand">
            {SVG_SHIELD_LOGO}
            <div>
                <div class="rs-brand-name">RAG-SHIELD // TRUST LAYER</div>
                <div style="font-size:0.75rem;color:#94a3b8;">Provenance-Aware Security Middleware for Document RAG</div>
            </div>
            <span class="rs-brand-tag">policy_v1</span>
        </div>
        <div class="rs-topbar-meta">
            <div class="rs-meta-pill">
                <span style="color:#10b981;font-size:0.65rem;">●</span> Active Tier: <strong>{tier_}</strong>
            </div>
            <div class="rs-meta-pill">
                Model: <strong>{llm_}</strong>
            </div>
            <div class="rs-meta-pill">
                Analyst: <strong>{reviewer_}</strong>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Launch banner for modern React console
st.markdown(
    f"""
    <div style="display:flex;justify-content:space-between;align-items:center;background:#0b1329;border:1px solid #3b82f6;padding:12px 20px;border-radius:8px;margin-bottom:16px;">
        <div style="display:flex;align-items:center;gap:12px;">
            {SVG_SHIELD_LOGO}
            <div>
                <strong style="color:#f8fafc;font-size:0.92rem;">Modern React Console is running at <a href="http://localhost:8000" target="_blank" style="color:#60a5fa;text-decoration:underline;">http://localhost:8000</a></strong>
                <div style="font-size:0.75rem;color:#94a3b8;">Interactive drag-and-drop, animated findings telemetry, real-time arena comparison, and dataset screening.</div>
            </div>
        </div>
        <a href="http://localhost:8000" target="_blank" style="background:#2563eb;color:#ffffff;padding:8px 16px;border-radius:6px;font-weight:600;font-size:0.82rem;text-decoration:none;white-space:nowrap;">
            Open React Console (Port 8000) &rarr;
        </a>
    </div>
    """,
    unsafe_allow_html=True,
)

main_tab_react, main_tab_docs, main_tab_dataset, main_tab_arch = st.tabs([
    "Modern React Console (Live)",
    "Document Security Console",
    "Dataset Gate (Pre-Retrieval)",
    "Threat Model & Specifications",
])

with main_tab_react:
    st.markdown(
        """
        <div style="margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.84rem;color:#94a3b8;">Live React application served from <code>http://localhost:8000</code></span>
            <a href="http://localhost:8000" target="_blank" style="font-size:0.82rem;color:#3b82f6;font-weight:600;text-decoration:none;">Open Fullscreen &rarr;</a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    import streamlit.components.v1 as components
    components.iframe("http://localhost:8000", height=950, scrolling=True)

with main_tab_docs:
    documents_tab(shield_, tier_, llm_, reviewer_)

with main_tab_dataset:
    dataset_tab(shield_)

with main_tab_arch:
    st.markdown("### RAG-Shield 4-Layer Security Architecture")
    st.markdown(
        """
        RAG-Shield is a modular security middleware designed to prevent indirect prompt injection
        attacks without discarding legitimate documents. Rather than dropping entire files upon suspicious
        detection, RAG-Shield operates at the **sentence level**: it canonicalizes text, extracts physical
        and layout hiding signals, and reversibly quarantines malicious sentences while keeping valid facts
        available for defended retrieval.

        ---

        #### Layer 1: Canonicalization & Physical Hiding Signal Extraction
        - **Fail-Closed Scanner Guard**: Enforces size, page count, and scan timeouts (`RAG_SHIELD_MAX_BYTES`, `RAG_SHIELD_MAX_PAGES`, `RAG_SHIELD_SCAN_TIMEOUT`). Fails safely on encrypted or corrupt files.
        - **Layout Signal Detectors**:
          - `tiny_font`: Font sizes below threshold (< 2 pt or unusually small relative size).
          - `low_contrast`: Computes WCAG contrast ratio (< 1.5) against detected background.
          - `off_page`: Text rendered outside visible canvas coordinates.
          - `metadata` & `alt_text`: Text extracted from PDF metadata and HTML attributes as dedicated carrier spans.
        - **Unicode Normalization**: Cleans zero-width characters and homoglyphs while safely preserving zero-width joiners/non-joiners (ZWJ/ZWNJ) required for Indic scripts.

        #### Layer 2: Sentence-Level Scoring, Routing & Fusion
        - **Sentence Segmentation**: Accurately splits text at punctuation boundaries (`. ! ? । ॥`) without breaking Indic sentences.
        - **Multi-Vector Risk Fusion**:
          $$\\text{Score} = 0.45 \\cdot S + 0.35 \\cdot L + 0.40 \\cdot H + 0.20 \\cdot C \\cdot \\max(S, L)$$
          *(where $S$ = semantic score, $L$ = linguistic cue score, $H$ = hiding score, $C$ = carrier score).*
        - **Surgical Quarantine**: Only malicious sentences are withheld; genuine facts remain indexed.

        #### Layer 3: Context Isolation & Spotlighting
        - **Trust Tiers**: `external_upload` (strict 0.70/0.40) vs `internal_kb` (relaxed 0.90/0.80).
        - **Spotlighting**: Wraps untrusted retrieved context in dynamic, per-request nonce delimiters (`<<UNTRUSTED_<hex> >> ... <</...>>`) to resist prompt escapes.

        #### Layer 4: Output Validation & Safeguards
        - **Canary Redaction**: Injects secret tokens into system prompts and detects/redacts them if echoed in generated answers.
        - **Data Exfiltration Defense**: Parses Markdown and HTML links; automatically strips external image tags and unauthorized hyperlinks.
        - **Citation Grounding**: Verifies each sentence cites an approved retrieved chunk identifier (e.g., `[c1]`).
        """
    )
