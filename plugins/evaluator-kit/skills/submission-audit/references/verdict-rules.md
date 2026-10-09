# Verdict Rules

How the scorecard becomes a verdict, how the two evaluator-voice verdicts are written, how gaps are ranked, and the honesty rule for retrofits.

## The scorecard

One row per rubric criterion from the Lens, in the Lens's order. Columns: criterion, weight, best candidate's strength, factor, contribution, address.

```
| Criterion | Weight | Strength | Factor | Contrib. | Where |
|---|---|---|---|---|---|
| AI direction visible | 30% | Missing | 0 | 0 | — (PROMPTS.md header: "very helpful"; no direction turns) |
| Decisions defended | 25% | Weak | 0.3 | 7.5 | SUBMISSION.md §Decisions, 3 entries, no alternatives |
| … |
| **Weighted score** | | | | **41** | |
```

Factors: Strong 1.0 · Adequate 0.7 · Weak 0.3 · Missing 0. Gates are listed below the table as pass/fail and are not in the sum. Tiebreaker criteria (the Lens marks them) are in the sum at their small weight.

The number is a summary, not the verdict. Two submissions can both score 60 and get different verdicts because one of them failed the veto.

## Verdict

Apply in order; the first that matches wins.

**not-ready** — any of:
- the veto criterion is Weak or Missing;
- a gate fails (core function; a hard format limit; a mandatory requirement absent);
- a required-to-exist event is Empty;
- a blocks-review mechanic is tripped (wrong platform, missing collaborator, link not where asked, public when private was required, wrong channel).

Why these four: each one ends the evaluator's read before the content is weighed. The score is irrelevant because it is never computed.

**fix-first** — none of the above, and any of:
- weighted score under 70;
- any criterion weighted 15% or more is Weak or Missing;
- any required-to-exist event is Thin;
- the veto proof is present but not on `first_surface` (the evaluator forms their impression without it).

Why: the submission survives the first pass, but in a comparison against others to the same brief it loses on a primary axis. These gaps are fixable in hours and the fix list says how.

**ship** — otherwise. Remaining gaps are tiebreakers or secondary. Say what they are; do not pretend there are none.

The thresholds are judgment aids. If the Lens gave a criterion 14% and it is Missing, and it is plainly primary, treat it as primary. Say in the report when you overrode a threshold and why.

## The two verdicts in the evaluator's voice

**First-pass**: written in Phase 2 after the first surface only, and not edited afterwards. One or two sentences, present tense, the evaluator talking to a colleague: *"Opened SUBMISSION.md. Three decisions, no alternatives, nothing about the broken seed, time 'about 3h'. I'll skim the transcript but I'm expecting the AI drove."*

**Final**: after everything. Same voice. If the submission is rejected, the sentence should be one that could appear in the rejection email. If accepted, the sentence should name what tipped it. *"Careful code — the race-safe limit is nice — but the session is the AI proposing and the candidate approving. Not this one."*

Then compare both with the Lens's own predicted verdicts (the Lens wrote "if the plan is followed" and "if the current approach is followed"). Where the audit's verdict matches a Lens prediction, say which. Where it matches neither, say what the Lens did not anticipate.

## Gap severity classes

Rank gaps by class, then by rubric weight within class:

1. **blocks-review** — the evaluator cannot open the work. Fix first; minutes.
2. **veto** — the veto criterion Weak or Missing.
3. **gate** — a pass/fail requirement failed.
4. **event-empty** — a required-to-exist event with no record.
5. **primary** — a criterion weighted 15% or more, Weak or Missing.
6. **event-thin** — a required-to-exist event with a generic record.
7. **first-surface** — veto proof exists but not where the evaluator starts.
8. **secondary** — a criterion under 15%, Weak or Missing.
9. **trap** — a Lens trap tripped that is not already covered above (tone, over-delivery, sanitisation).
10. **tiebreaker** — the Lens's tiebreaker criteria.

Within a class, higher weight first. Across the whole list, no more than the user can act on before the deadline should be above the fold; put a line in the report saying which gaps are the "must" set and which are the "if time" set.

## Writing a gap

```
### <n>. <class> · <criterion or event> · <weight>
- **Missing:** <one line, and where the evaluator notices its absence>
- **Fix:** <the concrete thing to add or change, quotable>
- **Where:** <surface § section; first-surface yes/no>
- **Retrofit:** add | make-it-happen-then-record | disclose
- **Effort:** <minutes>
- [ ] done
```

The **Fix** line is the point of the file. It must be specific enough that the user could do it without re-reading the audit: the sentence to write, the heading to add, the commit to make, the turn to produce. "Improve the decisions section" is not a fix. "Add four entries in the form decision / alternative / why: (1) validate at checkout vs at apply, (2) snapshot the discount on the order vs reference the code, (3) case-insensitive matching vs exact, (4) seeds vs admin UI — put (1) first" is.

## Retrofit honesty

Three kinds of fix, and the audit says which each gap is:

- **add** — the evidence exists in the work and only needs to be surfaced: a decision that was made but not written down; a commit that fixed the obstacle but no note mentions it; a sample that exists but was not attached. Write it up.
- **make-it-happen-then-record** — the event has not occurred. A cut was never decided; the tool was never pushed back on; the obstacle was never looked for; the community was never asked. The fix is to do the thing now, in whatever time remains, and then record it with its real trace. The audit says this plainly because the alternative — writing it up as if it happened — produces a record with no trace behind it, and evaluators check traces (turn numbers, timestamps, commits).
- **disclose** — the event cannot happen now (the timebox is spent; the relationship does not exist; the data was never collected). The honest fix is to say so in the notes, with why, and let the evaluator weigh it. A disclosed gap often costs less than a thin cover for it.

Never write a fix that amounts to fabricating a trace. If the user asks for one, say why it will not survive the evaluator's cross-check and offer the honest version.

## Re-audit rounds

When `audit-final.md` exists from a previous round:

- Read the previous `gaps.md`. For each gap: closed (evidence now present at the stated address), still open, or changed.
- New gaps found this round are marked `new in round <n>`.
- The report gets a "Since last round" block: closed / open / new counts and the score delta.
- `gaps.md` keeps closed items with their checkbox ticked, below the open ones, so the user sees progress.
- Verdict is recomputed from scratch; a round-1 not-ready can be a round-2 ship.

## What the report never does

- It never grades on a criterion the Lens does not have. Analysis gaps are reported, not scored.
- It never softens the first-pass verdict after reading further.
- It never passes an unverified surface. "Could not verify" is written where the grade would go.
- It never rewards effort the rubric does not weigh beyond one clause of acknowledgement.
- It never proposes a fabricated trace.
