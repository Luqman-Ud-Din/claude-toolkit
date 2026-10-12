# Interrogation Techniques

How to extract implicit requirements from a document by questioning every sentence that is not a plain description of the task.

The method rests on one observation: **authors of briefs are not writing for you. They are writing against the last ten submissions that disappointed them.** Every instruction, caveat, reassurance and aside is a reaction to something that went wrong before. If you can reconstruct what went wrong, you know what they are checking for now.

The examples below are drawn from several document types — a hiring take-home, a freelance client brief, an internal PRD, an RFP, a grant call, a job post — because the questions are the same across all of them and the answers are not. If every example you can think of comes from one kind of document, you have learned the case rather than the method.

## First, sort the sentences

Read the document once and tag each sentence as one of:

- **Task description** — what the thing should do. ("Agents can insert a saved reply from the composer." "Revenue, orders and AOV by day/week/month.") These feed Phase 1. Skip them here — but see "Audit the explicit requirements for defects" below; task sentences are exempt from the nine questions, not from scrutiny.
- **Meta** — about the exercise, the process, the submission, the evaluator, or the reader. ("What we care about is how you reason." "I'm not technical, please don't send me a list of frameworks." "Please review and leave comments inline.") Interrogate every one.
- **Logistics** — where, when, how to send. Mostly Phase 1, but check for buried meta ("that's your whole submission" implies self-containment; "I'll pick someone by end of this week" implies a timing test).
- **Boilerplate** — greetings, legal, thanks. Usually skip, but a warm opener on an otherwise clinical document tells you about the persona.

Meta-sentences are typically 20–40% of a take-home brief, 10–20% of a job post or client brief, and 5–10% of a PRD or RFP. If you find far fewer than that, you are tagging too many as task description. Re-read.

## The nine questions

Ask each of a meta-sentence. Not every question yields something for every sentence; usually two or three do. Write down what you find with the quote attached.

### 1. Why is this sentence here?

What previous submission caused the author to add it? Instructions are scar tissue.

- *Client brief:* "We tried a freelancer last year who built something in Looker Studio that broke every time Shopify changed something and then he stopped answering messages." → Two scars: fragility and abandonment. The post that follows will grade durability and reachability above everything else, whatever the feature list says.
- *Take-home:* "Commit as you go. Your real history is more useful to us than one squashed commit." → Someone sent one squashed commit and the evaluators could not see the process. They now grade on history.
- *PRD:* "The panel should build on the new composer, not the old one." → A previous feature was built on the old thing and had to be migrated. Building on the old composer, however expedient, is a known failure mode.
- *RFP:* "Responses that exceed the page limit will not be evaluated." → Someone sent forty pages. The limit is now a filter, not a guideline.

### 2. Is this a rubric line in disguise?

Any sentence of the form "we care about / we're interested in / we're looking for / what matters to us / what I actually need / we want to see" is a criterion stated as a value. Rewrite it as a rubric row.

- *Client brief:* "So what I actually need is something that keeps working, and someone who will tell me if it's going to break." → Two criteria: *durability* and *proactive communication*. The phrase "what I actually need" marks this as the real brief; the bulleted feature list above it is the vehicle.
- *Take-home:* "What we care about is how you reason." → Criterion: *quality and visibility of reasoning.* The word "how" makes it process, not conclusions.
- *Grant call:* "We prioritise proposals that demonstrate community co-design." → Criterion: *evidence of co-design in the method.* Not a preference — a scored line, and probably a veto if absent.
- *Job post:* "We're looking for someone who can own a problem end to end." → Criterion: *evidence of ownership*, which means the cover note should contain a story with a beginning, a decision, and an outcome.

### 3. Permission or test?

Permissions in a brief are almost always also tests. The author is telling you something is allowed *because they intend to look at how you use it.*

- *Client brief:* "Honestly I don't care what it's built with." → Permission: any stack. Test: whether you *stop talking about the stack*. A proposal that spends a paragraph on tools has failed a test the client told you about.
- *Take-home:* "Use AI. We expect it." → Permission: you may. Test: your AI use will be examined, and the artifacts of it will be read.
- *PRD:* "Anyone can create a personal reply." → Permission for a permissive model. Test: whether you notice this has no definition of who is a "manager" and so no permissions model at all.
- *RFP:* "Bidders may propose alternative approaches." → Permission to deviate. Test: whether you also answer the approach as specified, because evaluators score against the original.

### 4. What does failing this look like?

If you can picture the failing submission concretely, you have a criterion. Write the failing picture down; it becomes the anti-pattern in the evidence plan.

- *PRD:* "Success metrics: TBD — Priya to confirm." → Failing: an estimate that prices the six requirements and never mentions the first-response-time number sitting in the Background section. The PM reads it and thinks, "they didn't read the first paragraph."
- *Client brief:* "Tell me what you'd build, roughly how long, and what you'd need from me to get started." → Failing: a proposal organized around the freelancer's credentials, with the three questions answered somewhere in the middle, out of order, or not at all.
- *Take-home:* "Deciding what fits in the time is part of the exercise." → Failing: going over the timebox, or finishing early without saying what was cut, or cutting the core flow to keep the nice-to-have.
- *Grant call:* "Describe measurable outcomes." → Failing: outcomes described as activities ("we will run twelve workshops") rather than changes ("participants' X will improve by Y, measured by Z").

### 5. Does it mandate an artifact? Then what must the artifact contain to count?

This question catches the most dangerous class of implicit requirement: **required-to-exist events.** When a document says "include a file with these sections" or "your proposal should cover these questions," every section is a claim that the thing it names will have happened.

- *Take-home:* "At the top [of PROMPTS.md], add a few lines covering … the moments where the AI got something wrong, and the places where you changed direction." → The headings *are* the rubric. The evaluator expects you to have caught errors and overridden the tool. A submission where neither happened has two empty headings, which is a failed criterion visible from across the room.
- *Client brief:* "what you'd need from me to get started" → You are expected to produce a specific access list. An experienced bidder's list (store collaborator access, ad-account read permissions, a read-only API key, the current spreadsheet) proves experience without claiming it; "your credentials" proves the opposite.
- *PRD:* "Open questions" section with four items, and "We'll go through open questions in Thursday's sync." → The evaluator expects you to arrive with a position on each, not to discover them on Thursday.
- *RFP:* "Section 4: Past performance (three references)." → Three references that match *this* scope, with contactable names. Two, or three generic ones, fails a scored section.

Rule: for every mandated heading, ask "what would make this section strong?" and then "will that thing exist by the time I write it?" If not, schedule it.

### 6. Does it preview a future interaction?

Sentences about what happens after submission tell you what will be examined most closely, because the author is committing to discuss it.

- *Take-home:* "Expect questions about your decisions and your prompts." → Decisions and prompts will be read line by line. Nobody plans an interview around a transcript they skimmed.
- *PRD:* "Eng estimate requested by: Jan 9" followed by "Need a call by Jan 10" on the dependency. → The estimate is an input to the dependency decision, so it must already contain the dependency analysis; "let's see on the 10th" is a failed estimate.
- *Client brief:* "I'll pick someone by end of this week." → There is no second round. Everything must be in the first message, and the message must arrive before the decision.
- *RFP:* "Shortlisted bidders will be invited to present." → The written bid is a filter; the presentation is the confirmation. Write the bid to survive a filter.

### 7. Is it a reassurance?

Reassurances name the anxiety the author expects you to have. **That anxiety is usually what they are grading at a deeper level**, because they are reassuring you that the surface version does not matter — which means the deeper version does.

- *Take-home:* "We don't have a hidden checklist of right answers." → Reassurance about *correctness*. Translation: there is no correctness rubric, so what remains is a *reasoning* rubric.
- *Client brief:* "Honestly I don't care what it's built with." → Reassurance about *stack*. Translation: the stack is not graded, so stop justifying it and spend the words on durability.
- *Job post:* "No prior experience with Rust needed." → Reassurance about *qualification*. Translation: they expect to teach Rust, so they are grading learnability and attitude; a cover note that over-claims Rust reads as not listening.
- *PRD:* "a small change in the customer serializer" → Reassurance about *effort*. Translation: the PM has pre-sized it; if it is not small, saying so early is graded, and discovering it late is a failure.

### 8. Does it hand you a decision?

Any sentence of the form "up to you / your call / we leave this to you / TBD / make the decision you'd make" is delegating a decision **and announcing that the decision will be reviewed.** The decision is rarely graded on outcome; it is graded on whether you noticed it was a decision, what alternatives you considered, and whether you wrote down why.

- *PRD:* "Should inserting a reply replace the composer contents or append? (Marco leans append.)" → A decision with a stated lean. The evaluator wants a recommendation *with an engineering cost*, not agreement with Marco and not a counter-opinion without reasons.
- *Take-home:* "How you do that is up to you." → The evaluator will look for whether you considered the alternatives (seed data vs. admin UI vs. task vs. config) and picked one with a reason tied to the brief's own hints.
- *Client brief:* "I don't care what it's built with." → Also a delegation: you choose, and the choice will be judged by whether it serves the thing they do care about (durability).
- *Grant call:* "Applicants may propose their own evaluation framework." → The framework you propose is itself scored; a weak one signals you do not understand what success would look like.

### 9. Does it warn that the ground is unstable?

"Existing codebase", "we don't promise it runs", "legacy", "inherited", "rough edges", "the data is messy", "stakeholders have different views" — these are planted-obstacle warnings. The obstacle exists. The test has three parts: notice it, handle it proportionately (fix or work around, not rewrite), and **report it** (what you found, what you did, why).

- *Take-home:* "We don't promise that everything runs cleanly out of the box. If you run into something that's broken, fix it or work around it, and tell us what you found." → At least one deliberate break. Grade: found it, fixed proportionately, wrote a note.
- *PRD:* "If the composer refactor slips, we either block or build against the old composer and migrate." → The dependency *will* be at risk. Grade: did you design so a slip costs days, not the beta.
- *Client brief:* "Every Monday I spend 4 hours pulling numbers from Shopify, our ad accounts (Meta + Google) and Klaviyo into a Google Sheet." → The unstable ground is attribution: those four sources will not agree with each other, and the client will notice on the first Monday. Grade: did you warn them before they found out.
- *RFP:* "The incumbent vendor's documentation is incomplete." → Transition risk. Grade: did your plan include discovery time and a knowledge-transfer approach.

## Cross-sentence techniques

After the per-sentence pass, run these across the whole document.

### Count the imperatives aimed at communication

Tally every "tell us", "write it down", "explain", "note", "walk us through", "describe", "flag", "show me". Then tally the build imperatives ("implement", "add", "build", "integrate"). In a document that grades process or communication, the first group rivals or exceeds the second. In a pure spec it is near zero. The ratio is a fast indicator of where the weight sits.

### Trace the required artifacts back to criteria

List every mandated artifact or section. For each, ask which criterion it serves. If an artifact serves no stated criterion, you have missed an implicit one. A session export serves no feature requirement — it exists to grade how the tool was directed. A "what you'd need from me" section serves no deliverable — it exists to grade experience. A "risks" section in an RFP response serves no scored requirement — it exists because committees distrust bids that claim no risk.

### Look for what the submitter would naturally optimize that the document never mentions

Code quality, test coverage, UI polish, performance, completeness, cleverness, stack choice, visual design, breadth of portfolio. If the document is silent on them, they are at most a tiebreaker. Submitters who spend their budget here are optimizing an ungraded axis. Say so explicitly in the output — it is the most common and most expensive misallocation, and it is usually the thing the submitter is best at.

### Audit the explicit requirements for defects

Task-description sentences are not exempt from scrutiny; they are exempt only from the nine questions. Read each stated requirement against reality and against its neighbors:

- **Conflicts with the platform or environment.** A keyboard shortcut that collides with a browser default (Cmd/Ctrl+Shift+R is hard-reload). A deadline on a public holiday. A data field the named source does not expose.
- **Conflicts with another requirement.** "One code per order" alongside a flow that lets you add a second. "Text only" alongside a placeholder that will hold a URL. "Fixed price" alongside "tell me whenever it's going to break" with no end date.
- **Conflicts with the stated goal.** A usage counter offered as the measurement for a time-based metric. A "simple" build that needs four live integrations.
- **Silently under-specified.** "Manager" with no definition of who is a manager. "Filled from the ticket" with no rule for a missing value. "ROAS per channel" with no statement of whose revenue number is the truth.

A defect in a stated requirement is either a planted trap or an honest mistake. Either way, the evaluator notices who notices. Flag each with a one-line fix. This is a reliable differentiator because most submitters treat the numbered list as settled.

### Find the tension pairs

Deliberate tensions: timebox vs. completeness; "brief not spec" vs. "tell us what you decided"; "any stack" vs. "it must keep working"; "simple" vs. four integrations; "fixed fee" vs. open-ended support; "focus on your role" vs. "do as much of the other side as you can". Each tension is placed (or left) to watch how you resolve it. The submission must visibly resolve each one *and say how.* Silent resolution looks like not noticing.

### Read the voice

A warm, conversational brief ("Thanks for taking this on!", "Hi there") is written by someone who wants to work with a person, not a résumé. Match it: a clinical, over-formal submission to a warm brief reads as not having read it. A terse, bulleted PRD wants a terse, bulleted review. A numbered RFP wants a numbered compliance response. Register mismatch is noticed before content is.

## Two worked micro-examples

### A client-brief sentence

*"I'm not technical. Please don't send me a list of frameworks. Tell me what you'd build, roughly how long, and what you'd need from me to get started."*

| Question | Finding |
|---|---|
| Why here? | Previous proposals were acronym lists the client could not evaluate. |
| Rubric in disguise? | Yes: plain-language communication is graded; structure in their order is graded. |
| Permission or test? | Permission to skip technical detail; test of whether you can explain an outcome without it. |
| Failing looks like? | A proposal opening with "I am a full-stack developer with 8 years in React, Node, Postgres…" |
| Mandates artifact? | Yes: three answers, in this order. "What you'd need from me" is a required-to-exist access list. |
| Previews interaction? | Implicitly — a non-technical client will manage the project in the same plain language. |
| Reassurance? | "I'm not technical" reassures you that depth is not needed; it means clarity is graded instead. |
| Hands you a decision? | Yes: how to describe the build is yours, and it will be judged on whether a non-technical reader could repeat it. |
| Unstable ground? | No. |

Result: implicit requirement *"the proposal itself is the communication test — three headings in their order, outcome-language, no stack list, and an access list specific enough to prove experience"*, confidence **Stated**, weight high, surface = proposal body, proof moment = three labeled sections in the client's order, anti-pattern = credentials-first opener.

### A PRD sentence

*"Success metrics: TBD — Priya to confirm with Support leadership."*

| Question | Finding |
|---|---|
| Why here? | The PM has a number from leadership but has not yet put it in the doc; the template demanded a section. |
| Rubric in disguise? | Inverted: the *absence* is the rubric. The evaluator who finds the metric in the Background section ("get FRT back under 2h30 by end of Q1 without adding headcount") is the evaluator who read the doc. |
| Permission or test? | Test: whether you treat TBD as "not my problem" or as "the most important line in the document." |
| Failing looks like? | An estimate that prices R1–R6 and never mentions first-response time. |
| Mandates artifact? | Not directly — but the estimate is the artifact, and it must contain the metric and how the feature will be measured against it. |
| Previews interaction? | Yes, indirectly: leadership will ask in April whether the number moved. |
| Reassurance? | "Priya to confirm" reassures you that it is the PM's job; it is, but the eng lead who hands her the draft wins. |
| Hands you a decision? | Yes: how to instrument the feature so impact on the metric is attributable. The listed usage counter cannot do that. |
| Unstable ground? | Yes: the metric itself may be only partly movable by this feature (queue time vs. handle time). Raising that early is graded. |

Result: implicit requirement *"name the real success metric, state that the listed goals are instruments for it, and price the instrumentation that attributes impact"*, confidence **Strong**, weight highest, surface = first paragraph of the estimate, proof moment = the FRT number in the opening line with a measurement plan, anti-pattern = "metrics are the PM's section."

Two documents, two different vetoes, one method.
