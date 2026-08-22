"""
NetSage AI — Streamlit Operations Dashboard

Run with:
    streamlit run src/app.py

API key is read from:
  1. st.secrets["GEMINI_API_KEY"]  (Streamlit Cloud / secrets.toml)
  2. GEMINI_API_KEY environment variable
  3. Sidebar text input (fallback for local dev)

The rule checker and fallback diagnostician work with no API key at all.
"""

import csv
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

# ── resolve project root ──────────────────────────────────────────────────────
ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.checker import check_rules
from src.engine import diagnose_case

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NetSage AI - Network Troubleshooter",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS — aligned with reference dark teal theme ──────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap');

    :root {
        --ink: #e7f0ed; --muted: #82938e; --line: #223531;
        --paper: #07110f; --panel: #0d1a17;
        --teal: #71e1c1; --teal-dark: #103c35; --amber: #f5bd43;
    }
    .stApp { background: var(--paper); color: var(--ink); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] { background: #0b1714; border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] * { color: #dceae5 !important; }
    [data-testid="stSidebar"] hr { border-color: var(--line); }
    h1, h2, h3, h4, p, label, .stMarkdown { font-family: 'DM Sans', sans-serif; }
    h1 { letter-spacing: 0; font-weight: 700; color: var(--ink); }
    h2, h3 { color: var(--ink); }
    code, .stCode, [data-testid="stMetricValue"] { font-family: 'Space Mono', monospace; }
    [data-testid="stMetric"] {
        background: var(--panel); border: 1px solid var(--line);
        border-radius: 2px; padding: 0.8rem 1rem;
    }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    .stButton > button[kind="primary"] { background: var(--teal); border-color: var(--teal); color: #09211b; }
    .stButton > button[kind="primary"]:hover { background: var(--teal-dark); border-color: var(--teal-dark); }
    .stTextInput input, .stTextArea textarea {
        background: var(--panel) !important; border: 1px solid var(--line) !important;
        color: var(--ink) !important; font-family: 'Space Mono', monospace;
    }
    .fallback-badge {
        display: inline-block; background: #2a2500; color: var(--amber);
        border: 1px solid #5a4800; border-radius: 4px;
        padding: 0.2rem 0.6rem; font: 700 0.72rem 'Space Mono', monospace;
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


# ── load system config ────────────────────────────────────────────────────────
with open(os.path.join(ROOT, "system_config.json")) as f:
    CONFIG = json.load(f)

DATA_PATH       = os.path.join(ROOT, CONFIG["data_path"])
REVIEW_LOG_PATH = os.path.join(ROOT, "data", "review_log.csv")
AUDIT_LOG_PATH  = os.path.join(ROOT, CONFIG["audit_log_path"])

# ── resolve API key (secrets > env > sidebar) ─────────────────────────────────
def get_api_key(sidebar_key: str = "") -> str:
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    env = os.environ.get("GEMINI_API_KEY", "")
    if env:
        return env
    return sidebar_key


# ── helpers ───────────────────────────────────────────────────────────────────

def load_cases():
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


REVIEW_COLUMNS = [
    "timestamp", "case_id", "symptom",
    "ai_fault", "ai_layer", "ai_confidence",
    "human_verdict", "corrected_fault", "reviewer_notes",
]

def load_reviews() -> pd.DataFrame:
    if not os.path.exists(REVIEW_LOG_PATH) or os.path.getsize(REVIEW_LOG_PATH) == 0:
        df = pd.DataFrame(columns=REVIEW_COLUMNS)
        os.makedirs(os.path.dirname(REVIEW_LOG_PATH), exist_ok=True)
        df.to_csv(REVIEW_LOG_PATH, index=False)
        return df
    try:
        return pd.read_csv(REVIEW_LOG_PATH)
    except Exception:
        return pd.DataFrame(columns=REVIEW_COLUMNS)


def append_review(case_id, symptom, ai_result, human_verdict, corrected_fault, reviewer_notes):
    df = load_reviews()
    row = {
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "case_id":         case_id,
        "symptom":         symptom,
        "ai_fault":        ai_result.get("root_cause", "") if ai_result else "N/A",
        "ai_layer":        ai_result.get("osi_layer", "") if ai_result else "N/A",
        "ai_confidence":   ai_result.get("confidence", "") if ai_result else "N/A",
        "human_verdict":   human_verdict,
        "corrected_fault": corrected_fault,
        "reviewer_notes":  reviewer_notes,
    }
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(REVIEW_LOG_PATH, index=False)


def severity_color(severity):
    return {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "🔵"}.get(
        (severity or "").upper(), "⚪"
    )

def confidence_color(conf: str) -> str:
    return {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(conf, "⚪")

def osi_label(layer: int) -> str:
    labels = {1:"Physical",2:"Data Link",3:"Network",4:"Transport",
               5:"Session",6:"Presentation",7:"Application"}
    return f"L{layer} — {labels.get(layer, 'Unknown')}"


# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:12px;padding:1rem 0 0.5rem;">
        <div style="background:#71e1c1;color:#09211b;border-radius:10px;font-size:1.5rem;padding:0.45rem 0.65rem;">🌐</div>
        <div>
            <div style="font:700 1.1rem 'Space Mono',monospace;letter-spacing:0.06em;color:#e7f0ed;">NetSage AI</div>
            <div style="color:#82938e;font:0.68rem 'Space Mono',monospace;">Network Troubleshooter</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    cases = load_cases()
    case_ids = [c.get("case_id", "") for c in cases if c.get("case_id")]

    view = st.radio(
        "View",
        ["🔍 Diagnose", "📊 Dashboard", "📋 Audit Log"],
        label_visibility="collapsed",
    )

    st.divider()
    if case_ids:
        selected_case_id = st.selectbox("Load case from dataset", ["— manual entry —"] + case_ids)
    else:
        selected_case_id = "— manual entry —"
        st.info("No cases.csv found at data/cases.csv")

    st.divider()
    st.caption(f"Model: `{CONFIG.get('model')}`")

    # Only show API key input if not available via secrets/env
    _has_secret = bool(get_api_key())
    if _has_secret:
        st.success("🔑 API key loaded", icon="✅")
        sidebar_key = ""
    else:
        sidebar_key = st.text_input("Gemini API Key", type="password",
                                    help="Or set GEMINI_API_KEY in .streamlit/secrets.toml")
        st.markdown("[Get a free key →](https://aistudio.google.com/app/apikey)")


# ═══════════════════════════════════════════════════════════════════════════════
# VIEW: DIAGNOSE
# ═══════════════════════════════════════════════════════════════════════════════

if "🔍 Diagnose" in view:

    st.title("🌐 NetSage AI — Network Diagnosis")
    st.caption("Enter a case manually or load one from the dataset. The rule checker runs without an API key. AI diagnosis is optional.")

    # ── pre-fill from dataset ─────────────────────────────────────────────────
    prefill = {}
    if selected_case_id != "— manual entry —":
        for c in cases:
            if c.get("case_id") == selected_case_id:
                prefill = c
                break

    # ── input form ────────────────────────────────────────────────────────────
    with st.form("case_form"):
        col1, col2 = st.columns(2)
        with col1:
            case_id = st.text_input("Case ID", value=prefill.get("case_id", "CASE001"))
        with col2:
            affected_network = st.text_input(
                "Affected Network (CIDR or prefix)",
                value=prefill.get("affected_network", "192.168.20."),
            )

        symptom = st.text_area(
            "Symptom",
            value=prefill.get("symptom", "PC0 can ping its gateway at 192.168.10.1 but cannot reach Server0 at 192.168.20.10."),
            height=80,
        )
        topology = st.text_input(
            "Topology / Lab Notes",
            value=prefill.get("topology_note", "PC0 -> Switch0 -> Router0 -> Server0"),
        )

        show_outputs = st.text_area(
            "Cisco CLI Evidence (show ip interface brief, show ip route, show vlan brief, etc.)",
            value=prefill.get("show_outputs", "Interface              IP-Address      OK? Method Status                Protocol\nGigabitEthernet0/0     192.168.10.1    YES manual up                    up\nGigabitEthernet0/1     192.168.20.1    YES manual administratively down down"),
            height=200,
            help="Paste any combination of show commands here — the rule checker will parse all of them.",
        )

        show_route = st.text_area(
            "`show ip route`  (optional — paste separately for route analysis)",
            value=prefill.get("show_ip_route", ""),
            height=80,
        )

        with st.expander("Advanced inputs (ARP, VLAN, host details)"):
            show_arp  = st.text_area("`show ip arp`",      value=prefill.get("show_ip_arp", ""),    height=70)
            show_vlan = st.text_area("`show vlan brief`",  value=prefill.get("show_vlan_brief", ""), height=70)
            req_vlan  = st.text_input("Required VLAN ID",  value=prefill.get("required_vlan", ""))
            port      = st.text_input("Access port",       value=prefill.get("port", ""))
            host_ip   = st.text_input("Host IP",           value=prefill.get("host_ip", ""))
            host_mask = st.text_input("Host mask",         value=prefill.get("host_mask", ""))
            client_gw = st.text_input("Client gateway",   value=prefill.get("client_gateway", ""))

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            run_rule = st.form_submit_button("▶ Run Rule Checker", type="primary", use_container_width=True)
        with col_btn2:
            run_ai = st.form_submit_button("🤖 Run AI Diagnosis", use_container_width=True)

    # ── rule checker ──────────────────────────────────────────────────────────
    if run_rule or run_ai:
        rule_result = check_rules(
            show_outputs, affected_network,
            show_ip_route=show_route,
            show_ip_arp=show_arp,
            show_vlan_brief=show_vlan,
            required_vlan=req_vlan or None,
            port=port or None,
            host_ip=host_ip or None,
            host_mask=host_mask or None,
            client_gateway=client_gw or None,
        )
        st.session_state["rule_result"]     = rule_result
        st.session_state["current_case_id"] = case_id
        st.session_state["current_symptom"] = symptom
        st.session_state["ai_result"]       = None

    if "rule_result" in st.session_state:
        rule_result = st.session_state["rule_result"]

        st.divider()
        st.subheader("① Rule Checker — Deterministic")

        sev   = rule_result.get("severity", "INFO")
        rtype = rule_result.get("type", "")

        col_a, col_b = st.columns([1, 4])
        with col_a:
            st.metric("Severity", f"{severity_color(sev)} {sev}")
            st.metric("Rule type", rtype)
        with col_b:
            st.info(rule_result.get("message", ""))
            all_findings = rule_result.get("all_findings", [])
            if len(all_findings) > 1:
                with st.expander(f"All findings ({len(all_findings)})"):
                    for f in all_findings:
                        st.markdown(f"**{severity_color(f.get('severity'))} {f.get('type')}** — {f.get('message')}")

        with st.expander("Raw rule-checker JSON"):
            st.json(rule_result)

    # ── AI diagnoser ──────────────────────────────────────────────────────────
    if run_ai and "rule_result" in st.session_state:
        resolved_key = get_api_key(sidebar_key)
        case_payload = {
            "case_id":               st.session_state["current_case_id"],
            "symptom":               symptom,
            "topology":              topology,
            "show_ip_interface_brief": show_outputs,
            "show_ip_route":         show_route,
            "rule_checker_result":   st.session_state["rule_result"],
        }
        label = "Calling Gemini API…" if resolved_key else "Generating offline diagnosis…"
        with st.spinner(label):
            ai_result = diagnose_case(case_payload, resolved_key)
        st.session_state["ai_result"] = ai_result

    elif run_ai and "rule_result" not in st.session_state:
        st.error("Run the rule checker first before requesting an AI diagnosis.")

    # ── display AI result ─────────────────────────────────────────────────────
    if st.session_state.get("ai_result") is not None:
        ai = st.session_state["ai_result"]
        rule_result = st.session_state["rule_result"]

        st.divider()
        st.subheader("② AI Diagnosis — NetSage AI")

        is_fallback = ai.get("_fallback") or ai.get("_error")
        if is_fallback:
            st.markdown('<span class="fallback-badge">⚡ OFFLINE / DEMO MODE</span>', unsafe_allow_html=True)
            if ai.get("_error"):
                st.caption(f"API error: {ai['_error']}")

        conf_str = ai.get("confidence", "Low")
        osi      = ai.get("osi_layer", 3)

        col_x, col_y, col_z = st.columns(3)
        col_x.metric("Confidence",  f"{confidence_color(conf_str)} {conf_str}")
        col_y.metric("OSI Layer",   osi_label(osi))
        col_z.metric("Rule Match",  rule_result.get("type", "—"))

        st.markdown("**Root Cause**")
        st.warning(ai.get("root_cause", ""))

        evidence = ai.get("evidence", [])
        if evidence:
            st.markdown("**Evidence**")
            for e in evidence:
                st.markdown(f"- `{e}`")

        next_cmds = ai.get("next_commands", [])
        if next_cmds:
            st.markdown("**Recommended Next Commands**")
            st.code("\n".join(next_cmds), language="text")

        rem_steps = ai.get("remediation_steps", [])
        if rem_steps:
            st.markdown("**Remediation Steps**")
            st.code("\n".join(rem_steps), language="text")
            st.error("⚠️ Human approval required before applying any fix. NetSage AI does not execute commands automatically.")
        else:
            st.markdown("_No automatic fix recommended — gather more evidence first._")

        verif = ai.get("verification", [])
        if verif:
            st.markdown("**Verification Commands**")
            st.code("\n".join(verif), language="text")

        with st.expander("Raw AI JSON"):
            st.json(ai)

        # ── human review ──────────────────────────────────────────────────────
        st.divider()
        st.subheader("③ Human Review")
        st.caption("A human must accept, edit, or reject every diagnosis before it is logged.")

        with st.form("review_form"):
            human_verdict = st.radio(
                "Verdict",
                ["Accepted", "Edited", "Rejected"],
                horizontal=True,
            )
            corrected_fault = st.text_input(
                "Corrected fault description (required if Edited / Rejected)",
                value="",
            )
            reviewer_notes = st.text_area("Reviewer notes", height=80)
            submitted = st.form_submit_button("✅ Submit Review", type="primary")

        if submitted:
            if human_verdict in ("Edited", "Rejected") and not corrected_fault.strip():
                st.error("Please provide a corrected fault description for Edited / Rejected decisions.")
            else:
                append_review(
                    st.session_state.get("current_case_id", ""),
                    st.session_state.get("current_symptom", ""),
                    ai,
                    human_verdict,
                    corrected_fault,
                    reviewer_notes,
                )
                st.success(f"✅ Review logged as **{human_verdict}**.")


# ═══════════════════════════════════════════════════════════════════════════════
# VIEW: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

elif "📊 Dashboard" in view:

    st.title("📊 NetSage AI — Dashboard")

    # ── Dataset Overview ──────────────────────────────────────────────────────
    st.subheader("📁 Dataset Overview")

    if os.path.exists(DATA_PATH):
        df_cases = pd.read_csv(DATA_PATH)
        total_cases = len(df_cases)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Cases", total_cases)
        # New schema uses concept_tag instead of category
        tag_col = "concept_tag" if "concept_tag" in df_cases.columns else "category"
        if tag_col in df_cases.columns:
            c2.metric("Fault Types", df_cases[tag_col].nunique())
        if "osi_layer" in df_cases.columns:
            c3.metric("OSI Layers Covered", df_cases["osi_layer"].nunique())

        st.divider()
        col_l, col_r = st.columns(2)

        with col_l:
            tag_col = "concept_tag" if "concept_tag" in df_cases.columns else "category"
            if tag_col in df_cases.columns:
                fig = px.bar(
                    df_cases[tag_col].value_counts().reset_index(),
                    x=tag_col, y="count",
                    title="Fault Type Distribution",
                    color=tag_col,
                    color_discrete_sequence=px.colors.sequential.Teal,
                )
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  font_color="#e7f0ed", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        with col_r:
            if "severity" in df_cases.columns:
                fig = px.pie(
                    df_cases["severity"].value_counts().reset_index(),
                    names="severity", values="count",
                    title="Severity Distribution",
                    color_discrete_map={"HIGH":"#ef4444","MEDIUM":"#f5bd43","LOW":"#71e1c1"},
                )
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#e7f0ed")
                st.plotly_chart(fig, use_container_width=True)

        col_l2, col_r2 = st.columns(2)
        with col_l2:
            if "osi_layer" in df_cases.columns:
                fig = px.bar(
                    df_cases["osi_layer"].value_counts().sort_index().reset_index(),
                    x="osi_layer", y="count",
                    title="OSI Layer Distribution",
                    color_discrete_sequence=["#71e1c1"],
                )
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  font_color="#e7f0ed", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        with col_r2:
            if "concept_tag" in df_cases.columns:
                fig = px.bar(
                    df_cases["concept_tag"].value_counts().reset_index(),
                    x="concept_tag", y="count",
                    title="Concept Tag Distribution",
                    color_discrete_sequence=["#f5bd43"],
                )
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  font_color="#e7f0ed", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        with st.expander("Full case dataset"):
            st.dataframe(df_cases, use_container_width=True)
    else:
        st.info("No cases.csv found at data/cases.csv")

    # ── Human Review Analytics ────────────────────────────────────────────────
    st.divider()
    st.subheader("🤝 AI vs Human Agreement")

    df_rev = load_reviews()
    if df_rev.empty:
        st.info("No reviews logged yet. Run diagnoses and submit reviews to populate this section.")
    else:
        total    = len(df_rev)
        accepted = (df_rev["human_verdict"] == "Accepted").sum()
        edited   = (df_rev["human_verdict"] == "Edited").sum()
        rejected = (df_rev["human_verdict"] == "Rejected").sum()
        agree_pct = round(accepted / total * 100, 1) if total else 0

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Reviewed", total)
        col2.metric("✅ Accepted",    accepted)
        col3.metric("✏️ Edited",      edited)
        col4.metric("❌ Rejected",    rejected)
        col5.metric("Agreement Rate", f"{agree_pct}%")

        st.divider()
        col_rl, col_rr = st.columns(2)

        with col_rl:
            verdict_counts = df_rev["human_verdict"].value_counts().reset_index()
            fig = px.bar(verdict_counts, x="human_verdict", y="count",
                         title="Decision Breakdown",
                         color="human_verdict",
                         color_discrete_map={"Accepted":"#71e1c1","Edited":"#f5bd43","Rejected":"#ef4444"})
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color="#e7f0ed", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col_rr:
            if "ai_confidence" in df_rev.columns:
                conf_counts = df_rev["ai_confidence"].value_counts().reset_index()
                fig = px.pie(conf_counts, names="ai_confidence", values="count",
                             title="AI Confidence Distribution",
                             color_discrete_map={"High":"#71e1c1","Medium":"#f5bd43","Low":"#ef4444"})
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#e7f0ed")
                st.plotly_chart(fig, use_container_width=True)

        st.divider()
        corrections = df_rev[df_rev["human_verdict"].isin(["Edited", "Rejected"])]
        if not corrections.empty:
            st.subheader("Human Corrections")
            st.dataframe(corrections[["case_id", "ai_fault", "human_verdict", "corrected_fault", "reviewer_notes"]],
                         use_container_width=True)

        st.divider()
        st.subheader("Full Review Log")
        st.dataframe(df_rev, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# VIEW: AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════════

elif "📋 Audit Log" in view:

    st.title("📋 Responsible AI Audit Log")
    st.caption("Cases where the AI diagnosis was corrected or rejected by a human reviewer.")

    if not os.path.exists(AUDIT_LOG_PATH):
        st.warning(f"Audit log not found at `{AUDIT_LOG_PATH}`.")
        st.stop()

    with open(AUDIT_LOG_PATH, encoding="utf-8") as f:
        content = f.read()

    st.markdown(content)
