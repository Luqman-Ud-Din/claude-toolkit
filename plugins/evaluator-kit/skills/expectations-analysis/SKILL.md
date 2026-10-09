---
name: expectations-analysis
description: Analyze any requirements input — take-home, job post, client brief, PRD, RFP, assignment, hackathon brief, grant call, ticket, interview task, or a message or chat history — from the evaluator's point of view. Produces one Evaluator Lens document with seven sections — description with references, context understanding, evaluator intent, explicit requirements and implicit requirements (each with reference, impact and severity; implicit ones with confidence), the evaluator's receptiveness to AI with a recommended AI-usage disclosure and confidence, and an understanding section (weighted matrix, deal breakers, deal makers, submission package) — saved in docs/evaluator-expectations/ for the submission audit. Use whenever the user shares a brief, spec, assignment, job description, client message or chat thread and wants to know what the evaluator, reviewer, client, grader or stakeholder is really looking for, what they will check, how to approach or prioritize the submission, how much AI use they will accept, or asks "what do they want", "what are they testing", "summarize the requirements" — even without the word "evaluator". Also use before starting work on any such document, and in post-mortem mode when the user shares feedback, a rejection or an outcome on a submission that has a Lens.
---

## Plugin invocation

When invoking a skill from this bundle, use `evaluator-kit:<skill-name>`. Keep bare skill
IDs in front-matter, handoff files and output paths. Resolve `scripts/`, `references/`
and `assets/` relative to this SKILL.md, not the user's project or submission; quote
script paths when running commands.


# Expectations Analysis

You are reading a document the way the person who will *judge the submission* reads it — not the way the person *doing* the submission reads it. Those are different readings, and the gap between them is where good work gets rejected.

## Why this skill exists

Requirements documents are written by people who have been disappointed before. A hiring team that writes "tell us what you decided and why" has received submissions with no reasoning. A client who writes "someone who will tell me if it's going to break" has been ghosted. A PM who writes "Success metrics: TBD" has a number from leadership they have not yet put in the doc. Every such sentence is a grading criterion that was never labeled as one — and submitters, reading as *doers*, see the task and miss the test.

The gap between the two readings is where good work gets rejected: a careful implementation with no visible reasoning; a polished proposal that never mentions what happens after launch; an accurate estimate that never names the metric the project exists to move. In each case the submitter optimized something real and ungraded, because the document described the graded thing as a value rather than a requirement.

Your job is to make the evaluator's reading systematic. The person using this skill does not want a summary of the document. They want to know **what the evaluator will actually check, how heavily, and what they need to put in front of the evaluator to pass.**

## The three principles

Hold these through every phase. They are the difference between a requirements list and an evaluator-lens analysis.

**1. Every meta-sentence is a rubric line.** Sentences about the feature describe the work. Sentences about *the exercise* ("we care about…", "part of the exercise is…", "tell us why…", "we expect…", "we don't promise…", "no hidden checklist") describe how the work is judged. Authors rarely write a rubric section; they scatter the rubric through the prose. Collect it.

**2. Required deliverables are grading surfaces, and their required contents are required-to-exist events.** If a submission must include a file, that file will be read. If that file must have a section called "assumptions you made", "what you'd do with more time", "risks", or "questions for the client", then the thing the heading names is expected to have happened, and a submission where it never happened fails before the main work is opened. Treat every mandated heading, field or artifact as a claim about what the evaluator wants to find there.

**3. Repetition is weight.** Authors repeat what they care about, in different words, because they have been burned before. Count how many times a theme recurs and on how many surfaces (instructions, deliverable spec, interview preview, FAQ). A theme that appears once is a preference. A theme that appears five times across three sections is the primary criterion, and anything mentioned zero times — often the thing the submitter is best at — is probably not what they are grading.

## Inputs

Anything that tells the user what someone else will judge: a take-home, job post, client brief, PRD, RFP, assignment, hackathon brief, grant call, ticket or interview task — and equally a single **message** or a **chat history** (email thread, Slack or Teams DM, LinkedIn or Upwork conversation, WhatsApp exchange). Requirements in a conversation are as binding as requirements in a spec; they are only harder to see.

For a message or chat history:

- **Separate the speakers.** The evaluator's messages carry the requirements; the user's own messages are context (what they already promised, asked or assumed). A requirement the user already agreed to in the thread is explicit.
- **Later overrides earlier.** When the evaluator changes their mind mid-thread, the latest version is the requirement and the change itself is a signal: name it in the Description and cite both messages.
- **Reference by message.** Cite as `msg 4 — Sarah, 14 Oct` (or the platform's own numbering) instead of a section name. Number the messages yourself when the thread has no numbering, and keep that numbering in `brief.md`.
- **Tone, response speed, and what they repeat across messages are persona evidence.** A client who asks twice whether you'll "be around after launch" has told you their veto.
- **Short inputs still get all seven sections.** A two-line message produces a short document, not a skipped section: say what the input does not tell you and how confident you are.

## Workflow

Work through all the phases internally. The thinking should be exhaustive; the *output* is the seven-section Evaluator Lens (see Output), as long as the input warrants and no longer. Do not skip phases to save effort — the implicit requirements live in phases 2–4 and are the whole point.

### Phase 0 — Classify the document and the evaluator

Decide what kind of document this is and who reads the submission. Read `references/document-archetypes.md` for the archetype table. Establish:

- **Document type**: take-home, job post, client brief, PRD, RFP, assignment, hackathon, grant call, internal ticket, interview exercise, message / chat thread, or hybrid.
- **Evaluator persona**: who judges (hiring engineers? a non-technical founder? a procurement committee? a professor? a PM?), how many submissions they compare, how long they spend per submission.
- **Decision being made**: hire / interview / award / fund / approve / merge. The decision shapes the rubric — an interview screen is graded on vetoes, a final-round task on differentiators.
- **Filter or confirmation**: many → few (evaluator hunts for reasons to say no) vs. few → one (evaluator hunts for reasons to say yes). This changes which criteria are vetoes.
- **Stakes and tone**: the document's voice (warm, bureaucratic, terse, over-specified) tells you how the evaluator thinks and what they are tired of seeing.

If the user has given context (their role, what they're applying for, the deadline, a prior rejection), fold it in here; it goes into the **Context understanding** section of the output rather than a separate file. Prior rejections are gold — they are the evaluator's rubric stated in retrospect.

### Phase 1 — Literal pass: explicit requirements

Enumerate everything the document actually states. Keep source quotes short; they are evidence, not decoration. Split into:

- **Functional** — what the thing must do.
- **Deliverables** — every artifact that must be handed over (files, links, videos, repos, forms, headings inside files).
- **Constraints** — time, stack, role, format, length, platform, budget.
- **Process rules** — how to work (commit as you go, don't publish, ask vs. decide, use X tool).
- **Submission mechanics** — where, to whom, by when, in what form.

Tag each MUST / SHOULD / MAY using the author's own force: "please don't go much over" is a MUST wearing politeness; "it's enough to…" is a MAY; "you can start from this" is a SHOULD with a strong hint.

For each requirement also record what the output needs: a **reference** (section, heading or message number, plus a short quote when the wording's force matters), the **impact** (what missing or botching it costs the submission, in one clause) and a **severity**:

- **Critical** — missing it ends the evaluation on its own (a MUST whose absence blocks review, a hard filter, the veto).
- **High** — a major deduction; the evaluator will notice and mark down.
- **Medium** — noticed and counted, but recoverable by strength elsewhere.
- **Low** — a tiebreaker or a courtesy.

Severity comes from the author's force *and* the consequence: a polite "please don't go much over" on a timebox the evaluator repeats three times is High, not Medium.

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
7. **Is it a reassurance?** "No hidden checklist", "don't worry about X", "there's no right answer" — reassurances mark the exact anxiety the evaluator is grading. "No right answer" means *your reasoning* is the answer.
8. **Does it hand you a decision?** "How you do that is up to you", "make the call and write it down" → the decision *and its rationale* are the deliverable; the implementation is secondary.
9. **Does it warn that the ground is unstable?** "We don't promise it runs cleanly", "treat it like an existing codebase" → a planted obstacle. Handling it is graded; *reporting* how you handled it is graded more.

Use `references/signal-lexicon.md` as the decoder ring for common phrasings. It maps phrase patterns to the criterion they usually encode, with the failure mode each one is guarding against.

Then run the cross-sentence techniques at the end of `references/interrogation-techniques.md`: count the communication imperatives against the build imperatives, trace every mandated artifact back to the criterion it serves, list what the submitter would naturally optimize that the document never mentions, find the tension pairs, read the voice — and **audit the stated requirements themselves for defects** (a shortcut that collides with a browser default, two requirements that contradict each other, a role named but never defined). Task sentences are exempt from the nine questions, not from scrutiny; a defect in the numbered list is something the evaluator notices who notices.

For each implicit requirement you extract, record: the requirement, the reference (quote and where it sits), its impact and severity on the same scale as Phase 1, and a **confidence tier**:
- **Stated** — said outright, just not labeled as a criterion.
- **Strong** — multiple signals converge; a reasonable evaluator would confirm it.
- **Inferred** — one signal plus archetype knowledge; probably true.
- **Speculative** — plausible, worth hedging for, but do not build the plan around it.

### Phase 3 — Aggregate signals into themes and weights

Cluster the implicit requirements into themes. Then, for each theme:

- **Count occurrences.** Same idea in different words still counts.
- **Count surfaces.** Does the theme appear in the instructions? The deliverable template? The "what happens next" section? The FAQ? Each additional surface is a multiplier.
- **Note what is absent.** If the document never mentions a thing the submitter would naturally optimize for (code elegance, visual polish, completeness), that absence is information. The evaluator may still notice it, but it is not what they are grading.
- **Flag deliberate tensions.** Timebox vs. completeness, "brief not spec" vs. "tell us what you decided", "use AI" vs. "we want to see *you*". Tensions are placed on purpose; they are where the evaluator watches judgment. The submission must visibly resolve each tension and say how.

The optional pre-pass script `scripts/signal_scan.py` extracts candidate meta-sentences, counts recurring evaluative terms, and lists mandated headings. Run it on long documents (`python scripts/signal_scan.py <file>`) so nothing is lost to skimming, then do the real reading yourself — the script finds sentences, it does not understand them.

### Phase 4 — Model the evaluator

Write a short first-person sketch of the evaluator, two to four sentences. What have they seen thirty times this month? What makes them stop reading? What makes them forward a submission to a colleague with "look at this one"? What are they afraid of hiring/awarding/approving by mistake?

When the document tells you who the evaluator is — "your future teammates", "at least one of whom has been a fellow", "two of our engineers", a store owner writing in the first person — that is the most specific evidence you have about the persona, and the sketch should carry it. An evaluator who has done the applicant's job reads differently from one who has not; an evaluator who was burned personally reads differently from a committee. A persona that would fit any evaluator of any document is a persona built from the archetype, not from this document.

For any document that mentions AI tools, read `references/ai-era-signals.md`. Evaluators of AI-assisted work often carry an unstated question — **can I tell a human with opinions was steering?** — and when a brief asks for transcripts or prompts, that question is usually why. Treat it as a *candidate* veto, not a default: test it against the document's own repetition count like any other theme. A brief that mentions AI once in passing and talks about load, correctness, or test design ten times has a different veto, and reading "steer the AI" into it would be the same mistake this skill exists to prevent.

The persona is not decoration. It is what lets you predict the veto criterion and the differentiators in Phase 5, and it is what the user will read to recalibrate their own framing.

### Phase 4b — Gauge the evaluator's receptiveness to AI

Every evaluator now holds a position on AI-assisted work, and the user will be asked about it — in an interview, a client call, a proposal form, a grant panel. This phase produces the **AI receptiveness** section and always runs, even when the input never mentions AI. Read `references/ai-era-signals.md` → *Gauging receptiveness*.

Estimate:

- **Receptiveness %** — 0 means AI use would disqualify or offend this evaluator, 50 means neutral or no signal, 100 means they expect and reward it. Anchor it on quotes and on what the input asks for (transcripts, prompts, "no AI", "use whatever tools"), then adjust for archetype and tone.
- **Is AI use examined?** — graded, candidate veto, tiebreaker, forbidden, or silent (the classification in `ai-era-signals.md`).
- **Recommended AI involvement** — the share of the work it is wise to do with AI for *this* evaluator, and which parts should visibly stay human.
- **If asked "how much AI did you use?"** — the recommended answer: the user's *actual* share, stated plainly, framed around the decisions the human made. Give a band that fits the evaluator (e.g. "~60% — lead with what you decided and verified yourself") and the sentence to say it with. Never recommend stating a number the user's real usage does not support: a disclosed figure that a transcript, commit history or follow-up question later contradicts is worse than any honest number, and it is exactly what an AI-wary evaluator is checking for. If the user's actual usage sits far from what the evaluator will accept, say so and recommend changing how the work is done, not what is said about it.
- **Confidence** — a percentage and one line on why. Silence on AI means low confidence: say "no signal; defaulting to the archetype" instead of inventing precision.

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

When the user has asked how to *approach*, *frame*, *structure*, or *write* the submission — not only what will be graded — add a **Recommended shape** block under **Submission package**: the submission's sections in the evaluator's reading order, each with a share of the length or time roughly proportional to its rubric weight, and the proof moment that belongs in it. The rubric already implies this plan; handing it over saves the user from translating weights into an outline themselves, and it is where the analysis becomes something they can start writing from. For a scored call with published weights, the shares follow the weights. For a timeboxed exercise, the shares are hours. For a proposal, they are paragraphs.

### Phase 7 — Traps, planted obstacles and hidden tests

List what the document does not say but the evaluator is checking:

- **Planted obstacles**: broken setup, missing config, contradictory specs, an intentionally vague acceptance criterion. The test is whether you notice, how you handle it, and whether you report it.
- **Embedded filters**: a phrase to include, a question to answer, a specific format — attention tests that silently reject copy-paste responses.
- **Over-delivery traps**: places where doing more signals worse judgment (blowing the timebox, gold-plating, solving the unasked problem).
- **Graded-but-looks-optional**: commit history, naming, the "questions" section, the cover note, the order things are presented in the video.
- **Blocks-review-entirely mechanics**: the wrong platform, a missing collaborator, a file not at the path named, a link not where it was asked for, a reply sent through the wrong channel. These look like logistics and are easy to list as requirements and forget as risks. An evaluator who cannot open the work does not grade it; name them as traps, not just as MUSTs, because the consequence is total.
- **Tone traps**: the document's voice invites a matching register; mismatch (over-formal reply to a casual brief, or the reverse) is noticed.

### Phase 8 — Open decisions and questions

The document deliberately leaves things undecided. For each gap:

- For documents where asking is possible (client briefs, PRDs, RFPs with a Q&A window): decide whether to **ask** or **assume**. Asking too much reads as inability to proceed; assuming too much reads as not listening. Recommend which, and draft the question or the assumption.
- For documents where asking is explicitly discouraged ("make the call and write it down"): list each decision with a **recommended call and a one-line rationale** the user could write down verbatim. The rationale is the deliverable.

Group decisions by stakes: the ones the evaluator will definitely ask about first.

### Phase 9 — Simulate the evaluator's verdict

Re-read the plan as the persona from Phase 4. Write the one-line verdict they would give a submission that follows this plan. If it is not the verdict the user wants, name the missing proof moment and add it to Phase 6.

Then produce a short pre-submission checklist: every required artifact present and populated with what its name promises; every primary criterion has at least one visible proof; the veto criterion is addressed within the first ninety seconds of any video, the first paragraph of any written note, and the first screen of any transcript.

## Output

One document: the **Evaluator Lens**, in seven sections, using `assets/output-template.md`. The section names are fixed — the audit skill reads them by name — and every section appears even when the input is short.

**Length.** There is no length cap. The document is as long as the input's actual requirements make it: a twelve-page RFP with forty mandatory items produces a long Lens, a three-line client message a short one. What is capped is *unnecessary* text. Every line is a claim backed by a reference or a labeled inference; nothing restates what another section already says; nothing re-presents the input for its own sake. Cut first: narrative framing, restated evidence, a second example that adds no second insight, and explicit requirements that are obvious from the input's own headings (group those into one row). Never cut the veto, any implicit requirement at Strong confidence or above, any Critical or High requirement, any required-to-exist event, any planted obstacle, or the simulated verdict.

**References.** Every requirement, signal and claim points back to the input: a section or heading name, a line or message number, and a short quote when the wording's force is the point (`§Deliverables — "please don't go much over"`, `msg 3 — Sarah`). Inference from archetype knowledge is labeled as such, not dressed up as a quote.

The seven sections, and which phases feed them:

1. **Description** (Phases 0–1) — what is being asked, by whom, for what decision, by when, and in what form, in plain language. Preferably seven or eight lines, each sentence carrying an inline reference. A reader who reads only this knows what the task is.
2. **Context understanding** (Phase 0) — document type and archetype, who evaluates and how many submissions they compare, the decision being made, filter or confirmation, stakes and tone, constraints (time, budget, stack, platform), and the user's own context: role, deadline, prior attempts or rejections, what they have already said or promised in the thread. This replaces the old separate `context.md`.
3. **Evaluator intent** (Phases 3–4) — what the evaluator actually wants underneath what they wrote. The first-person mental model (two to four sentences, one per audience if two grade differently), the themes that carry the most weight and why, what they are afraid of approving by mistake, and what is conspicuously *not* graded.
4. **Explicit requirements** (Phase 1) — a table: requirement (short description) · reference · impact · severity. Group related items into one row. Order by severity, Critical first.
5. **Implicit requirements** (Phase 2) — a table: requirement (short description) · reference · impact · severity · confidence (Stated / Strong / Inferred / Speculative). Lead with the one behind the veto.
6. **AI receptiveness** (Phase 4b) — receptiveness %, whether AI use is examined, recommended AI involvement, the recommended answer to "how much AI did you use?" with the sentence to say it with, the evidence it rests on, and your confidence %.
7. **Understanding** (Phases 5–9), four parts:
   - **Matrix** — the weighted rubric: criterion · weight (percentages summing to 100) · confidence · what failing looks like. Below it: what is not graded, and the simulated verdict if the plan is followed (and if the user's current approach is followed, when known).
   - **Deal breakers** (what to avoid) — the **veto criterion** first, as one sentence the evaluator could put in a rejection email plus the evidence that points at it; then every trap from Phase 7 — planted obstacles, embedded filters, blocks-review mechanics, over-delivery traps, tone traps, defects in the stated requirements — each with its reference.
   - **Deal makers** (what to do) — the differentiators that separate a pass from a strong pass, and the open decisions from Phase 8 as *decision → recommended call — rationale* (marked Ask or Assume where asking is possible).
   - **Submission package** — a list of what the submission should include, not the submission itself. The form follows the input: a message reply, a proposal, a repo plus README, a video, a cover note, a form, a deck. Each item in the evaluator's reading order, with what it must contain. Then the proof per criterion (criterion · surface · proof moment · anti-pattern), the required-to-exist events with when each must happen, the recommended shape when the user asked how to approach or structure the work, and the pre-submission checklist.

Lead the chat reply with the veto and the Description; the user may read nothing else before deciding whether the rest is right.

## Persist the Lens

The document you just wrote is the contract that every later step reads: the user's own work, the halfway checkpoint, the pre-submission audit, and the post-mortem if there is one. A reply in chat is not a contract; it scrolls away and the next session cannot find it. So the last step of every analysis is to write it to disk, in a known place, with the input it was built from.

The place is `docs/evaluator-expectations/` inside the project (or the current working directory when there is no project). Write:

- `expectations.md` — the Evaluator Lens, exactly as presented, with the front-matter block from the template at the top. The front-matter is what a downstream skill anchors on; the section headings are what it reads by name. Keep both exactly as the template has them.
- `brief.md` — the input, verbatim: the document, or the message or chat history with its speakers, dates and message numbers. It is not a second analysis; it is the source the references point into, kept so the audit and the post-mortem can check the exact wording.

Then say in one line where you wrote them. `references/handoff-folder.md` has the full contract for the folder — file names, which skill writes and reads each, the front-matter fields — and is what the audit skill is built against; read it before writing the folder the first time in a session.

Two environment rules:

- **With a filesystem and a repo** (Claude Code or a linked folder): the folder must not ship with the submission. An evaluator who finds a model of their own rubric in the repo reads it as gaming, not diligence. Add `docs/evaluator-expectations/` to `.gitignore` in the same step, say that you did, and let the user remove the line if they want the folder tracked. If the brief asks for "all prompts" or "the full session", that request is about the *analysis session*, not this folder; the Lens already flags that decision under Deal breakers.
- **Without a persistent filesystem** (claude.ai): write both files anyway, send them to the user, and tell them to attach both when they run the audit. Same format, carried by hand.

If the user asks you to re-run or revise the analysis on the same input, overwrite `expectations.md` and bump `version` in its front-matter; do not accumulate copies. When a chat continues and new messages arrive, append them to `brief.md` and re-run: a changed requirement is a new version. The audit records which version it graded against.

## Post-mortem mode

When the outcome is known — the user pastes feedback, a rejection, an acceptance with notes, or `docs/evaluator-expectations/outcome.md` exists — the skill runs again on different inputs. Read `brief.md`, `expectations.md`, `docs/submission-audit/audit-final.md` and `gaps.md` if the audit skill wrote them, and the feedback. Then answer four questions, in this order:

1. **Which criterion did the feedback grade on?** Map each sentence of the feedback to a Matrix row, a deal breaker, or a required-to-exist event in the Lens. Feedback is the evaluator's rubric stated in retrospect; this is the only ground truth the method ever gets.
2. **Was it in the Lens?** If yes, at what weight and confidence, and was it the veto? If the feedback's main point was weighted 5% in the Lens, the count was wrong, and the question is which signals were under-read. If it was not in the Lens at all, find the sentence in the brief that should have produced it and name the interrogation question that would have caught it.
3. **Did the audit pass it?** If an audit ran and passed a criterion the evaluator failed, the audit's proof-moment test was too lenient; say what evidence it accepted that the evaluator did not.
4. **What changes next time?** One line per change, phrased as an instruction to the next analysis — "count reassurances as criteria", "treat a named evaluator background as persona evidence". These are what the user carries forward, and what belongs in this skill's worked examples if the case is clean enough to teach from.

Write the answers to `docs/evaluator-expectations/calibration.md` using the post-mortem section of the template, and present the four answers in the reply. Do not re-run the full analysis; the Lens already exists and the point is to grade *it*, not the document.

Praise in feedback is evidence too. "The race-safe limit stood out" tells you what the evaluator noticed and still rejected; that is the clearest possible measure of how little the praised axis weighed.

## Evidence discipline

Everything in the Lens must trace to the input in front of you, the user's own context, or archetype knowledge clearly labeled as such. Two rules:

- **The worked examples are for calibration, not citation.** `references/worked-examples.md` records analyses of specific documents, one with a real outcome. Use them to check the depth of your reading. Do not present an example's outcome to the user as evidence about a *different* document ("submissions like this have been rejected for…") — that is the archetype talking, so say so: "evaluators in this archetype commonly reject on…". If the user's document is one of the worked examples, you may mention the known outcome, attributed to this skill's reference material.
- **Mark inference as inference.** The confidence tiers exist for this. A claim about what the evaluator will do that is not Stated or Strong should read as a prediction, not a fact.
- **Do not import a veto from a previous document.** Each document's veto comes from its own repetition count, mandated headings, and interaction previews. If you find yourself reaching for the same veto you found last time before you have counted, stop and count.

## Calibration

Read `references/worked-examples.md` when you want to check your reading against a worked case. It holds three documents from different archetypes — a technical take-home with a real rejection on record, a freelance client brief, and an internal PRD — each with the analysis this skill should produce and the veto it should find. The vetoes differ in kind (process visibility, post-launch trust, an unstated metric), which is the point: if your analyses of different document types keep arriving at the same veto, your Phase 3 count is being skipped.

## When the user disagrees with the veto

Users sometimes resist the veto criterion because it is not what they are good at or not what they expected to be graded on. Hold the line with evidence. Quote the repetitions. Point at the mandated headings. Then help them build the proof moments — the point of the analysis is to redirect effort before it is spent, not to be right about the document.

## Reference files

- `references/document-archetypes.md` — evaluator persona, comparison set, typical vetoes and differentiators per document type. Read in Phase 0.
- `references/interrogation-techniques.md` — the nine questions expanded, with examples from several document types. Read before Phase 2.
- `references/signal-lexicon.md` — phrase patterns → encoded criterion → failure mode guarded against. Use during Phase 2.
- `references/rubric-reconstruction.md` — weighting by repetition and surface, confidence tiers, locating the veto. Read in Phase 5.
- `references/evidence-planning.md` — surfaces, proof moments, anti-patterns, the required-to-exist rule. Read in Phase 6.
- `references/ai-era-signals.md` — what "use AI" actually tests; markers of human direction in transcripts. Read in Phase 4 for documents that mention AI tools, and in Phase 4b (*Gauging receptiveness*) for every input.
- `references/worked-examples.md` — three calibration cases from different archetypes, one with a real outcome. Read when uncertain.
- `references/handoff-folder.md` — the `docs/evaluator-expectations/` and `docs/submission-audit/` contract: files, front-matter, who writes and reads each. Read before persisting the first time in a session; identical copy lives in the audit skill.
- `assets/output-template.md` — the seven-section Lens skeleton, including the front-matter block and the post-mortem section.
- `scripts/signal_scan.py` — optional deterministic pre-pass for long documents.
