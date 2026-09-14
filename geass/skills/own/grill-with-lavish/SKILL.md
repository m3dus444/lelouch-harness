---
name: grill-with-lavish
description: "Run the intake interview as a Lavish artifact instead of terminal questions, and write the glossary as it goes. Use for any Full-tier request - a design choice, new behaviour, or more than one file - before a spec or tickets exist. Replaces asking the user a long series of questions in chat."
metadata:
  author: the Lelouch harness
  hermes-tags: intake, design, interview, lavish
---

# grill-with-lavish

The intake interview, rendered as a page the user can see whole, answer out of
order, and come back to — instead of twenty questions they have to scroll
through.

It composes three skills. It adds no logic of its own:

| | |
|---|---|
| `grilling` | produces the questions |
| `lavish` | renders them, and carries the answers back |
| `domain-modeling` | writes `CONTEXT.md` and the ADRs from what got settled |

## The loop

**One artifact for the whole interview.** Rounds are republished to the same
file, so the user keeps their history and can revisit an earlier answer.

1. **Run `grilling`** to produce this round's questions. Do not ask them in the
   terminal.
2. **Build the round into the artifact** (see below), then open it:
   `lavish-axi <file>`.
3. **Poll and wait:** `lavish-axi poll <file>`. It blocks silently — that is
   normal. Never kill it.
4. **Run `domain-modeling`** on what that round settled. Every round, not at the
   end.
5. **Next round, same file.** Write the new questions in the vocabulary the
   glossary now holds, mark the answered ones as settled, and republish. Reply
   into the page with `poll --agent-reply "<message>"`, which both answers and
   resumes waiting.
6. **Stop when nothing is left that would change the build.** Then hand off to
   `to-spec`.

### Why `domain-modeling` runs every round

Because the interview should start speaking the project's language as soon as
there is one. A term settled in round one is a term round three can use without
re-litigating, and the glossary is written while the reasoning is still fresh
rather than reconstructed at the end.

It is also the only thing that reliably makes it happen at all. In run 2
`domain-modeling` was invoked **zero times in six days**, and a hand-written
`CONTEXT.md` stood in for it. A skill that calls it is worth more than a rule
that asks someone to remember.

## Building the round

**Read the playbooks first.** `lavish-axi playbook input` is mandatory here —
this artifact exists to collect structured answers — and `playbook plan` or
`playbook comparison` when a question is really a choice between shapes.

Rules that matter for this particular page:

- **One control per question, and a Submit per question.** Do not queue a prompt
  on every radio change; the user is allowed to change their mind before
  sending.
- **Say why each question is being asked.** A question whose consequence is
  invisible gets answered carelessly. "This decides whether we can page results
  later" earns a better answer than "Sort order?".
- **Give each question a recommendation where you have one**, with the cheaper
  alternative named. §4's shape: not an options survey.
- **Show what is already settled**, struck through or collapsed, so the page
  reads as progress rather than an unchanging wall.
- **Questions the user has not answered yet stay visible.** Do not silently drop
  one because the round moved on.

### Design

Follow lavish's own design priority. On a **fresh project there is no design
system yet**, so its recommended default is correct — do not invent a look for a
product that has not decided on one. Once the project has tokens, use them, and
keep **one shared copy at `.lavish/ds/`** with pages at `.lavish/` root: a page
in a subfolder cannot reach a folder above it, and Lavish serves each artifact
from its own directory.

## What the terminal sees

**One line: the page is ready.** Nothing about what is in it, how it is laid
out, or what you put in each section.

The user has the page open and a feedback sidebar in it. Describing the artifact
in chat is the exact duplication §0 forbids — and it is the loudest instance of
it, because a grill produces many rounds.

Between publishing and their answer, say nothing at all.

## When an answer arrives in chat instead

Put it back in the page. Record it as that question's answer, republish, and
continue there. The page is the record of the interview; an answer that only
exists in the conversation is one that does not survive the session, which is
the same reason decisions live in the backlog rather than in chat.

## What this skill is not

- **Not the approval gate.** §6's ticket breakdown is a separate artifact, after
  `to-spec` and `to-tickets`. Do not fold the two into one page.
- **Not for Direct or Trusted tier.** A fully specified one-file change does not
  get an interview, and "just do X" is an instruction, not an opening question.
- **Not a replacement for escalation.** A decision that arises mid-build goes
  through §4, not through reopening the grill.
