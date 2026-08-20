"""
NetSage AI - deterministic rule checker.

This module is the "safety net" that runs BEFORE and independently of the
AI diagnoser. It never guesses: every finding here is derived from a
straightforward parse of show-command text, and the AI diagnoser is told
to treat these findings as authoritative (see src/engine.py).

Checks implemented (per the project spec, "Build the rule checker" step):
  1. Interface administratively down
  2. Line protocol down (interface up / protocol down)
  3. Missing route to the affected network
  4. Duplicate IP address on the same interface/subnet
  5. Wrong subnet mask (host address on the wrong-size prefix vs the gateway)
  6. Gateway mismatch (client's configured gateway not present on router)
  7. Missing / wrong VLAN assignment
"""

import ipaddress
import re


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

def _parse_show_ip_interface_brief(text):
    """
    Parse `show ip interface brief` text into a list of dicts:
    {interface, ip_address, status, protocol}

    Tolerant of Packet Tracer formatting (multi-word status like
    "administratively down").
    """
    rows = []
    if not text:
        return rows

    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("interface"):
            continue

        parts = line.split()
        if len(parts) < 4:
            continue

        interface = parts[0]
        ip_address = parts[1]
        protocol = parts[-1]
        status_tokens = parts[4:-1] if len(parts) > 5 else parts[3:-1]
        status = " ".join(status_tokens) if status_tokens else parts[-2]

        rows.append({
            "interface": interface,
            "ip_address": ip_address,
            "status": status,
            "protocol": protocol,
        })

    return rows


def _network_matches(ip_address, affected_network):
    """True if ip_address falls within affected_network (CIDR or bare prefix)."""
    if ip_address in ("unassigned", ""):
        return False
    try:
        if "/" in affected_network:
            return ipaddress.ip_address(ip_address) in ipaddress.ip_network(
                affected_network, strict=False
            )
        prefix = affected_network.rstrip(".")
        return ip_address.startswith(prefix)
    except ValueError:
        return ip_address.startswith(affected_network.rstrip("."))


# --------------------------------------------------------------------
# Individual checks - each returns a list of problem dicts (possibly empty)
# --------------------------------------------------------------------

def check_interface_status(show_ip_interface_brief, affected_network):
    """Detect an administratively down interface belonging to the affected network."""
    problems = []
    for row in _parse_show_ip_interface_brief(show_ip_interface_brief):
        if "administratively down" not in row["status"]:
            continue
        if not _network_matches(row["ip_address"], affected_network):
            continue
        problems.append({
            "type": "INTERFACE_DOWN",
            "interface": row["interface"],
            "ip_address": row["ip_address"],
            "status": "administratively down",
            "severity": "HIGH",
            "message": (
                f"{row['interface']} ({row['ip_address']}) is administratively "
                f"down and belongs to the affected network {affected_network}."
            ),
        })
    return problems


def check_protocol_status(show_ip_interface_brief, affected_network):
    """Detect an interface that is physically up but line protocol is down."""
    problems = []
    for row in _parse_show_ip_interface_brief(show_ip_interface_brief):
        if row["status"] != "up" or row["protocol"] != "down":
            continue
        if not _network_matches(row["ip_address"], affected_network):
            continue
        problems.append({
            "type": "PROTOCOL_DOWN",
            "interface": row["interface"],
            "ip_address": row["ip_address"],
            "status": row["status"],
            "protocol": row["protocol"],
            "severity": "HIGH",
            "message": (
                f"{row['interface']} ({row['ip_address']}) is physically up "
                f"but its line protocol is down."
            ),
        })
    return problems


def check_route(show_ip_route, affected_network):
    """Detect whether the affected network is missing from the routing table."""
    if not show_ip_route:
        return None

    network = affected_network
    network_without_mask = network.split("/")[0]
    network_prefix = ".".join(network_without_mask.split(".")[:3])

    if network in show_ip_route:
        return None
    if network_without_mask in show_ip_route:
        return None
    if network_prefix in show_ip_route:
        return None

    return {
        "type": "ROUTE_MISSING",
        "network": affected_network,
        "severity": "HIGH",
        "message": (
            f"No route to affected network {affected_network} was found "
            f"in the routing table."
        ),
    }


def check_duplicate_ip(show_ip_interface_brief, show_ip_arp=""):
    """
    Detect duplicate IP addresses either:
      - two router interfaces sharing the same IP in `show ip interface brief`, or
      - `show ip arp` reporting one IP mapped to two different MAC addresses.
    """
    problems = []

    rows = _parse_show_ip_interface_brief(show_ip_interface_brief)
    seen = {}
    for row in rows:
        ip = row["ip_address"]
        if ip in ("unassigned", ""):
            continue
        if ip in seen:
            problems.append({
                "type": "DUPLICATE_IP",
                "ip_address": ip,
                "interfaces": [seen[ip], row["interface"]],
                "severity": "HIGH",
                "message": (
                    f"IP address {ip} is configured on both "
                    f"{seen[ip]} and {row['interface']}."
                ),
            })
        else:
            seen[ip] = row["interface"]

    if show_ip_arp:
        arp_seen = {}
        for line in show_ip_arp.splitlines():
            m = re.search(
                r"(\d{1,3}(?:\.\d{1,3}){3}).*?"
                r"([0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4})",
                line,
            )
            if not m:
                continue
            ip, mac = m.group(1), m.group(2)
            if ip in arp_seen and arp_seen[ip] != mac:
                problems.append({
                    "type": "DUPLICATE_IP",
                    "ip_address": ip,
                    "macs": [arp_seen[ip], mac],
                    "severity": "HIGH",
                    "message": (
                        f"ARP shows {ip} associated with two different MAC "
                        f"addresses ({arp_seen[ip]} and {mac}) - likely a "
                        f"duplicate/statically conflicting IP assignment."
                    ),
                })
            else:
                arp_seen[ip] = mac

    return problems


def check_wrong_mask(host_ip, host_mask, gateway_ip):
    """
    Detect a subnet mask mismatch: the host's IP/mask does not place it in
    the same subnet as its configured gateway.
    """
    if not (host_ip and host_mask and gateway_ip):
        return None
    try:
        host_iface = ipaddress.ip_interface(f"{host_ip}/{host_mask}")
        if ipaddress.ip_address(gateway_ip) not in host_iface.network:
            return {
                "type": "WRONG_MASK",
                "host_ip": host_ip,
                "host_mask": host_mask,
                "gateway_ip": gateway_ip,
                "severity": "MEDIUM",
                "message": (
                    f"Host {host_ip}/{host_mask} does not share a subnet "
                    f"with its configured gateway {gateway_ip} - the mask "
                    f"is likely misconfigured."
                ),
            }
    except ValueError:
        return {
            "type": "WRONG_MASK",
            "host_ip": host_ip,
            "host_mask": host_mask,
            "severity": "MEDIUM",
            "message": f"Host IP/mask combination {host_ip}/{host_mask} is invalid.",
        }
    return None


def check_gateway_mismatch(client_gateway, show_ip_interface_brief):
    """
    Detect a client pointed at a gateway IP that does not exist on any
    router interface in the supplied `show ip interface brief` output.
    """
    if not client_gateway:
        return None

    rows = _parse_show_ip_interface_brief(show_ip_interface_brief)
    router_ips = {row["ip_address"] for row in rows if row["ip_address"] != "unassigned"}

    if client_gateway not in router_ips:
        return {
            "type": "GATEWAY_MISMATCH",
            "configured_gateway": client_gateway,
            "router_interfaces": sorted(router_ips),
            "severity": "HIGH",
            "message": (
                f"Client's configured gateway {client_gateway} does not "
                f"match any router interface IP in the supplied evidence "
                f"({', '.join(sorted(router_ips)) or 'none found'})."
            ),
        }
    return None


def check_missing_vlan(show_vlan_brief, required_vlan, port=None):
    """
    Detect that a required VLAN is missing from the switch entirely, or
    that a specific access port is not a member of it.
    """
    if not show_vlan_brief or not required_vlan:
        return None

    vlan_line = None
    for line in show_vlan_brief.splitlines():
        if re.match(rf"^\s*{re.escape(str(required_vlan))}\b", line):
            vlan_line = line
            break

    if vlan_line is None:
        return {
            "type": "VLAN_MISSING",
            "vlan": required_vlan,
            "severity": "HIGH",
            "message": f"VLAN {required_vlan} does not exist on this switch.",
        }

    if port and port not in vlan_line:
        return {
            "type": "VLAN_PORT_MISMATCH",
            "vlan": required_vlan,
            "port": port,
            "severity": "MEDIUM",
            "message": (
                f"Port {port} is not listed as a member of VLAN "
                f"{required_vlan} ({vlan_line.strip()})."
            ),
        }

    return None


# --------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------

def check_rules(show_ip_interface_brief, affected_network, show_ip_route="",
                 show_ip_arp="", show_vlan_brief="", required_vlan=None,
                 port=None, host_ip=None, host_mask=None, client_gateway=None):
    """
    Run every deterministic check and return ALL findings (not just the
    first match), most severe/specific first. Backward compatible: callers
    that only pass the original three positional args still work exactly
    as before. The returned dict mirrors the single highest-priority
    finding for legacy consumers, with the full list under "all_findings".
    """
    all_findings = []

    all_findings += check_interface_status(show_ip_interface_brief, affected_network)
    all_findings += check_protocol_status(show_ip_interface_brief, affected_network)

    route_problem = check_route(show_ip_route, affected_network)
    if route_problem:
        all_findings.append(route_problem)

    all_findings += check_duplicate_ip(show_ip_interface_brief, show_ip_arp)

    mask_problem = check_wrong_mask(host_ip, host_mask, client_gateway)
    if mask_problem:
        all_findings.append(mask_problem)

    gateway_problem = check_gateway_mismatch(client_gateway, show_ip_interface_brief)
    if gateway_problem:
        all_findings.append(gateway_problem)

    vlan_problem = check_missing_vlan(show_vlan_brief, required_vlan, port)
    if vlan_problem:
        all_findings.append(vlan_problem)

    if not all_findings:
        return {
            "type": "NO_PROBLEM",
            "severity": "INFO",
            "message": "No matching network problem detected by deterministic checks.",
            "all_findings": [],
        }

    priority = [
        "INTERFACE_DOWN", "PROTOCOL_DOWN", "DUPLICATE_IP", "GATEWAY_MISMATCH",
        "ROUTE_MISSING", "VLAN_MISSING", "VLAN_PORT_MISMATCH", "WRONG_MASK",
    ]
    all_findings.sort(key=lambda f: priority.index(f["type"]) if f["type"] in priority else 99)

    primary = dict(all_findings[0])
    primary["all_findings"] = all_findings
    return primary


# --------------------------------------------------------------------
# Direct test
# --------------------------------------------------------------------

if __name__ == "__main__":
    show_output = """
Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0     192.168.10.1    YES manual up                    up
GigabitEthernet0/1     192.168.20.1    YES manual administratively down down
GigabitEthernet0/2     unassigned      YES unset  administratively down down
Vlan1                  unassigned      YES unset  administratively down down
"""

    affected_network = "192.168.20.0/24"

    result = check_rules(show_output, affected_network)
    import json
    print(json.dumps(result, indent=2))
