# ADR-0002 — Seen-up duration, not uptime

**Status:** accepted · 2026-09-03

## Context

The milestone asked to show "how long it's been up" for each device. Two
different quantities hide under that phrase:

- **Boot uptime** — time since the device powered on. Obtainable only from the
  device itself, via SSH or SNMP, and therefore only for devices whose
  credentials we hold. On a typical LAN that is nearly none of them.
- **Observed presence** — how long *murphy* has continuously seen the device.
  Available for every device, and meaningless before murphy started running.

Presenting the second under the name of the first would be a quiet lie in the
most prominent column of the dashboard. A dashboard that lies about one number
is not trusted about any of them.

## Decision

Milestone 1 ships **observed presence only**, named **seen-up duration**
throughout code, API, and UI.

Semantics:

- The clock starts at **first sighting**, not at server start. A device first
  seen ten minutes after startup reads `0s`. Reporting `10m` would claim
  presence that was never observed.
- **Three consecutive missed liveness checks** mark a device down. One miss does
  not; Wi-Fi devices drop single pings routinely.
- A device that goes down and returns **resets to zero**. It is a new continuous
  presence.
- A **server restart resets every clock.** No presence history is persisted.

UI copy reads **"seen up 3h 20m"**, with "since murphy started" available on
hover. The word "uptime" does not appear.

## Consequences

- The number is small and uninformative immediately after a restart. This is
  honest and accepted.
- Boot uptime remains available later as a **module** run against a declared
  endpoint (ADR-0003). It will be a separate field with a separate name, never a
  substitution into this one.
- No persistence layer is needed for presence. The only thing written to disk is
  the user label store.
