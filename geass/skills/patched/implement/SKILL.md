---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
---

Implement the work described by the user in the spec or tickets.

Use /tdd where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, use /prod-review to review the work against its spec.

Do NOT also run a standards/lint review here - the no-mistakes ship gate
owns that axis, and running both produces contradictory findings.

Commit your work to the current branch.
