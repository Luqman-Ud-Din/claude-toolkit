---
kind: evaluator-lens
version: 1
written: <YYYY-MM-DD>
document: "<document title, or 'Chat with <name>, <platform>'>"
archetype: <technical-take-home | interview-exercise | job-application | client-brief | prd | internal-ticket | rfp | grant | academic-assignment | hackathon | design-brief | message-thread | hybrid>
brief: brief.md
veto: "<the one-sentence veto, verbatim from Deal breakers>"
first_surface: <the first thing the evaluator opens or reads>
submission_form: <message reply | proposal | repo + README | video | cover note | form | deck | hybrid>
ai_receptiveness: <0–100>
---

<!-- The front-matter is what the audit skill anchors on; the seven section headings below are what it reads by name. Keep both as they are. In the chat reply, show the body from the title down; the front-matter is for the file. -->
<!-- No length cap: as long as the input's real requirements make it, never longer. Every line is a claim with a reference or a labeled inference. Reference format: §<section or heading> or msg <n> — <speaker>, plus a short "quote" when the wording's force matters. -->

# Evaluator Lens — <document title>

## 1. Description

<Preferably 7–8 lines, plain language: what is being asked, by whom, for what decision, by when, in what form. Each sentence carries an inline reference. A reader who reads only this knows what the task is.>

## 2. Context understanding

- **Type / archetype:** <archetype; hybrid notes if any> — <reference>
- **Evaluator:** <who judges, how many submissions they compare, how long each gets>
- **Decision:** <hire / interview / award / fund / approve / merge / reply> · **Filter or confirmation:** <which, one clause on why it matters here>
- **Constraints:** <time, budget, stack, platform, length, format — each with reference>
- **Stakes and tone:** <the voice of the input and what it says about the evaluator>
- **User's context:** <role, deadline, prior attempts or rejections, what the user has already said or promised in the thread — or "none given">

## 3. Evaluator intent

**In their words (first person):** <2–4 sentences. What they've seen too often, what makes them stop reading, what makes them forward this, what they're afraid of approving by mistake. One paragraph per audience if two grade differently.>

**What they actually want:** <the underlying goal behind the stated task, with the evidence: repetition count, surfaces, scar-tissue sentences>

**Weightiest themes:** <theme — ×N mentions across M surfaces — reference> (one line each, heaviest first)

**Not graded (or tiebreaker only):** <what the submitter would naturally optimize that the input never mentions>

## 4. Explicit requirements

<Ordered by severity, Critical first. Group related items into one row.>

| # | Requirement | Reference | Impact if missed | Severity |
|---|---|---|---|---|
| E1 | <short description> | <§section / msg n — "quote" when needed> | <one clause> | Critical / High / Medium / Low |

## 5. Implicit requirements

<Lead with the one behind the veto.>

| # | Requirement | Reference | Impact if missed | Severity | Confidence |
|---|---|---|---|---|---|
| I1 | <short description> | <"quote" — §section / msg n> | <one clause> | Critical / High / Medium / Low | Stated / Strong / Inferred / Speculative |

## 6. AI receptiveness

| | |
|---|---|
| **Receptiveness** | <0–100>% — <Expects / Welcomes / Tolerates / Wary / Forbids / No signal> |
| **Is AI use examined?** | <graded / candidate veto / tiebreaker / forbidden / silent> — <reference> |
| **Recommended AI involvement** | <~N% of the work> — <which parts should visibly stay human> |
| **If asked "how much AI did you use?"** | <band, e.g. "~60%"> — "<the sentence to say it with, framed around the decisions you made>". State your real share; if it is far from this band, change how you work, not what you say. |
| **Evidence** | <quotes and signals, with references; or "no signal — defaulting to the <archetype> norm"> |
| **Confidence** | <0–100>% — <one line on why> |

## 7. Understanding

### Matrix

| Criterion | Weight | Conf. | Failing looks like |
|---|---|---|---|
| <criterion> | <%> | <tier> | <one concrete image> |

**Simulated verdict (if the plan is followed):** <one line in the evaluator's voice>
**Simulated verdict (if the user's current approach is followed, when known):** <one line>

### Deal breakers

**Veto criterion:** <one sentence the evaluator could put in a rejection email.> <The evidence: the surfaces and references that point at it.>

- <trap — planted obstacle / embedded filter / blocks-review mechanic / over-delivery / tone / defect in a stated requirement> — <reference> — <how to avoid it>

### Deal makers

**Differentiators:**
- <what separates a pass from a strong pass> — <reference>

**Decisions to make / questions to ask** (ordered by stakes; Ask or Assume where asking is possible):
- <decision> → <recommended call> — <rationale the user could write verbatim>

### Submission package

<What the submission should include — a list, not the submission. In the evaluator's reading order.>

| # | Item | Form | Must contain |
|---|---|---|---|
| P1 | <e.g. reply message, proposal, README, video, cover note> | <format, length or limit> | <what it must show, with the criterion it proves> |

**Proof per criterion:**

| Criterion | Surface | Proof moment | Anti-pattern |
|---|---|---|---|
| <criterion> | <package item> | <one quotable thing to create> | <what the failing version looks like> |

**Required-to-exist events:**
- "<mandated heading or field>" — <what must actually happen> — <when>

**Recommended shape** (when the user asked how to approach or structure the work):

| Section (in reading order) | Share | Carries |
|---|---|---|
| <section> | <~N words / hours / paragraphs> | <proof moment> |

**Pre-submission check:**
- [ ] Every package item present and populated with what its name promises
- [ ] Veto-criterion proof is on the first surface the evaluator reads
- [ ] Every Critical and High requirement visibly met
- [ ] Every Matrix criterion has at least one quotable proof moment
- [ ] <input-specific checks>

**Saved to:** `docs/evaluator-expectations/` — expectations.md · brief.md <(and `.gitignore` updated, when in a repo)>

---

<!-- POST-MORTEM: a separate file, calibration.md, written only in post-mortem mode. Not part of the Lens. -->

# Calibration — <document title>

```yaml
kind: evaluator-calibration
lens_version: <n>
audit_verdict: <ship | fix-first | not-ready | none>
result: <rejected | accepted | revise | no-response>
written: <YYYY-MM-DD>
```

## 1. What the feedback graded on
| Feedback sentence | Maps to (Matrix row / deal breaker / event) | In the Lens? | Lens weight · confidence |
|---|---|---|---|
| "<quote>" | <criterion> | yes / no / partly | <%> · <tier> |

## 2. Where the Lens was wrong
<One line per miss: the input sentence that should have produced it, and the interrogation question that would have caught it. If the Lens had it right and the submission failed it anyway, say that — the miss is then in execution or in the audit, not the analysis.>

## 3. What the audit let through
<If an audit ran: each criterion it passed that the evaluator failed, and the evidence it accepted that the evaluator did not. If no audit ran: "no audit".>

## 4. Next time
- <one-line instruction to the next analysis>
- <…>

**Praise in the feedback:** <what was praised, and what its weight turned out to be>
**AI receptiveness, in hindsight:** <did the evaluator's reaction to AI match the estimate? the corrected %, if the feedback says>
