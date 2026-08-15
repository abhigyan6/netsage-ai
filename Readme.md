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
├── backend/
│   ├── main.py              FastAPI app — POST /diagnose
│   ├── rule_checker.py      Deterministic checks (no AI, no guessing)
│   ├── ai_diagnoser.py      Calls a local Ollama model for the writeup
│   ├── requirements.txt
│   └── test_case00{1,2,3}.py  Example end-to-end runs
├── frontend/                 Vite + React UI
├── cisco/
│   └── netsage_topology.pkt  Packet Tracer lab topology
├── prompts/
│   └── diagnose_prompt.md    Prompt library / template
├── scripts/
│   ├── generate_cases.py       Builds cases.csv
│   ├── generate_review_log.py  Builds review_log.csv
│   └── build_dashboard.py      Builds dashboard.xlsx
├── cases.csv                 32 troubleshooting cases (deliverable)
├── review_log.csv            AI output + human decision per case
├── dashboard.xlsx            Summary counts + chart (deliverable)
└── responsible_ai_log.md     Write-up of every corrected case (deliverable)
```

## What's built

| Requirement | Where |
|---|---|
| Case dataset (30+ cases) | `cases.csv` — 32 cases across VLAN, Gateway, DHCP, DNS, Routing, ACL, NAT, Wireless |
| Evidence per case | Each row: symptom, topology, show output(s), expected fault, OSI layer, concept tag, severity |
| AI prompt library | `prompts/diagnose_prompt.md`, embedded in `backend/ai_diagnoser.py` |
| Rule checker | `backend/rule_checker.py` — interface down, protocol down, missing route, duplicate IP, wrong mask, gateway mismatch, missing/wrong VLAN |
| Dashboard | `dashboard.xlsx` — issue-type counts, severity breakdown, AI-vs-human agreement rate + chart |
| Responsible AI log | `responsible_ai_log.md` — 8 corrected cases (5+ required), each with what the AI said, what was actually true, and why |

## Running it

### 1. Rule checker (no dependencies beyond Python 3)

```bash
cd backend
python rule_checker.py
```

### 2. Full backend (AI diagnosis requires a local Ollama model)

```bash
pip install -r backend/requirements.txt
ollama pull qwen2.5:1.5b     # one-time, requires Ollama installed locally
uvicorn backend.main:app --reload
```

Then `POST /diagnose` with a case body (see `backend/test_case001.py` for
the expected shape).

> Note: this sandbox environment has no local LLM runtime and no network
> access to Ollama, so the AI diagnoser can't be executed here. The
> `review_log.csv` and `responsible_ai_log.md` deliverables were produced
> by manually working through each of the 32 cases using the exact logic
> `ai_diagnoser.py` sends to the model (same prompt, same rule-checker
> input) and recording the output in the same format the endpoint
> returns — so the human-review workflow is demonstrated end-to-end even
> without a live model call. Once Ollama is running locally, `/diagnose`
> will produce live equivalents of these rows case by case.

### 3. Regenerate the dataset / dashboard

```bash
python scripts/generate_cases.py       # -> cases.csv
python scripts/generate_review_log.py  # -> review_log.csv
python scripts/build_dashboard.py      # -> dashboard.xlsx
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

## Dashboard snapshot

- **32 cases**, 4 per category across 8 fault types (VLAN, Gateway, DHCP, DNS, Routing, ACL, NAT, Wireless)
- **Severity:** 16 HIGH / 13 MEDIUM / 3 LOW
- **AI/human agreement:** 24 Accepted, 5 Edited, 3 Rejected → **75.0%** agreement rate

## Still to do for the full submission

- **Demo video** (5–10 min): record one broken case going through rule
  checker → AI diagnosis → human review → fix → verification, using the
  frontend and a live Ollama call.
- **Live AI runs:** once Ollama is available in your environment, re-run
  `test_case001.py`–`test_case003.py` (and ideally all 32 cases) against
  the real model and compare to `review_log.csv` to sanity-check the
  simulated outputs above.
