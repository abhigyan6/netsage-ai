# NetSage AI

**An AI troubleshooting helper for Cisco-style lab networks — with mandatory human review.**

NetSage AI reads a symptom, a topology note, and Cisco show-command output
from a Packet Tracer lab, runs it through a deterministic rule checker,
then asks an AI diagnoser to explain the finding in plain language with a
root cause, confidence score, evidence, next command, and fix steps. A
human reviewer always has the final say — nothing is auto-applied.

> Safety rule: **the AI never executes a fix.** Every diagnosis is logged
> as Accepted, Edited, or Rejected by a human before it's considered final.

---

## Project layout

```
netsage-ai/
├── src/
│   ├── checker.py           Deterministic checks (no AI, no guessing)
│   ├── engine.py            Calls a local Ollama model for the write-up
│   └── app.py               Streamlit operations dashboard
├── data/
│   └── cases.csv            32 troubleshooting cases (deliverable)
├── docs/
│   └── model_audit_log.md   Write-up of every corrected case (deliverable)
├── prompts/
│   └── diagnose_prompt.md   Prompt library / template
├── cisco/
│   └── netsage_topology.pkt Packet Tracer lab topology
├── scripts/
│   ├── generate_cases.py       Builds data/cases.csv
│   ├── generate_review_log.py  Builds review_log.csv
│   └── build_dashboard.py      Builds dashboard.xlsx
├── system_config.json       Thresholds, model, and execution parameters
├── requirements.txt
├── review_log.csv           AI output + human decision per case
└── dashboard.xlsx           Summary counts + chart (deliverable)
```

## What's built

| Requirement | Where |
|---|---|
| Case dataset (30+ cases) | `data/cases.csv` — 32 cases across VLAN, Gateway, DHCP, DNS, Routing, ACL, NAT, Wireless |
| Evidence per case | Each row: symptom, topology, show output(s), expected fault, OSI layer, concept tag, severity |
| AI prompt library | `prompts/diagnose_prompt.md`, embedded in `src/engine.py` |
| Rule checker | `src/checker.py` — interface down, protocol down, missing route, duplicate IP, wrong mask, gateway mismatch, missing/wrong VLAN |
| Streamlit dashboard | `src/app.py` — Diagnose view, Dashboard view, Audit Log view |
| System config | `system_config.json` — model, temperature, confidence threshold, all file paths |
| Dashboard | `dashboard.xlsx` — issue-type counts, severity breakdown, AI-vs-human agreement rate + chart |
| Responsible AI log | `docs/model_audit_log.md` — 8 corrected cases (5+ required), each with what the AI said, what was actually true, and why |

## Running it

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Rule checker only (no LLM required)

```bash
python src/checker.py
```

### 3. Full Streamlit dashboard

```bash
# Pull the Ollama model first (one-time, requires Ollama installed)
ollama pull qwen2.5:1.5b

# Launch the app
streamlit run src/app.py
```

Open <http://localhost:8501> in your browser.

> If Ollama is not running, the rule checker panel works fully — only the
> AI Diagnosis step will show a connection error.

### 4. Regenerate the dataset / dashboard

```bash
python scripts/generate_cases.py       # -> data/cases.csv
python scripts/generate_review_log.py  # -> review_log.csv
python scripts/build_dashboard.py      # -> dashboard.xlsx
```

## Dashboard snapshot

- **32 cases**, 4 per category across 8 fault types (VLAN, Gateway, DHCP, DNS, Routing, ACL, NAT, Wireless)
- **Severity:** 16 HIGH / 13 MEDIUM / 3 LOW
- **AI/human agreement:** 24 Accepted, 5 Edited, 3 Rejected → **75.0%** agreement rate

## Still to do for the full submission

- **Demo video** (5–10 min): record one broken case going through rule
  checker → AI diagnosis → human review → fix → verification, using the
  Streamlit dashboard and a live Ollama call.
- **Live AI runs:** once Ollama is available, re-run all 32 cases against
  the real model and compare to `review_log.csv` to sanity-check the
  simulated outputs.

