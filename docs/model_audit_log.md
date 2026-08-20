# NetSage AI — Responsible AI Log

This log documents every case in `review_log.csv` where the AI diagnoser's
output was **Edited** or **Rejected** by a human reviewer, as required by
the project's safety rule: *a human must approve or correct every
diagnosis before it is accepted.*

Full source data: `review_log.csv` (all 32 cases, including the 24 the AI
got right on the first pass). This document expands on the 8 cases where
it didn't.

---

## 1. CASE002 — VLAN port assignment (Edited)

- **AI said:** Trunk misconfiguration between SW2 and Router0 is blocking VLAN 30 traffic. (confidence 0.55)
- **Human found:** Access port Fa0/5 is still assigned to VLAN 1 (default) instead of VLAN 30.
- **Why the AI was wrong:** It pattern-matched "new device, no VLAN connectivity" to the more common trunk-pruning failure mode (as seen correctly in CASE003) without checking `show vlan brief`, where the port is plainly listed under VLAN 1.
- **Lesson:** Low-confidence trunk explanations should trigger an explicit VLAN-table cross-check before being surfaced.

## 2. CASE008 — Duplicate IP address (Rejected)

- **AI said:** Intermittent routing instability between PC and gateway subnet. (confidence 0.4)
- **Human found:** A second device is statically assigned the gateway's own IP (192.168.12.1); `show ip arp` shows two MAC addresses for the same IP.
- **Why the AI was wrong:** The low confidence score correctly signaled uncertainty, but the model still produced a vague answer instead of using the ARP evidence that was directly supplied.
- **Lesson:** This is exactly the kind of case the rule checker exists for — `check_duplicate_ip()` was added specifically after this review to catch it deterministically going forward, rather than relying on the AI to notice it.

## 3. CASE010 — DHCP pool exhaustion (Edited)

- **AI said:** The DHCP server process on Router0 has stopped responding to requests. (confidence 0.5)
- **Human found:** Pool `STAFF_POOL` is a /28 (14 usable addresses) serving 20+ hosts and shows `Leased: 14` — exhaustion, not an outage.
- **Why the AI was wrong:** "Existing clients still work" is inconsistent with a full service outage; the AI didn't reconcile that detail against its own answer.
- **Lesson:** Prompt the model to explicitly check its root cause against *all* stated symptoms, not just the failing one.

## 4. CASE015 — Stale DNS record (Edited)

- **AI said:** DNS server is unreachable from the client's subnet. (confidence 0.45)
- **Human found:** DNS resolves successfully — just to the wrong (decommissioned) IP.
- **Why the AI was wrong:** Conflated "wrong destination" with "unreachable service"; the symptom explicitly says resolution succeeds.
- **Lesson:** "Resolves to the wrong host" and "fails to resolve" are different fault classes and should be treated as separate branches in the prompt.

## 5. CASE019 — OSPF timer mismatch (Edited)

- **AI said:** The serial link between Router1 and Router2 is flapping due to a physical layer issue. (confidence 0.48)
- **Human found:** Interface is up/up; the real cause is an OSPF hello/dead timer mismatch (10s vs 5s) preventing a stable adjacency.
- **Why the AI was wrong:** Defaulted to the more common "physical flap" explanation without reading the supplied `show ip ospf neighbor` state-cycling evidence.
- **Lesson:** When protocol-level evidence (OSPF neighbor states, timers) is present, it should be weighted above generic physical-layer explanations.

## 6. CASE022 — ACL rule ordering (Edited)

- **AI said:** A new permit rule was added but traffic is still blocked by an existing rule. (confidence 0.6)
- **Human found:** The new permit line was appended *after* an existing `deny ip any any`, making it unreachable — an ordering problem specifically.
- **Why the AI was wrong:** Directionally correct but too vague to act on — "an existing rule" doesn't tell the engineer what to fix.
- **Lesson:** For ACL cases, the prompt should require the diagnosis to name the specific line/order relationship, not just "a rule conflict."

## 7. CASE026 — NAT overload missing (Rejected)

- **AI said:** An ACL is blocking outbound traffic for all but one internal host. (confidence 0.42)
- **Human found:** NAT pool `INSIDE-POOL` has no `overload` keyword and only one public address — only one simultaneous PAT translation is possible.
- **Why the AI was wrong:** No ACL evidence was supplied for this case at all; the AI invented a cause not present in the evidence, which directly violates the "do not invent evidence" rule in `diagnose_prompt.md`.
- **Lesson:** This is treated as a policy violation, not just an accuracy miss — it's logged as Rejected (not Edited) specifically because the AI fabricated an evidence source.

## 8. CASE030 — Guest VLAN isolation gap (Rejected)

- **AI said:** No problem detected — guest devices reaching internal hosts is expected behavior on a shared LAN. (confidence 0.3)
- **Human found:** Guest VLAN 40 has no inter-VLAN ACL isolating it from the internal staff subnet — a real security/isolation gap requiring a deny ACL.
- **Why the AI was wrong:** The deterministic rule checker doesn't flag missing ACLs as a "problem" (it only flags rules that actively deny traffic), and the AI treated that silence as confirmation nothing was wrong.
- **Lesson:** The most important one in this log — **absence of a rule-checker finding is not the same as "safe."** Security-relevant gaps (missing isolation, missing hardening) need their own review lens beyond "does traffic flow." This case is the strongest argument in the whole project for keeping a mandatory human review step rather than auto-accepting AI output.

---

## Summary

| Metric | Value |
|---|---|
| Total cases reviewed | 32 |
| Accepted as-is | 24 |
| Edited (partially correct) | 5 |
| Rejected (materially wrong) | 3 |
| AI/human agreement rate | 75.0% |

The two Rejected cases that involved invented evidence (CASE026) and
mistaking "no rule fired" for "no problem" (CASE030) are the most
important findings in this log — they are the clearest evidence that the
human-review safety rule in this project is load-bearing, not a
formality.
