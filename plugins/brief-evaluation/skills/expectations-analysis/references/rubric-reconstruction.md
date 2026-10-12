# Rubric Reconstruction

How to turn the themes from Phase 3 into a weighted rubric with a single veto criterion. The goal is not to guess the evaluator's private spreadsheet exactly; it is to allocate the submitter's effort in the same proportions the evaluator allocates their attention.

## Step 1 — List candidate criteria

Start from the themes you clustered in Phase 3. Each theme becomes a candidate criterion. Phrase each as the evaluator would, as a quality of the submission, not as a task:

- Not "write a decision log" but "reasoning is visible and defended".
- Not "include a transcript" but "AI is directed, not followed".
- Not "finish in 3 hours" but "scope is judged well under constraint".

Typical candidate set for a technical take-home: reasoning visibility, AI direction, scoping/time judgment, obstacle handling, communication quality, functional correctness, code quality, design extensibility, role-appropriate depth. For a client brief: problem understanding, scope definition, reliability signals, relevant evidence, price fit, communication plan. For a PRD: success-metric alignment, scope respect, risk awareness, stakeholder coverage, phase-2 readiness. Prune to what the document actually supports.

## Step 2 — Score each criterion on evidence

For each candidate, record:

| Signal | How to measure |
|---|---|
| **Repetition count** | How many sentences encode it, across all phrasings |
| **Surface count** | How many distinct sections it appears in (instructions, deliverable spec, interview preview, FAQ, template headings) |
| **Mandated artifact** | Does a required file, heading, or field exist specifically to prove it? |
| **Future-interaction mention** | Will it be discussed after submission? |
| **Reassurance pointing at it** | Does a "don't worry about X" reveal that the deeper form of X is graded? |
| **Explicit "we care about"** | Is it stated as a value? |

## Step 3 — Assign weights

Weights are percentages summing to 100. The rule of thumb:

- A criterion with a mandated artifact **and** three or more repetitions **and** a future-interaction mention is a primary criterion. Primary criteria share 50–70% of the weight.
- A criterion with one or two repetitions and no artifact is secondary, 10–20% each.
- A criterion the document never mentions but the submitter would naturally optimize (code quality, polish, completeness) is a tiebreaker: 5–10%. State explicitly that it is a tiebreaker so the user does not over-invest.
- Functional correctness of the core flow is almost always a gate rather than a weighted criterion — it has to work or nothing else is read — but once it works, additional correctness earns little. Represent it as "gate" in the rubric and give it a modest weight.

Sanity check: if your weights put more than 30% on anything the document does not mention, you have reverted to the submitter's lens. Re-read the signals.

## Step 4 — Assign confidence

Each criterion gets a confidence tier, which tells the user how much to trust the weight:

- **Stated** — the document says it in so many words. ("What we care about is how you reason.")
- **Strong** — two or more independent signals converge (a repetition plus a mandated heading plus an interview preview). An evaluator, shown the inference, would nod.
- **Inferred** — one signal plus archetype knowledge. Probably right; hedge by making sure the proof moment is cheap.
- **Speculative** — plausible from persona alone. Do not plan around it; mention it so the user is not blindsided.

Confidence and weight are independent. A Speculative criterion can still be worth 10% if the archetype strongly suggests it; a Stated criterion can be worth 5% if it is stated once and never reinforced.

## Step 5 — Find the veto criterion

The veto criterion is the one whose failure rejects the submission regardless of everything else. It is not always the highest-weighted criterion, though it often is.

Candidates for veto, in rough order of frequency across document types:

1. **The most-repeated value-phrased criterion** ("how you reason", "how you direct", "communication", "judgment"). Evaluators who repeat a value five times will reject on it.
2. **A required-to-exist event with a mandated heading.** If a section must exist and would be empty, the evaluator sees the failure before reading anything else.
3. **A hard filter** in job posts and RFPs (mandatory skill, attention phrase, format compliance, budget ceiling).
4. **A tension the submission must visibly resolve** (timebox vs. completeness) when the document says resolving it "is part of the exercise".
5. **The archetype default**, used only when the document is thin and the count is inconclusive: human direction of the tool for AI-permitted technical work; problem understanding and trust for client briefs; success-metric alignment for PRDs; compliance for RFPs; priority alignment for grants. The default is a tiebreaker for the count, not a replacement for it.

To choose: ask "if a submission were excellent on everything but this, would the evaluator still reject?" The first criterion for which the answer is clearly yes is the veto. There is usually exactly one. If you find two, one is probably a gate (must work at all) and the other is the real veto (must show the graded quality).

Write the veto as a sentence an evaluator could say in a rejection email. Then check it against the document one more time: can you point at three or more places that support it? If you can only point at one, you have a differentiator, not a veto — or you have imported a veto from a different document.

## Step 6 — Name the differentiators

After the veto and the primary criteria, name two or three things that separate a pass from a strong pass. These are where surplus effort should go once the veto is covered. They are usually:

- Noticing more delegated decisions than the typical submission (the evaluator has a mental count).
- Proportionate handling of the planted obstacle, reported crisply.
- An extension-ready design that visibly anticipates the "we may extend this together" conversation.
- Matching the document's voice.
- For client briefs: restating the problem better than the client did.
- For PRDs: a risk the PM had not considered.

## Step 7 — Picture failure for each row

For every rubric row, write one line describing the failing submission. Concrete, not abstract. "Transcript is 'ok' / 'continue' / 'looks good' for 40 turns" rather than "insufficient AI direction." These lines become the anti-pattern column of the evidence plan and are the most useful thing in the output for a user reviewing their own draft.

## Worked example — an internal PRD under eng review

Document: a PRD for a "saved replies" feature in a support inbox. Background says first-response time has drifted from 2h10 to 3h40 while volume grew 30%, and leadership wants it "back under 2h30 by end of Q1 without adding headcount." The PRD lists three goals, three non-goals, six numbered requirements, four open questions, one dependency (a composer refactor landing mid-January, with a "need a call by Jan 10"), and "Success metrics: TBD." Eng lead is listed as TBD. The evaluator is asked for an estimate by Jan 9 and to "leave comments inline"; open questions go to Thursday's sync.

Signals found: the metric appears four ways in Background and nowhere in "Success metrics" (×4, one surface, plus a conspicuous absence); the composer dependency has its own risk entry and a dated decision (×3 across Dependencies, Risks, Timeline); open questions are listed and scheduled (×2); non-goals are explicit (×3 items, ×2 "for v1"); "simple" appears twice; "Eng lead: TBD" (×1); beta and GA dates are already fixed before the estimate is requested (×2). Architecture, test coverage, search sophistication: ×0.

| Criterion | Weight | Confidence | Failing looks like |
|---|---|---|---|
| Names the real success metric and prices how impact will be measured | 25% | Strong | Estimate prices the six requirements and never mentions first-response time |
| Estimate fits the fixed dates, or names the cut that makes it fit | 20% | Strong | One number, no assumptions, no cut list |
| Composer-dependency call made with information by Jan 10 | 15% | Stated | "Let's see where the refactor is on the 10th" |
| Positions with eng cost on all four open questions before Thursday | 15% | Stated | Arriving with "whatever design prefers" |
| Scope restraint: respects non-goals, leaves phase-2 seams without building them | 10% | Stated | Proposes folders, rich text, or an AI hook "while we're in there" |
| Risk register beyond the one the PM wrote | 10% | Inferred | Only the composer risk; placeholder leakage, undefined "manager", adoption unmentioned |
| Engagement form: inline comments, owns the TBD slot | 5% | Stated | A chat reply: "looks fine, ~4 weeks" |
| Six requirements work on the new composer at beta | Gate | Stated | Beta agents can't insert; or panel is on the old composer |

**Veto:** the unstated metric. "Success metrics: TBD" is the hole; Background fills it. An estimate that is accurate, on time, and silent on first-response time tells the PM the evaluator did not read the first paragraph, and tells leadership — in April — that nobody can say whether the feature worked. Everything else on the table is additive; this one is not.

**Differentiators:** per-ticket insert events so impact on the metric can be attributed (the listed usage counter proves adoption, not time saved); a two-track estimate split by dependency so a refactor slip costs days, not the beta; raising the question of whether this feature alone can move a queue-dominated metric *before* leadership does.

Notice what the method did here: the PRD never says "we care about the metric." It is found by counting (four mentions in Background), by absence (an empty section with a template heading), and by the archetype (PRD authors have a number from above). The veto came from the document, not from a prior.

## Common mistakes in reconstruction

- **Weighting what the submitter is good at.** The rubric is the evaluator's, not the user's. If the user is a strong coder and the document never mentions code, code is still a tiebreaker.
- **Treating every mention as equal.** A mention in the deliverable template or the interview preview is worth more than a mention in the intro.
- **Missing the gate/veto distinction.** "It must work" is a gate. "It must show judgment" is a veto. Both reject, but the first is obvious to the submitter and the second is not; spend the output's attention on the second.
- **Splitting one criterion into many.** "Reasoning visible", "decisions documented", "trade-offs named" are one criterion with three proof moments. Merge, or the weights lose meaning.
- **Ignoring absence.** If a document is silent on something the archetype usually cares about, say so and downgrade it. Absence is information.
