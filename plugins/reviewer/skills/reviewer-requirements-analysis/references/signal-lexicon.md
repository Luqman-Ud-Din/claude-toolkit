# Signal Lexicon

Phrase patterns that encode a grading criterion, the criterion they usually encode, and the failure mode the author is guarding against. Use this during Phase 2 as a decoder ring — then confirm each match against the specific document, because context can flip a reading.

Entries are grouped by what they tell you. Each row: **pattern → encoded criterion → what the author has seen go wrong → what the reviewer will look for.**

## Contents

1. Reasoning and judgment signals
2. Process and communication signals
3. AI-use signals
4. Scope and time signals
5. Delegated-decision signals
6. Planted-obstacle signals
7. Deliverable-shape signals
8. Future-interaction signals
9. Reassurance signals
10. Job-post and client-brief signals
11. PRD / spec / ticket signals
12. RFP / procurement / grant signals
13. Absence signals (what is *not* said)
14. Voice and register signals

---

## 1. Reasoning and judgment signals

| Pattern | Encodes | Guarding against | Reviewer looks for |
|---|---|---|---|
| "what we care about is how you reason / think / approach" | Reasoning quality and visibility is primary | Submissions that are correct but opaque | Decision log with alternatives and trade-offs; rationale in commits, notes, video |
| "we're interested in how you…" / "we want to see how you…" | The *how* is graded, not the *what* | Outcome-only submissions | Process artifacts |
| "there's no right answer" / "no hidden checklist" | Reasoning rubric replaces correctness rubric | Candidates guessing at a canonical solution | Justification depth, not solution match |
| "make the decision you'd make if this were real / shipping / production" | Judgment under realistic constraints | Toy decisions that ignore real-world consequences | Decisions that reference users, ops, money, failure modes |
| "tell us why" / "explain your reasoning" / "walk us through" | Rationale is a deliverable | Decisions stated without reasons | Every non-trivial decision has a why |
| "trade-offs" | Expect explicit cost/benefit framing | Candidates presenting one option as obviously right | Named alternatives, named costs |
| "what you chose not to do" | Deliberate omission is graded positively | Gold-plating; inability to cut | A list of cut items with reasons |
| "judgment" / "taste" / "pragmatic" | Proportionality: effort matched to value | Over- or under-engineering | Solutions sized to the problem |

## 2. Process and communication signals

| Pattern | Encodes | Guarding against | Reviewer looks for |
|---|---|---|---|
| "commit as you go" / "real history" / "not one squashed commit" | Commit log is a graded narrative | Opaque history | Small commits with messages that explain intent; visible course corrections |
| "tell us what you found and what you did" | Reporting is graded separately from doing | Silent fixes | A note for every obstacle encountered |
| "document your assumptions" | Assumption-noticing is graded | Unstated assumptions | An explicit assumptions list |
| "notes don't count toward the timebox" | Notes are a primary deliverable | Skimping on write-up to protect code time | Thorough notes |
| "a short note" / "brief write-up" | Concision is graded | Walls of text | Dense, scannable, front-loaded |
| "keep it simple" / "don't over-engineer" | Restraint is graded | Framework-heavy solutions to small problems | Minimal viable structure |
| "as you would on a real team" / "the same way you would at work" | Professional habits (PR hygiene, tests, naming, comms) | Hackathon-style dumps | Habits visible in the artifacts |

## 3. AI-use signals

See `ai-era-signals.md` for the full treatment. Quick decoder:

| Pattern | Encodes | Guarding against | Reviewer looks for |
|---|---|---|---|
| "use AI, we expect it" | AI use is permitted *and will be examined* | Hidden use; passive use | Visible direction |
| "how you direct them, not whether you used them" | Direction quality is the criterion; usage is not | Approval-only sessions | Human-authored constraints, rejections, reshaping |
| "include your prompts / session / export" | Transcript is a graded artifact | Cleaned-up or missing transcripts | Raw transcript with human voice visible |
| "the moments where the AI got something wrong" | Error-catching is expected to have happened | Uncritical acceptance | ≥1 documented catch |
| "the places where you changed direction" | Overriding the AI is expected to have happened | Passenger behavior | ≥1 documented override with reason |
| "we'd rather see the raw session than a cleaned-up one" | They will read it for authenticity | Curated transcripts | Messiness is fine; sanitization is suspicious |
| "expect questions about your prompts" | Transcript will be discussed live | Candidates who cannot explain their own prompts | Prompts the candidate can defend |
| "we don't allow AI" / "please complete without assistance" | Independence is graded; AI use is a veto | Undisclosed AI use | Idiosyncratic human style; ability to explain every line |

## 4. Scope and time signals

| Pattern | Encodes | Guarding against | Reviewer looks for |
|---|---|---|---|
| "timebox: about N hours" | Time discipline is graded | Candidates spending 20 hours on a 3-hour task | Scope sized to N hours; honest time report |
| "please don't go much over" | Overrun is a *negative*, not a bonus | Gold-plating as a strategy | Evidence of cutting |
| "deciding what fits is part of the exercise" | Scoping is a first-class criterion | Trying to do everything | Explicit cut list with rationale |
| "what you'd do next if you had more time" | Forward thinking is graded; cuts are expected | Submissions that pretend to be complete | A credible, prioritized next-steps list |
| "a working X plus a clearly marked mocked Y is better than…" | Honest partial > dishonest whole | Half-configured everything | Clean boundaries, clearly labeled mocks |
| "focus on [your role] and do as much of the other as you can" | Graded relative to role; stretch is a differentiator | Backend candidates ignoring mobile entirely, or vice versa | Core role done well; other side attempted and honestly scoped |
| "MVP" / "minimum" / "enough to…" | Floor defined; ceiling is yours | Under-delivery | Floor met cleanly; any extra is deliberate |

## 5. Delegated-decision signals

| Pattern | Encodes | Guarding against | Reviewer looks for |
|---|---|---|---|
| "up to you" / "your call" / "we leave this to you" | Decision noticed + alternatives + rationale are graded | Silent choice | Written decision with why |
| "this is a brief, not a spec" / "on purpose" | Gaps are deliberate; noticing them is graded | Candidates who do not see ambiguity | A list of gaps found and resolved |
| "wherever that happens, make the decision you'd make" | Each gap → decision → rationale | Asking instead of deciding | Decisions, not questions |
| "if you have a question, make the call and write it down" | Asking is unavailable; recording is mandatory | Unwritten assumptions | Assumptions section populated |
| "we may extend the feature together" | Extensibility is probed live | Dead-end designs | Design with obvious seams |

## 6. Planted-obstacle signals

| Pattern | Encodes | Guarding against | Reviewer looks for |
|---|---|---|---|
| "treat it like an existing codebase" | Respect conventions; do not rewrite | Candidates who replace everything with their preferred stack | Changes that fit the existing style |
| "we don't promise everything runs cleanly" | At least one deliberate break exists | Candidates who give up or silently patch | Found it, fixed proportionately, reported it |
| "if you run into something broken, fix it or work around it, and tell us" | Three-part test: notice, handle, report | Any one part missing | All three in the notes |
| "legacy" / "inherited" / "has some rough edges" | Same as above, softer | Same | Same |
| "you may need to…" | A known gotcha | Candidates blocked by it | Handled without fuss |

## 7. Deliverable-shape signals

| Pattern | Encodes | Guarding against | Reviewer looks for |
|---|---|---|---|
| A mandated file with mandated headings | Each heading is a required-to-exist event | Empty or thin sections | Every heading substantive |
| "you can start from this [template]" | Template is a strong hint, not optional | Ignoring it | Template followed, possibly extended |
| "first show the feature working, then walk us through…" | Order of presentation is graded | Videos that start with the code tour | Demo first, then reasoning |
| "5–10 minute video" | Concision under a soft cap | 25-minute rambles | Tight, structured |
| "that's your whole submission" | Self-containment | Submissions that depend on a follow-up email | Everything in the one place |
| "screen plus voice is plenty, camera optional" | They want to hear you think, not see you | Over-produced videos | Narration quality |

## 8. Future-interaction signals

| Pattern | Encodes | Guarding against | Reviewer looks for |
|---|---|---|---|
| "expect questions about X" | X will be examined closely | Candidates unprepared on X | X documented well enough to discuss |
| "we may go through your submission together" | Every line is fair game | Code the candidate cannot explain | Candidate ownership of every decision |
| "we may extend the feature together" | Design will be stress-tested live | Brittle designs | Visible extension points |
| "we'll let you know either way" | Fairness signaling; persona is considerate | — | Match the courtesy |
| "within N business days" | Multiple reviewers, limited time each | Submissions that bury the lede | Front-loaded artifacts |

## 9. Reassurance signals

Reassurances mark the anxiety being graded at a deeper level.

| Pattern | Surface reassurance | What it actually means |
|---|---|---|
| "no hidden checklist" | Don't worry about matching a key | Reasoning is graded instead of correctness |
| "no right answer" | Any choice is acceptable | The *justification* is the answer |
| "don't spend your timebox on [setup]" | Setup is not graded | Time allocation is graded; they want to see you cut losses |
| "notes don't count toward the time" | Take your time on notes | Notes are primary |
| "we don't promise it runs" | Don't panic if it's broken | It is broken; find it |
| "any tools are fine" | Tool choice is not graded | Stop justifying tools; show direction instead |
| "camera optional" | No need to be on video | Narration matters, presence does not |
| "no experience with X needed" (job) | You can apply without X | They are grading learnability and fit, not X |

## 10. Job-post and client-brief signals

The reviewer is a buyer. They are afraid of being ghosted, of scope creep, of paying for someone's learning curve, and of not being understood.

| Pattern | Encodes | Reviewer looks for |
|---|---|---|
| "must have" vs "nice to have" vs "familiarity with" | Hard filter vs. soft filter vs. non-filter | Hard filters met explicitly in the first lines |
| "please include the word X" / "start your reply with…" | Attention filter | Exact compliance; this alone rejects most applicants |
| "answer these questions in your proposal" | Structured screening; non-answers are rejected | Each question answered in order, labeled |
| "long-term" / "ongoing" / "looking for a partner" | Relationship over price; reliability graded | Evidence of staying power, communication cadence |
| "simple" / "quick" / "should only take…" | Budget anchor, often wrong | Gentle scope reality-check without condescension |
| "we've been burned before" / "previous freelancer…" | Trust is the veto | Proof of reliability, references, communication plan |
| "share similar work" / "portfolio" | Relevance of samples is graded, not volume | Two or three closely matched samples, not twenty |
| Vague scope + fixed budget | Scope-definition skill is graded | A proposed scope with assumptions and what is excluded |
| Non-technical language describing a technical task | Client cannot evaluate code; they evaluate communication | Plain-language explanation, no jargon, confidence without arrogance |
| "urgent" / "ASAP" | Availability is a hard filter; also a red flag for planning | Explicit start date and a realistic timeline |
| "NDA required" / "confidential" | Discretion graded | No pressing for details before signing |

## 11. PRD / spec / ticket signals

The reviewer is a stakeholder, a PM, or a tech lead. They are afraid of building the wrong thing, of surprises late, and of having to explain delays upward.

| Pattern | Encodes | Reviewer looks for |
|---|---|---|
| "success metric" / "we'll know it worked when…" | The real requirement; everything else is means | Design choices traced back to the metric |
| Absent success metric | The implicit metric is in the "why" section; find it | Engineer who infers and states the metric |
| "out of scope" | Boundaries are graded; crossing them is a negative | Respect the boundary, name it when adjacent |
| "open questions" section | They want these resolved or escalated, not ignored | Each one addressed |
| "stakeholders: …" | Each stakeholder has a different success criterion | Design that serves each named stakeholder |
| "phase 1 / phase 2" / "eventually" / "later" | Design for phase 2 without building it | Extension seams; no premature building |
| "non-goals" | Explicit non-requirements; building them is a negative | Restraint |
| Acceptance criteria written as user outcomes | Tests should map to these | Test names mirror AC |
| "TBD" | A decision someone forgot; noticing it is graded | Flagged, with a recommendation |
| "risks" / "dependencies" | They want risk awareness in the plan | Risk register in the response |
| "Owner: TBD" / "Eng lead: TBD" | The reviewer is auditioning you for the slot | Take ownership in the response |
| A numbered requirement that conflicts with the platform, another requirement, or the goal | A defect (planted or honest); noticing is a differentiator | Flagged with a one-line fix |
| A role named but never defined ("manager", "admin") | Permissions model is unspecified | Proposed definition, flagged as assumption |

## 12. RFP / procurement / grant signals

The reviewer is a committee with a scoring sheet. They are afraid of non-compliance, of being sold to, and of choosing a vendor who cannot deliver.

| Pattern | Encodes | Reviewer looks for |
|---|---|---|
| Numbered requirements | Each is a scored line; traceability is mandatory | A compliance matrix mapping each number to a response |
| "evaluation criteria" with percentages | The literal rubric; weight effort accordingly | Proportional page allocation |
| "mandatory" / "shall" | Pass/fail gate | Explicit "we comply" with evidence |
| "should" / "may" | Scored but not gating | Addressed, prioritized below mandatories |
| Page limits / format requirements | Compliance is a filter | Exact compliance; non-compliance is disqualifying |
| "demonstrate experience with…" | Past performance is the main evidence | Case studies that match the requirement, not generic ones |
| "describe your approach to…" | Methodology is scored | Specific, sequenced, with risks |
| "questions due by…" | They expect clarifying questions; silence can read as disengagement | Thoughtful questions submitted on time |
| "budget not to exceed" | Price is a gate and a score | Within budget, with itemization |

## 13. Absence signals

What the document does **not** say is as informative as what it does.

| Absent | Means |
|---|---|
| No mention of code quality / style / tests | Not a primary criterion. Still noticed, but spending the budget here is misallocation. |
| No mention of UI / design | Function over form. A plain UI with a working flow beats a polished UI with gaps. |
| No success metric in a PRD | Metric is implicit in the "why" paragraph; the reviewer wants you to find and state it. |
| No timebox | Reasonable-effort expectation; over-delivery is less penalized but still watched. |
| No deliverable template | Structure is yours; the reviewer will grade whether you chose a sensible one. |
| No mention of AI | Assume AI use is tolerated but will not be examined; do not volunteer a transcript unless asked. |
| No "what happens next" | One-shot evaluation; everything must be in the submission. |
| No named reviewers | Committee or rotating reviewers; write for a reader with no context. |

## 14. Voice and register signals

| Voice | Persona | Match with |
|---|---|---|
| Warm, first-person plural, contractions, "thanks for taking this on" | A team that wants a colleague | Conversational, direct, honest about limits |
| Terse, bulleted, no pleasantries | Busy engineers; respect their time | Dense, front-loaded, no throat-clearing |
| Bureaucratic, numbered, "shall" | Procurement; compliance first | Mirror their numbering; compliance matrix |
| Over-specified, defensive | Burned before; trust is the veto | Reliability signals, explicit acknowledgment of each requirement |
| Under-specified, vague | Non-technical or time-poor author; they need you to define scope | Proposed scope with assumptions, in plain language |
| Enthusiastic, mission-driven | Culture fit is graded | Genuine engagement with the mission, not flattery |
