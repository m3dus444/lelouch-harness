# ADR-0001 — Layered discovery: ICMP sweep + ARP harvest + passive mDNS/SSDP

**Status:** accepted · 2026-09-03

## Context

Milestone 1 must show every device that is up on the LAN. Four mechanisms were
available: passive mDNS/SSDP listening, reading the OS ARP table, an ICMP sweep,
and TCP connect probing.

The initial preference was strict passive listening. Measurement on the target
network (`192.168.1.0/24`) contradicted it:

| Method | Devices found |
|---|---|
| ICMP echo sweep of the /24 | **9** |
| OS ARP table read *after* that sweep | **18** |
| Reverse DNS over all responders | **0 hostnames** |

Nine devices answer ARP but silently drop ICMP. A ping-only view is blind to half
the network. A strictly passive view is blinder still: it sees only devices that
volunteer an advertisement, which excludes the gateway, the PCs, and most IoT
hardware. The cold ARP cache held 2 entries, so reading it without first
provoking traffic is not a substitute either.

## Decision

Discovery is **layered**, and a device is up if **any** layer proves it:

1. **ICMP sweep** across the auto-detected subnet — default every 60s.
2. **ARP table read** immediately after, harvesting the entries the sweep's own
   address resolution populated. This is what finds the nine ICMP-silent
   devices, and it is the only source of MAC addresses.
3. **Passive mDNS/SSDP listening**, continuous. Retained not as a discovery
   mechanism but as the **naming and typing** signal, which is where it is
   genuinely strong.
4. **NetBIOS name query** (UDP 137) for devices with no mDNS/SSDP name, because
   reverse DNS yields nothing.

Every device record carries which layers proved it. Presence is never an
unattributed boolean.

**TCP port fingerprinting is rejected.** It is an active probe, it conflicts with
the project's non-intrusive posture, and OUI plus service-type signals cover
typing adequately.

## Consequences

- Discovery generates traffic: one ICMP echo per address per sweep, and one UDP
  packet per unnamed host. This is accepted; it is bounded and small.
- MAC addresses — and therefore OUI vendor typing — depend on the ARP layer. A
  device reachable only via mDNS has no MAC and no vendor.
- No elevation is required. `IcmpSendEcho` and `GetIpNetTable` are unprivileged
  on Windows, as is joining a multicast group.
- Subnet is auto-detected from the active interface, with a configuration
  override. **Auto-detection must not select the WSL2 Hyper-V adapter**
  (`172.23.x.x` on the development machine); that network is NAT'd and contains
  no LAN devices.
