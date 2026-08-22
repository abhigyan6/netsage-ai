"""
NetSage AI - AI diagnoser engine.

Calls Google Gemini API (configured in system_config.json) to produce a
structured JSON diagnosis. Includes a fallback diagnostician for offline/demo mode.

Schema aligned with reference implementation:
  root_cause, osi_layer (int), confidence (High/Medium/Low), evidence (list),
  next_commands (list), remediation_steps (list), verification (list)
"""

import json
import os
from pydantic import BaseModel, Field
from typing import List

# --------------------------------------------------------------------
# Config
# --------------------------------------------------------------------

def _load_config():
    config_path = os.path.join(os.path.dirname(__file__), "..", "system_config.json")
    with open(os.path.normpath(config_path)) as f:
        return json.load(f)

CONFIG = _load_config()
MODEL = CONFIG.get("model", "gemini-2.0-flash")
TEMPERATURE = CONFIG.get("temperature", 0)


def _load_prompt_template():
    prompt_rel = CONFIG.get("prompt_path", "prompts/diagnose_prompt.md")
    root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    with open(os.path.join(root, prompt_rel), encoding="utf-8") as f:
        return f.read()

PROMPT_TEMPLATE = _load_prompt_template()


# --------------------------------------------------------------------
# Pydantic Schema — aligned with reference repo
# --------------------------------------------------------------------

class DiagnosisResult(BaseModel):
    root_cause: str = Field(description="Clear explanation of the diagnosed network failure")
    osi_layer: int = Field(description="OSI Layer number from 1 to 7")
    confidence: str = Field(description="High, Medium, or Low")
    evidence: List[str] = Field(description="Exact lines or parameters from show command output")
    next_commands: List[str] = Field(description="Commands recommended to isolate or verify the issue")
    remediation_steps: List[str] = Field(description="Exact Cisco IOS commands to fix the issue")
    verification: List[str] = Field(description="Commands or steps to confirm the fix worked")


# --------------------------------------------------------------------
# Fallback diagnostician (offline / no API key)
# --------------------------------------------------------------------

FALLBACK_DIAGNOSES = {
    "INTERFACE_DOWN": {
        "root_cause": "A router interface is administratively shut down, blocking traffic to the destination network.",
        "osi_layer": 1,
        "confidence": "High",
        "evidence": ["Interface shown as 'administratively down' in show ip interface brief"],
        "next_commands": ["show interfaces", "show running-config interface"],
        "remediation_steps": ["configure terminal", "interface <interface>", "no shutdown", "end"],
        "verification": ["ping <destination>", "show ip interface brief"],
    },
    "PROTOCOL_DOWN": {
        "root_cause": "Interface is physically up but line protocol is down, indicating a Layer 1/2 issue (e.g. cable fault, encapsulation mismatch).",
        "osi_layer": 2,
        "confidence": "Medium",
        "evidence": ["Line protocol shown as 'down' in show ip interface brief"],
        "next_commands": ["show interfaces", "show controllers"],
        "remediation_steps": [],
        "verification": ["show interfaces", "show ip interface brief"],
    },
    "ROUTE_MISSING": {
        "root_cause": "The routing table has no entry for the destination network, causing traffic to be dropped.",
        "osi_layer": 3,
        "confidence": "High",
        "evidence": ["No matching route found in show ip route output"],
        "next_commands": ["show ip route", "show running-config | section router"],
        "remediation_steps": [],
        "verification": ["show ip route", "ping <destination>"],
    },
    "DUPLICATE_IP": {
        "root_cause": "Two devices share the same IP address, causing ARP conflicts and intermittent connectivity.",
        "osi_layer": 3,
        "confidence": "Medium",
        "evidence": ["Duplicate IP detected in ARP table or interface config"],
        "next_commands": ["show ip arp", "show ip interface brief"],
        "remediation_steps": [],
        "verification": ["show ip arp", "ping <destination>"],
    },
    "NO_PROBLEM": {
        "root_cause": "No matching network problem was detected by the deterministic rule checker.",
        "osi_layer": 7,
        "confidence": "Low",
        "evidence": ["All checked interfaces are up/up; routing table has expected entries"],
        "next_commands": ["show ip interface brief"],
        "remediation_steps": [],
        "verification": ["ping <destination>"],
    },
}


def fallback_diagnose(rule_type: str) -> dict:
    """Return a static fallback diagnosis when Gemini is unavailable."""
    base = FALLBACK_DIAGNOSES.get(rule_type, FALLBACK_DIAGNOSES["NO_PROBLEM"])
    result = dict(base)
    result["_fallback"] = True
    return result


# --------------------------------------------------------------------
# Main diagnoser
# --------------------------------------------------------------------

def diagnose_case(case: dict, api_key: str = "") -> dict:
    """
    Call Gemini API and return a structured diagnosis dict.
    Falls back to a static response if no API key is provided or on error.
    """
    rule = case.get("rule_checker_result", {})
    rule_type = rule.get("type", "NO_PROBLEM")

    # Use fallback if no key
    if not api_key:
        return fallback_diagnose(rule_type)

    case_section = f"""
---

## Current Case

CASE ID: {case.get("case_id", "")}
SYMPTOM: {case.get("symptom", "")}
TOPOLOGY: {case.get("topology", "")}

SHOW IP INTERFACE BRIEF:
{case.get("show_ip_interface_brief", "")}

SHOW IP ROUTE:
{case.get("show_ip_route", "")}

DETERMINISTIC RULE CHECKER RESULT:
{json.dumps(rule, indent=2)}

RULE TYPE: {rule_type}

IMPORTANT: The Rule Checker is authoritative. Explain the problem it identified.
Do NOT invent additional problems or fabricate CLI output.

Return ONLY a JSON object matching the required schema.
"""

    full_prompt = PROMPT_TEMPLATE + "\n" + case_section

    try:
        from google import genai
        from google.genai import types

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
        return json.loads(response.text)
    except Exception as e:
        print("AI diagnosis error:", e)
        # Fall back to static response rather than returning None
        result = fallback_diagnose(rule_type)
        result["_error"] = str(e)
        return result
