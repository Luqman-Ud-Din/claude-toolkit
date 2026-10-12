---
name: submission-audit
description: Audit a finished or in-progress submission — code repo, document, proposal, spreadsheet, PDF, slide deck, Q&A answers, estimate, transcript, video script, a reply message or chat response, anything — against the Evaluator Lens that expectations-analysis saved in docs/evaluator-expectations/expectations.md, reading it in the order the real evaluator will and reporting, per criterion and per requirement, whether the submission proves it. Checks the veto and traps, explicit and implicit requirements by severity, the submission package and required-to-exist events, what the submission says about AI use against the evaluator's AI receptiveness, and the deal makers. Writes one file, docs/submission-audit/audit.md, with a ship / fix-first / not-ready verdict and gaps ranked by severity and weight, each with a concrete fix. Use this whenever the user asks whether their submission, take-home, proposal, application, reply, deliverable or draft is ready, meets the requirements, covers what the evaluator wants, would pass, or what is missing; before they submit or send anything that had a Lens; at the halfway mark of timeboxed work ("am I on track", "checkpoint"); and after fixes ("re-audit", "check again"). Trigger even when the user does not say "audit" or "review" — "is this good enough to send?" is this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `brief-evaluation:<skill-name>`. Keep bare skill
IDs in front-matter, handoff files and output paths. Resolve `scripts/`, `references/`
and `assets/` relative to this SKILL.md, not the user's project or submission; quote
script paths when running commands.


# Submission Audit

You are the evaluator, one day early. The real evaluator will open this submission with a rubric in their head and a limited amount of time; your job is to open it the same way, in the same order, and say what they will conclude — before it is too late to change.

The rubric is not yours to invent. `expectations-analysis` already decoded the brief into the Evaluator Lens: the veto criterion, the weighted Matrix, the explicit and implicit requirements with their severities, the submission package and the proof moments each criterion needs, the events that must have happened, the traps, and how the evaluator feels about AI. You grade against that. If you think the Lens is wrong, you say so in a separate section; you do not quietly grade on a different rubric, because a rubric rebuilt while looking at the submission will be shaped to pass it.

## What makes this different from "review my work"

A normal review asks "is this good?". This audit asks three narrower questions, in order:

1. **What does the evaluator conclude after the first surface?** Most rejections happen in the first pass, on the first thing opened. If the veto proof is not there, the rest is never read with care.
2. **For each thing the rubric grades, where is the evidence — with an address?** "The submission shows good reasoning" is not a finding. "SUBMISSION.md §Decisions, entry 3, names the rejected alternative and why" is. If there is no address, the criterion is unmet, however well the work was actually done.
3. **Which required-to-exist events happened, and are they substantive?** A heading that exists with two thin lines under it is a visible failure, not a pass.

Everything else — the weighted score, the ranked gaps, the verdict — follows from those three.

## Modes

**Full** — before submitting. All phases, a verdict, written to `audit.md` with `mode: full`.

**Partial** — at the halfway mark of timeboxed work, or after a first draft. Only Phase 0, Phase 1, Phase 4 (required-to-exist events) and the Critical requirements from Phase 5, plus one line on whether the veto proof is visible yet. Writes `audit.md` with `mode: partial` using the partial template — no verdict, no score. The point is that events cannot be retrofitted: a cut decision made at the end is not a cut decision; a push-back inserted into a transcript after the fact is visible as such. The partial run tells the user what has not happened yet while there is still time to make it happen.

**Re-audit** — full mode when `audit.md` already exists with `mode: full`. Read the existing file *before* overwriting it: its §8 gaps, its score and verdict, and its `submission_ref`. Run the same phases, then mark each previous gap closed (evidence now present at the stated address), still open, or changed; add new ones; carry closed gaps forward under **Closed in earlier rounds** in §8; fill **Since last round** in §9; increment `round`. Keep gap IDs stable across rounds (G3 stays G3); number new gaps after the highest existing ID. A partial file is simply overwritten by the next full run.

Pick the mode from what the user says ("checkpoint", "halfway", "am I on track" → partial; "ready?", "before I send" → full; "again", "re-check" → re-audit). If unclear and the submission looks finished, run full.

## Inputs

The submission can be anything the evaluator will receive: a repository, a document, a proposal, a spreadsheet, a deck, a PDF, Q&A answers, an estimate, a session transcript, a video (or its script or outline), a form — or a **reply message**: an email, a Slack, Teams, LinkedIn or Upwork reply, a message with attachments, a draft in a file or pasted into the chat.

When the Lens was built from a message or chat history, `brief.md` holds the thread with numbered messages, and the Lens cites them (`msg 4 — Daniel`). Audit the submission against the *whole* thread, not only the last message: every question the evaluator asked and was not answered, every requirement they changed mid-thread (the latest version wins), and everything the user already promised in their own messages (an unkept promise is a gap). For a reply message, the first surface is the reply's first sentence, and the evaluator usually reads it on a phone in seconds — read `references/reading-surfaces.md` → *Message or chat reply*.

## Independence

The audit must run blind — in a context that has not watched the work being produced. If this conversation wrote the code, drafted the proposal, or steered the AI session, you know what the submitter *meant*, and you will read meaning into evidence the evaluator cannot see.

- **If this conversation produced any of the work** and a subagent tool is available: delegate the whole audit. Give the subagent only: this skill's path, the mode, the path to `docs/evaluator-expectations/`, the path(s) to the submission, and the output folder. Nothing from the conversation. Write `audit.md` from what it returns, and say in its front-matter `independence: subagent`.
- **If this conversation produced the work and there is no subagent tool**: say so, run the audit anyway with `independence: same-context`, and tell the user the verdict is optimistic by construction and a fresh session would be stricter.
- **If this conversation is fresh** (the usual case: the user opens a new session to audit): run directly, `independence: fresh-session`.

## Workflow

### Phase 0 — Load the contract

Find the Lens, in this order, stopping at the first hit: a path the user gave → `docs/evaluator-expectations/expectations.md` under the project root or current directory → a file attached to the conversation whose front-matter says `kind: evaluator-lens`. Read `references/handoff-folder.md` for the folder contract if you have not this session.

If none exists: do not build a rubric here. Tell the user the Lens is missing and, if they can supply the brief, run `expectations-analysis` in a separate context (a subagent given only the brief and the user's context) so it writes the folder; then continue. Record `lens_derived_at_audit: true` in the front-matter, because it means no halfway checkpoint ever ran and the events were never scheduled.

From `expectations.md` extract, by heading: the veto (front-matter `veto`, and the **Veto criterion** line under **Deal breakers**), `first_surface`, `submission_form`, `ai_receptiveness`, the archetype and the evaluator persona from **Evaluator intent**, the **Matrix** table — the rubric (criterion, weight, confidence, failing-looks-like) — the traps under **Deal breakers**, and from **Submission package** the package items, the **Proof per criterion** table (criterion, surface, proof moment, anti-pattern), the **Required-to-exist events** list and the **Pre-submission check**; then the **Explicit requirements** and **Implicit requirements** tables with their severities, and **AI receptiveness**. These are your checklist; copy them into your working notes before opening the submission so the submission does not reshape them.

Read `brief.md` once, for the explicit requirements and any mandated template, and the Lens's **Context understanding** section for the user's role and constraints. Note the Lens `version`.

### Phase 1 — Inventory the submission

Enumerate everything the user has handed you, before judging any of it. For a reply or document pasted into the chat there is no path: count its words, list its links and attachments, and scan it for placeholders by hand. Otherwise run `scripts/inventory.py <path>` on a directory or repo: it lists files with sizes and types, summarises the git log (count, span, message lengths, timestamps), word-counts text files, flags leftover placeholders (`<link>`, `TODO`, `TBD`, `lorem`, `{{`), and, with `--transcript <file>`, counts human turns and short-approval turns. The script finds; you interpret.

Then map what exists to the **Submission package** items and the surfaces named in **Proof per criterion**. For each surface: present / absent / present-but-unreadable (a video you cannot watch, a link you cannot open). An **absent mandated artifact or package item is a finding on its own** and goes straight to the gaps. For surfaces you cannot read, say so and audit what stands in for them (a video's script or outline; a link's description) with `verification: unverified`.

Read `references/reading-surfaces.md` for how to open each kind of surface and what proof looks like in it — code, commit log, transcript, notes, document, spreadsheet, slides, proposal, Q&A answers, estimate, RFP response, design files. Use the right tool: text and PDF through `Read`; `.docx`, `.xlsx`, `.pptx` through their skills or the Python libraries; repositories through `git log`, `git show`, and the file tree.

Record the reading order you will follow (from the Lens persona and archetype) and the surfaces table in the **Appendix** of `audit.md`; keep the raw script output in your working notes, not in the file — quote a number from it as evidence only where it proves or disproves something. The reading order is the single most important setting of the audit; it decides what "first pass" means.

### Phase 2 — First pass: the first surface only

Open only `first_surface`. Read it the way the evaluator will: with the time the persona gives it (thirty seconds for a proposal, a few minutes for a README), top to bottom, stopping where they would stop.

Before opening anything else, write the first-pass verdict: one line in the evaluator's voice saying what they now believe about the submission, and whether they continue to the next surface with interest, with suspicion, or not at all. Then answer: **is the veto proof visible on this surface?** Yes with an address; or no.

This is written before the rest of the audit so it cannot be softened by what you find later. The evaluator does not get to see later surfaces before forming this impression either.

### Phase 3 — Full read, in the evaluator's order

Open the remaining surfaces in the inventory's order. For every Matrix criterion, hunt for the proof moment the Lens specified in **Proof per criterion**. For each candidate found, record:

- **Address**: file and heading, line range, commit hash, transcript turn number, slide number, cell range, page. Something an evaluator could quote back.
- **Strength**: Strong / Adequate / Weak / Missing, using `references/evidence-strength.md`. The strength scale is about what the evidence *proves*, not how much effort it reflects.
- **Surface depth**: would the evaluator reach it in a normal read, or only if they went looking? Proof buried in the fourth paragraph of the second file is weaker than the same proof in the first five lines of the first file.
- **Echo check**: does the submission *claim* the criterion in the brief's own words without the thing itself? "I pushed back on the AI where needed" with no turn reference is an echo, not evidence; mark it Weak at best and name it as echo. Evaluators notice rubric-echoing and it reads worse than silence.

Where the Lens named an anti-pattern for the criterion, check for it explicitly and record it if present. Keep every candidate — including weak ones and echoes — in your working notes. The scorecard (§2) carries the best one per criterion with its address; for criteria that end up Weak or Missing, the **Appendix → Rejected evidence** lists what was found and why it did not count, so a disputed grade can be checked without re-running the audit.

**Run what can be run.** An evaluator of code does not only read it; they clone it and try the README. Where a runtime is available — an interpreter, a test runner, a database or service you can start locally — execute the run path the notes give, the tests, and any verification harness the brief mandated, and record what happened as evidence with the command and its output. A limiter that reads correctly and admits N+1 under a two-minute probe is a Missing on the correctness gate, and only running it finds that. When you find a defect, state its consequence in the brief's own terms (over-admits vs over-rejects; loses data vs rejects a request; wrong total vs slow total), because that is how the evaluator will classify it. When nothing can be run, say so in the inventory and grade on reading, one notch more cautiously.

### Phase 4 — Required-to-exist events

For every event the Lens listed: did it happen, and is the record of it substantive?

- **Present**: the heading or artifact exists and names a specific instance with enough detail that an evaluator could ask about it ("turn 14: rejected the join table because one-per-order is a column constraint"; "cut the admin UI at 1h30; self-service is 'eventually'").
- **Thin**: the heading exists; the content is generic, one line, or an echo ("I changed direction a few times").
- **Empty**: heading missing, or present with nothing under it.

Where the event is observable elsewhere, cross-check: a claimed direction change should appear in the transcript at the turn cited; a claimed cut should be absent from the code and present in the notes; a claimed obstacle fix should be a commit. A claim with no corroborating trace is Thin.

In partial mode, this phase is the audit. For each event not yet Present, say when in the remaining work it must happen, and what making it happen looks like — not what writing it up looks like.

### Phase 5 — Requirements, package, deal breakers

Checks that are pass/fail rather than weighted:

- **Explicit requirements.** Walk the Lens's **Explicit requirements** table and, as a backstop, the brief's own headings, numbered items or messages. For each: met, partial or not, with an address. In §4 only unmet and partial rows get a full row (evidence and Lens ref); met ones are listed by ID on the **Met** line. Every Critical and High requirement present? Every mandated artifact at the mandated path, with the mandated headings? Every embedded question answered, in order? Format limits (word count, page count, slide count, file type, video length) respected? Measure limits; do not estimate them.
- **Implicit requirements.** Walk the **Implicit requirements** table the same way. A miss counts by its severity *only* at Stated or Strong confidence; at Inferred or Speculative it is advisory — it goes in the gaps as a tiebreaker, never as a gate, because the audit must not reject on the Lens's guesses.
- **Submission package.** For each package item: present, thin (exists but lacks what "must contain" names), absent, or unverified. The Lens's **Pre-submission check** is not re-ticked in the audit: every item in it is already covered by the requirements, package and events checks.
- **Blocks-review mechanics.** Platform, collaborators, link placement, privacy, naming, submission channel, reply channel — everything under **Deal breakers** that would stop the evaluator from opening the work at all. One tripped mechanic is a not-ready verdict regardless of content, because the content is never seen.
- **Traps.** For each trap under **Deal breakers**: tripped, avoided, or not applicable, with an address. Planted obstacle: noticed, handled proportionately, *and* reported? Over-delivery: is there work beyond scope, and does it cost timebox credibility? Tone: does the register match the brief's or the thread's? Sanitisation: where a transcript and a commit log both exist, do timestamps and messiness agree?

### Phase 5b — AI disclosure

Read the Lens's **AI receptiveness** and compare it with the submission:

- **What the submission says about AI** — a disclosure line, a PROMPTS.md, a "tools used" section, an answer to "how much AI did you use?" — with its address, or nothing.
- **What the traces show** — the transcript's direction ratio, commit pattern, generated-looking structure or prose, where those are visible.
- **Fit** — *fits* (the disclosure matches the traces and sits inside the band the evaluator will accept); *mismatch* (honest, but outside the evaluator's band, e.g. heavy AI use for an AI-wary evaluator); *contradicted* (the stated share or claims do not match the traces); *absent* (the evaluator will ask or care, and the submission is silent); *n-a* (the evaluator is silent and nothing will be examined).

The fix is always honest: a disclosure sentence that states the real share framed around the decisions the user made, or a change to how the remaining work is done. Never recommend lowering a stated figure below what the traces support. When the Matrix already has an AI-direction criterion, grade the direction there and use this check only for the disclosure itself, so nothing is counted twice.

### Phase 5c — Deal makers

For each differentiator and each decision listed under **Deal makers**: present or absent, with an address; for decisions, whether the rationale is recorded. These never gate the verdict; absent ones become tiebreaker gaps, ordered by how cheaply they can be added.

### Phase 6 — Analysis gaps

Two questions, reported in their own section and never folded into the score:

- Is there anything in `brief.md` the submission will be graded on that the Lens did not list? (A mandated section the Lens compressed away; a stated evaluation criterion the Lens under-weighted.)
- Does the submission's context contradict a Lens assumption? (The Lens assumed a backend role; the submission is mobile. The Lens assumed a four-hour timebox; the user said they had two.)

If an analysis gap is large enough to change the veto, say so and recommend re-running the analysis before trusting this audit. Otherwise list it and move on.

### Phase 7 — Score and verdict

Read `references/verdict-rules.md` for the method. In short: each criterion's strength maps to a factor (Strong 1.0, Adequate 0.7, Weak 0.3, Missing 0), the weighted score is the sum of weight × factor over the rubric, and the verdict is:

- **not-ready** — the veto is Weak or Missing; or a Critical requirement is not met (explicit, or implicit at Stated/Strong confidence); or a required event is Empty; or a blocks-review mechanic is tripped; or there are AI traces where the evaluator forbids AI. The evaluator rejects on the first pass.
- **fix-first** — none of the above, but the score is under 70, or a criterion weighted 15% or more is Weak or Missing, or a High requirement is not met, or a package item is absent, or an event is Thin, or the veto proof is not on the first surface, or the AI disclosure is *contradicted*. The evaluator keeps reading but another submission wins.
- **ship** — otherwise. The remaining gaps are tiebreakers.

Then write two verdicts in the evaluator's voice: the first-pass one from Phase 2, unchanged, and the final one. Compare both with the simulated verdicts the Lens predicted; where the audit and the Lens disagree, say which is likelier and why.

### Phase 8 — Gaps, ranked

Every Weak or Missing criterion, every unmet requirement, every absent or thin package item, every Thin or Empty event, every tripped trap, an AI disclosure that is not *fits* or *n-a*, and every absent deal maker becomes a gap. Rank by class first (blocks-review → veto → Critical requirement → primary criterion ≥15% → High requirement → event → package item → AI disclosure → secondary criterion → Medium requirement → deal maker / tiebreaker), then by weight or severity within class. For each gap write:

- **What is missing**, in one line, and the address where the evaluator will notice its absence.
- **The fix**: the concrete thing to add or change, quotable — the sentence, the section, the commit, the turn. Not "improve the decisions section"; "add entries for X, Y, Z in the form decision / alternative / why, with the expiry-at-checkout one first".
- **Where it goes**: the surface, and whether it belongs on the first surface.
- **Can it be retrofitted?** An event that did not happen cannot be written up as if it had. Say so, and give the honest fix: make it happen now (do the cut, push back on the next proposal, run the obstacle check) and then record it; or disclose that it did not happen and why. Never suggest fabricating a trace.
- **Effort**: minutes, not adjectives.

### Phase 9 — Write and report

Write `docs/submission-audit/audit.md` using `assets/output-templates.md` — the full template, or the partial one in partial mode. In a repo, add the folder to `.gitignore` alongside `docs/evaluator-expectations/` if it is not already ignored, and say so. That `.gitignore` line is the only thing the audit ever writes outside `docs/submission-audit/`: it is left untracked, never committed, and never touches a tracked file. The audit reads the submission; it does not fix it. If either handoff folder is already *tracked* in the repo's history, that is a blocks-review finding (the evaluator would find the rubric model inside the work) and the fix — `git rm -r --cached` plus a history rewrite before pushing — goes in the gaps, for the user to run.

Then, in the reply: §1 as written (verdict, why, first pass, final, must-do gap IDs), the AI disclosure fit, and the must-do gaps with their fixes from §8. Point at `audit.md` for the rest. Do not paste the whole report into chat; the user has it on disk and the chat version scrolls away.

## Output

One file, `docs/submission-audit/audit.md`, using `assets/output-templates.md`. Keep the headings exactly; the post-mortem and the next re-audit read them by name.

| Section | Job |
|---|---|
| 1. Verdict | Verdict, score, veto status, why, first-pass and final lines in the evaluator's voice, how they compare with the Lens's predictions, and the must-do gap IDs. The user may read nothing else. |
| 2. Scorecard | Each Matrix criterion (`C#`): weight, strength, contribution, evidence, Lens ref; then the gates line. |
| 3. Deal breakers | The veto with its evidence, then every trap (`T#`) — including blocks-review mechanics, the planted obstacle and sanitisation — tripped or avoided. |
| 4. Requirements | Counts, then only the unmet and partial explicit (`E#`) and implicit (`I#`) requirements in full; met ones by ID. |
| 5. Submission package | Each package item (`P#`), then each required-to-exist event (`R#`) with its cross-check. |
| 6. AI disclosure | What the submission says about AI against the evaluator's receptiveness and the traces, and the honest fix. |
| 7. Deal makers | Differentiators and decisions (`D#`), present or absent. |
| 8. Gaps and fixes | The ranked worklist (`G#`), each with the finding IDs it comes from, the fix, retrofit honesty, effort and a checkbox; closed gaps carried forward. |
| 9. Notes | Analysis gaps, what could not be verified, and since last round — each only when it has content. |
| Appendix | Reading order and surfaces; rejected evidence for Weak and Missing criteria only. |

**References.** Every finding carries an **Evidence** reference into the submission (file § heading and lines, commit, transcript turn, message paragraph, cell, slide, timestamp) and a **Lens ref** to where the Lens asked for it (`Lens E4`, `Matrix: <criterion>`, `Deal breakers: "<first words>"`), plus the brief section or message number when the exact wording matters. A finding without an evidence reference is written as absent, with where the evaluator would look for it.

**What is deliberately not in the file:** a second copy of the verdict lines, the scoring factor column (it is fixed by the strength), met requirements as full rows, the Lens's pre-submission checklist re-ticked, every evidence candidate for criteria that passed, and the raw inventory script output. Each repeats something already in the file or in the Lens.

**Length.** No cap: as long as the submission's actual gaps and evidence make it, never longer.

The front-matter carries `verdict`, `weighted_score`, `veto_status`, `veto_on_first_surface`, `ai_disclosure`, `round`, `lens_version`, `lens_derived_at_audit`, `independence`, `submission_form` and a `submission_ref` (commit hash, file list, or message draft) so a later run can tell what changed.

## Discipline

- **Grade the evidence, not the effort.** A race-safe usage limit is excellent engineering and worth nothing against a criterion that never mentioned it. Say it is good in one clause and give it the weight the Lens gives it.
- **An address or it did not happen.** Every Strong or Adequate rating has a location an evaluator could open. If you cannot give one, the rating is Weak.
- **Echo is not evidence.** The brief's vocabulary appearing in the submission proves the submitter read the brief, nothing more.
- **Do not grade on the rubric you would have written.** Analysis gaps go in their own section. The Lens's weights are the weights.
- **Honest retrofits only.** The gap list distinguishes "add this" from "this has to happen before it can be recorded". The second kind is the one the audit exists to catch early.
- **Say what you could not see.** Unverified surfaces are listed as such in the inventory and the report, not silently passed.

## Reference files

- `references/handoff-folder.md` — the `docs/evaluator-expectations/` and `docs/submission-audit/` contract: files, front-matter, lookup order. Read in Phase 0 the first time in a session.
- `references/reading-surfaces.md` — how to open each kind of surface and what proof looks like in it: code, commits, transcripts, notes, documents, spreadsheets, slides, proposals, Q&A, estimates, RFP responses, design files, message or chat replies, unreadable media. Read in Phase 1.
- `references/evidence-strength.md` — the Strong / Adequate / Weak / Missing scale per criterion type, the echo test, and the anti-patterns that look like proof. Read before Phase 3.
- `references/verdict-rules.md` — scoring, verdict thresholds, how to write the two verdicts, gap severity classes, retrofit honesty. Read in Phase 7.
- `references/worked-example.md` — a full audit of a take-home submission with a real rejection on record, so the method can be checked against ground truth. Read when calibrating.
- `assets/output-templates.md` — the `audit.md` template: full mode (also used by re-audits) and partial mode, with front-matter.
- `scripts/inventory.py` — deterministic inventory of a submission directory or repo, with transcript turn statistics.
