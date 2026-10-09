---
name: submission-audit
description: Audit a finished or in-progress submission — code repo, document, proposal, spreadsheet, PDF, slide deck, Q&A answers, estimate, transcript, anything — against the Evaluator Lens that expectations-analysis saved in docs/evaluator-expectations/, reading it in the order the real evaluator will and reporting, per criterion, whether the submission proves it. Writes a structured audit to docs/submission-audit/ with a ship / fix-first / not-ready verdict and gaps ranked by rubric weight, each with a concrete fix. Use this whenever the user asks whether their submission, take-home, proposal, application, deliverable or draft is ready, meets the requirements, covers what the evaluator wants, would pass, or what is missing; before they submit anything that had a Lens; at the halfway mark of timeboxed work ("am I on track", "checkpoint"); and after fixes ("re-audit", "check again"). Trigger even when the user does not say "audit" or "review" — "is this good enough to send?" is this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `evaluator-kit:<skill-name>`. Keep bare skill
IDs in front-matter, handoff files and output paths. Resolve `scripts/`, `references/`
and `assets/` relative to this SKILL.md, not the user's project or submission; quote
script paths when running commands.


# Submission Audit

You are the evaluator, one day early. The real evaluator will open this submission with a rubric in their head and a limited amount of time; your job is to open it the same way, in the same order, and say what they will conclude — before it is too late to change.

The rubric is not yours to invent. `expectations-analysis` already decoded the brief into the Evaluator Lens: the veto criterion, the weighted rubric, the proof moments each criterion needs, the events that must have happened, the traps. You grade against that. If you think the Lens is wrong, you say so in a separate section; you do not quietly grade on a different rubric, because a rubric rebuilt while looking at the submission will be shaped to pass it.

## What makes this different from "review my work"

A normal review asks "is this good?". This audit asks three narrower questions, in order:

1. **What does the evaluator conclude after the first surface?** Most rejections happen in the first pass, on the first thing opened. If the veto proof is not there, the rest is never read with care.
2. **For each thing the rubric grades, where is the evidence — with an address?** "The submission shows good reasoning" is not a finding. "SUBMISSION.md §Decisions, entry 3, names the rejected alternative and why" is. If there is no address, the criterion is unmet, however well the work was actually done.
3. **Which required-to-exist events happened, and are they substantive?** A heading that exists with two thin lines under it is a visible failure, not a pass.

Everything else — the weighted score, the ranked gaps, the verdict — follows from those three.

## Modes

**Full** — before submitting. All phases, all five output files, a verdict.

**Partial** — at the halfway mark of timeboxed work, or after a first draft. Only Phase 0, Phase 1, and Phase 4 (required-to-exist events), plus one line on whether the veto proof is visible yet. Writes `audit-partial.md` only. No verdict, no score. The point is that events cannot be retrofitted: a cut decision made at the end is not a cut decision; a push-back inserted into a transcript after the fact is visible as such. The partial run tells the user what has not happened yet while there is still time to make it happen.

**Re-audit** — full mode when `audit-final.md` already exists. Same phases; additionally diff against the previous round: which gaps closed, which remain, which are new. Increment `round` in the front-matter.

Pick the mode from what the user says ("checkpoint", "halfway", "am I on track" → partial; "ready?", "before I send" → full; "again", "re-check" → re-audit). If unclear and the submission looks finished, run full.

## Independence

The audit must run blind — in a context that has not watched the work being produced. If this conversation wrote the code, drafted the proposal, or steered the AI session, you know what the submitter *meant*, and you will read meaning into evidence the evaluator cannot see.

- **If this conversation produced any of the work** and a subagent tool is available: delegate the whole audit. Give the subagent only: this skill's path, the mode, the path to `docs/evaluator-expectations/`, the path(s) to the submission, and the output folder. Nothing from the conversation. Write the files from what it returns, and say in the report front-matter `independence: subagent`.
- **If this conversation produced the work and there is no subagent tool**: say so, run the audit anyway with `independence: same-context`, and tell the user the verdict is optimistic by construction and a fresh session would be stricter.
- **If this conversation is fresh** (the usual case: the user opens a new session to audit): run directly, `independence: fresh-session`.

## Workflow

### Phase 0 — Load the contract

Find the Lens, in this order, stopping at the first hit: a path the user gave → `docs/evaluator-expectations/expectations.md` under the project root or current directory → a file attached to the conversation whose front-matter says `kind: evaluator-lens`. Read `references/handoff-folder.md` for the folder contract if you have not this session.

If none exists: do not build a rubric here. Tell the user the Lens is missing and, if they can supply the brief, run `expectations-analysis` in a separate context (a subagent given only the brief and the user's context) so it writes the folder; then continue. Record `lens_derived_at_audit: true` in the front-matter, because it means no halfway checkpoint ever ran and the events were never scheduled.

From `expectations.md` extract, by heading: the veto (front-matter `veto`, and the **Veto criterion** line under **Deal breakers**), `first_surface`, `submission_form`, `ai_receptiveness`, the archetype and the evaluator persona from **Evaluator intent**, the **Matrix** table — the rubric (criterion, weight, confidence, failing-looks-like) — the traps under **Deal breakers**, and from **Submission package** the package items, the **Proof per criterion** table (criterion, surface, proof moment, anti-pattern), the **Required-to-exist events** list and the **Pre-submission check**; then the **Explicit requirements** and **Implicit requirements** tables with their severities, and **AI receptiveness**. These are your checklist; copy them into your working notes before opening the submission so the submission does not reshape them.

Read `brief.md` once, for the explicit requirements and any mandated template, and the Lens's **Context understanding** section for the user's role and constraints. Note the Lens `version`.

### Phase 1 — Inventory the submission

Enumerate everything the user has handed you, before judging any of it. Run `scripts/inventory.py <path>` on a directory or repo: it lists files with sizes and types, summarises the git log (count, span, message lengths, timestamps), word-counts text files, flags leftover placeholders (`<link>`, `TODO`, `TBD`, `lorem`, `{{`), and, with `--transcript <file>`, counts human turns and short-approval turns. The script finds; you interpret.

Then map what exists to the surfaces the Lens's What-to-show table names. For each surface: present / absent / present-but-unreadable (a video you cannot watch, a link you cannot open). An **absent mandated artifact is a finding on its own** and goes straight to the gaps. For surfaces you cannot read, say so and audit what stands in for them (a video's script or outline; a link's description) with `verification: unverified`.

Read `references/reading-surfaces.md` for how to open each kind of surface and what proof looks like in it — code, commit log, transcript, notes, document, spreadsheet, slides, proposal, Q&A answers, estimate, RFP response, design files. Use the right tool: text and PDF through `Read`; `.docx`, `.xlsx`, `.pptx` through their skills or the Python libraries; repositories through `git log`, `git show`, and the file tree.

Record the inventory with the reading order you will follow (from the Lens persona and archetype) in `inventory.md`. The reading order is the single most important setting of the audit; it decides what "first pass" means.

### Phase 2 — First pass: the first surface only

Open only `first_surface`. Read it the way the evaluator will: with the time the persona gives it (thirty seconds for a proposal, a few minutes for a README), top to bottom, stopping where they would stop.

Before opening anything else, write the first-pass verdict: one line in the evaluator's voice saying what they now believe about the submission, and whether they continue to the next surface with interest, with suspicion, or not at all. Then answer: **is the veto proof visible on this surface?** Yes with an address; or no.

This is written before the rest of the audit so it cannot be softened by what you find later. The evaluator does not get to see later surfaces before forming this impression either.

### Phase 3 — Full read, in the evaluator's order

Open the remaining surfaces in the inventory's order. For every rubric criterion, hunt for the proof moment the Lens specified. For each candidate found, record:

- **Address**: file and heading, line range, commit hash, transcript turn number, slide number, cell range, page. Something an evaluator could quote back.
- **Strength**: Strong / Adequate / Weak / Missing, using `references/evidence-strength.md`. The strength scale is about what the evidence *proves*, not how much effort it reflects.
- **Surface depth**: would the evaluator reach it in a normal read, or only if they went looking? Proof buried in the fourth paragraph of the second file is weaker than the same proof in the first five lines of the first file.
- **Echo check**: does the submission *claim* the criterion in the brief's own words without the thing itself? "I pushed back on the AI where needed" with no turn reference is an echo, not evidence; mark it Weak at best and name it as echo. Evaluators notice rubric-echoing and it reads worse than silence.

Where the Lens named an anti-pattern for the criterion, check for it explicitly and record it if present. Write every candidate — including weak ones and echoes — into `evidence.md`; the report will keep only the strongest per criterion.

**Run what can be run.** An evaluator of code does not only read it; they clone it and try the README. Where a runtime is available — an interpreter, a test runner, a database or service you can start locally — execute the run path the notes give, the tests, and any verification harness the brief mandated, and record what happened as evidence with the command and its output. A limiter that reads correctly and admits N+1 under a two-minute probe is a Missing on the correctness gate, and only running it finds that. When you find a defect, state its consequence in the brief's own terms (over-admits vs over-rejects; loses data vs rejects a request; wrong total vs slow total), because that is how the evaluator will classify it. When nothing can be run, say so in the inventory and grade on reading, one notch more cautiously.

### Phase 4 — Required-to-exist events

For every event the Lens listed: did it happen, and is the record of it substantive?

- **Present**: the heading or artifact exists and names a specific instance with enough detail that an evaluator could ask about it ("turn 14: rejected the join table because one-per-order is a column constraint"; "cut the admin UI at 1h30; self-service is 'eventually'").
- **Thin**: the heading exists; the content is generic, one line, or an echo ("I changed direction a few times").
- **Empty**: heading missing, or present with nothing under it.

Where the event is observable elsewhere, cross-check: a claimed direction change should appear in the transcript at the turn cited; a claimed cut should be absent from the code and present in the notes; a claimed obstacle fix should be a commit. A claim with no corroborating trace is Thin.

In partial mode, this phase is the audit. For each event not yet Present, say when in the remaining work it must happen, and what making it happen looks like — not what writing it up looks like.

### Phase 5 — Gates, mechanics, traps

Three checks that are pass/fail rather than weighted:

- **Explicit requirements complete.** Walk the Lens's explicit-requirements list and, as a backstop, the brief's own headings and numbered items. Every Critical and High requirement present? Every mandated artifact at the mandated path, with the mandated headings? Every embedded question answered, in order? Format limits (word count, page count, slide count, file type) respected? Measure limits; do not estimate them.
- **Blocks-review mechanics.** Platform, collaborators, link placement, privacy, naming, submission channel — everything from the Lens's traps that would stop the evaluator from opening the work at all. One tripped mechanic is a not-ready verdict regardless of content, because the content is never seen.
- **Traps.** For each trap the Lens listed: tripped, avoided, or not applicable, with an address. Planted obstacle: noticed, handled proportionately, *and* reported? Over-delivery: is there work beyond scope, and does it cost timebox credibility? Tone: does the register match the brief's? Sanitisation: where a transcript and a commit log both exist, do timestamps and messiness agree?

### Phase 6 — Analysis gaps

Two questions, reported in their own section and never folded into the score:

- Is there anything in `brief.md` the submission will be graded on that the Lens did not list? (A mandated section the Lens compressed away; a stated evaluation criterion the Lens under-weighted.)
- Does the submission's context contradict a Lens assumption? (The Lens assumed a backend role; the submission is mobile. The Lens assumed a four-hour timebox; the user said they had two.)

If an analysis gap is large enough to change the veto, say so and recommend re-running the analysis before trusting this audit. Otherwise list it and move on.

### Phase 7 — Score and verdict

Read `references/verdict-rules.md` for the method. In short: each criterion's strength maps to a factor (Strong 1.0, Adequate 0.7, Weak 0.3, Missing 0), the weighted score is the sum of weight × factor over the rubric, and the verdict is:

- **not-ready** — the veto is Weak or Missing; or a gate fails; or a required event is Empty; or a blocks-review mechanic is tripped. The evaluator rejects on the first pass.
- **fix-first** — none of the above, but the score is under 70, or a criterion weighted 15% or more is Weak or Missing, or an event is Thin, or the veto proof is not on the first surface. The evaluator keeps reading but another submission wins.
- **ship** — otherwise. The remaining gaps are tiebreakers.

Then write two verdicts in the evaluator's voice: the first-pass one from Phase 2, unchanged, and the final one. Compare both with the simulated verdicts the Lens predicted; where the audit and the Lens disagree, say which is likelier and why.

### Phase 8 — Gaps, ranked

Every Weak or Missing criterion, every Thin or Empty event, every tripped trap and failed gate becomes a gap. Rank by severity class first (blocks-review → veto → gate → primary criterion ≥15% → event → secondary → tiebreaker), then by weight within class. For each gap write:

- **What is missing**, in one line, and the address where the evaluator will notice its absence.
- **The fix**: the concrete thing to add or change, quotable — the sentence, the section, the commit, the turn. Not "improve the decisions section"; "add entries for X, Y, Z in the form decision / alternative / why, with the expiry-at-checkout one first".
- **Where it goes**: the surface, and whether it belongs on the first surface.
- **Can it be retrofitted?** An event that did not happen cannot be written up as if it had. Say so, and give the honest fix: make it happen now (do the cut, push back on the next proposal, run the obstacle check) and then record it; or disclose that it did not happen and why. Never suggest fabricating a trace.
- **Effort**: minutes, not adjectives.

### Phase 9 — Write and report

Write the five files to `docs/submission-audit/` using `assets/output-templates.md`. In a repo, add the folder to `.gitignore` alongside `docs/evaluator-expectations/` if it is not already ignored, and say so. That `.gitignore` line is the only thing the audit ever writes outside `docs/submission-audit/`: it is left untracked, never committed, and never touches a tracked file. The audit reads the submission; it does not fix it. If either handoff folder is already *tracked* in the repo's history, that is a blocks-review finding (the evaluator would find the rubric model inside the work) and the fix — `git rm -r --cached` plus a history rewrite before pushing — goes in the gaps, for the user to run.

Then, in the reply: the verdict, the first-pass line, the veto status with its address or absence, the weighted score, and the top five gaps with their fixes. Point at the files for the rest. Do not paste the whole report into chat; the user has it on disk and the chat version scrolls away.

## Output

Five files, each with one job. Templates and front-matter are in `assets/output-templates.md`; keep the headings exactly, because the post-mortem and the next re-audit read them by name.

| File | Job | Reader |
|---|---|---|
| `audit-final.md` | The report: verdict, first pass, scorecard, veto, events, gates and traps, analysis gaps, top fixes. Self-contained. | The user, first |
| `gaps.md` | The worklist: every gap ranked, with fix, location, retrofit honesty, effort, and a checkbox. Carried forward across rounds. | The user, while fixing |
| `evidence.md` | The ledger: every proof candidate per criterion with address, strength, depth, echo flag; every anti-pattern found. | The user who disputes a grade; the post-mortem |
| `inventory.md` | What was audited: surfaces, files, commit range, word counts, reading order, what could not be read. | The re-audit, to diff |
| `audit-partial.md` | Partial mode only: the events table with not-yet and when. | The user, mid-work |

Front-matter on `audit-final.md` carries `verdict`, `weighted_score`, `veto_status`, `first_pass`, `round`, `lens_version`, `independence`, and a `submission_ref` (commit hash or file list) so a later run can tell what changed.

## Discipline

- **Grade the evidence, not the effort.** A race-safe usage limit is excellent engineering and worth nothing against a criterion that never mentioned it. Say it is good in one clause and give it the weight the Lens gives it.
- **An address or it did not happen.** Every Strong or Adequate rating has a location an evaluator could open. If you cannot give one, the rating is Weak.
- **Echo is not evidence.** The brief's vocabulary appearing in the submission proves the submitter read the brief, nothing more.
- **Do not grade on the rubric you would have written.** Analysis gaps go in their own section. The Lens's weights are the weights.
- **Honest retrofits only.** The gap list distinguishes "add this" from "this has to happen before it can be recorded". The second kind is the one the audit exists to catch early.
- **Say what you could not see.** Unverified surfaces are listed as such in the inventory and the report, not silently passed.

## Reference files

- `references/handoff-folder.md` — the `docs/evaluator-expectations/` and `docs/submission-audit/` contract: files, front-matter, lookup order. Read in Phase 0 the first time in a session.
- `references/reading-surfaces.md` — how to open each kind of surface and what proof looks like in it: code, commits, transcripts, notes, documents, spreadsheets, slides, proposals, Q&A, estimates, RFP responses, design files, unreadable media. Read in Phase 1.
- `references/evidence-strength.md` — the Strong / Adequate / Weak / Missing scale per criterion type, the echo test, and the anti-patterns that look like proof. Read before Phase 3.
- `references/verdict-rules.md` — scoring, verdict thresholds, how to write the two verdicts, gap severity classes, retrofit honesty. Read in Phase 7.
- `references/worked-example.md` — a full audit of a take-home submission with a real rejection on record, so the method can be checked against ground truth. Read when calibrating.
- `assets/output-templates.md` — the five file templates with front-matter.
- `scripts/inventory.py` — deterministic inventory of a submission directory or repo, with transcript turn statistics.
