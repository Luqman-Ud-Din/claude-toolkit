# Worked Example: A Take-Home Audit With a Real Rejection on Record

A full audit of a code submission to a brief whose actual outcome is known, so the method can be checked against ground truth. Use it to calibrate: if an audit of a similar submission would not have predicted this rejection, the first pass is too kind or the evidence scale is too loose.

## The brief, in one paragraph

A hiring take-home: add promo codes to a small Rails + React Native shopping app in 2–3 hours. The brief said, in six places, that it graded reasoning and how the candidate directed the AI ("we're interested in how you direct them, not in whether you used them"), mandated a `PROMPTS.md` with a raw session export and a header covering "the moments where the AI got something wrong, and the places where you changed direction", a 5–10 minute video, and a `SUBMISSION.md` with four headings. The Reviewer Lens for it (see the analysis skill's worked examples) put the veto on **human direction of the AI session**, weighted 30%, with reasoning at 25%, scoping 15%, obstacle handling 10%, core flow as a 10% gate, communication 5%, and code quality as a 5% tiebreaker. First surface: `SUBMISSION.md`.

## The submission

Six commits over 3h38 (2h46 hands-on by timestamp). Clean backend: a `PromoCode` model with a case-insensitive unique index, an apply/remove service with distinct error messages, re-validation at checkout, the discount snapshotted onto the order, and a race-safe per-code usage limit with a two-thread spec. Mobile layer mocked with a comment. `SUBMISSION.md` with four decisions listed as facts, time "about 3 hours", next steps "wire it up, add an admin UI, add more tests". `PROMPTS.md` header: "The AI was very helpful and produced most of the code. It got a couple of small things wrong (a wrong column name) which I corrected. I changed direction once on naming the service object." Below it, a 19-turn session in which the human's turns are: the brief pasted plus "Implement the promo codes feature", then "ok", "continue", "yes do that", "looks good", "ok", "yes", "ok go ahead", one rename request, "ok thanks".

## The real outcome

> *"The code itself was careful (the race-safe usage limit stood out), but the session mostly shows the AI proposing and you approving the next step, and we'd have liked to see more of your own reasoning steering it, for example reshaping or pushing back on its design and scope."*

## The audit

### Phase 1 — inventory

`scripts/inventory.py` on the repo: 6 commits, span 3.63h, zero intent-bearing commit messages; transcript 10 human turns, 8 short approvals (ratio 0.80), 0 direction-word turns, first human turn 16 words beginning "Here is the take-home brief: [brief pasted]". Mandated files present. Two findings the script surfaced before any reading: the handoff folder `docs/reviewer-requirements/` was tracked in the root commit (the reviewer would find the Lens inside the submission), and the video link in `SUBMISSION.md` was `https://www.loom.com/share/placeholder-unlisted`.

Reading order from the Lens: `SUBMISSION.md` → `PROMPTS.md` → commit log → video → code.

### Phase 2 — first pass, `SUBMISSION.md` only

> "Opened SUBMISSION.md. The video link is a placeholder, time is 'about 3 hours', four decisions stated as facts with no alternative and no why — the only one with a reason is a usage limit we didn't ask for. Nothing about the session, nothing about what broke. I'll open PROMPTS.md expecting the tool drove."

Veto proof on this surface: **no**. The only reference to the session is "AI tools used: Claude Code".

Written and locked before `PROMPTS.md` was opened. It is already most of the verdict.

### Phase 3 — the veto, with addresses

Status **Missing**. The transcript is the veto sentence made literal:

- `PROMPTS.md` L3: "very helpful… produced most of the code" — an echo of the brief's permission, not a direction claim.
- H1 (L7): brief pasted + "Implement" — no constraints, no plan.
- H2–H8, H10: approvals. Every design decision was proposed by the assistant and accepted: schema (A1→H2), case-insensitive index (A2, unprompted), replace-not-reject (A3 "I'd suggest replacing"→H4), re-validate + snapshot (A4→H5), `max_uses` race guard (A5→H6), seeds (A6→H7), mock mobile (A7→H8).
- The header's two claims have no trace. "A wrong column name which I corrected": the model and migration were committed once (`38d04cd`) and never modified. "Changed direction once on naming": H9 asks for `ApplyPromoCode` not `PromoApplier`, but A2 (L13) already used `ApplyPromoCode`, and `git log -S PromoApplier` finds the string only in `PROMPTS.md`. The one direction turn is on naming, and it is contradicted by the transcript it sits in.
- Not a raw export: no timestamps, no tool calls, "[brief pasted]" as a redaction. The brief asked for the export; the sanitisation discount applies.

### Phase 4 — events

| Event | Status | Why |
|---|---|---|
| "moments where the AI got something wrong" | Thin | claimed, no turn, no commit trace |
| "places where you changed direction" | Thin | one rename, contradicted by A2 |
| "Decisions and assumptions" | Thin | 4 facts; the decisions that *were* made (re-validate at checkout, snapshot, replace-on-second-apply) are in the code and unwritten |
| "What I didn't get to" | Thin | mobile cut at 20:48, the end, not halfway; next steps generic |
| "Promo codes to try" | Present | seeds match exactly, cover every path |
| "Time spent, and on what" | Thin | honest number, field unanswered |
| obstacle note | Thin | the pre-warned mobile sink only; no backend obstacle found or reported |

### Phase 5 — gates, mechanics, traps

Blocks-review, three: placeholder video; the Lens tracked in history; GitLab/private/Reporters/Wellfound unverifiable (no remote). Over-delivery trap tripped: `max_uses`, the race guard, the thread spec and the `ONCE` seed were never asked for — and are the thing the submitter is proudest of. Sanitisation: transcript vs commits disagree (the transcript's rename never happened in git). Tone: clinical register to a warm brief.

### Phase 7 — scorecard and verdict

| Criterion | Weight | Strength | Contrib. |
|---|---|---|---|
| Human direction in the session | 30% | Missing | 0 |
| Reasoning visible and defended | 25% | Weak | 7.5 |
| Scoping under the timebox | 15% | Weak | 4.5 |
| Obstacle noticed, handled, reported | 10% | Weak | 3.0 |
| Core flow (gate) | 10% | Adequate on read, could not execute | 7.0 |
| Communication form | 5% | Weak | 1.5 |
| Code quality (tiebreaker) | 5% | Adequate | 3.5 |
| **Score** | | | **27** |

**Verdict: not-ready** — veto Missing, three blocks-review items, a mandated artifact absent.

**Final, in the reviewer's voice:** "The checkout snapshot is right and the code is tidy, but the session is the tool proposing and the candidate typing 'ok' eight times out of ten; the one override is a rename the transcript itself contradicts, and the thing they're proudest of is a usage limit we didn't ask for. No video, no word on what broke, and our own rubric is sitting in their docs folder. We can't see this person steer. Not this one."

Against the Lens's predictions: matches "if read as a feature spec". The Lens did not anticipate the placeholder video or the tracked Lens; both made it worse.

### Phase 8 — the veto gap, as written

Ranked fourth, behind the three blocks-review items (a reviewer who cannot open the work never reaches the veto). Retrofit: **make-it-happen-then-record**, with disclosure as the fallback:

> **(a) Make it happen.** Open a new session on the current code and steer it. First turn: constraints in your own words — "Backend role, ~1h left, treat cart/checkout as an existing codebase, one code per order enforced at the data level, checkout is the source of truth, no features beyond the brief." Then direct at least two real changes with reasons the reviewer can quote. True of this codebase: (1) *cut* — "Drop `max_uses` and the race guard; the brief didn't ask for limits — leave a one-line seam note." (2) *catch* — "`Checkout` raises the 'expired' message for any `usable?` failure (checkout.rb:10); return the real reason." (3) *catch* — "`CartScreen.tsx` is web React, not React Native." Commit each with intent. `/export`, append it **under** the existing session unedited as "Session 2", and rewrite the header to cite turns — including "Session 1: I accepted the tool's proposals with little pushback (H2–H8)."
> **(b) Disclose.** Replace the header with the truth: the export is reconstructed; the design was the tool's and approved without much pushback; in hindsight constraints up front and the usage limit cut. Put the reasoning into `SUBMISSION.md` §Decisions so the reviewer sees the design can be defended.
> **Never:** edit the existing export to insert pushback. The H9/A2 contradiction already shows what an inserted turn looks like.

## What this example teaches

- **The first pass carried the verdict.** Everything the final verdict says was visible on `SUBMISSION.md` or predictable from it. The real reviewer's email reads like a first pass too.
- **The header was echo.** It used the brief's own categories ("got something wrong", "changed direction") with claims the transcript did not support. Cross-checking claims against traces (turn numbers, `git log -S`) is what separated Thin from Present.
- **Effort the rubric did not weigh was named and weighted as the Lens weighed it.** The race-safe limit got one clause and 5%. The real reviewer gave it one clause too — in the rejection.
- **The honest fix was not "write a better header".** The event had not happened. The audit said so, offered the route to make it happen in the time left, and offered disclosure as the alternative. Neither route invents a trace.
- **The inventory script found two blocks-review items before any judgment.** Deterministic checks catch the things that embarrass most: placeholders left in, the rubric model tracked in the repo, dates that do not add up.
