# Domain Docs

How the engineering skills should consume this repo's domain documentation when
exploring the codebase. This repo is **single-context**.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — the glossary and shared vocabulary.
- **`docs/adr/`** — read the ADRs that touch the area you are about to work in.

If either is missing, **proceed silently**. Don't flag their absence and don't
suggest creating them upfront. `domain-modeling` creates them lazily, when a
term or decision is actually resolved.

## File structure

```
/
├── CONTEXT.md
├── backlog.md              ← tasks-axi, see issue-tracker.md
├── docs/
│   ├── adr/
│   │   └── 0001-<slug>.md
│   └── agents/
│       ├── issue-tracker.md
│       ├── domain.md
│       └── dispatch-templates.md
└── .lavish/                ← review artifacts
```

## Use the glossary's vocabulary

When your output names a domain concept — a ticket title, a refactor proposal, a
hypothesis, a test name — use the term as defined in `CONTEXT.md`. Don't drift to
synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're
inventing language the project doesn't use (reconsider), or there's a real gap
(note it for `/domain-modeling`).

This matters more than usual here, because ticket bodies written by Lelouch are
read by workers that never saw the conversation that produced them. The glossary
is the only vocabulary they share.

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than
silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
