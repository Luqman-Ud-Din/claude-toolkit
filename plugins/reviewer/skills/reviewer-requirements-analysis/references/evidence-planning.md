# Evidence Planning

Turning the rubric into a plan for what the submission must *show*. A criterion the reviewer cannot see is a criterion the submitter did not meet, however well they actually did it. This file is about making every graded quality visible on a surface the reviewer will actually look at.

## The central rule: required-to-exist events

If a mandated artifact's heading, field, or prompt names an event, that event must have happened by submission time — and happened in a form that produces something worth writing under that heading.

Examples of headings that are really events, across document types:

| Mandated heading or field | Event it assumes | What you must schedule |
|---|---|---|
| "Decisions and assumptions" (take-home) | You noticed ambiguities and resolved them | A running list from the first read; aim for 6–10 |
| "What I didn't get to, and what I'd do next" (take-home) | You cut scope deliberately and thought ahead | Decide the cut list at the halfway mark, not at the end |
| "Moments where the AI got something wrong" (AI-permitted take-home) | You reviewed the tool's output critically | Check every proposal against the brief; record the first catch when it happens |
| "What you'd need from me to get started" (client brief) | You know the access and inputs this kind of job requires | Draft the specific list before writing anything else |
| "Roughly how long" (client brief) | You have sized the work with buffer | A phased timeline with a verification step before the deadline |
| "Open questions" (PRD, with a sync scheduled) | You have a position on each | Resolve or recommend on every one before the meeting |
| "Risks" (PRD / RFP) | You thought about what could go wrong | 3+ risks with mitigations, including at least one the author did not list |
| "Past performance (three references)" (RFP) | You have done this scope before, contactably | Three matched references confirmed before the deadline |
| "Measurable outcomes" (grant) | You know what success looks like and how to count it | Outcomes as changes with a metric, not activities |
| "Time spent" (any) | You tracked time | Note start/stop; honesty is graded here, not speed |

A heading that will be thin or empty at submission time is a predicted failure. The evidence plan's job is to make sure each event is scheduled early enough to happen naturally. Manufactured events read as manufactured — the goal is to *create the conditions* (critical review, deliberate scoping, running decision log, early sizing) under which the events occur, then capture them.

## Surfaces: where reviewers actually look, in order

Not every surface gets equal attention, and the order differs by archetype.

**Technical take-home:** cover note / README → mandated transcript or prompts file (if any) → commit log → video → code → tests. Code is read last and only where the notes point.

**Freelance / client brief:** first line (any embedded filter) → first paragraph (do they understand my problem?) → answers to any embedded questions → price → relevant samples → everything else. Decided in under a minute on the first pass.

**Job application:** hard requirements scan → embedded filters → first paragraph of the cover note → evidence matched to the post's stated problem → the rest.

**PRD review / estimate:** summary line → the number and its assumptions → risks and dependencies → scope boundaries → design detail.

**RFP:** compliance matrix → mandatory sections (pass/fail) → scored sections in published weight order → appendices.

**Grant:** alignment with each stated priority → outcomes and measurement → budget vs. narrative consistency → team.

Put the veto-criterion proof on the first surface in the reviewer's reading order. If they stop after the first surface, they must already have seen it.

## Proof moments: concrete, not abstract

A proof moment is a specific, visible thing the reviewer can point at. Abstract plans ("show good judgment") produce nothing; concrete ones produce evidence.

Test each proof moment: *could a reviewer quote it in a feedback email?* If not, it is too abstract.

### Patterns by criterion type

**Reasoning visible and defended** (take-homes, PRD reviews, design briefs)
- Decision-log entry: *Decision — alternatives considered — why this one — what would change my mind.* Three or four of these beat twenty one-liners.
- Commit messages or review comments that carry intent, not content: "enforce the limit at the DB level, not just the UI, because support creates records by hand."
- One hard decision explained aloud in a video or walkthrough, with the losing option named.

**Direction of a tool or a team** (AI-permitted take-homes; also delegation-heavy roles)
- Constraints stated *before* asking for work, in your own words.
- Rejections with reasons, redirections when the work drifts, cuts the tool did not propose.
- A header or summary that names two or three of these with references. See `ai-era-signals.md`.

**Trust and reliability** (client briefs, long-term contracts)
- The client's problem restated in their language, slightly sharper than they put it, in the first two sentences.
- A durability sentence: what breaks in this kind of system, and what you do about it before it breaks.
- A named communication cadence and a bounded post-launch window — the ghosting fear answered with a schedule, not a promise.
- A verification step the client can perform themselves (a parallel run against their current spreadsheet).

**Scoping under constraint** (take-homes, fixed-fee proposals, PRD estimates)
- A cut list with reasons, decided before the deadline forced it.
- Honest time or effort reporting with a breakdown.
- A next-steps list ordered by value, not by ease.
- For fixed fees: *included — excluded — assumptions — recurring costs*, so the scope collision that ends engagements is prevented in writing.

**Metric alignment** (PRDs, grants, internal proposals)
- The success metric stated in the first paragraph of the response, with "inferred from…" if it was not explicit.
- Each listed goal or requirement tied back to the metric as an instrument.
- A measurement plan: how impact will be attributed, what the leading indicator is before the lagging number exists.

**Obstacle handling** (take-homes, transitions, messy-data projects)
- A note: *what I found — what I did — why that and not more.* Proportionality is the point; a one-line fix with a one-line note beats a refactor.

**Compliance** (RFPs, grants, procurement)
- A compliance matrix as the first appendix, mapping every numbered requirement to a response location.
- Section lengths proportional to published weights.
- Explicit "complies" / "partially complies, because…" on every mandatory.

**Communication quality** (everything)
- Front-loaded: the veto-criterion proof in the first five lines of the first surface.
- Order matching whatever the document requested ("first show it working, then…"; "what you'd build, how long, what you need").
- Register matching the document's voice.

**Core function works** (gate, where applicable)
- A demonstration in the first sixty seconds of any video; a one-command run path; sample data covering the success and failure cases the reviewer will try.

**Extension readiness** (anything with a "phase 2" or "we may extend this together")
- One sentence about where the next thing would plug in, and no code for it.

## Anti-patterns: what failing looks like

Write one per criterion so the user can recognize failure in their own draft.

| Criterion | Anti-pattern |
|---|---|
| Reasoning | Decisions listed as facts — "used X and Y" — with no alternatives and no why |
| Direction | The human's turns are "ok", "continue", "looks good"; every design choice originated with the tool |
| Trust | Proposal opens with credentials; nothing about what happens after launch; "feel free to reach out anytime" as the cadence |
| Scoping | Over the limit and silent about it; or "everything is done"; or a fixed price with an open-ended support promise |
| Metric alignment | The number the project exists to move is never mentioned; the listed proxy (a counter, a completion) is treated as the goal |
| Obstacle | Fixed silently; or rewrote the module; or "setup didn't work" and stopped |
| Compliance | A mandatory requirement addressed in prose instead of a clear "complies"; page limit exceeded |
| Communication | Squashed commit; video opens with a code tour; the important point is in paragraph four; wrong register |
| Core function | Reviewer needs three commands and a config edit to see it work |
| Extension | Built phase 2 |

## Ordering the plan

Sequence the proof moments by when they must occur. The shape is the same across document types; the contents differ.

- **Before starting work**: the running decisions/assumptions list; the cut-list placeholder; the metric or problem restatement written down; for proposals, the access list and the attention-filter answer.
- **During the first third**: obstacle encountered and noted; first constraint-before-ask or first push against a default; dependency conversations started.
- **At the halfway mark**: cut list decided; scope locked; estimate range narrowed.
- **During the last third**: verification step (parallel run, test pass, dry run); next-steps list; risk register completed.
- **After work, before submission**: the first surface written with the veto-criterion proof in its first five lines; everything else in the order the document asked for.

Giving the user this sequence is more useful than giving them the list, because required-to-exist events only happen if they are scheduled.

## Self-check before submission

For each rubric criterion, the user should be able to answer:

1. Which surface proves it?
2. What exact line, turn, commit, timestamp, or section is the proof?
3. Would the reviewer see it if they stopped reading after the first surface?

If any criterion fails question 2, there is no evidence, however well the work was done.
