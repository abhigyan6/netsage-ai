"""
NetSage AI - AI diagnoser engine.

Calls a local Ollama model (configured in system_config.json) to produce a
structured JSON explanation of the deterministic rule-checker finding.

The prompt template is loaded from prompts/diagnose_prompt.md so it can be
iterated on independently of this code.
"""

import json
import re
import os

import ollama


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
MODEL = CONFIG.get("model", "qwen2.5:1.5b")
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
# Helpers
# --------------------------------------------------------------------

def clean_json(text):
    """Remove markdown code fences if the model adds them."""
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


# --------------------------------------------------------------------
# Main diagnoser
# --------------------------------------------------------------------

def diagnose_case(case):
    """
    Build a prompt from the case dict + rule-checker result, call Ollama,
    and return the parsed JSON diagnosis dict (or None on failure).

    The prompt is constructed by prepending the full prompt template
    (with worked examples and rules) to the case-specific data, giving
    the model all the context and format guidance it needs.
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

Return ONLY valid JSON. No explanatory text before or after the JSON object.
"""

    # Combine: template (with worked examples) + case-specific data
    full_prompt = PROMPT_TEMPLATE + "\n" + case_section

    try:
        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": full_prompt}],
            options={"temperature": TEMPERATURE},
        )

        result = response["message"]["content"]
        result = clean_json(result)
        diagnosis = json.loads(result)
        return diagnosis

    except Exception as e:
        print("AI diagnosis error:", e)
        return None
