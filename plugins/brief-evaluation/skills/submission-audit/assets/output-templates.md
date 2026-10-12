# Output Template

One file: `docs/submission-audit/audit.md`. Every mode writes it — full, partial and re-audit — and each run overwrites it (a re-audit reads it first; see SKILL.md → Modes). Keep the section headings exactly as written; the post-mortem and the next re-audit read them by name. Front-matter is YAML between `---` lines.

No length cap: as long as the submission's actual gaps and evidence make it, never longer. Show what is wrong in full; list what is right by ID.

**IDs.** Lens IDs are reused as they are: `E#` explicit requirements, `I#` implicit requirements, `P#` package items. The audit assigns its own: `C#` scorecard criteria (Matrix order), `T#` traps, `R#` required-to-exist events, `D#` deal makers, `G#` gaps. Every gap names the IDs it comes `From`, so each fix traces back to a finding and each finding to the Lens.

**References.** Every finding carries two:
- **Evidence** — where in the submission it is proven or missing: `SUBMISSION.md §Decisions L12–18` · `commit 38d04cd` · `PROMPTS.md turn 14` · `reply.md ¶1` · `budget.xlsx Sheet1!C14` · `slide 3` · `video 02:40` · `—` when absent, with where the evaluator looks for it.
- **Lens ref** — where the Lens asked for it: `Lens E4` · `Lens I1` · `Lens P2` · `Matrix: <criterion>` · `Deal breakers: "<first words of the trap>"` · `Required events: "<heading>"`. Add the brief when the exact wording matters: `brief §Deliverables` or `msg 8`.

---

## Full mode (and re-audit)

```markdown
---
kind: evaluator-audit
mode: full
round: 1
written: <YYYY-MM-DD>
lens_path: docs/evaluator-expectations/expectations.md
lens_version: <n>
lens_derived_at_audit: false
independence: fresh-session | subagent | same-context
submission_form: <from the Lens, or what was actually submitted if different>
submission_ref: "<git <hash> (<n> commits, <first>..<last>) | files: a.md, b.xlsx, … | message draft, <n> words>"
verdict: ship | fix-first | not-ready
weighted_score: <0–100>
veto_status: strong | adequate | weak | missing
veto_on_first_surface: true | false
ai_disclosure: fits | mismatch | contradicted | absent | n-a
---

# Submission Audit — <document title>

## 1. Verdict

**Verdict:** <ship | fix-first | not-ready> · score <n>/100 · veto <status> — <evidence ref, or "absent">
**Why:** <the rule from verdict-rules.md that decided it, and the finding IDs behind it>
**First pass:** "<one line in the evaluator's voice after `<first_surface>` only — written before anything else was opened, never edited>" · veto proof visible there: yes — <ref> | no
**Final:** "<one line in the evaluator's voice after the full read>"
**Against the Lens:** <matches "plan followed" | matches "current approach" | neither> — <one line why>
**Must do:** G1, G2, G3 · **If time:** G4–G<n> → §8
**Audited:** <submission_ref> · Lens v<n> · <independence>

## 2. Scorecard

| # | Criterion | Weight | Strength | Contrib. | Evidence | Lens ref |
|---|---|---|---|---|---|---|
| C1 | <criterion> | <%> | Strong / Adequate / Weak / Missing | <weight × factor> | <ref, or "—"> | Matrix: <criterion> |
| | **Weighted score** | | | **<n>** | | |

**Gates:** core function <pass/fail — ref> · format limits <pass/fail — measured vs limit, ref> · Critical requirements <n> unmet → §4 · mandatory package items <n> absent → §5

## 3. Deal breakers

**Veto:** <veto sentence from the Lens> — **<strength>** — <evidence ref> — Lens: Deal breakers · Matrix: <criterion>
<One sentence: what the evaluator concludes from it.>

| # | Trap | Status | Evidence | Lens ref |
|---|---|---|---|---|
| T1 | <trap, short> | avoided / **tripped** / n-a | <ref> | Deal breakers: "<first words>" |

<Blocks-review mechanics, the planted obstacle (noticed · handled · reported) and the sanitisation check go in this table as their own rows.>

## 4. Requirements

**Explicit:** <n>/<n> met · **Implicit:** <n>/<n> met · **Critical unmet:** <n> · **High unmet:** <n>

| ID | Requirement | Severity | Status | Evidence | Lens ref |
|---|---|---|---|---|---|
| E1 | <short, from the Lens> | Critical | **not met** / partial | <ref, or measured value vs limit> | Lens E1 · <brief §… / msg n> |
| I3 | <short> | High · Strong | partial | <ref> | Lens I3 |

**Met:** E2, E3, E5–E9, I1, I2
<Implicit rows show severity and Lens confidence; at Inferred/Speculative confidence a miss is advisory only.>

## 5. Submission package

| ID | Item | State | Evidence | What is missing |
|---|---|---|---|---|
| P1 | <item from the Lens> | present / **thin** / **absent** / unverified | <ref> | <from the Lens's "must contain", or "—"> |

| # | Required event | Status | Evidence | Cross-check |
|---|---|---|---|---|
| R1 | "<heading or event>" | Present / **Thin** / **Empty** | <ref and the specific instance> | <corroborating trace with ref, or "no trace"> |

## 6. AI disclosure

| | |
|---|---|
| **Evaluator** | <n>% — <stance> · AI use <graded / candidate veto / tiebreaker / forbidden / silent> — Lens §6 |
| **Submission says** | "<quote>" — <ref> · or "nothing" |
| **Traces show** | <direction ratio, commit pattern, style signals> — <refs> · or "no traces available" |
| **Fit** | fits / mismatch / contradicted / absent / n-a — <one line why> |
| **Fix** | <honest disclosure sentence stating the real share, or a process change> → G<n> |

## 7. Deal makers

| # | Differentiator or decision | Status | Evidence |
|---|---|---|---|
| D1 | <from the Lens> | present / recorded without rationale / **absent** | <ref> |

## 8. Gaps and fixes

| ID | Class | From | Missing | Fix | Where | Retrofit | Effort | Done |
|---|---|---|---|---|---|---|---|---|
| G1 | <blocks-review / veto / gate / …> | <C2, E1, R3, T1 …> | <one line, and where the evaluator notices> | <the concrete sentence, section, commit or turn> | <surface § section> · first surface: y/n | add / make-it-happen-then-record / disclose | <min> | [ ] |

**Closed in earlier rounds:** <re-audit only — same columns, Done ticked, with the round it closed in>

## 9. Notes

<Each line only when it has content; omit the section when all three are empty.>
- **Analysis gaps:** <what the brief grades that the Lens missed, or a Lens assumption the submission contradicts — with brief ref; say if it would change the veto>
- **Could not verify:** <surface — what the evaluator will see there that this audit could not>
- **Since last round:** <round 2+: closed <n> · open <n> · new <n> · score <before> → <after> · verdict <before> → <after>>

---

## Appendix. Reading order and weak evidence

**Reading order:** 1. `<first_surface>` — <why first> · 2. <surface> · 3. …

| Surface | Present as | Readable |
|---|---|---|
| <e.g. notes> | `SUBMISSION.md` (1,240 words) | yes |
| <e.g. video> | link in SUBMISSION.md L4 | **unverified** |

**Rejected evidence** (Weak or Missing criteria only):
- **C2 <criterion>** — wanted: <proof moment from the Lens>. Found: <candidate> — <ref> — <why it did not count: echo / thin / buried / anti-pattern>.
```

---

## Partial mode (halfway checkpoint)

The same file, shorter. No verdict, no score, no scorecard. The next full run overwrites it.

```markdown
---
kind: evaluator-audit
mode: partial
round: 0
written: <YYYY-MM-DD>
lens_path: docs/evaluator-expectations/expectations.md
lens_version: <n>
independence: <…>
submission_ref: "<…>"
---

# Checkpoint — <document title>

## 1. Status

**Where you are:** <one line: what exists so far, with refs>
**Veto proof visible yet:** yes — <ref> | not yet — <what it will take>
**Time left:** <from the Lens's timebox and the user's context, when known>

## 2. Required events

| # | Event | Happened? | Evidence | If not: when, and what making it happen looks like |
|---|---|---|---|---|
| R1 | "<heading>" | yes / thin / not yet | <ref or —> | <"next 30 min: decide the cut list and commit it as a note"> |

## 3. Critical requirements

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| E1 | <from the Lens> | on track / at risk / not started | <ref or —> |

## 4. Do next

1. <the event or requirement most at risk, and the action> — R<n> / E<n>
2. <…>
3. <…>

**Reading order and surfaces so far:** <one line>
**Re-run a full audit before submitting.**
```
