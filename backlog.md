# Backlog

## In flight
## Queued
- [ ] m1-scaffold - Scaffold backend + frontend and freeze the API contract (repo: murphy-c2) (kind: ship) (since 2026-09-03)
  Stand up the two halves of murphy-c2 and FREEZE the API contract, so that
  discovery, enrichment and UI work can proceed in parallel against a stable shape.

  Read CONTEXT.md first. Its vocabulary is binding: device, registry, endpoint,
  evidence layer, sighting, seen-up duration, label, display name, type guess.
  Note especially that "endpoint" means an SSH-reachable device - HTTP paths are
  "routes", never endpoints.

  ## Build

  Backend: a Rust crate at /backend using axum + tokio.
  Frontend: Vite + React 18 + TypeScript + Tailwind v3 + Zustand + Framer Motion
  at /frontend, with a dev proxy to the backend.

  Define the wire contract as Rust types with `ts-rs` derives that generate the
  TypeScript types the frontend imports. The contract must express:

  - device identity (MAC where known, else IP) and IP address
  - observed hostname (optional), user label (optional), and the display-name
    fallback chain: label -> hostname -> IP
  - presence: up/down, plus which evidence layers proved it (icmp, arp, mdns,
    ssdp, netbios)
  - seen-up duration, as a first-sighting timestamp the client renders from
  - type guess as { type, confidence, evidence[] } over the closed taxonomy
    router | computer | phone | printer | media | iot | unknown
  - ssh_declared: bool

  Routes, all stubbed in this ticket against fixture data:
  - GET  /api/devices             -> current registry snapshot
  - GET  /api/events              -> SSE stream of device added/updated/removed
  - PUT  /api/devices/{mac}/label -> set a user label

  The fixtures must include the awkward cases the real LAN contains, because the
  UI ticket is built against them: a device with no hostname at all, a device with
  a locally-administered (randomised) MAC and therefore no vendor, a device typed
  `unknown`, a device that is down, and a device with ssh_declared = true.

  ## Done means

  - `cargo run` serves all three routes; GET /api/devices returns the fixtures and
    /api/events emits a fixture event periodically.
  - `npm run dev` proxies to the backend and renders the fetched data (raw is fine
    - the dashboard is a separate ticket).
  - TypeScript types are generated from the Rust types, not hand-written, and the
    frontend imports them.
  - cargo test, cargo clippy, and tsc all clean.

  ## Out of scope

  Real network access of any kind. No ICMP, no ARP, no sockets. This ticket ships
  fixtures only.

- [ ] m1-discovery - Discovery engine and seen-up presence model blocked-by: m1-scaffold (repo: murphy-c2) (kind: ship) (since 2026-09-03)
  Implement the discovery engine and the presence model: find the devices on the
  LAN and track how long each has been continuously seen.

  Read CONTEXT.md, docs/adr/0001-layered-discovery.md and
  docs/adr/0002-seen-up-not-uptime.md before starting. ADR-0001 records measured
  evidence that shaped this design; do not re-litigate it.

  ## Build

  Subnet detection: auto-detect the active interface IPv4 subnet, with a config
  override. It MUST NOT select the WSL2 Hyper-V adapter (172.23.x.x on the
  development machine) - that network is NAT'd and holds no LAN devices. This is a
  concrete trap, not a hypothetical.

  Discovery sweep (default 60s):
  1. ICMP echo across the subnet via the Windows `IcmpSendEcho` API, fully
     concurrent. No elevation is required and none may be requested.
  2. Immediately after, read the OS ARP table via `GetIpNetTable`. This harvests
     entries the sweep's own address resolution populated, and is the ONLY source
     of MAC addresses. On the development LAN it finds roughly twice what ICMP
     alone finds - around 18 devices versus 9.

  Liveness loop (default 10s): re-check devices already in the registry.

  Both cadences configurable, with those defaults.

  Presence semantics, exactly as ADR-0002 specifies:
  - The seen-up clock starts at FIRST SIGHTING, not at server start. A device
    first seen ten minutes after startup reads 0s.
  - Three consecutive missed liveness checks mark a device down. One miss does not.
  - Down-then-returned resets the clock to zero.
  - Nothing about presence is persisted; a restart resets every clock.

  Every device record carries which evidence layers proved it.

  ## Seams to test at

  The registry state transitions, with an INJECTED CLOCK and an injected prober.
  The seen-up state machine - first sighting, miss, miss, miss, down, return,
  reset - must be tested deterministically without touching the network. Put the
  seam where a fake prober can feed sightings in.

  ## Done means

  - Tests cover the seen-up state machine at every transition above, using a fake
    clock. No test sleeps in real time.
  - Running against the real LAN finds substantially more devices than ICMP alone
    would, and each record names its evidence layers.
  - Subnet auto-detection is tested against a fixture interface list that includes
    a WSL-style adapter, proving it is not selected.
  - cargo test and cargo clippy clean.

  ## Out of scope

  Naming, typing, mDNS/SSDP, NetBIOS, OUI - those are m1-enrich. Wiring the
  registry into the routes is m1-integrate. No TCP port probing, ever (ADR-0001).

- [ ] m1-ssh-seam - Endpoint declaration and module seam blocked-by: m1-scaffold (repo: murphy-c2) (kind: ship) (since 2026-09-03)
  Define the endpoint declaration surface and the module seam. Ship no module and
  open no SSH connection.

  Read CONTEXT.md and docs/adr/0003-declared-ssh-endpoints.md. That ADR is a
  product constraint: SSH access is declared by the operator and NEVER discovered.

  ## Build

  - Parse an optional `endpoints.toml` at startup: each entry declares a host
    (hostname or IP), a user, and a key path. A missing file is normal, not an
    error.
  - An Endpoint is a device with declared SSH access. Match declarations onto
    device records by IP, and by MAC where the declaration allows it.
  - Set `ssh_declared` on matching device records (the field is already in the
    contract from m1-scaffold).
  - Define the module trait: the shape a future module implements to run against
    an endpoint. Include the registry that would hold modules. Nothing implements
    it yet.
  - A declaration for a device murphy has never sighted is valid and must not
    error; the declaration is independent of discovery.

  ## Done means

  - Tests: a well-formed endpoints.toml parses; a missing file is a no-op; a
    malformed file produces a clear error naming the problem; declarations match
    onto device records by IP and by MAC; a declaration for an unsighted device is
    retained without error.
  - ZERO SSH connections are opened. ZERO credential-handling code ships. No
    probing of port 22, no banner fingerprinting.
  - cargo test and cargo clippy clean.

  ## Out of scope

  Any actual module. Any SSH client code. Credential storage or entry UI.

- [ ] m1-ui - Device dashboard against the stub backend blocked-by: m1-scaffold (repo: murphy-c2) (kind: ship) (since 2026-09-03)
  Build the device dashboard against the stub backend from m1-scaffold.

  Read CONTEXT.md. Its vocabulary is binding in UI copy too - and one rule matters
  above the rest, from docs/adr/0002-seen-up-not-uptime.md:

    The word "uptime" MUST NOT appear anywhere in the UI. The column reads
    "seen up 3h 20m", with "since murphy started" available on hover. We are
    showing observed presence, not boot time, and saying otherwise is a lie in
    the most prominent column of the dashboard.

  ## Build

  A single dashboard listing every device, using the generated TypeScript types
  from the contract - do not hand-write them.

  - Zustand store fed by the SSE stream at /api/events, seeded from GET
    /api/devices.
  - Columns: display name, IP, seen-up duration, device type.
  - Display name follows the fallback chain: label -> hostname -> IP. A device
    with no observed name shows its IP. It must NOT show "Unknown".
  - Seen-up renders as a live-ticking duration from the first-sighting timestamp.
  - Device type shows the type plus its confidence, and the evidence list is
    reachable (tooltip or expansion): the dashboard explains WHY it thinks
    something is a printer. `unknown` is a normal, respectable value - do not
    style it as an error.
  - Devices with ssh_declared get a distinct badge.
  - Down devices remain visible and are visually distinct from up devices.
  - Framer Motion animates devices entering, leaving, and reordering. This is the
    reason the stack includes it: results trickle in over seconds and the list
    should feel alive rather than snapping.
  - A rename control that PUTs to /api/devices/{mac}/label and optimistically
    updates the store.

  ## Done means

  - Every fixture case from m1-scaffold renders correctly: no hostname, randomised
    MAC with no vendor, type `unknown`, a down device, an ssh_declared device.
  - The string "uptime" appears nowhere in user-facing copy.
  - Reconnects on SSE drop without losing store state.
  - tsc clean, lint clean, and component tests cover the display-name fallback
    chain and the seen-up formatting.

  ## Out of scope

  Any backend work. Build strictly against the stub routes.

- [ ] m1-enrich - Naming and device-type inference blocked-by: m1-discovery (repo: murphy-c2) (kind: ship) (since 2026-09-03)
  Give devices names and types. This is where mDNS, SSDP, NetBIOS and the OUI
  table earn their place.

  Read CONTEXT.md and docs/adr/0001-layered-discovery.md first.

  ## Build

  Naming - reverse DNS is NOT a source; it returns nothing on the target network,
  which is why the other three exist:
  - Passive mDNS listener (continuous multicast listen).
  - Passive SSDP/UPnP listener (continuous).
  - NetBIOS name query over UDP 137, for devices that have no mDNS/SSDP name.
    This is what names Windows machines and NAS boxes.
  - Label store: user-assigned names, keyed by MAC, persisted as JSON on disk.
    Implement the PUT /api/devices/{mac}/label route for real. THE STORE HOLDS
    LABELS ONLY - no scan history, no presence data, no device records.

  Typing - produce { type, confidence, evidence[] } over the closed taxonomy
  router | computer | phone | printer | media | iot | unknown. Signals, in
  descending strength:
  1. OUI vendor: first three MAC octets against a bundled IEEE table. BUNDLE the
     table at build time - a LAN tool that needs internet to name a vendor is
     broken by design. Trim it to what is needed.
     Locally-administered MACs (bit 1 of the first octet set) are randomised
     addresses and have NO vendor. Roughly 4 of 18 devices on the development LAN
     are in this category, so this path is common, not exotic.
  2. Service type from mDNS/SSDP (_ipp -> printer, _googlecast -> media, and so
     on), which names the category outright.
  3. Hostname pattern - weakest, a tiebreaker only, never a sole basis.

  `unknown` with honest evidence beats a confident wrong guess. The evidence list
  is shown to the user, so it must be meaningful rather than internal jargon.

  ## Seams to test at

  The type inference function: MAC + services + hostname in, type guess out. Pure,
  table-driven, no network. And the name resolver, likewise pure.

  ## Done means

  - Table-driven tests for type inference including: a real OUI resolving to a
    vendor; a locally-administered MAC yielding no vendor and not crashing; an
    mDNS service that outranks a weak OUI signal; a case that correctly yields
    `unknown`.
  - OUI lookup works with no network access at all - prove it in a test.
  - A label survives a process restart; the store file contains labels and nothing
    else.
  - cargo test and cargo clippy clean.

  ## Out of scope

  TCP port fingerprinting (rejected in ADR-0001). Router DHCP-lease scraping.

- [ ] m1-integrate - Wire the real registry end to end on a live LAN blocked-by: m1-enrich blocked-by: m1-ui blocked-by: m1-ssh-seam (repo: murphy-c2) (kind: ship) (since 2026-09-03)
  Replace the fixtures with the real thing and prove milestone 1 end to end on a
  live LAN.

  ## Build

  - Wire the real registry into GET /api/devices and the /api/events SSE stream.
    Delete the fixture data path.
  - Emit SSE events from real registry transitions: device discovered, device
    updated (name or type resolved), device went down.
  - Surface the configurable cadences (10s liveness, 60s discovery) plus the
    subnet override in one config file.
  - Embed the built frontend in the release binary so `cargo run --release` serves
    the dashboard on one URL. Keep the Vite dev proxy working for development.

  ## Done means

  - Running against the real LAN, the dashboard shows the devices actually present
    with IP, a name where one is obtainable, a live seen-up duration, and a type
    guess with its evidence.
  - Devices that answer ARP but drop ICMP appear - this is the specific thing the
    layered design exists for, so verify it explicitly rather than assuming it.
  - Devices appear and disappear in the UI as they come and go, animated.
  - No fixture data remains in the codebase.
  - Full test suite, clippy, and tsc all clean.

  ## Verification to report

  State in your completion report how many devices were found, and how many of
  those ICMP alone would have missed. That number is the milestone's proof.

## Done
