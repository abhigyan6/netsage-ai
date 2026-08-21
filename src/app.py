"""
NetSage AI — Streamlit Operations Dashboard

Run with:
    streamlit run src/app.py

Requires a Gemini API Key to run the AI diagnoser.
The rule checker (src/checker.py) works without any LLM.
"""

import csv
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

# ── resolve project root so imports work regardless of cwd ───────────────────
ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.checker import check_rules
from src.engine import diagnose_case

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NetSage AI",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

def inject_custom_css():
    st.markdown("""
    <style>
    /* Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global Typography */
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }

    /* Dark Mode Palette & Gradients */
    :root {
        --primary-gradient: linear-gradient(135deg, #00C9FF 0%, #92FE9D 100%);
        --bg-color: #0d1117;
        --card-bg: rgba(22, 27, 34, 0.6);
        --border-color: rgba(255, 255, 255, 0.1);
        --text-color: #c9d1d9;
    }

    /* Base Styling */
    .stApp {
        background-color: var(--bg-color);
        background-image: 
            radial-gradient(at 0% 0%, rgba(0, 201, 255, 0.15) 0px, transparent 50%),
            radial-gradient(at 100% 0%, rgba(146, 254, 157, 0.15) 0px, transparent 50%);
        color: var(--text-color);
    }

    /* Glassmorphism Cards */
    div.stForm, div[data-testid="stExpander"], div[data-testid="stMetric"] {
        background: var(--card-bg) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    div.stForm:hover, div[data-testid="stExpander"]:hover, div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.4) !important;
    }

    /* Buttons with Gradients & Micro-animations */
    button[kind="primary"] {
        background: var(--primary-gradient) !important;
        color: #000 !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.5rem !important;
        transition: all 0.3s ease !important;
    }
    button[kind="primary"]:hover {
        transform: scale(1.05) !important;
        box-shadow: 0 0 15px rgba(0, 201, 255, 0.6) !important;
    }
    
    button[kind="secondaryFormSubmit"] {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        transition: all 0.3s ease !important;
    }
    button[kind="secondaryFormSubmit"]:hover {
        background: rgba(255, 255, 255, 0.1) !important;
        transform: scale(1.02) !important;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background: rgba(13, 17, 23, 0.8) !important;
        backdrop-filter: blur(20px) !important;
        border-right: 1px solid var(--border-color) !important;
    }

    /* Text Inputs & Areas */
    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 8px !important;
        color: white !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox > div > div:focus {
        border-color: rgba(0, 201, 255, 0.5) !important;
        box-shadow: 0 0 0 2px rgba(0, 201, 255, 0.2) !important;
    }

    /* Fade-in Animation for Results */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    div[data-testid="stVerticalBlock"] > div {
        animation: fadeIn 0.5s ease forwards;
    }

    /* Header styling */
    h1, h2, h3 {
        background: var(--primary-gradient);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        letter-spacing: -0.5px;
    }

    /* Metric Values */
    div[data-testid="stMetricValue"] {
        color: white !important;
        font-weight: 700;
    }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()


# ── load system config ────────────────────────────────────────────────────────
with open(os.path.join(ROOT, "system_config.json")) as f:
    CONFIG = json.load(f)

DATA_PATH        = os.path.join(ROOT, CONFIG["data_path"])
REVIEW_LOG_PATH  = os.path.join(ROOT, CONFIG["review_log_path"])
AUDIT_LOG_PATH   = os.path.join(ROOT, CONFIG["audit_log_path"])

# ── helpers ───────────────────────────────────────────────────────────────────

def load_cases():
    """Return cases.csv as a list of row dicts, or [] if missing."""
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_review(case_id, rule_result, ai_result, decision, notes):
    """Append one row to review_log.csv."""
    fieldnames = [
        "timestamp", "case_id", "rule_type", "rule_severity",
        "ai_root_cause", "ai_confidence", "decision", "reviewer_notes",
    ]
    row = {
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "case_id":         case_id,
        "rule_type":       rule_result.get("type", ""),
        "rule_severity":   rule_result.get("severity", ""),
        "ai_root_cause":   ai_result.get("root_cause", "") if ai_result else "N/A",
        "ai_confidence":   ai_result.get("confidence", "") if ai_result else "N/A",
        "decision":        decision,
        "reviewer_notes":  notes,
    }
    write_header = not os.path.exists(REVIEW_LOG_PATH)
    with open(REVIEW_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def severity_color(severity):
    return {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "🔵"}.get(
        (severity or "").upper(), "⚪"
    )


# ── sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.image(
    "https://img.icons8.com/fluency/96/cisco.png",
    width=64,
)
st.sidebar.title("NetSage AI")
st.sidebar.caption("Cisco Network Troubleshooting")
st.sidebar.divider()

cases = load_cases()
case_ids = [c.get("case_id", "") for c in cases if c.get("case_id")]

view = st.sidebar.radio(
    "View",
    ["🔍 Diagnose", "📊 Dashboard", "📋 Audit Log"],
    label_visibility="collapsed",
)

st.sidebar.divider()
if case_ids:
    selected_case_id = st.sidebar.selectbox("Load case from dataset", ["— manual entry —"] + case_ids)
else:
    selected_case_id = "— manual entry —"
    st.sidebar.info("No cases.csv found at data/cases.csv")

st.sidebar.divider()
st.sidebar.caption(f"Model: `{CONFIG.get('model')}`  |  Conf threshold: `{CONFIG.get('confidence_threshold')}`")

st.sidebar.divider()
api_key = st.sidebar.text_input("Gemini API Key", type="password")
st.sidebar.markdown("[Get a free key here](https://aistudio.google.com/app/apikey)", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# VIEW: DIAGNOSE
# ═══════════════════════════════════════════════════════════════════════════════

if "🔍 Diagnose" in view:

    st.title("🔬 NetSage AI — Network Diagnosis")
    st.caption("Enter a case manually or load one from the dataset. Run the rule checker first, then optionally the AI diagnoser.")

    # ── pre-fill from dataset ─────────────────────────────────────────────────
    prefill = {}
    if selected_case_id != "— manual entry —":
        for c in cases:
            if c.get("case_id") == selected_case_id:
                prefill = c
                break

    # ── input form ─────────────────────────────────────────────────────────────
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
            "Topology",
            value=prefill.get("topology", "PC0 -> Switch0 -> Router0 -> Server0"),
        )

        show_brief = st.text_area(
            "`show ip interface brief`",
            value=prefill.get("show_ip_interface_brief", """\
Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0     192.168.10.1    YES manual up                    up
GigabitEthernet0/1     192.168.20.1    YES manual administratively down down
GigabitEthernet0/2     unassigned      YES unset  administratively down down
Vlan1                  unassigned      YES unset  administratively down down"""),
            height=160,
        )

        show_route = st.text_area(
            "`show ip route`  (optional)",
            value=prefill.get("show_ip_route", ""),
            height=100,
        )

        with st.expander("Advanced inputs (ARP, VLAN, host mask)"):
            show_arp    = st.text_area("`show ip arp`",        value=prefill.get("show_ip_arp", ""),    height=80)
            show_vlan   = st.text_area("`show vlan brief`",    value=prefill.get("show_vlan_brief", ""), height=80)
            req_vlan    = st.text_input("Required VLAN ID",    value=prefill.get("required_vlan", ""))
            port        = st.text_input("Access port",         value=prefill.get("port", ""))
            host_ip     = st.text_input("Host IP",             value=prefill.get("host_ip", ""))
            host_mask   = st.text_input("Host mask",           value=prefill.get("host_mask", ""))
            client_gw   = st.text_input("Client gateway",      value=prefill.get("client_gateway", ""))

        run_rule   = st.form_submit_button("▶ Run Rule Checker", type="primary")
        run_ai     = st.form_submit_button("🤖 Run AI Diagnosis (requires API Key)")

    # ── rule checker ──────────────────────────────────────────────────────────
    if run_rule or run_ai:
        rule_result = check_rules(
            show_brief, affected_network,
            show_ip_route=show_route,
            show_ip_arp=show_arp,
            show_vlan_brief=show_vlan,
            required_vlan=req_vlan or None,
            port=port or None,
            host_ip=host_ip or None,
            host_mask=host_mask or None,
            client_gateway=client_gw or None,
        )
        st.session_state["rule_result"]    = rule_result
        st.session_state["current_case_id"] = case_id
        st.session_state["ai_result"]       = None  # reset AI result on new run

    if "rule_result" in st.session_state:
        rule_result = st.session_state["rule_result"]

        st.divider()
        st.subheader("① Rule Checker  — Deterministic")

        sev  = rule_result.get("severity", "INFO")
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
        if not api_key:
            st.error("Please enter a Gemini API Key in the sidebar.")
        else:
            case_payload = {
                "case_id":               st.session_state["current_case_id"],
                "symptom":               symptom,
                "topology":              topology,
                "show_ip_interface_brief": show_brief,
                "show_ip_route":         show_route,
                "rule_checker_result":   st.session_state["rule_result"],
            }
            with st.spinner("Calling Gemini API…"):
                ai_result = diagnose_case(case_payload, api_key)
            st.session_state["ai_result"] = ai_result

    if st.session_state.get("ai_result") is not None:
        ai_result = st.session_state["ai_result"]
        rule_result = st.session_state["rule_result"]

        st.divider()
        st.subheader("② AI Diagnosis  — NetSage AI")

        conf = ai_result.get("confidence", 0)
        threshold = CONFIG.get("confidence_threshold", 0.5)

        col_x, col_y = st.columns([1, 4])
        with col_x:
            st.metric(
                "Confidence",
                f"{round(conf * 100)}%",
                delta="above threshold" if conf >= threshold else "below threshold",
                delta_color="normal" if conf >= threshold else "inverse",
            )
        with col_y:
            st.progress(conf, text=f"AI confidence: {round(conf*100)}%")

        st.markdown("**Root Cause**")
        st.warning(ai_result.get("root_cause", ""))

        evidence = ai_result.get("evidence", [])
        if evidence:
            st.markdown("**Evidence**")
            for e in evidence:
                st.markdown(f"- {e}" if isinstance(e, str) else f"```\n{json.dumps(e, indent=2)}\n```")

        next_cmd = ai_result.get("next_command", "")
        if next_cmd:
            st.markdown("**Recommended Next Command**")
            st.code(next_cmd, language="text")

        fix_steps = ai_result.get("fix_steps", [])
        if fix_steps:
            st.markdown("**Recommended Fix**")
            st.code("\n".join(fix_steps), language="text")
            st.error("⚠️ Human approval required before applying any fix. NetSage AI does not execute commands automatically.")
        else:
            st.markdown("_No automatic fix recommended — gather more evidence first._")

        with st.expander("Raw AI JSON"):
            st.json(ai_result)

        # ── human review ──────────────────────────────────────────────────────
        st.divider()
        st.subheader("③ Human Review")

        with st.form("review_form"):
            decision = st.radio(
                "Decision",
                ["Accepted", "Edited", "Rejected"],
                horizontal=True,
            )
            notes = st.text_area("Reviewer notes (required for Edited / Rejected)", height=80)
            submitted = st.form_submit_button("Submit Review")

        if submitted:
            if decision in ("Edited", "Rejected") and not notes.strip():
                st.error("Please add reviewer notes for Edited / Rejected decisions.")
            else:
                append_review(
                    st.session_state.get("current_case_id", ""),
                    rule_result,
                    ai_result,
                    decision,
                    notes,
                )
                st.success(f"✅ Review logged as **{decision}**.")

    elif run_ai and "rule_result" not in st.session_state:
        st.error("Run the rule checker first before requesting an AI diagnosis.")

    elif run_ai and st.session_state.get("ai_result") is None and "rule_result" in st.session_state and api_key:
        # ai_result was attempted but returned None
        st.error("AI diagnosis failed. Please check your API key and network connection.")


# ═══════════════════════════════════════════════════════════════════════════════
# VIEW: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

elif "📊 Dashboard" in view:

    st.title("📊 NetSage AI — Dashboard")

    # ── Dataset Overview (from cases.csv) ─────────────────────────────────
    st.subheader("📁 Dataset Overview")

    if os.path.exists(DATA_PATH):
        df_cases = pd.read_csv(DATA_PATH)
        total_cases = len(df_cases)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Cases", total_cases)
        if "category" in df_cases.columns:
            c2.metric("Fault Categories", df_cases["category"].nunique())
        if "osi_layer" in df_cases.columns:
            c3.metric("OSI Layers Covered", df_cases["osi_layer"].nunique())

        st.divider()

        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown("**Issue Type Distribution**")
            if "category" in df_cases.columns:
                cat_counts = df_cases["category"].value_counts()
                st.bar_chart(cat_counts)

        with col_r:
            st.markdown("**Severity Distribution**")
            if "severity" in df_cases.columns:
                sev_counts = df_cases["severity"].value_counts()
                st.bar_chart(sev_counts)

        st.divider()

        col_l2, col_r2 = st.columns(2)

        with col_l2:
            st.markdown("**OSI Layer Distribution**")
            if "osi_layer" in df_cases.columns:
                osi_counts = df_cases["osi_layer"].value_counts()
                st.bar_chart(osi_counts)

        with col_r2:
            st.markdown("**Concept Tag Distribution**")
            if "concept_tag" in df_cases.columns:
                tag_counts = df_cases["concept_tag"].value_counts()
                st.bar_chart(tag_counts)

        with st.expander("Full case dataset"):
            st.dataframe(df_cases, width=None)
    else:
        st.info("No cases.csv found at data/cases.csv")

    # ── Human Review Analytics (from review_log.csv) ──────────────────────
    st.divider()
    st.subheader("🤝 AI vs Human Agreement")

    if not os.path.exists(REVIEW_LOG_PATH):
        st.info("No review_log.csv found yet. Run some diagnoses and submit reviews to populate this section.")
    else:
        df = pd.read_csv(REVIEW_LOG_PATH)

        if df.empty:
            st.info("review_log.csv is empty.")
        else:
            total   = len(df)
            accepted = (df["decision"] == "Accepted").sum()
            edited   = (df["decision"] == "Edited").sum()
            rejected = (df["decision"] == "Rejected").sum()
            agreement = round(accepted / total * 100, 1) if total else 0

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Total reviewed", total)
            col2.metric("✅ Accepted",  accepted)
            col3.metric("✏️ Edited",    edited)
            col4.metric("❌ Rejected",  rejected)
            col5.metric("Agreement rate", f"{agreement}%")

            st.divider()

            col_rl, col_rr = st.columns(2)

            with col_rl:
                st.markdown("**Decision Breakdown**")
                decision_counts = df["decision"].value_counts()
                st.bar_chart(decision_counts)

            with col_rr:
                if "corrected_root_cause" in df.columns:
                    st.markdown("**Correction Rate by Category**")
                    corrections = df[df["decision"].isin(["Edited", "Rejected"])]
                    if not corrections.empty and "case_id" in corrections.columns:
                        st.dataframe(corrections[["case_id", "decision", "reviewer_notes"]], width=None)
                    else:
                        st.info("No corrections logged yet.")

            st.divider()
            st.subheader("Full review log")
            st.dataframe(df, width=None)


# ═══════════════════════════════════════════════════════════════════════════════
# VIEW: AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════════

elif "📋 Audit Log" in view:

    st.title("📋 Responsible AI Audit Log")

    if not os.path.exists(AUDIT_LOG_PATH):
        st.warning(f"Audit log not found at `{AUDIT_LOG_PATH}`.")
        st.stop()

    with open(AUDIT_LOG_PATH, encoding="utf-8") as f:
        content = f.read()

    st.markdown(content)
