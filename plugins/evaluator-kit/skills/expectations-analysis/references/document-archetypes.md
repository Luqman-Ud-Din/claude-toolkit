# Document Archetypes

Who reviews each kind of document, what they compare the submission against, how long they spend, what usually vetoes, and what usually differentiates. Use in Phase 0 to pick a starting persona, then refine from the document's own signals.

Hybrids are common (a take-home with job-post framing; a client brief that reads like a PRD). Pick the dominant archetype for the persona and borrow vetoes from the secondary one.

## Quick table

| Archetype | Evaluator | Compares against | Time per submission | Filter or confirmation | Typical veto | Typical differentiator |
|---|---|---|---|---|---|---|
| Technical take-home | 2–3 engineers, often the future teammates | 5–30 other submissions, same brief | 30–90 min each, plus a sync | Filter (→ interview) | Whatever the brief repeats most — commonly silent decisions, blown timebox, not reading the brief; passive AI use when transcripts are requested | Decision log depth; proportionate fixes; honest scoping; extension-ready design |
| Interview exercise (live or short) | 1–2 interviewers | A mental model of a "good" answer | Real-time | Confirmation | Inability to explain own choices | Thinking aloud; asking the one right question |
| Job post / application | Hiring manager or recruiter | 50–500 applications | 30–120 seconds first pass | Hard filter | Missing hard requirement; generic cover note; attention-filter miss | Specific evidence matched to their stated problem |
| Freelance / client brief | The buyer (founder, PM, owner), often non-technical | 10–60 proposals | 20–60 seconds first pass | Hard filter | Copy-paste proposal; ignored embedded question; price far outside budget | Restating their problem better than they did; a scope proposal; a communication plan |
| PRD / product spec | PM + tech lead + sometimes design | Their own intent; previous features | Varies; iterative | Confirmation (approve plan / merge) | Building out-of-scope; missing the success metric; surprises late | Finding the unstated metric; risk register; phase-2 seams without building phase 2 |
| Internal ticket / issue | Tech lead or evaluator of the PR | The ticket's AC; codebase conventions | 10–30 min PR review | Confirmation | Not matching AC; breaking conventions; no tests | Noticing adjacent issues; crisp PR description |
| RFP / procurement | Committee with a scoring sheet | 3–20 bids | Hours, structured | Filter then confirmation | Non-compliance with format; missing mandatory; over budget | Compliance matrix; matched case studies; realistic risks |
| Grant / fellowship call | Panel of domain evaluators | Dozens to hundreds | 15–30 min | Filter | Misfit with call priorities; vague impact; budget mismatch | Explicit alignment with each stated priority; measurable outcomes |
| Academic assignment | Instructor or TA with a rubric | Rubric + class cohort | 10–20 min | Confirmation (grade) | Missing rubric line; not following format | Insight beyond rubric; clear structure |
| Hackathon brief | Judges, often sponsors | 20–100 teams | 3–5 min demo | Filter | Demo fails; doesn't use sponsor tech; unclear problem | Story + working demo + obvious next step |
| Design brief / creative brief | Creative director or client | Their brand; competitors | Minutes | Filter | Off-brief; off-brand; ignored constraints | Interpreting the brief, not executing it literally |
| Message / chat thread | The sender: a client, recruiter, hiring manager, colleague or stakeholder writing informally | Other replies they have had, or their own expectation | Seconds to read a reply; days of context in the thread | Either; often confirmation once a conversation has started | Missing what they asked two messages ago; ignoring a changed requirement; wrong register; slow or vague reply | Answering every open question in order; restating the latest requirement accurately; a concrete next step |

## Per-archetype notes

### Technical take-home

The evaluators are usually the people you would work with. They have a standing brief and have read many responses to it, so they know its ambiguities intimately and have a mental list of which ones a strong candidate notices. They are tired of: feature-complete submissions with no reasoning, giant squashed commits, over-engineered solutions to a 3-hour problem, and — increasingly — transcripts that show the candidate as a spectator to the AI.

When a take-home permits AI tools *and* asks for transcripts, prompts, or a session export, the reason is almost always that the evaluators want to see whether a human with opinions was directing the work — see `ai-era-signals.md`. When it permits AI but asks for nothing of the kind, the veto is wherever the brief's own repetition points (correctness under load, test design, data modelling, communication), and AI direction is at most a differentiator. Count before assuming.

What they compare against: the other submissions to the same brief. Your decision log is read alongside ten others; the ones that noticed the most ambiguities and resolved them with the clearest rationale stand out immediately.

Filter dynamic: they are looking for a reason to say no in the first pass (read SUBMISSION.md, skim transcript, skim commits), then a reason to say yes in the second (read code, watch video). Front-load the veto-criterion proof into the first-pass surfaces.

### Interview exercise

Confirmation mode: they already like you. Veto is inability to explain your own reasoning or to adapt when they change a constraint. Differentiator: asking the one question that reveals you understood the problem's real difficulty.

### Job post / application

The first pass is seconds. Hard requirements are scanned for; a missing one ends the read. Attention filters ("mention the word…", "answer these three questions") are deliberately placed to reject the 80% who do not read. Generic cover letters are a veto because they prove the applicant did not read the post.

The evaluator's real question: *does this person understand what I need and can they show me, not tell me, that they have done it before?* Specific evidence matched to the post's stated problem beats any amount of credentials.

### Freelance / client brief

The evaluator is a buyer, usually not an expert in what they are buying. They fear: being ghosted, scope creep, paying for your learning, being talked down to, and not understanding what they are getting. They decide in under a minute on the first pass.

Winning proposals restate the client's problem more clearly than the client did (proves listening), propose a scope with explicit assumptions and exclusions (proves judgment and protects both sides), name a communication cadence (addresses the ghosting fear), and answer any embedded question first.

Price: far outside the posted range in either direction is a veto. Slightly above with a justification is fine. Far below reads as not understanding the work.

### PRD / product spec

The evaluator wants the thing they imagined, built without surprises, and they want to know early if that is not possible. The real requirement is the success metric; if it is absent, it is implicit in the "why" or "background" section and the evaluator expects you to find it. Once found, say outright that the listed goals and requirements are instruments for that metric — "insert in under 3 seconds" is a means to "first-response time under 2h30", not an end — because the PM knows this and wants to hear that you do too.

Vetoes: building listed non-goals or out-of-scope items; missing a stakeholder's need; late surprises. Differentiators: a risk register, a phase-2-aware design that does not build phase 2, clear flagging of every TBD with a recommendation.

### Internal ticket

Short, often under-specified. The evaluator is the PR evaluator. Veto: not meeting the AC or breaking conventions. Differentiator: noticing and flagging the adjacent bug without fixing it unasked; a PR description that lets the evaluator approve without opening every file.

### RFP / procurement

Committee scoring against a published or semi-published sheet. Compliance is binary and filters first. Then scored sections, often with stated weights — those weights *are* the rubric, allocate pages proportionally. Vetoes are almost always format or mandatory-requirement misses. Differentiators: a compliance matrix, case studies matched to each requirement rather than generic ones, and a risk section that names real risks (committees distrust bids with no risks).

### Grant / fellowship

Panel evaluators score against the call's stated priorities. Misalignment with a priority is a veto even if the work is excellent. Vague impact is a veto. Differentiators: explicit mapping of the proposal to each priority, measurable outcomes, a budget that matches the narrative.

### Academic assignment

Rubric-driven. Missing a rubric line is a direct deduction. Differentiator is insight beyond the rubric, but only after every rubric line is visibly covered. Format compliance (length, citation style) is a silent filter.

### Hackathon

Judges see a demo for minutes. Veto: the demo does not work, or the problem is unclear. Sponsor-provided briefs usually require using the sponsor's technology meaningfully — token usage is noticed and penalized. Differentiator: a story (problem → solution → impact) told in the first thirty seconds.

### Design / creative brief

The brief states constraints and a goal; the evaluator grades interpretation. Literal execution of the brief is a weak pass; a solution that reveals an insight about the brand or audience is a strong pass. Vetoes: ignoring a stated constraint (brand colors, audience, format); off-brief concepts however polished.

### Message / chat thread

The requirements are spread across turns, mixed with small talk, and sometimes revised mid-thread. The evaluator is the person on the other side, and they judge the reply against everything they have said so far, not just the last message. They are tired of: replies that answer only the latest message, replies that re-ask something already answered, and replies in a register that does not match theirs (a formal proposal to a two-line Slack message, or the reverse).

Read every evaluator message as a requirement source, number the messages, and track changes: the latest statement wins, but the change itself tells you what they care about. What they repeat across messages is weight, exactly as in a document. Questions they ask and you have not answered are Critical explicit requirements. The submission package is usually a reply, sometimes with an attachment, a call, or a follow-up date; its first line should answer the thing they most recently asked.

## Identifying hybrids

- **Take-home that reads like a job post** ("we're looking for someone who…"): persona is the hiring team; veto is from the take-home column; add culture-fit differentiators from the job-post column.
- **Client brief that reads like a PRD** (detailed features, non-technical client): persona is the buyer; use PRD technique to find the success metric, but write the response in the client-brief register.
- **Ticket with a PRD attached**: persona is the PR evaluator, but the PRD's success metric and non-goals govern scope.
- **RFP with a take-home component** ("submit a sample solution to…"): compliance filters first, then the take-home vetoes apply to the sample.

## Evaluator-persona template

Fill this in Phase 4 after choosing an archetype:

> I am [role]. I have [N] of these to read and about [time] for each. I have seen [the common failure] too many times and I am looking for [the thing that would make me stop and forward this to a colleague]. I will reject on sight if [veto]. I will be impressed if [differentiator]. The thing I most want to know and cannot easily tell from a résumé is [the real question].
