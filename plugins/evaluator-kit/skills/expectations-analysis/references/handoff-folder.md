# The Handoff Folders

The contract between the two evaluator-lens skills and the user's work. `expectations-analysis` owns `docs/evaluator-expectations/`; `submission-audit` owns `docs/submission-audit/`; the post-mortem reads both. Nothing in the pipeline depends on chat history — if a file is not here, the next step cannot see it.

This file is identical in both skills. If you change it in one, change it in the other.

## Location

Both folders sit under `docs/` relative to the project root. When there is no project (a proposal in a scratch directory, a claude.ai conversation), use the current working directory. The paths are fixed so every skill and every session finds them without being told.

Both folders are working material, not part of the submission. In a repo, add them to `.gitignore` when creating them and say so; the user removes the lines if they want them tracked. Never let an evaluator find a model of their own rubric, or an audit against it, inside the thing they are reviewing.

```
docs/
  evaluator-expectations/      ← analysis skill
    expectations.md
    brief.md
    outcome.md                ← user pastes feedback here
    calibration.md            ← post-mortem
  submission-audit/           ← audit skill
    inventory.md
    audit-partial.md          ← partial mode
    audit-final.md
    evidence.md
    gaps.md
```

## `docs/evaluator-expectations/`

| File | Written by | Read by | When |
|---|---|---|---|
| `expectations.md` | analysis | user (guides the work), audit, post-mortem | Analysis, stage 1; overwritten on re-run |
| `brief.md` | analysis | audit (backstop), post-mortem | Analysis, stage 1; appended when a chat continues |
| `outcome.md` | user (pasted feedback) | post-mortem | When the result arrives |
| `calibration.md` | post-mortem | user; the next analysis | After the outcome |

### `brief.md`

The input, verbatim. If it arrived as a PDF, a web page, or a chat message, extract the text and keep the structure (headings, bullets, mandated templates). For a message or chat history, keep every message with its speaker and date and number them (`msg 1`, `msg 2`, …) — the Lens cites those numbers. Do not summarise. The audit uses this as the backstop for explicit requirements the Lens may have compressed, and the post-mortem needs the exact sentences.

There is no separate `context.md`: what the user said that the input did not (role, deadline, prior rejection, their own framing) lives in the Lens's **Context understanding** section.

### `expectations.md`

The Evaluator Lens exactly as presented to the user — one document, seven sections — with the front-matter block at the top. Headings are the template's and are not renamed, because the audit reads sections by name.

Front-matter:

```yaml
---
kind: evaluator-lens
version: 1
written: 2026-10-08
document: "Sniffspot Take-Home: Promo Codes"
archetype: technical-take-home
brief: brief.md
veto: "The session shows the AI proposing and you approving; we couldn't see your reasoning steering it."
first_surface: SUBMISSION.md
submission_form: repo + README
ai_receptiveness: 85
---
```

- `kind` identifies the file to any reader.
- `version` increments on every overwrite. The audit records the version it graded against; a post-mortem compares.
- `archetype` is the Phase 0 classification, one of: `technical-take-home`, `interview-exercise`, `job-application`, `client-brief`, `prd`, `internal-ticket`, `rfp`, `grant`, `academic-assignment`, `hackathon`, `design-brief`, `message-thread`, `hybrid`.
- `veto` is the one-sentence veto from **Deal breakers**, verbatim. A reader that reads nothing else reads this.
- `first_surface` is the first thing the evaluator opens, from the reading order in Phase 6. The audit checks the veto proof lives there.
- `submission_form` is the form the **Submission package** takes (message reply, proposal, repo + README, video, cover note, form, deck, hybrid).
- `ai_receptiveness` is the percentage from **AI receptiveness**; recorded so the audit can compare what the submission says about AI use against it (planned for the audit skill; not checked yet).

Sections the audit reads by name, in this order: **Deal breakers** (the veto criterion and the traps), **Matrix** (criterion, weight, confidence, failing looks like), **Submission package** (the package items, **Proof per criterion**, **Required-to-exist events**, **Pre-submission check**), **Explicit requirements** and **Implicit requirements** (severity drives which misses are blocking), and **AI receptiveness**. **Description**, **Context understanding**, **Evaluator intent** and **Deal makers** are for the user; the audit reads **Context understanding** for the user's role and constraints.

### `outcome.md`

Pasted by the user, or written by the analysis skill when the user shares feedback in chat. The feedback verbatim, plus one line for the result:

```
result: rejected | accepted | revise | no-response
date: 2026-10-21
---
<feedback verbatim>
```

### `calibration.md`

Written by the post-mortem. The four answers from the post-mortem section of the analysis template, plus the `lens_version` and audit verdict that were in force. This file is the one that teaches: the "what changes next time" lines are instructions to the next analysis.

## `docs/submission-audit/`

| File | Written by | Read by | When |
|---|---|---|---|
| `inventory.md` | audit | re-audit (to diff), post-mortem | Every audit run |
| `audit-partial.md` | audit, partial mode | user, audit full mode | Halfway through the work |
| `audit-final.md` | audit, full mode | user, post-mortem | Before submitting; overwritten each round |
| `evidence.md` | audit, full mode | user who disputes a grade, post-mortem | Every full run |
| `gaps.md` | audit, full mode | user, while fixing; next round | Every full run; closed items carried forward |

### `audit-final.md` front-matter

```yaml
---
kind: evaluator-audit
mode: full
round: 1
written: 2026-10-10
lens_path: docs/evaluator-expectations/expectations.md
lens_version: 1
lens_derived_at_audit: false
independence: fresh-session | subagent | same-context
submission_ref: "git a1b2c3d (6 commits, 2026-10-09T18:02..2026-10-09T21:40) | files: …"
verdict: ship | fix-first | not-ready
weighted_score: 41
veto_status: strong | adequate | weak | missing
veto_on_first_surface: false
first_pass: "<one line in the evaluator's voice, written after the first surface only>"
---
```

- `round` increments on each full re-audit; `gaps.md` carries closed items forward.
- `lens_derived_at_audit: true` means no Lens existed before the work and no halfway checkpoint ran; the post-mortem weighs that.
- `independence` records whether the audit ran blind. `same-context` verdicts are optimistic by construction.
- `submission_ref` lets a later run tell what changed: a commit hash and range for a repo, or the file list with sizes for documents.

### `audit-partial.md` front-matter

```yaml
---
kind: evaluator-audit
mode: partial
written: 2026-10-09
lens_version: 1
independence: …
submission_ref: "…"
---
```

Contains only the required-to-exist events table (event · happened? · evidence · if not, when and what) and a three-line "do next". No verdict, no score.

### `evidence.md`, `gaps.md`, `inventory.md`

Templates in the audit skill's `assets/output-templates.md`. Their front-matter carries `kind` (`evaluator-audit-evidence`, `evaluator-audit-gaps`, `evaluator-audit-inventory`), `round`, and `written`.

## Lookup rules for downstream skills

When the audit (or any later step) needs the Lens:

1. A path the user gave in the request.
2. `docs/evaluator-expectations/expectations.md` under the project root or current directory.
3. A file attached to the conversation whose front-matter says `kind: evaluator-lens`.

Stop at the first hit. If none: do not derive a rubric in the same context as the submission. Say the Lens is missing, run `expectations-analysis` in a separate context on the brief alone (the user must supply the brief), let it write the folder, then proceed — and set `lens_derived_at_audit: true` in the audit's front-matter.

When the post-mortem needs the audit: `docs/submission-audit/audit-final.md` (latest round), then `gaps.md` for what was known and left open, then `evidence.md` if a specific grade is in question.

## Why folders and not the conversation

Three reasons, each of which has already bitten once:

- **Sessions end.** The analysis is done days before the audit. Chat history is not an input a later session can read.
- **Independence.** The audit must run blind — a fresh context that has not watched the work being produced. The only way to hand it the rubric without handing it the conversation is a file.
- **One rubric.** If the audit cannot find the Lens, the temptation is to rebuild it from the brief while looking at the submission, which produces a rubric shaped to pass the submission. A fixed file at a fixed path removes the temptation.
