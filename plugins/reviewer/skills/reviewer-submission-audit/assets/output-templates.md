# Output Templates

Five files in `docs/submission-audit/`. Keep headings exactly as written; downstream steps read them by name. Front-matter is YAML between `---` lines.

---

## 1. `audit-final.md` — the report

```markdown
---
kind: reviewer-audit
mode: full
round: 1
written: <YYYY-MM-DD>
lens_path: docs/reviewer-requirements/lens.md
lens_version: <n>
lens_derived_at_audit: false
independence: fresh-session | subagent | same-context
submission_ref: "<git <hash> (<n> commits, <first>..<last>) | files: a.md, b.xlsx, …>"
verdict: ship | fix-first | not-ready
weighted_score: <0–100>
veto_status: strong | adequate | weak | missing
veto_on_first_surface: true | false
first_pass: "<one line in the reviewer's voice, written after the first surface only>"
---

# Submission Audit — <document title>

**Verdict:** <ship | fix-first | not-ready> · score <n>/100 · veto <status> <(address | absent)>
**Lens:** v<n> · <archetype> · first surface: `<first_surface>`
**Audited:** <submission_ref> · <independence>

## First pass
<The reviewer opens `<first_surface>`. One or two sentences in their voice: what they now believe, whether they read on. Then:>
**Veto proof visible here:** yes — <address> | no

## Scorecard
| Criterion | Weight | Strength | Factor | Contrib. | Where |
|---|---|---|---|---|---|
| <criterion> | <%> | <S/A/W/M> | <f> | <w×f> | <address or "—"> |
| **Weighted score** | | | | **<n>** | |

**Gates:** <core function: pass/fail — address> · <format limits: pass/fail — measured value vs limit> · <mandatory artifacts: pass/fail — missing: …>

## Veto criterion
**<veto sentence from the Lens>**
Status: <strength> — <the best evidence with its address, or what is there instead>. <One sentence: what the reviewer concludes from this.>

## Required-to-exist events
| Event | Status | Evidence | Cross-check |
|---|---|---|---|
| "<heading>" | Present / Thin / Empty | <address and the specific instance, or "—"> | <corroborating trace, or "no trace"> |

## Gates, mechanics, traps
- **Explicit requirements:** <n>/<n> present. Missing: <list or none>.
- **Blocks-review mechanics:** <each: ok / TRIPPED — detail>
- **Traps:** <each from the Lens: avoided / tripped / n-a — address>
- **Obstacle:** <noticed / handled / reported — each yes/no with address>
- **Sanitisation check:** <transcript vs commits agree / disagree — detail / n-a>

## Analysis gaps
<Things the brief grades that the Lens omitted, or Lens assumptions the submission contradicts. Each one line with the brief sentence. "None found" if none. If any would change the veto: say so and recommend re-running the analysis.>

## Verdicts in the reviewer's voice
**First pass (unchanged from above):** "<…>"
**Final:** "<…>"
**Against the Lens's predictions:** <matches "plan followed" / matches "current approach" / neither — one line why>

## Top fixes
<The must-do set, from gaps.md, numbered, one line each: class · what · where · effort. Point at gaps.md for the rest.>

## Could not verify
<Surfaces listed as unverified in the inventory, and what the reviewer will see there that this audit could not. "None" if none.>

## Since last round
<Round 2+: closed <n> · open <n> · new <n> · score <before> → <after>. Omit in round 1.>
```

---

## 2. `gaps.md` — the worklist

```markdown
---
kind: reviewer-audit-gaps
round: <n>
written: <YYYY-MM-DD>
must_do: <n>
if_time: <n>
---

# Gaps — <document title>

**Must do before submitting** (<n>): items 1–<k>. **If time** (<n>): items <k+1>–<end>.

## Open

### 1. <class> · <criterion or event> · <weight>
- **Missing:** <one line, and where the reviewer notices its absence>
- **Fix:** <the concrete thing to add or change — the sentence, the section, the commit, the turn>
- **Where:** <surface § section> · first surface: <yes/no>
- **Retrofit:** add | make-it-happen-then-record | disclose — <one clause why>
- **Effort:** <minutes>
- [ ] done

### 2. …

## Closed in earlier rounds
<Round 2+. Same format, checkbox ticked, with the round it closed in. Omit in round 1.>
```

---

## 3. `evidence.md` — the ledger

```markdown
---
kind: reviewer-audit-evidence
round: <n>
written: <YYYY-MM-DD>
---

# Evidence Ledger — <document title>

<One block per rubric criterion, in Lens order. Every candidate found, including weak ones and echoes.>

## <criterion> (<weight>)
Proof moment the Lens asked for: <quoted from What-to-show>
Anti-pattern the Lens named: <quoted>

- Candidate: <what was found>
  - Address: <file § heading / lines / commit / turn / slide / cell / page>
  - Strength: Strong | Adequate | Weak | Missing
  - Depth: first-pass | normal-read | search-only
  - Echo: yes | no
  - Anti-pattern present: <name | none>
  - Note: <why this rating>
- Candidate: …

**Best:** <strength> — <address>

## <next criterion> …

## Explicit requirements trace
| Requirement (Lens / brief) | Where implemented or answered | Present |
|---|---|---|
| <MUST …> | <address> | yes / no / partial |

## Traps trace
| Trap | Status | Address |
|---|---|---|
```

---

## 4. `inventory.md` — what was audited

```markdown
---
kind: reviewer-audit-inventory
round: <n>
written: <YYYY-MM-DD>
submission_ref: "<same as audit-final>"
---

# Inventory — <document title>

## Reading order used
1. `<first_surface>` — <why first, from the Lens persona>
2. <next surface>
3. …

## Surfaces
| Surface (from Lens What-to-show) | Present as | Readable | Notes |
|---|---|---|---|
| <e.g. notes> | `SUBMISSION.md` (1,240 words) | yes | |
| <e.g. transcript> | `PROMPTS.md` (38 human turns, 29 short approvals) | yes | |
| <e.g. video> | link in SUBMISSION.md | **unverified** | no script provided |
| <e.g. mandated DESIGN.md> | — | **absent** | mandated by brief §Submission |

## Files
<output of scripts/inventory.py, trimmed: path, size, type, word count where text>

## Repository
<commits: n · span: first..last (hours) · messages: median length · timestamps vs claimed hours · notable: …; or "not a repository">

## Placeholders and leftovers
<from scripts/inventory.py: file:line — `<link>`, `TBD`, `TODO`, `{{…}}`; or "none">

## Limits measured
| Limit (from brief) | Measured | Inside? |
|---|---|---|
| <1,500 words> | <1,912> | **no** |
```

---

## 5. `audit-partial.md` — the halfway checkpoint (partial mode only)

```markdown
---
kind: reviewer-audit
mode: partial
written: <YYYY-MM-DD>
lens_version: <n>
independence: <…>
submission_ref: "<…>"
---

# Checkpoint — <document title>

**Where you are:** <one line: what exists so far, from the inventory>
**Veto proof visible yet:** yes — <address> | not yet — <what it will take>

## Required-to-exist events
| Event | Happened? | Evidence | If not: when, and what making it happen looks like |
|---|---|---|---|
| "<heading>" | yes / thin / not yet | <address or —> | <"next 30 min: decide the cut list and commit it as a note"> |

## Do next
1. <the one event most at risk of never happening, and the action>
2. <…>
3. <…>

**Re-run full audit before submitting.**
```
