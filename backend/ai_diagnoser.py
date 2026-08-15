import json
import re
import ollama


MODEL = "qwen2.5:1.5b"


def clean_json(text):
    """
    Remove markdown code fences if the model adds them.
    """

    text = text.strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    return text.strip()


def diagnose_case(case):

    rule = case.get("rule_checker_result", {})

    prompt = f"""
You are NetSage AI, a Cisco network troubleshooting assistant.

Analyze this network troubleshooting case.

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

RULE TYPE:
{rule.get("type", "")}

RULE DETAILS:
{json.dumps(rule, indent=2)}

Return ONLY valid JSON.

Use exactly this format:

{{
    "root_cause": "",
    "confidence": 0.0,
    "evidence": [],
    "next_command": "",
    "fix_steps": []
}}

RULE-SPECIFIC INSTRUCTIONS:

If RULE TYPE is INTERFACE_DOWN:

root_cause must explain that the specified router interface
is administratively down and therefore traffic cannot reach
the affected network/server.

next_command must be:

"show interfaces GigabitEthernet0/1"

fix_steps must be:

[
    "configure terminal",
    "interface GigabitEthernet0/1",
    "no shutdown",
    "end"
]

If RULE TYPE is PROTOCOL_DOWN:

root_cause must explain that the interface is physically up
but its line protocol is down.

next_command must be:

"show interfaces GigabitEthernet0/1"

fix_steps must be an empty list unless the supplied evidence
identifies a specific safe fix.

If RULE TYPE is ROUTE_MISSING:

root_cause must explain that the affected network does not
have a route in the supplied routing table.

next_command must be:

"show ip route"

fix_steps must be an empty list because the correct routing
fix cannot be safely invented from the supplied evidence.

If RULE TYPE is NO_PROBLEM:

root_cause must say that no matching network problem was
detected from the supplied evidence.

next_command must be:

"show ip interface brief"

fix_steps must be an empty list.

IMPORTANT RULES:

- Use ONLY supplied evidence.
- Do not invent evidence.
- Do not claim a fix was already performed.
- Do not automatically execute commands.
- Human approval is required before applying any fix.
- Do not confuse an IP address with a network address.
- The affected network is 192.168.20.0/24.
- Do not mention VLAN 1 unless it is explicitly relevant.
- Do not claim an interface has no IP address when it does.
- Do not call a router interface a switch interface.
- confidence must be between 0.0 and 1.0.
- evidence must contain facts from the supplied evidence.
"""

    try:

        response = ollama.chat(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            options={
                "temperature": 0
            }
        )

        result = response["message"]["content"]

        result = clean_json(result)

        diagnosis = json.loads(result)

        return diagnosis

    except Exception as e:

        print("AI diagnosis error:", e)

        return None