import json

from rule_checker import check_rules
from ai_diagnoser import diagnose_case


case = {

    "case_id": "CASE002",

    "symptom": (
        "PC0 can reach the router but cannot reach "
        "Server0 at 192.168.20.10."
    ),

    "topology": (
        "PC0 -> Switch0 -> Router0 -> Server0"
    ),

    "show_ip_interface_brief": """
Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0     192.168.10.1    YES manual up                    up
GigabitEthernet0/1     192.168.20.1    YES manual up                    down
GigabitEthernet0/2     unassigned      YES unset  administratively down down
Vlan1                  unassigned      YES unset  administratively down down
""",

    "show_ip_route": """
Gateway of last resort is not set

C    192.168.10.0/24 is directly connected, GigabitEthernet0/0
C    192.168.20.0/24 is directly connected, GigabitEthernet0/1
"""
}


affected_network = "192.168.20."


rule_result = check_rules(
    case["show_ip_interface_brief"],
    affected_network,
    case["show_ip_route"]
)

case["rule_checker_result"] = rule_result


print("\n===== RULE CHECKER RESULT =====")

print(
    json.dumps(
        rule_result,
        indent=4
    )
)


diagnosis = diagnose_case(case)


print("\n===== NETSAGE AI DIAGNOSIS =====")

if diagnosis:

    print(
        json.dumps(
            diagnosis,
            indent=4
        )
    )

else:

    print("AI diagnosis failed.")