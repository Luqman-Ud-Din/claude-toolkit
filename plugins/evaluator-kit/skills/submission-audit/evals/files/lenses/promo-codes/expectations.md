---
kind: evaluator-lens
version: 1
written: 2026-10-08
document: "Sniffspot Take-Home: Promo Codes"
archetype: technical-take-home
brief: brief.md
context: context.md
veto: "The code was fine, but the session shows the AI proposing and you approving; we wanted to see your own reasoning steering it."
first_surface: SUBMISSION.md
---

# Evaluator Lens — Sniffspot Take-Home: Promo Codes (Backend role)

**Doc type / evaluator / decision:** Technical take-home · three named engineers (@pbhepworth, @skulikov112, @mshmykov), future teammates, ~1 hour each within 3 business days · invite to live technical interview
**Filter or confirmation:** Filter — many submissions to one standing brief; the first pass hunts for a reason to say no in SUBMISSION.md and PROMPTS.md before any code is opened.

**Veto criterion:** "The code was careful, but the session shows the AI proposing and you approving — we couldn't see you steering it." Four surfaces: "how you direct them, not whether you used them"; two mandated PROMPTS.md headings (AI got something wrong, you changed direction); "we'd rather see the raw session"; "expect questions about your prompts".

**Evaluator's mental model:**
I've read a dozen working promo features this month; the tool writes one in twenty minutes, so the diff no longer tells me whether this person has opinions. I open PROMPTS.md first and skim the human turns for constraints, rejections and cuts in their own words, then check whether the decisions in SUBMISSION.md were theirs or the tool's. I'll forgive a backend applicant a mocked mobile screen; I won't forgive a code validated at apply but never at checkout, with no note about it.

## Implicit requirements
- You overrode the AI at least once and caught at least one of its errors — "the moments where the AI got something wrong, and the places where you changed direction" — **Stated**
- Every gap you noticed is written down as decision + why — "tell us what you decided and why" — **Stated**
- You cut scope on purpose and can name what you cut — "Deciding what fits in the time is part of the exercise" — **Stated**
- A deliberate break exists; find it, fix proportionately, report it — "We don't promise that everything runs cleanly" — **Stated**
- The commit log is a readable narrative — "Your real history is more useful to us than one squashed commit" — **Stated**
- Seams for admin CRUD and redemption rules, unbuilt — "Marketing will eventually want to… manage codes" / "we may extend the feature together" — **Strong**
- Backend depth is graded; mobile is graded on honesty — "Focus on the backend… just tell us what you didn't get to" — **Stated**

## Rubric
| Criterion | Weight | Conf. | Failing looks like |
|---|---|---|---|
| Human direction visible in the AI session | 30% | Stated | Human turns are "ok", "continue"; header says "no direction changes" |
| Reasoning visible and defended | 25% | Stated | Decisions listed as facts, no alternative, no why |
| Scoping under the timebox | 15% | Stated | Six hours in commit timestamps; "didn't get to" is empty |
| Obstacle noticed, handled, reported | 10% | Stated | Fixed silently inside a big commit, or "setup broke" and stopped |
| Core backend flow works (gate) | 10% | Stated | Can't apply a code via API and see a discounted total persist |
| Communication form: commits, video order, mechanics | 5% | Strong | One squashed commit; video opens on a code tour |
| Code quality, tests, mobile polish | 5% | Inferred | Tiebreaker only |

**Not graded (or tiebreaker only):** code elegance, test breadth, UI polish, mobile completeness, redemption limits or any unasked feature — zero mentions in the brief.
**Differentiators:** more delegated decisions noticed than the typical submission (validate-at-checkout, snapshot-on-order); a three-line obstacle note; one sentence on where admin CRUD and limits would plug in, with no code.

## What to show
| Criterion | Surface | Proof moment | Anti-pattern |
|---|---|---|---|
| AI direction | PROMPTS.md header + raw export | ≥2 catches and ≥2 overrides cited by turn: "Turn 14: AI validated only at apply; I made checkout re-validate" | "AI was mostly right; no major changes" |
| Reasoning | SUBMISSION.md "Decisions and assumptions" | 6–10 entries as decision — alternative — why: "Snapshot discount on order, not FK to live code: disabling must not rewrite history" | "Added a PromoCode model with a type enum" |
| Scoping | "Time spent" + "What I didn't get to" | Per-phase breakdown ≤3h; cut list ordered by value, one reason each | "~3h"; next step is "add tests" |
| Obstacle | SUBMISSION.md + one `fix:` commit | "Found: X on db:seed. Did: one-line fix. Didn't: refactor Y, out of scope" | Silent patch inside "add promo codes" |
| Core flow (gate) | Video first 60s + "Promo codes to try" | Valid → total drops → checkout → history shows paid total; seeds cover percent, fixed, expired, disabled | Evaluator needs three commands and a config edit |
| Communication | Commits, video, GitLab, Wellfound | 8–15 intent-named commits; demo-then-why video; three Reporters; link in the Wellfound reply | Squashed commit; GitHub link; link only in email |

**Required-to-exist events:**
- "moments where the AI got something wrong" — log the first catch by turn — first third
- "places where you changed direction" — constraints before the first "implement"; reshape the AI's data model — first third
- "Decisions and assumptions" — running list, 6–10 entries — from the first read
- "What I didn't get to, and what I'd do next" — cut list decided at the halfway mark — ~1h30
- "Promo codes to try" — seeds covering every validation branch — last third
- "Time spent: roughly, and on what" — start/stop per phase — from minute one
- "tell us what you found and what you did" — obstacle note written when you hit it — setup

**Simulated verdict (if the plan is followed):** "Pushed back on the tool where it mattered, wrote down ten decisions with reasons, scoped mobile honestly and told us what broke. Bring them in."
**Simulated verdict (if read as a feature spec):** Per this skill's reference material, that approach drew a real rejection on this brief: "the session mostly shows the AI proposing and you approving the next step."

---

## Explicit requirements
- [MUST] Shopper flow: signed-in user applies a code on the cart; valid → discount and new total shown before checkout; invalid → a reason, can retry; order and order history reflect what was paid.
- [MUST] Code rules: percentage and fixed types; optional end date; manual off-switch ("switch a code off early"); one code per order.
- [MUST] A way to try a few working codes — method is yours ("How you do that is up to you"); admin management is explicitly later.
- [MUST] Timebox 2–3h hands-on, notes and video excluded — "Please don't go much over" is a MUST in polite clothing; report what you'd do next.
- [SHOULD] Use AI, any tool ("we expect it"). [MUST] Commit as you go.
- [MUST] Treat as an existing codebase; fix or work around breaks and report what you found.
- [SHOULD] Backend role: backend first, mobile as far as you get; a mocked mobile layer clearly marked beats a half-built one; say what you skipped.
- [MUST] Deliverables: private GitLab repo (never public; import from GitHub if needed) with @pbhepworth, @skulikov112, @mshmykov as Reporter; PROMPTS.md with all prompts + session export + top header (tools, AI-wrong moments, direction changes); 5–10 min video, feature first then decisions / trade-offs / cuts, unlisted link placed in SUBMISSION.md; SUBMISSION.md at root with the template's three fields and four headings.
- [MUST] Submit by replying to the Wellfound message with the repo link — "That's your whole submission."
- [MUST] Product questions: decide and write it down. [MAY] Setup or logistics questions: Wellfound.
- Constraints: Ruby 3.2.2; React Native TypeScript; seeded login test@example.com / password123.

## Traps
- **Planted break.** "We don't promise everything runs cleanly" guarantees at least one. Likely near `db:migrate db:seed` or an existing cart/checkout path. Three-part test: notice, fix proportionately (no rewrite), report. Budget ~15 minutes before working around.
- **Mobile setup is a known sink.** "If the mobile setup fights you" is a warning that it will. For a backend applicant, cap it at ~20 minutes; a mocked layer with a note is the brief's own recommendation.
- **Blocks review entirely.** GitHub instead of GitLab; repo public; wrong usernames or Developer instead of Reporter; a video link that needs login; SUBMISSION.md not at root; the repo link sent anywhere but the Wellfound thread. Any one of these means nobody grades the work.
- **Over-delivery.** The marketing admin UI ("eventually" = phase 2); redemption limits, per-customer codes, first-order-only, minimum spend — none asked; refactoring the existing cart or checkout ("treat it like an existing codebase"); polishing mobile for a backend role. This skill's reference material records a submission to this brief whose race-safe usage limit was praised in the rejection email — the extra feature bought nothing.
- **Timebox honesty.** Commit timestamps and the session export both carry wall-clock time. "Time spent: ~3h" over a six-hour commit range is noticed.
- **Sanitized transcript.** "We'd rather see the raw session" — a cleaned transcript reads as curated and removes your voice along with the mess.
- **Graded-but-looks-optional.** "Time spent: roughly, and on what" wants a breakdown; "AI tools used" is cross-checked against PROMPTS.md; "Promo codes to try" is the evaluator's test harness — without an expired and a disabled code they cannot exercise two of marketing's requirements; the video's order is specified.
- **Tone.** Warm, first-person brief. A clinical SUBMISSION.md reads as not having read it; write it the way the brief is written.
- **Defects in the stated requirements** (noticing is the differentiator):
  - "End date" + "switch off early" + "see the new total before they check out" collide: a code can die between apply and checkout, and nothing says when validation happens. Fix: validate at apply for feedback, re-validate at checkout as the source of truth.
  - "Order reflects what they actually paid, and so does their order history" is impossible if the order only references the live code — disabling or editing a code would rewrite history. Fix: snapshot code string, discount amount and paid total on the order.
  - "Only one code per order" on a flow that lets a shopper "try a different code": a second apply is replace or reject — unspecified. Fix: one column, replace with a message.
  - A fixed amount larger than the subtotal: negative total unspecified. Fix: floor at zero.
  - "Percentage off" — of what? If the app has tax or shipping, the base is unspecified. Fix: item subtotal, and say so.
  - The shopper enters the code "on their cart" but the rule is "per order". Fix: code lives on the cart, moves to the order at checkout.

## Decisions to make / questions to ask
Decide, don't ask — "make the call you'd make and write it down." Ordered by what the evaluator will ask about first.

1. **When a code is validated** → at apply (for feedback) and again at checkout (source of truth) — "A code can expire or be switched off between cart and checkout; checkout is the moment money moves, so it re-checks and returns a clear error rather than honoring a dead code."
2. **What the order stores** → snapshot of code string, discount_cents and total_cents at checkout, plus a nullable reference to the code — "Order history must show what was paid even after marketing disables or edits the code."
3. **How one-code-per-order is enforced** → one nullable promo_code_id column on the cart (and the snapshot on the order), not a join table; applying a second code replaces the first with a message — "A column can hold one value; a join table invites stacking. Replace keeps 'try a different code' one step."
4. **Discount base and bounds** → applied to the item subtotal before any tax/shipping; fixed discount capped at subtotal; totals never below zero; money as integer cents, round half up — "Shoppers read '10% off' as off the items; a negative total is a bug no customer should see."
5. **How to try codes** → 4–6 seeded codes in db/seeds.rb (percent, fixed, expired, disabled, one far-future), listed in SUBMISSION.md; no admin UI — "db:seed is already in the run instructions, so it's the codebase's convention and costs minutes; admin CRUD is the brief's stated phase 2."
6. **The off-switch** → an `active` boolean flipped via console or seed — "Marketing's switch is a flag today; the screen for it is later."
7. **Error messages** → distinct reasons: not found, expired, switched off (and any limit you add); never a bare "invalid" — "The brief says they 'understand why'; one generic message fails that bullet."
8. **Code normalization** → uppercase and strip on input; unique index on the normalized value — "SUMMER10 and summer10 are the same code to a shopper."
9. **API shape** → `POST /cart/promo_code` and `DELETE /cart/promo_code`, both returning the cart with subtotal, discount and total — "Shoppers see the new total before checkout in one round trip; the existing cart serializer is extended, not replaced."
10. **Mobile for a backend applicant** → if the build runs in under 20 minutes, a single input wired to the real endpoint; otherwise a clearly-marked mocked hook/component and a note — "The brief's own ranking: working backend plus marked mock beats a half-configured build."
11. **Tests** → one or two request specs on apply and checkout covering a valid code, an expired code, and the snapshot — "Same way you would on a real team; timeboxed to the branches the brief names."
12. **Redemption limits, per-customer codes, first-order-only** → not built; named in next steps with the seam — "The 'make-good' and 'welcome' examples imply these; a max_redemptions column and a redemptions count is where they plug in."

## Pre-submission check
- [ ] Every required artifact present and populated with what its name promises: SUBMISSION.md at root with all three fields and four headings; PROMPTS.md with header and raw export; video 5–10 min, unlisted, opens in an incognito window
- [ ] Veto-criterion proof is on the first surface the evaluator reads: PROMPTS.md header names catches and overrides by turn; SUBMISSION.md's first screen mentions one pushback
- [ ] Every primary criterion has at least one quotable proof moment (see What to show)
- [ ] "Decisions and assumptions" has 6–10 entries in decision — alternative — why form; validate-at-checkout and snapshot-on-order are among them
- [ ] "What I didn't get to" lists what was cut on purpose, one reason each, ordered by value
- [ ] "Time spent" is a per-phase breakdown consistent with commit timestamps
- [ ] Obstacle note exists: found / did / didn't do more because
- [ ] "Promo codes to try" covers percent, fixed, expired, disabled, invalid
- [ ] Video opens on the feature working (valid → invalid → checkout → order history) within 60 seconds, then decisions, trade-offs, cuts
- [ ] Commit log: 8–15 commits with intent in the messages; no squash; one `fix:` commit for the obstacle
- [ ] Mechanics: GitLab, private, @pbhepworth @skulikov112 @mshmykov as Reporter, repo link in the Wellfound reply, nothing public
- [ ] Register matches the brief: warm, direct, honest about limits

**Sequencing:**
- Before starting: read the brief twice; open the decisions list with the first five gaps (validation timing, snapshot, one-code enforcement, bounds, how-to-try); note start time; write your first AI prompt as constraints in your own words (timebox, backend role, one code per order at the data level, snapshot on order, re-validate at checkout, don't refactor cart/checkout).
- First third (to ~1h): setup; hit the break, fix in one commit, note it; when the AI proposes the data model, review it against the brief and override at least one thing — note the turn number.
- Halfway (~1h30): lock scope; write the cut list; commit.
- Last third (to 3h): checkout snapshot and order history; seeds and "Promo codes to try"; one or two request specs; mobile thin or mocked; stop.
- After work (untimed): SUBMISSION.md with the pushback in the first screen; PROMPTS.md header with turn references and the export; video, feature first; push to GitLab, add Reporters, test the video link logged out, reply on Wellfound.
