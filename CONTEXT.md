# CONTEXT — murphy-c2

murphy-c2 is a LAN device-awareness server. It watches a local network, keeps a
live picture of which devices are present, and — where SSH access has been
explicitly declared — runs modules against them.

This file is the shared vocabulary. Ticket bodies, test names, type names, and UI
copy use these terms. Workers reading a ticket never saw the conversation that
produced it; this glossary is the only language they share with it.

---

## Core nouns

**Device** — one physical or virtual machine observed on the LAN, identified by
its **MAC address** where known, otherwise by IP. The MAC is the stable identity;
IPs move.

**Device record** — murphy's current knowledge of one device: identity,
addresses, names, presence, and type guess. Held in the **registry**.

**Registry** — the in-memory collection of device records. It is authoritative
for the running process and is **not** persisted; only user labels survive a
restart (see **Label**).

**Endpoint** — a device against which murphy has **declared SSH access**. Every
endpoint is a device; almost no device is an endpoint. Access is declared in
configuration, never discovered.

> **Reserved word.** "Endpoint" means an SSH-reachable device and nothing else.
> HTTP paths served by the backend are **routes**, never endpoints.

**Module** — a unit of work that runs against an endpoint over SSH. Modules
require a pre-existing declared endpoint. They never probe for SSH, never
enumerate credentials, and never attempt authentication against an undeclared
device.

---

## Presence

**Sighting** — a single observation that proves a device exists right now, from
exactly one **evidence layer**.

**Evidence layer** — the mechanism that produced a sighting. Exactly five exist:

| Layer | Mechanism | Yields |
|---|---|---|
| `icmp` | ICMP echo (`IcmpSendEcho`) | liveness |
| `arp` | reading the OS ARP table (`GetIpNetTable`) | liveness + MAC |
| `mdns` | passive multicast DNS listen | name + service type |
| `ssdp` | passive SSDP/UPnP listen | name + service type |
| `netbios` | NetBIOS name query, UDP 137 | name |

A device is **up** if any layer has proven it within the current window. The
record always carries *which* layers proved it — presence is never an
unattributed boolean.

**Discovery sweep** — the periodic pass that looks for devices murphy does not
yet know about: ICMP across the subnet, then a read of the ARP table that sweep
populated. Default every 60s.

**Liveness loop** — the faster pass that re-checks devices already in the
registry. Default every 10s.

> These are different operations. Do not call either one "the scan".

**Down** — three consecutive missed liveness checks. One miss is not down; Wi-Fi
devices drop single pings routinely.

**Seen-up duration** — how long murphy has continuously observed a device, its
clock starting at **first sighting**. A device discovered ten minutes after the
server started reads `0s`, not `10m`. Going down and returning resets it to zero.
A server restart resets every device's clock.

> **Never call this "uptime".** Uptime means time since the device booted, which
> murphy cannot measure without credentials. UI copy reads **"seen up 3h 20m"**.
> Boot uptime may arrive later as a module against an endpoint; it is a different
> field with a different name.

---

## Naming

**Hostname** — a name murphy *observed*, via mDNS, SSDP, or NetBIOS. Reverse DNS
is not a source; it yields nothing on the target network. May be absent.

**Label** — a name the *user* assigned to a device. Keyed by MAC and persisted to
disk. The label store holds labels only — no scan history, no presence data.

**Display name** — what the UI shows: label if present, else hostname, else IP.
A device with no observed name is displayed as its IP, not as "Unknown".

---

## Typing

**Type guess** — murphy's inference about what a device *is*, always carried as
`{ type, confidence, evidence[] }`, never a bare string. The evidence list is
shown to the user: the dashboard explains *why* it thinks something is a printer.

**Type taxonomy** — the closed set of values:

`router` · `computer` · `phone` · `printer` · `media` · `iot` · `unknown`

`unknown` is a legitimate, common answer. It is preferable to a confident wrong
guess.

**Typing signals**, in descending strength:

1. **OUI vendor** — the first three MAC octets resolved against a bundled IEEE
   table. Unavailable for **locally-administered MACs** (randomised addresses,
   common on phones) — those are detectable by bit 1 of the first octet.
2. **Service type** — mDNS/SSDP service names (`_ipp` → printer, `_googlecast` →
   media, and so on), which name the category outright.
3. **Hostname pattern** — weakest; a tiebreaker, never a sole basis.

TCP port fingerprinting is **out of scope**. It is an active probe and does not
fit the project's posture.

---

## Posture

murphy is **non-intrusive by design**:

- It sends ICMP echo, NetBIOS name queries, and joins multicast groups. Nothing
  else touches the network.
- It does not port-scan.
- It does not discover SSH, enumerate credentials, or attempt authentication.
- It requires no elevation: `IcmpSendEcho`, `GetIpNetTable`, and ordinary UDP
  sockets cover every mechanism above.

These are product constraints, not implementation preferences. A change that
breaks one is an ADR-level decision.
