---
name: reviewer-requirements-analysis
description: Analyze any requirements document — take-home, job post, client brief, PRD, RFP, assignment, hackathon brief, grant call, ticket, interview task — from the reviewer's point of view. Extracts explicit and implicit requirements, reconstructs the weighted grading rubric and the single veto criterion, plans what to show to prove each criterion, and saves the result as the Reviewer Lens in docs/reviewer-requirements/ for the submission audit. Use whenever the user shares a brief, spec, assignment or job description and wants to know what the reviewer, client, grader or stakeholder is really looking for, what they will check, how to approach or prioritize the submission, or asks "what do they want", "what are they testing", "summarize the requirements" — even without the word "reviewer". Also use before starting work on any such document, and in post-mortem mode when the user shares feedback, a rejection or an outcome on a submission that has a Lens.
---

## Plugin invocation

When invoking a skill from this bundle, use `reviewer:<skill-name>`. Keep bare skill
IDs in front-matter, handoff files and output paths. Resolve `scripts/`, `references/`
and `assets/` relative to this SKILL.md, not the user's project or submission; quote
script paths when running commands.


# Reviewer Requirements Analysis

You are reading a document the way the person who will *judge the submission* reads it — not the way the person *doing* the submission reads it. Those are different readings, and the gap between them is where good work gets rejected.

## Why this skill exists

Requirements documents are written by people who have been disappointed before. A hiring team that writes "tell us what you decided and why" has received submissions with no reasoning. A client who writes "someone who will tell me if it's going to break" has been ghosted. A PM who writes "Success metrics: TBD" has a number from leadership they have not yet put in the doc. Every such sentence is a grading criterion that was never labeled as one — and submitters, reading as *doers*, see the task and miss the test.

The gap between the two readings is where good work gets rejected: a careful implementation with no visible reasoning; a polished proposal that never mentions what happens after launch; an accurate estimate that never names the metric the project exists to move. In each case the submitter optimized something real and ungraded, because the document described the graded thing as a value rather than a requirement.

Your job is to make the reviewer's reading systematic. The person using this skill does not want a summary of the document. They want to know **what the reviewer will actually check, how heavily, and what they need to put in front of the reviewer to pass.**

## The three principles

Hold these through every phase. They are the difference between a requirements list and a reviewer-lens analysis.

**1. Every meta-sentence is a rubric line.** Sentences about the feature describe the work. Sentences about *the exercise* ("we care about…", "part of the exercise is…", "tell us why…", "we expect…", "we don't promise…", "no hidden checklist") describe how the work is judged. Authors rarely write a rubric section; they scatter the rubric through the prose. Collect it.

**2. Required deliverables are grading surfaces, and their required contents are required-to-exist events.** If a submission must include a file, that file will be read. If that file must have a section called "assumptions you made", "what you'd do with more time", "risks", or "questions for the client", then the thing the heading names is expected to have happened, and a submission where it never happened fails before the main work is opened. Treat every mandated heading, field or artifact as a claim about what the reviewer wants to find there.

**3. Repetition is weight.** Authors repeat what they care about, in different words, because they have been burned before. Count how many times a theme recurs and on how many surfaces (instructions, deliverable spec, interview preview, FAQ). A theme that appears once is a preference. A theme that appears five times across three sections is the primary criterion, and anything mentioned zero times — often the thing the submitter is best at — is probably not what they are grading.

## Workflow

Work through all nine phases internally. The thinking should be exhaustive; the *output* is a short brief with a scannable lead (see Output). Do not skip phases to save effort — the implicit requirements live in phases 2–4 and are the whole point.

### Phase 0 — Classify the document and the reviewer

Decide what kind of document this is and who reads the submission. Read `references/document-archetypes.md` for the archetype table. Establish:

- **Document type**: take-home, job post, client brief, PRD, RFP, assignment, hackathon, grant call, internal ticket, interview exercise, or hybrid.
- **Reviewer persona**: who judges (hiring engineers? a non-technical founder? a procurement committee? a professor? a PM?), how many submissions they compare, how long they spend per submission.
- **Decision being made**: hire / interview / award / fund / approve / merge. The decision shapes the rubric — an interview screen is graded on vetoes, a final-round task on differentiators.
- **Filter or confirmation**: many → few (reviewer hunts for reasons to say no) vs. few → one (reviewer hunts for reasons to say yes). This changes which criteria are vetoes.
- **Stakes and tone**: the document's voice (warm, bureaucratic, terse, over-specified) tells you how the reviewer thinks and what they are tired of seeing.

If the user has given context (their role, what they're applying for, a prior rejection), fold it in here. Prior rejections are gold — they are the reviewer's rubric stated in retrospect.

### Phase 1 — Literal pass: explicit requirements

Enumerate everything the document actually states. Keep source quotes short; they are evidence, not decoration. Split into:

- **Functional** — what the thing must do.
- **Deliverables** — every artifact that must be handed over (files, links, videos, repos, forms, headings inside files).
- **Constraints** — time, stack, role, format, length, platform, budget.
- **Process rules** — how to work (commit as you go, don't publish, ask vs. decide, use X tool).
- **Submission mechanics** — where, to whom, by when, in what form.

Tag each MUST / SHOULD / MAY using the author's own force: "please don't go much over" is a MUST wearing politeness; "it's enough to…" is a MAY; "you can start from this" is a SHOULD with a strong hint.

Explicit requirements are the floor. Missing one is an unforced error, so be complete here — but do not mistake completeness here for the analysis. Most rejections are not for missing explicit requirements.

### Phase 2 — Sentence interrogation: implicit requirements

This is the core phase. Read `references/interrogation-techniques.md` before doing it the first time in a session.

Go through the document sentence by sentence. For every sentence that is **not** a plain description of the feature or task, ask:

1. **Why is this sentence here?** What prior submission made the author write it? Instructions are scar tissue.
2. **Is this a rubric line in disguise?** "What we care about is X" → X is graded. "We're interested in Y" → Y is graded.
3. **Permission or test?** "Use AI, we expect it" grants permission *and* announces that AI use will be examined. Both halves matter.
4. **What does failing this look like?** If you can picture the failing submission, you have found a criterion.
5. **Does it mandate an artifact? Then what must the artifact contain to count?** A required file with required headings is a required-to-exist set of events.
6. **Does it preview a future interaction?** "Expect questions about your decisions and your prompts" → those will be read closely enough to ask about.
7. **Is it a reassurance?** "No hidden checklist", "don't worry about X", "there's no right answer" — reassurances mark the exact anxiety the reviewer is grading. "No right answer" means *your reasoning* is the answer.
8. **Does it hand you a decision?** "How you do that is up to you", "make the call and write it down" → the decision *and its rationale* are the deliverable; the implementation is secondary.
9. **Does it warn that the ground is unstable?** "We don't promise it runs cleanly", "treat it like an existing codebase" → a planted obstacle. Handling it is graded; *reporting* how you handled it is graded more.

Use `references/signal-lexicon.md` as the decoder ring for common phrasings. It maps phrase patterns to the criterion they usually encode, with the failure mode each one is guarding against.

Then run the cross-sentence techniques at the end of `references/interrogation-techniques.md`: count the communication imperatives against the build imperatives, trace every mandated artifact back to the criterion it serves, list what the submitter would naturally optimize that the document never mentions, find the tension pairs, read the voice — and **audit the stated requirements themselves for defects** (a shortcut that collides with a browser default, two requirements that contradict each other, a role named but never defined). Task sentences are exempt from the nine questions, not from scrutiny; a defect in the numbered list is something the reviewer notices who notices.

For each implicit requirement you extract, record: the requirement, the evidence (quote), and a **confidence tier**:
- **Stated** — said outright, just not labeled as a criterion.
- **Strong** — multiple signals converge; a reasonable reviewer would confirm it.
- **Inferred** — one signal plus archetype knowledge; probably true.
- **Speculative** — plausible, worth hedging for, but do not build the plan around it.

### Phase 3 — Aggregate signals into themes and weights

Cluster the implicit requirements into themes. Then, for each theme:

- **Count occurrences.** Same idea in different words still counts.
- **Count surfaces.** Does the theme appear in the instructions? The deliverable template? The "what happens next" section? The FAQ? Each additional surface is a multiplier.
- **Note what is absent.** If the document never mentions a thing the submitter would naturally optimize for (code elegance, visual polish, completeness), that absence is information. The reviewer may still notice it, but it is not what they are grading.
- **Flag deliberate tensions.** Timebox vs. completeness, "brief not spec" vs. "tell us what you decided", "use AI" vs. "we want to see *you*". Tensions are placed on purpose; they are where the reviewer watches judgment. The submission must visibly resolve each tension and say how.

The optional pre-pass script `scripts/signal_scan.py` extracts candidate meta-sentences, counts recurring evaluative terms, and lists mandated headings. Run it on long documents (`python scripts/signal_scan.py <file>`) so nothing is lost to skimming, then do the real reading yourself — the script finds sentences, it does not understand them.

### Phase 4 — Model the reviewer

Write a short first-person sketch of the reviewer, two to four sentences. What have they seen thirty times this month? What makes them stop reading? What makes them forward a submission to a colleague with "look at this one"? What are they afraid of hiring/awarding/approving by mistake?

When the document tells you who the reviewer is — "your future teammates", "at least one of whom has been a fellow", "two of our engineers", a store owner writing in the first person — that is the most specific evidence you have about the persona, and the sketch should carry it. A reviewer who has done the applicant's job reads differently from one who has not; a reviewer who was burned personally reads differently from a committee. A persona that would fit any reviewer of any document is a persona built from the archetype, not from this document.

For any document that mentions AI tools, read `references/ai-era-signals.md`. Reviewers of AI-assisted work often carry an unstated question — **can I tell a human with opinions was steering?** — and when a brief asks for transcripts or prompts, that question is usually why. Treat it as a *candidate* veto, not a default: test it against the document's own repetition count like any other theme. A brief that mentions AI once in passing and talks about load, correctness, or test design ten times has a different veto, and reading "steer the AI" into it would be the same mistake this skill exists to prevent.

The persona is not decoration. It is what lets you predict the veto criterion and the differentiators in Phase 5, and it is what the user will read to recalibrate their own framing.

### Phase 5 — Reconstruct the rubric

Read `references/rubric-reconstruction.md` for the method. Produce a weighted rubric: criterion, weight (percentages that sum to 100), confidence tier, and a one-line picture of what failing looks like.

Then identify the **veto criterion**: the one criterion that causes rejection even if everything else is excellent. It is usually the most-repeated theme, usually phrased as a value ("how you reason", "how you direct", "communication", "judgment"), and usually the thing the submitter is least likely to think of as gradable. State it explicitly and say why you chose it.

Also name the **differentiators** — the two or three things that separate a pass from a strong pass — because a user who is already clear on the veto will want to know where to spend surplus effort.

### Phase 6 — Evidence plan: what to display, and where

Read `references/evidence-planning.md`. For every criterion in the rubric, specify:

- **Surface** — which part of the submission will prove it (code, commit history, session transcript, README/SUBMISSION, video, proposal text, cover note, demo, test suite, decision log).
- **Proof moment** — the concrete, visible thing to create or capture. Not "show good reasoning" but "a decision-log entry that names two alternatives and why each was rejected". Not "steer the AI" but "at least three transcript moments where you reject or reshape the AI's proposal, in your own words, before accepting".
- **Anti-pattern** — what the failing version looks like, so the user can recognize it in their own draft.

Apply the required-to-exist rule here: if a mandated artifact's headings or fields name an event ("where you changed direction", "what you'd do with more time", "assumptions you made", "questions for the client"), the plan must schedule that event. A heading that will be empty or thin at submission time is a predicted failure.

When the user has asked how to *approach*, *frame*, *structure*, or *write* the submission — not only what will be graded — add a **Recommended shape** block to the Detail section: the submission's sections in the reviewer's reading order, each with a share of the length or time roughly proportional to its rubric weight, and the proof moment that belongs in it. The rubric already implies this plan; handing it over saves the user from translating weights into an outline themselves, and it is where the analysis becomes something they can start writing from. For a scored call with published weights, the shares follow the weights. For a timeboxed exercise, the shares are hours. For a proposal, they are paragraphs.

### Phase 7 — Traps, planted obstacles and hidden tests

List what the document does not say but the reviewer is checking:

- **Planted obstacles**: broken setup, missing config, contradictory specs, an intentionally vague acceptance criterion. The test is whether you notice, how you handle it, and whether you report it.
- **Embedded filters**: a phrase to include, a question to answer, a specific format — attention tests that silently reject copy-paste responses.
- **Over-delivery traps**: places where doing more signals worse judgment (blowing the timebox, gold-plating, solving the unasked problem).
- **Graded-but-looks-optional**: commit history, naming, the "questions" section, the cover note, the order things are presented in the video.
- **Blocks-review-entirely mechanics**: the wrong platform, a missing collaborator, a file not at the path named, a link not where it was asked for, a reply sent through the wrong channel. These look like logistics and are easy to list as requirements and forget as risks. A reviewer who cannot open the work does not grade it; name them as traps, not just as MUSTs, because the consequence is total.
- **Tone traps**: the document's voice invites a matching register; mismatch (over-formal reply to a casual brief, or the reverse) is noticed.

### Phase 8 — Open decisions and questions

The document deliberately leaves things undecided. For each gap:

- For documents where asking is possible (client briefs, PRDs, RFPs with a Q&A window): decide whether to **ask** or **assume**. Asking too much reads as inability to proceed; assuming too much reads as not listening. Recommend which, and draft the question or the assumption.
- For documents where asking is explicitly discouraged ("make the call and write it down"): list each decision with a **recommended call and a one-line rationale** the user could write down verbatim. The rationale is the deliverable.

Group decisions by stakes: the ones the reviewer will definitely ask about first.

### Phase 9 — Simulate the reviewer's verdict

Re-read the plan as the persona from Phase 4. Write the one-line verdict they would give a submission that follows this plan. If it is not the verdict the user wants, name the missing proof moment and add it to Phase 6.

Then produce a short pre-submission checklist: every required artifact present and populated with what its name promises; every primary criterion has at least one visible proof; the veto criterion is addressed within the first ninety seconds of any video, the first paragraph of any written note, and the first screen of any transcript.

## Output

Use the template in `assets/output-template.md`. The template has two halves and they serve different readers.

**The lead** (profile, veto, reviewer model, implicit requirements, rubric, what-to-show) is what the user reads first and may be all they read. It should be scannable in about two minutes: roughly 500–800 words, tables over prose, every line a claim with its evidence. Lead with the veto criterion; if the user reads only one line, that is the line.

The lead bloats in predictable places, and each has a budget. The budgets exist because the user is scanning: a second example in a cell does not add a second insight, it adds reading time, and the first example was the one that mattered.
- Veto: one sentence in the reviewer's voice, then one sentence of evidence naming the surfaces. Not a paragraph.
- Reviewer model: two to four sentences. One per audience if there are two.
- Implicit requirements: four to seven bullets, each one line — the requirement, **one** quote (a second only when it comes from a different surface and that matters), the tier. The quote proves the point; three quotes prove it three times.
- Rubric cells: a phrase, not a sentence. "Failing looks like" is one concrete image, under fifteen words.
- What-to-show: one proof moment per row with **one** example, under thirty words; one anti-pattern, under twelve. The second and third examples belong in the Decisions section if they are decisions, or nowhere if they are variations.
- Required-to-exist events: one line each — the heading, what must happen, when.

**The detail** (explicit requirements, traps, decisions, checklist, verdicts) supports the lead. It can run as long as the document warrants — a brief with twelve delegated decisions needs twelve entries — but it sits after the lead so the brief reads short-first, long-optional. Even here, prefer the shortest form that carries the point: a decision is *call — rationale*, not a paragraph.

Compress the explicit requirements hard. The user has read the document; this section exists so nothing is missed, not to re-present it. Group related items into one line and quote only where the force of the wording is the point ("please don't go much over" is a MUST in polite clothing).

Completeness still wins over brevity where it matters: never cut the veto criterion, any implicit requirement rated Strong or above, any required-to-exist event, any planted obstacle, or the simulated verdict. Cut first: narrative framing, restated evidence, anything the reader can reconstruct from a quote, and any explicit requirement that is obvious from the document's own headings.

If the user asks for the long form, expand with the full sentence-by-sentence interrogation from Phase 2 — but do not lead with it.

## Persist the Lens

The brief you just wrote is the contract that every later step reads: your own work, the halfway checkpoint, the pre-submission audit, and the post-mortem if there is one. A reply in chat is not a contract; it scrolls away and the next session cannot find it. So the last step of every analysis is to write it to disk, in a known place, with the inputs it was built from.

The place is `docs/reviewer-requirements/` inside the project (or the current working directory when there is no project). Write:

- `brief.md` — the document, verbatim. The audit needs it as a backstop and the user may not have it to hand later.
- `context.md` — what the user told you that the document did not: their role, the deadline, a prior rejection, what they are applying for. A few lines.
- `lens.md` — the brief, exactly as you presented it, with the front-matter block from the template at the top. The front-matter is what a downstream skill anchors on; the headings are what it reads by name. Keep both exactly as the template has them.

Then say in one line where you wrote them. `references/handoff-folder.md` has the full contract for the folder — file names, which skill writes and reads each, the front-matter fields — and is what the audit skill is built against; read it before writing the folder the first time in a session.

Two environment rules:

- **With a filesystem and a repo** (Claude Code or a linked folder): the folder must not ship with the submission. A reviewer who finds a model of their own rubric in the repo reads it as gaming, not diligence. Add `docs/reviewer-requirements/` to `.gitignore` in the same step, say that you did, and let the user remove the line if they want the folder tracked. If the brief asks for "all prompts" or "the full session", that request is about the *analysis session*, not this folder; the Lens already flags that decision under traps.
- **Without a persistent filesystem** (claude.ai): write the three files anyway, send `lens.md` and `brief.md` to the user as files, and tell them to attach both when they run the audit. Same format, carried by hand.

If the user asks you to re-run or revise the analysis on the same document, overwrite `lens.md` and bump `version` in its front-matter; do not accumulate copies. The audit records which version it graded against.

## Post-mortem mode

When the outcome is known — the user pastes feedback, a rejection, an acceptance with notes, or `docs/reviewer-requirements/outcome.md` exists — the skill runs again on different inputs. Read `brief.md`, `lens.md`, `docs/submission-audit/audit-final.md` and `gaps.md` if the audit skill wrote them, and the feedback. Then answer four questions, in this order:

1. **Which criterion did the feedback grade on?** Map each sentence of the feedback to a rubric row, a trap, or a required-to-exist event in the Lens. Feedback is the reviewer's rubric stated in retrospect; this is the only ground truth the method ever gets.
2. **Was it in the Lens?** If yes, at what weight and confidence, and was it the veto? If the feedback's main point was weighted 5% in the Lens, the count was wrong, and the question is which signals were under-read. If it was not in the Lens at all, find the sentence in the brief that should have produced it and name the interrogation question that would have caught it.
3. **Did the audit pass it?** If an audit ran and passed a criterion the reviewer failed, the audit's proof-moment test was too lenient; say what evidence it accepted that the reviewer did not.
4. **What changes next time?** One line per change, phrased as an instruction to the next analysis — "count reassurances as criteria", "treat a named reviewer background as persona evidence". These are what the user carries forward, and what belongs in this skill's worked examples if the case is clean enough to teach from.

Write the answers to `docs/reviewer-requirements/calibration.md` using the post-mortem section of the template, and present the four answers in the reply. Do not re-run the full nine phases; the Lens already exists and the point is to grade *it*, not the document.

Praise in feedback is evidence too. "The race-safe limit stood out" tells you what the reviewer noticed and still rejected; that is the clearest possible measure of how little the praised axis weighed.

## Evidence discipline

Everything in the brief must trace to the document in front of you, the user's own context, or archetype knowledge clearly labeled as such. Two rules:

- **The worked examples are for calibration, not citation.** `references/worked-examples.md` records analyses of specific documents, one with a real outcome. Use them to check the depth of your reading. Do not present an example's outcome to the user as evidence about a *different* document ("submissions like this have been rejected for…") — that is the archetype talking, so say so: "reviewers in this archetype commonly reject on…". If the user's document is one of the worked examples, you may mention the known outcome, attributed to this skill's reference material.
- **Mark inference as inference.** The confidence tiers exist for this. A claim about what the reviewer will do that is not Stated or Strong should read as a prediction, not a fact.
- **Do not import a veto from a previous document.** Each document's veto comes from its own repetition count, mandated headings, and interaction previews. If you find yourself reaching for the same veto you found last time before you have counted, stop and count.

## Calibration

Read `references/worked-examples.md` when you want to check your reading against a worked case. It holds three documents from different archetypes — a technical take-home with a real rejection on record, a freelance client brief, and an internal PRD — each with the analysis this skill should produce and the veto it should find. The vetoes differ in kind (process visibility, post-launch trust, an unstated metric), which is the point: if your analyses of different document types keep arriving at the same veto, your Phase 3 count is being skipped.

## When the user disagrees with the veto

Users sometimes resist the veto criterion because it is not what they are good at or not what they expected to be graded on. Hold the line with evidence. Quote the repetitions. Point at the mandated headings. Then help them build the proof moments — the point of the analysis is to redirect effort before it is spent, not to be right about the document.

## Reference files

- `references/document-archetypes.md` — reviewer persona, comparison set, typical vetoes and differentiators per document type. Read in Phase 0.
- `references/interrogation-techniques.md` — the nine questions expanded, with examples from several document types. Read before Phase 2.
- `references/signal-lexicon.md` — phrase patterns → encoded criterion → failure mode guarded against. Use during Phase 2.
- `references/rubric-reconstruction.md` — weighting by repetition and surface, confidence tiers, locating the veto. Read in Phase 5.
- `references/evidence-planning.md` — surfaces, proof moments, anti-patterns, the required-to-exist rule. Read in Phase 6.
- `references/ai-era-signals.md` — what "use AI" actually tests; markers of human direction in transcripts. Read in Phase 4 only for documents that mention AI tools.
- `references/worked-examples.md` — three calibration cases from different archetypes, one with a real outcome. Read when uncertain.
- `references/handoff-folder.md` — the `docs/reviewer-requirements/` and `docs/submission-audit/` contract: files, front-matter, who writes and reads each. Read before persisting the first time in a session; identical copy lives in the audit skill.
- `assets/output-template.md` — the brief skeleton, including the front-matter block and the post-mortem section.
- `scripts/signal_scan.py` — optional deterministic pre-pass for long documents.
