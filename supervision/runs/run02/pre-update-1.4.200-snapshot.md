# Pre-update state snapshot - Orca 1.4.195 to 1.4.200

Captured 2026-09-11 23:32:04Z, orchestration.db user_version=30

Migrations v35-v38 run on next launch. **v38 closes already-pending question_threads**
on dispatches that settled before the fix existed. These are the rows it will act on.
After updating, compare against this list: anything closed here was closed by the
migration, not by the run.

## question_threads, status=pending

- **msg_3eef6b7e5dd5** created 2026-09-09 21:46:20
  - dispatch `ctx_303da4e0dd85`  asker `term_c7b7375d-122f-4df7-ace0-384c2911e52c`
  - dispatch status now: **failed**
  - subject: Question
  - body: wa-app-shell: two decisions I do not think are mine to make alone. Both are built and working; say the word and I adjust.  (1) NEW ROUTE 'GET /contract'. The ticket says the builder must derive its an
- **msg_32cdfe750cf6** created 2026-09-10 02:07:47
  - dispatch `ctx_586bcbcb7116`  asker `term_87a0b13a-272a-464b-8e40-1773a770c021`
  - dispatch status now: **failed**
  - subject: Question
  - body: wa-landing-route: three small decisions on the one permitted design/ edit, before I ship. Work is done and green (339 tests, browser-proved: / draws the landing page with its graph, CTA lands on the b
- **msg_392687777cd8** created 2026-09-10 03:20:08
  - dispatch `ctx_586bcbcb7116`  asker `term_87a0b13a-272a-464b-8e40-1773a770c021`
  - dispatch status now: **failed**
  - subject: Question
  - body: wa-landing-route: short one. Gate is at the document step, everything else is green (review clean, tests clean). This is the only thing left before push/PR.  My change makes docs/design/brief.md wrong

## outstanding deliveries at capture

- `delivery_a5d33e0a2c9b` created 2026-09-07 21:26:03 msgs=["msg_7d6e42447ff9"]
- `delivery_9c7535566d8a` created 2026-09-05 03:49:01 msgs=["msg_a4a761eac900"]
