---
kind: reviewer-lens
version: 1
written: <YYYY-MM-DD>
document: "<document title>"
archetype: <technical-take-home | interview-exercise | job-application | client-brief | prd | internal-ticket | rfp | grant | academic-assignment | hackathon | design-brief | hybrid>
brief: brief.md
context: context.md
veto: "<the one-sentence veto, verbatim from below>"
first_surface: <the first thing the reviewer opens>
---

<!-- The front-matter is what the audit skill anchors on; the headings below are what it reads by name. Keep both as they are. In the chat reply, show the body from the title down; the front-matter is for the file. -->

# Reviewer Lens — <document title>

<!-- LEAD: scannable in ~2 minutes, ~500–800 words total. This may be all the user reads. Budgets are in SKILL.md → Output. -->

**Doc type / reviewer / decision:** <archetype> · <who reads it, how many, how long each> · <hire / interview / award / approve>
**Filter or confirmation:** <which — one clause on why it matters here>

**Veto criterion:** <one sentence a reviewer could put in a rejection email.> <One sentence of evidence: the surfaces that point at it.>

**Reviewer's mental model:**
<2–4 sentences, first person. What they've seen too often, what makes them stop reading, what makes them forward this, the one thing they can't tell from a résumé. One line per audience if two grade differently.>

## Implicit requirements
<4–7 bullets, one line each. Lead with the one behind the veto.>
- <requirement> — "<one quote>" — **Stated | Strong | Inferred | Speculative**

## Rubric
| Criterion | Weight | Conf. | Failing looks like |
|---|---|---|---|
| <phrase> | <%> | <tier> | <one image, under 15 words> |

**Not graded (or tiebreaker only):** <what the submitter would naturally optimize that the document never mentions>
**Differentiators:** <2–3, one clause each>

## What to show
| Criterion | Surface | Proof moment | Anti-pattern |
|---|---|---|---|
| <criterion> | <where the reviewer looks> | <one quotable thing to create, under 30 words> | <under 12 words> |

**Required-to-exist events:**
- "<mandated heading>" — <what must happen> — <when>

**Simulated verdict (if the plan is followed):** <one line in the reviewer's voice>
**Simulated verdict (if the user's current approach is followed, when known):** <one line>

---

<!-- DETAIL: supports the lead. As long as the document warrants; the user reads it after deciding the lead is right. -->

## Explicit requirements
<Compressed. Group related items into one line. Quote only where the wording's force is the point. The reader has read the document.>
- [MUST] <grouped requirement> — "<quote only if needed>"
- [SHOULD] …
- [MAY] …

## Traps
- <planted obstacle / embedded filter / over-delivery trap / graded-but-looks-optional / tone trap / defect in a stated requirement>

## Decisions to make / questions to ask
<Every gap the document leaves open, ordered by stakes. For "decide, don't ask" documents: recommended call + one-line rationale the user could write verbatim. For documents where asking is possible: mark each Ask or Assume.>
- <decision> → <recommended call> — <rationale>

## Recommended shape
<Include when the user asked how to approach, frame, structure or write the submission. Sections in the reviewer's reading order; share proportional to rubric weight; the proof moment each section carries.>
| Section (in reading order) | Share | Carries |
|---|---|---|
| <section> | <~N words / hours / paragraphs> | <proof moment> |

## Pre-submission check
- [ ] Every required artifact present and populated with what its name promises
- [ ] Veto-criterion proof is on the first surface the reviewer reads
- [ ] Every primary criterion has at least one quotable proof moment
- [ ] <document-specific checks>

**Sequencing** (only when required-to-exist events need scheduling): <before starting / first third / halfway / last third / after work — one line each>

**Saved to:** `docs/reviewer-requirements/` — brief.md · context.md · lens.md <(and `.gitignore` updated, when in a repo)>

---

<!-- POST-MORTEM: a separate file, calibration.md, written only in post-mortem mode. Not part of the Lens. -->

# Calibration — <document title>

```yaml
kind: reviewer-calibration
lens_version: <n>
audit_verdict: <ship | fix-first | not-ready | none>
result: <rejected | accepted | revise | no-response>
written: <YYYY-MM-DD>
```

## 1. What the feedback graded on
| Feedback sentence | Maps to (rubric row / trap / event) | In the Lens? | Lens weight · confidence |
|---|---|---|---|
| "<quote>" | <criterion> | yes / no / partly | <%> · <tier> |

## 2. Where the Lens was wrong
<One line per miss: the brief sentence that should have produced it, and the interrogation question that would have caught it. If the Lens had it right and the submission failed it anyway, say that — the miss is then in execution or in the audit, not the analysis.>

## 3. What the audit let through
<If an audit ran: each criterion it passed that the reviewer failed, and the evidence it accepted that the reviewer did not. If no audit ran: "no audit".>

## 4. Next time
- <one-line instruction to the next analysis>
- <…>

**Praise in the feedback:** <what was praised, and what its weight turned out to be>
