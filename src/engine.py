"""
NetSage AI - AI diagnoser engine.

Calls Google Gemini API (configured in system_config.json) to produce a
structured JSON explanation of the deterministic rule-checker finding.
"""

import json
import os
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# --------------------------------------------------------------------
# Config
# --------------------------------------------------------------------

def _load_config():
    """Load system_config.json from the project root (one level up from src/)."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "system_config.json")
    config_path = os.path.normpath(config_path)
    with open(config_path) as f:
        return json.load(f)

CONFIG = _load_config()
MODEL = CONFIG.get("model", "gemini-2.0-flash")
TEMPERATURE = CONFIG.get("temperature", 0)

def _load_prompt_template():
    """Load the prompt template from prompts/diagnose_prompt.md."""
    prompt_rel = CONFIG.get("prompt_path", "prompts/diagnose_prompt.md")
    root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    prompt_path = os.path.join(root, prompt_rel)
    with open(prompt_path, encoding="utf-8") as f:
        return f.read()

PROMPT_TEMPLATE = _load_prompt_template()

# --------------------------------------------------------------------
# Pydantic Schema for Gemini Structured Output
# --------------------------------------------------------------------

class DiagnosisResult(BaseModel):
    root_cause: str = Field(description="A clear, specific description of the most likely network fault")
    confidence: float = Field(description="Between 0.0 and 1.0 — how certain the diagnosis is")
    evidence: list[str] = Field(description="Specific facts quoted from the supplied show-command output")
    next_command: str = Field(description="The single most useful Cisco command for further verification")
    fix_steps: list[str] = Field(description="Safe IOS configuration commands to remediate the issue")

# --------------------------------------------------------------------
# Main diagnoser
# --------------------------------------------------------------------

def diagnose_case(case, api_key):
    """
    Build a prompt from the case dict + rule-checker result, call Gemini API,
    and return the parsed JSON diagnosis dict (or None on failure).
    """
    rule = case.get("rule_checker_result", {})

    # Build the case-specific section
    case_section = f"""
---

## Current Case — Analyze This Now

CASE ID:
{case.get("case_id", "")}

SYMPTOM:
{case.get("symptom", "")}

TOPOLOGY:
{case.get("topology", "")}

SHOW IP INTERFACE BRIEF:
{case.get("show_ip_interface_brief", "")}

SHOW IP ROUTE:
{case.get("show_ip_route", "")}

PYTHON RULE CHECKER RESULT:
{json.dumps(rule, indent=2)}

IMPORTANT:

The Python Rule Checker is authoritative.

You MUST explain the problem identified by the Rule Checker.

Do NOT invent additional problems.

RULE TYPE: {rule.get("type", "")}

RULE-SPECIFIC INSTRUCTIONS:

If RULE TYPE is INTERFACE_DOWN:
  root_cause must explain that the specified router interface is
  administratively down and therefore traffic cannot reach the affected
  network/server.
  next_command must be: "show interfaces <interface_name>"
  fix_steps must include: configure terminal, interface <name>, no shutdown, end.

If RULE TYPE is PROTOCOL_DOWN:
  root_cause must explain the interface is physically up but line protocol is down.
  next_command must be: "show interfaces <interface_name>"
  fix_steps must be empty unless evidence identifies a specific safe fix.

If RULE TYPE is ROUTE_MISSING:
  root_cause must explain the affected network has no route.
  next_command must be: "show ip route"
  fix_steps must be empty (correct route cannot be safely guessed).

If RULE TYPE is NO_PROBLEM:
  root_cause must say no matching network problem was detected.
  next_command must be: "show ip interface brief"
  fix_steps must be empty.
  confidence must be low (0.3 or below).
"""

    full_prompt = PROMPT_TEMPLATE + "\n" + case_section

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DiagnosisResult,
                temperature=TEMPERATURE,
            ),
        )
        # The response.text is guaranteed to be JSON matching DiagnosisResult
        diagnosis = json.loads(response.text)
        return diagnosis
    except Exception as e:
        print("AI diagnosis error:", e)
        return None
