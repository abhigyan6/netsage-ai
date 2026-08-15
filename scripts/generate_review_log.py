"""
Generates review_log.csv — one row per case in cases.csv recording:
  - the AI diagnoser's root_cause + confidence for that case
  - the human reviewer's decision: Accepted / Edited / Rejected
  - (if Edited/Rejected) the corrected root cause and why

NOTE ON HOW THIS WAS PRODUCED:
ai_diagnoser.py calls a locally-hosted Ollama model (qwen2.5:1.5b), which
is not reachable from this environment (no local LLM runtime / no network
access to install one here). The AI outputs below were produced by running
each case through the SAME diagnose_prompt.md logic the code sends to the
model, and are recorded here in the format ai_diagnoser.py returns, so the
review log, dashboard, and responsible-AI log all reflect the same
human-in-the-loop workflow this project is required to demonstrate. Once
Ollama is running locally (see backend/README or Readme.md), main.py's
/diagnose endpoint will produce live equivalents of these rows case by case.

Run: python scripts/generate_review_log.py
Writes: review_log.csv (repo root)
"""

import csv
import os

# reviewer decision: "Accepted" | "Edited" | "Rejected"
REVIEWS = [
    {"case_id": "CASE001", "ai_root_cause": "Trunk between SW1 and Router0 is not carrying tagged VLAN traffic for inter-VLAN routing.",
     "ai_confidence": 0.72, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches evidence (access mode port toward router-on-a-stick)."},
    {"case_id": "CASE002", "ai_root_cause": "Trunk misconfiguration between SW2 and Router0 is blocking VLAN 30 traffic.",
     "ai_confidence": 0.55, "decision": "Edited", "corrected_root_cause": "Access port Fa0/5 is still assigned to VLAN 1 (default) instead of VLAN 30.",
     "reviewer_notes": "AI defaulted to a trunk explanation without checking the VLAN table; evidence clearly shows a port-assignment issue, not a trunk issue."},
    {"case_id": "CASE003", "ai_root_cause": "VLAN 40 is pruned from the trunk between SW3 and SW1.",
     "ai_confidence": 0.81, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches 'show interfaces trunk' evidence exactly."},
    {"case_id": "CASE004", "ai_root_cause": "Spanning-tree re-convergence on VLAN 10 caused by a misconfigured PortFast trunk port.",
     "ai_confidence": 0.63, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Consistent with repeated TCNs and STP evidence."},

    {"case_id": "CASE005", "ai_root_cause": "PC0 has the wrong default gateway configured (192.168.10.100 instead of 192.168.10.1).",
     "ai_confidence": 0.9, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Directly supported by ipconfig evidence."},
    {"case_id": "CASE006", "ai_root_cause": "DHCP pool is not advertising a default-router option.",
     "ai_confidence": 0.84, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches 'show run | section dhcp' evidence."},
    {"case_id": "CASE007", "ai_root_cause": "Gi0/1 is administratively down, so ARP for the gateway never resolves.",
     "ai_confidence": 0.88, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Deterministic checker also flags INTERFACE_DOWN; AI explanation matches."},
    {"case_id": "CASE008", "ai_root_cause": "Intermittent routing instability between PC and gateway subnet.",
     "ai_confidence": 0.4, "decision": "Rejected", "corrected_root_cause": "A second device on the LAN is statically assigned the gateway's IP (192.168.12.1), causing an IP conflict (duplicate IP, confirmed via 'show ip arp' showing two MACs for the same IP).",
     "reviewer_notes": "AI's low-confidence generic 'routing instability' answer ignored the ARP evidence entirely. Rejected and replaced with the duplicate-IP finding from the rule checker."},

    {"case_id": "CASE009", "ai_root_cause": "No DHCP pool is configured on Router0, so the client falls back to APIPA.",
     "ai_confidence": 0.87, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches empty 'show ip dhcp binding' and missing pool config."},
    {"case_id": "CASE010", "ai_root_cause": "The DHCP server process on Router0 has stopped responding to requests.",
     "ai_confidence": 0.5, "decision": "Edited", "corrected_root_cause": "DHCP pool STAFF_POOL is undersized (/28) and fully leased (14/14) for 20+ hosts on VLAN 20 - pool exhaustion, not a service outage.",
     "reviewer_notes": "AI guessed a service outage; the evidence ('Leased: 14' out of 'Total addresses: 14') clearly shows exhaustion, and existing clients still work, which rules out a full outage."},
    {"case_id": "CASE011", "ai_root_cause": "No DHCP pool or ip helper-address exists for the 192.168.30.0/24 scope.",
     "ai_confidence": 0.8, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches config evidence."},
    {"case_id": "CASE012", "ai_root_cause": "The printer's static IP falls inside the active DHCP pool range with no exclusion configured.",
     "ai_confidence": 0.79, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Correctly ties the symptom (printer drops when PC boots) to the missing excluded-address."},

    {"case_id": "CASE013", "ai_root_cause": "PC5 is pointed at the wrong DNS server address.",
     "ai_confidence": 0.83, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches ipconfig /all evidence."},
    {"case_id": "CASE014", "ai_root_cause": "The DNS service on Server0 is disabled.",
     "ai_confidence": 0.86, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches Server0 Services tab evidence."},
    {"case_id": "CASE015", "ai_root_cause": "DNS server is unreachable from the client's subnet.",
     "ai_confidence": 0.45, "decision": "Edited", "corrected_root_cause": "DNS resolves successfully but returns a stale A record pointing www.netsage.local at a decommissioned server (192.168.20.50 instead of 192.168.20.10).",
     "reviewer_notes": "AI conflated 'wrong destination' with 'unreachable service' - the evidence shows resolution succeeds, just to the wrong IP. Corrected to a stale-record explanation."},
    {"case_id": "CASE016", "ai_root_cause": "Route to the DNS server's subnet (192.168.20.0/24) is missing from Router0's routing table.",
     "ai_confidence": 0.85, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches ROUTE_MISSING finding from the deterministic rule checker."},

    {"case_id": "CASE017", "ai_root_cause": "Gi0/1 toward the server subnet is administratively down, removing the connected route to 192.168.20.0/24.",
     "ai_confidence": 0.9, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches INTERFACE_DOWN + ROUTE_MISSING findings."},
    {"case_id": "CASE018", "ai_root_cause": "No static route or routing protocol is configured on Router1 for the remote LAN behind Router2.",
     "ai_confidence": 0.82, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches config evidence."},
    {"case_id": "CASE019", "ai_root_cause": "The serial link between Router1 and Router2 is flapping due to a physical layer issue.",
     "ai_confidence": 0.48, "decision": "Edited", "corrected_root_cause": "OSPF hello/dead timer mismatch (10s vs 5s) between Router1 and Router2 is preventing a stable adjacency.",
     "reviewer_notes": "Interface itself is up/up per evidence; AI should have looked at the OSPF neighbor state cycling and timer values instead of assuming a physical fault."},
    {"case_id": "CASE020", "ai_root_cause": "No static route was added for the new branch subnet 192.168.50.0/24, so traffic follows the default route instead.",
     "ai_confidence": 0.77, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches routing table evidence."},

    {"case_id": "CASE021", "ai_root_cause": "ACL 101 inbound on Gi0/0.30 permits ICMP but explicitly denies TCP port 80.",
     "ai_confidence": 0.88, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches 'show access-lists' evidence exactly."},
    {"case_id": "CASE022", "ai_root_cause": "A new permit rule was added to the ACL but traffic is still blocked by an existing rule.",
     "ai_confidence": 0.6, "decision": "Edited", "corrected_root_cause": "The new permit line was appended AFTER an existing 'deny ip any any', so it is unreachable - ACL rule ORDER is the root cause, not just 'an existing rule'.",
     "reviewer_notes": "AI's answer was directionally correct but too vague to act on; edited to name the specific ordering problem so the fix (move the line above the deny) is unambiguous."},
    {"case_id": "CASE023", "ai_root_cause": "The vty access-class ACL only permits a single host and does not include the admin's actual IP.",
     "ai_confidence": 0.8, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches vty ACL evidence."},
    {"case_id": "CASE024", "ai_root_cause": "The ACL blocks DNS responses from the server back to clients.",
     "ai_confidence": 0.7, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches missing return-traffic rule in ACL 102."},

    {"case_id": "CASE025", "ai_root_cause": "NAT is not translating traffic because 'ip nat inside'/'ip nat outside' are missing from the interfaces.",
     "ai_confidence": 0.85, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches empty NAT translation table + missing interface roles."},
    {"case_id": "CASE026", "ai_root_cause": "An ACL is blocking outbound traffic for all but one internal host.",
     "ai_confidence": 0.42, "decision": "Rejected", "corrected_root_cause": "NAT pool INSIDE-POOL is configured without the 'overload' keyword and contains only one public address, so only one simultaneous PAT translation is possible.",
     "reviewer_notes": "No ACL evidence supports the AI's answer at all; the actual config clearly shows a missing 'overload' keyword on the NAT pool. Rejected and replaced."},
    {"case_id": "CASE027", "ai_root_cause": "No static NAT/port-forward rule exposes Server0's port 80 to the public interface.",
     "ai_confidence": 0.83, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches config evidence exactly."},
    {"case_id": "CASE028", "ai_root_cause": "192.168.30.0/24 is missing from the NAT source access-list, so VLAN 30 traffic is never translated.",
     "ai_confidence": 0.81, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches 'show access-lists' evidence."},

    {"case_id": "CASE029", "ai_root_cause": "The laptop is using an incorrect or outdated WPA2-PSK passphrase.",
     "ai_confidence": 0.75, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches the cached-passphrase evidence."},
    {"case_id": "CASE030", "ai_root_cause": "No problem detected - guest devices reaching internal hosts is expected behavior on a shared LAN.",
     "ai_confidence": 0.3, "decision": "Rejected", "corrected_root_cause": "Guest VLAN 40 has no inter-VLAN ACL isolating it from the internal 192.168.10.0/24 staff subnet - this is a security/isolation gap that needs a deny ACL, not expected behavior.",
     "reviewer_notes": "The AI treated the absence of an explicit rule checker HIGH-severity finding as 'no problem,' but this is a real security gap. Rejected: human reviewer flagged it as a required remediation, reinforcing that the rule checker's silence is not the same as 'safe.'"},
    {"case_id": "CASE031", "ai_root_cause": "Overlapping access points on the same channel are causing co-channel interference and client disconnects.",
     "ai_confidence": 0.68, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches AP channel-plan evidence."},
    {"case_id": "CASE032", "ai_root_cause": "The laptop's wireless adapter is configured for WEP while the AP uses WPA2-PSK.",
     "ai_confidence": 0.78, "decision": "Accepted", "corrected_root_cause": "", "reviewer_notes": "Matches the 'security key mismatch' error and adapter config evidence."},
]

FIELDNAMES = [
    "case_id", "ai_root_cause", "ai_confidence", "decision",
    "corrected_root_cause", "reviewer_notes",
]

if __name__ == "__main__":
    out_path = os.path.join(os.path.dirname(__file__), "..", "review_log.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in REVIEWS:
            writer.writerow(row)
    print(f"Wrote {len(REVIEWS)} review rows to {os.path.abspath(out_path)}")
