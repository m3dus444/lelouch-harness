# ADR-0003 — SSH access is declared, never discovered

**Status:** accepted · 2026-09-03

## Context

murphy runs modules against endpoints over SSH. A device-awareness server that
already sweeps the network is one small step from probing port 22, fingerprinting
SSH banners, or trying credentials against whatever it finds. That step turns a
network-visibility tool into a scanner of a different character.

## Decision

**SSH access is declared by the operator. murphy never discovers it.**

Concretely, and as a product constraint rather than an implementation detail:

- murphy does **not** probe for SSH, port-scan for 22, or fingerprint SSH
  services.
- murphy does **not** enumerate, guess, or attempt credentials.
- A **module** may run against a device only if that device is a declared
  **endpoint**.

At milestone 1, endpoints are declared in an optional `endpoints.toml` (host,
user, key path). murphy reads it, badges the matching device records as having
declared SSH access, and defines the module trait — but **opens no SSH
connection and ships no module**. Milestone 1 contains zero credential-handling
code.

## Consequences

- The endpoint set is small, deliberate, and operator-authored. This is the
  point.
- A device may be an endpoint before murphy ever sights it on the network; the
  declaration is independent of discovery.
- Credential storage, key management, and the module execution surface are
  deferred, and each deserves its own decision rather than a rushed corner of
  milestone 1.
- Reversing this — adding SSH discovery — would be an ADR-level change, not a
  feature toggle.
