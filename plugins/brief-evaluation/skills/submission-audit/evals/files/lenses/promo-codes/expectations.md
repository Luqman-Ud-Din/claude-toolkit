---
kind: evaluator-lens
version: 1
written: 2026-10-08
document: "Sniffspot Take-Home: Promo Codes"
archetype: technical-take-home
brief: brief.md
veto: "The code was fine, but the session shows the AI proposing and you approving; we wanted to see your own reasoning steering it."
first_surface: SUBMISSION.md
submission_form: repo + README
ai_receptiveness: 90
---

# Evaluator Lens — Sniffspot Take-Home: Promo Codes

## 1. Description

Sniffspot asks the applicant to add one feature, promo codes, to an existing small shopping app (Rails API in backend/, React Native TypeScript app in mobile/), "the same way you would on a real product team" (§intro).
Shoppers must be able to apply a code on their cart, see the discount and new total before checkout, understand why a code fails, and see what they actually paid on the order and in order history (§What shoppers need).
Marketing needs percentage and fixed codes, an end date, an early off-switch, one code per order, and for now just "a way to try out a few working codes" (§What marketing needs).
The brief is "a product brief, not a spec, on purpose": every gap is to be decided and written down, because "What we care about is how you reason" (§What we're leaving to you).
Work is timeboxed to about 2–3 hours, with AI expected and judged on "how you direct them", a possibly broken codebase to fix or work around, and backend-first scope for the Backend role (§How to work).
The submission is one private GitLab repo with the code and commit history, PROMPTS.md, a 5–10 minute video and SUBMISSION.md, sent by replying on Wellfound with the repo link (§What to send us).
Sniffspot's engineers review within about 3 business days and decide whether to invite the applicant to a live technical interview with questions about "your decisions and your prompts" (§What happens next).

## 2. Context understanding

- **Type / archetype:** technical take-home for a product engineering role — §intro "add one feature, the same way you would on a real product team"
- **Evaluator:** three named engineers, @pbhepworth, @skulikov112 and @mshmykov, added as Reporters (§Your code). They are future teammates who "review every submission" of a standing brief (§What happens next). Inferred: about an hour per submission, in a pile of similar working features.
- **Decision:** invite to a live technical interview, or not (§What happens next) · **Filter or confirmation:** Filter. Many submissions are compared against one standing brief, and the first pass looks for a reason to say no in SUBMISSION.md and PROMPTS.md before any code is opened (inferred from the archetype and from the fact that the deliverables are notes, transcript and video, not just code).
- **Constraints:** about 2–3h hands-on, notes and video excluded, "Please don't go much over" (§How to work) · Ruby 3.2.2, React Native TypeScript, seeded login test@example.com / password123 (§Getting started) · private GitLab only, "Please don't publish your solution anywhere public" (§Your code) · video 5–10 min with an unlisted link (§video)
- **Stakes and tone:** warm, first-person, collaborative ("Thanks for taking this on!", "We don't have a hidden checklist of right answers"). The writers want a teammate who decides and explains, not a candidate who asks for permission. A clinical or defensive register reads as not having read the brief.
- **User's context:** applying for the **Backend** role, so backend depth is graded and mobile is graded on honesty (§How to work "Applying for the Backend role?"). User's own deadline: **2026-10-14**. Prior rejection: none mentioned.

## 3. Evaluator intent

**In their words (first person):** I've read a dozen working promo features this month. The tool writes one in twenty minutes, so the diff no longer tells me whether this person has opinions. I open PROMPTS.md first and skim the human turns for constraints, rejections and cuts in their own words, then check whether the decisions in SUBMISSION.md were theirs or the tool's. I'll forgive a backend applicant a mocked mobile screen. I won't forgive a code that is validated at apply but never at checkout, with no note about it.

**What they actually want:** evidence that the applicant steers the AI and reasons about product gaps like a teammate shipping to real customers. The working feature is only the price of entry. Evidence: AI direction is asked about on four surfaces, and "how you reason" or "decided and why" appears in four sections. The brief also says outright that it has no hidden checklist (§What we're leaving to you).

**Weightiest themes:**
- Human direction of AI: ×4 across 3 sections. §How to work "how you direct them, not … whether you used them"; §PROMPTS.md the mandated header ("the moments where the AI got something wrong, and the places where you changed direction") and "We'd rather see the raw session"; §What happens next "Expect questions about … your prompts".
- Reasoning and decisions written down: ×5 across 4 sections. §What we're leaving to you "tell us what you decided and why" and "how you reason"; §video "your key decisions, the trade-offs"; §SUBMISSION.md "Decisions and assumptions"; §Questions? "make the call you'd make and write it down".
- Scoping under the timebox: ×5 across 3 sections. "Please don't go much over", "Deciding what fits in the time is part of the exercise", "tell us what you'd do next" (§How to work); "what you chose not to do" (§video); "What I didn't get to, and what I'd do next" (§SUBMISSION.md).
- Honest reporting of the codebase state and the scope cut: ×4 in §How to work. "tell us what you found and what you did about it", "Just tell us what you did", "just tell us what you didn't get to", and "Your real history is more useful to us".

**Not graded (or tiebreaker only):** code elegance, test breadth, UI polish, mobile completeness for a backend applicant, and redemption limits or any other unasked feature. The brief never mentions any of these.

## 4. Explicit requirements

| # | Requirement | Reference | Impact if missed | Severity |
|---|---|---|---|---|
| E1 | Private GitLab repo (import from GitHub if needed), never public; @pbhepworth, @skulikov112, @mshmykov added with the Reporter role | §Your code — "private GitLab repo", "Reporter role", "Please don't publish your solution anywhere public" | Nobody can open the work; a public repo breaks an explicit ask | Critical |
| E2 | Submit by replying to the Wellfound message with the repo link | §What to send us — "reply to our message on Wellfound with the repo link. That's your whole submission." | The submission is never received | Critical |
| E3 | PROMPTS.md with all the AI prompts, the session export where the tool allows it, and a top header listing the tools used, the moments the AI got something wrong, and the places where you changed direction | §PROMPTS.md — "We'd rather see the raw session than a cleaned-up one" | The veto surface is missing or empty, so the main criterion cannot be graded | Critical |
| E4 | SUBMISSION.md at the repo root with the three fields (Video walkthrough, Time spent, AI tools used) and the four headings (How to run what I added, Promo codes to try, Decisions and assumptions, What I didn't get to, and what I'd do next) | §SUBMISSION.md — "a short note at the root of the repo. You can start from this" | The first surface is missing; reasoning and scope go unread | Critical |
| E5 | Shopper flow: a signed-in user applies a code on the cart; a valid code shows the discount and new total before checkout; an invalid code shows a reason and allows retry; the order and order history reflect what was paid | §What shoppers need | The core flow (the gate) fails, and nothing else is credited | Critical |
| E6 | Code rules: percentage and fixed types; optional end date; manual early off-switch; one code per order | §What marketing needs — "switch a code off early", "Only one code can be used per order" | Marketing's stated needs are unmet, and the evaluator tests these first | High |
| E7 | A way to try a few working codes; the method is up to you; admin management comes later | §What marketing needs — "it's enough to give us a way to try out a few working codes. How you do that is up to you." | The evaluator cannot exercise the feature | High |
| E8 | Timebox of about 2–3h hands-on (notes and video excluded); don't go much over; say what you'd do next | §How to work — "Please don't go much over. Deciding what fits in the time is part of the exercise" | Scoping, a 15% criterion, fails, and commit timestamps expose it | High |
| E9 | Treat it as an existing codebase: fix or work around breaks, and report what you found and did | §How to work — "We don't promise that everything runs cleanly … tell us what you found and what you did about it" | The planted obstacle goes unreported or stalls the work | High |
| E10 | Commit as you go; no single squashed commit | §How to work — "Your real history is more useful to us than one squashed commit" | The process is invisible, and the timebox and direction cannot be checked | High |
| E11 | Use AI, any tool; judged on direction | §How to work — "Use AI. We expect it … how you direct them" | No AI session leaves nothing to grade on the heaviest criterion | High |
| E12 | Product questions: decide and write it down, don't ask | §Questions? — "make the call you'd make and write it down. That's part of the exercise." | Asking reads as unable to decide, and unrecorded calls are not credited | High |
| E13 | 5–10 min video: show the feature working first, then decisions, trade-offs and what you chose not to do; unlisted link placed in SUBMISSION.md | §video — "First show the feature working. Then walk us through …" | Wrong order or a login-gated link loses the demo and the reasoning | High |
| E14 | Backend role: backend first, mobile as far as you get; a clearly marked mock beats a half-configured build; say what you skipped | §How to work — "If the mobile setup fights you…", "Applying for the Backend role?" | Time sunk into Xcode/Gradle, or an unmarked fake | Medium |
| E15 | Stack constraints: Ruby 3.2.2, React Native TypeScript, seeded login test@example.com / password123 | §Getting started | Run instructions break for the evaluator | Medium |
| E16 | Setup or logistics questions may go to the Wellfound thread | §Questions? — "If you have a question about setup or logistics, reply to our message on Wellfound." | A courtesy channel is not used | Low |

## 5. Implicit requirements

| # | Requirement | Reference | Impact if missed | Severity | Confidence |
|---|---|---|---|---|---|
| I1 | You overrode the AI at least once and caught at least one of its errors, and both are visible by turn in the session | "the moments where the AI got something wrong, and the places where you changed direction" — §PROMPTS.md | The veto: the AI drove and you approved | Critical | Stated |
| I2 | Every gap you noticed is written down as a decision plus the reason | "tell us what you decided and why" — §What we're leaving to you | The 25% reasoning criterion fails | High | Stated |
| I3 | You cut scope on purpose and can name what you cut | "Deciding what fits in the time is part of the exercise" — §How to work | Reads as having run out of time rather than having scoped | High | Stated |
| I4 | A planted break exists; find it, fix it in proportion, report it | "We don't promise that everything runs cleanly out of the box" — §How to work | The obstacle criterion fails, through a silent fix or a stall | High | Stated |
| I5 | The commit log reads as a narrative | "Your real history is more useful to us than one squashed commit" — §How to work | The communication criterion drops; the process cannot be checked | Medium | Stated |
| I6 | Leave seams for admin CRUD and redemption rules, but don't build them | "Marketing will eventually want to create and manage codes themselves" — §What marketing needs; "we may extend the feature together" — §What happens next | A missed differentiator, or a timebox spent on phase 2 | Medium | Strong |
| I7 | Backend depth is graded; mobile is graded on honesty | "Focus on the backend … just tell us what you didn't get to" — §How to work | Unclear role fit; mobile effort is not credited | Medium | Stated |

## 6. AI receptiveness

| | |
|---|---|
| **Receptiveness** | 90% — Expects |
| **Is AI use examined?** | graded, and it is the veto criterion. §How to work "We're interested in how you direct them, not in whether you used them"; §PROMPTS.md mandated header and raw export |
| **Recommended AI involvement** | Up to ~60–75% of the implementation keystrokes. These parts must visibly stay human: the opening constraints prompt, the review and override of the AI's data model, validation timing and snapshot-on-order, the scope cuts, the obstacle diagnosis, and the SUBMISSION.md text and video narration in your own voice |
| **If asked "how much AI did you use?"** | State your actual share (likely ~60–75% of the code for this brief). For example: "The AI wrote most of the code, roughly <your real share>. I set the constraints up front, rejected its first data model in favour of snapshotting the paid total on the order, made checkout re-validate the code, and decided what to cut; the turns are marked in PROMPTS.md." State your real share. If it is far from this band, change how you work, not what you say. The export makes the number checkable. |
| **Evidence** | §How to work "Use AI. We expect it, because that's how our team works"; §PROMPTS.md "all of the AI prompts", session export, "We'd rather see the raw session than a cleaned-up one"; §What happens next "Expect questions about your decisions and your prompts" |
| **Confidence** | 90% — the brief states its position on AI explicitly and asks for transcripts |

## 7. Understanding

### Matrix

| Criterion | Weight | Conf. | Failing looks like |
|---|---|---|---|
| Human direction visible in the AI session | 30% | Stated | Human turns say "ok" and "continue"; the header says "no direction changes" |
| Reasoning visible and defended | 25% | Stated | Decisions listed as facts, with no alternative and no reason |
| Scoping under the timebox | 15% | Stated | Six hours in the commit timestamps; "didn't get to" is empty |
| Obstacle noticed, handled, reported | 10% | Stated | Fixed silently inside a big commit, or "setup broke" and the work stopped |
| Core backend flow works (gate) | 10% | Stated | You can't apply a code via the API and see a discounted total persist |
| Communication form: commits, video order, mechanics | 5% | Strong | One squashed commit; the video opens on a code tour |
| Code quality, tests, mobile polish | 5% | Inferred | Tiebreaker only |

**Not graded (or tiebreaker only):** code elegance, test breadth, UI polish, mobile completeness, and redemption limits (a race-safe max_uses, for example) or any other unasked feature. The brief never mentions any of these.

**Simulated verdict (if the plan is followed):** "Pushed back on the tool where it mattered, wrote down ten decisions with reasons, scoped mobile honestly and told us what broke. Bring them in."
**Simulated verdict (if the user's current approach is followed, when known):** If the brief is read as a feature spec (build everything, let the tool lead): per this skill's reference material, that approach drew a real rejection on this brief: "the session mostly shows the AI proposing and you approving the next step."

### Deal breakers

**Veto criterion:** "The code was fine, but the session shows the AI proposing and you approving; we wanted to see your own reasoning steering it." The evidence is four surfaces: "how you direct them, not … whether you used them" (§How to work); the two mandated PROMPTS.md headings, "the moments where the AI got something wrong" and "the places where you changed direction" (§PROMPTS.md); "We'd rather see the raw session than a cleaned-up one" (§PROMPTS.md); and "Expect questions about your decisions and your prompts" (§What happens next).

- **Planted obstacle** — §How to work "We don't promise that everything runs cleanly out of the box". The existing codebase may not run cleanly, and at least one break is effectively guaranteed, likely around `rails db:migrate db:seed` (§Getting started) or an existing cart/checkout path. Apply a three-part test: notice it, fix it in proportion (no rewrite), report it in SUBMISSION.md with one `fix:` commit. Budget about 15 minutes before working around it.
- **Mobile setup is a known sink** — §How to work "If the mobile setup fights you, don't spend your timebox on Xcode or Gradle". The warning means it will fight you. For a backend applicant, cap it at about 20 minutes; a mocked layer with a note is what the brief itself recommends.
- **Blocks review entirely** — §Your code, §What to send us. Using GitHub instead of GitLab; a public repo; wrong usernames, or Developer instead of Reporter; a video link that needs a login (§video "unlisted link"); SUBMISSION.md not at the root; the repo link sent anywhere but the Wellfound thread. Any one of these means nobody grades the work.
- **Over-delivery** — §What marketing needs "Marketing will eventually want…" and "it's enough to…". The marketing admin UI ("eventually" means phase 2); redemption limits, per-customer codes, first-order-only, minimum spend, none of which were asked for; refactoring the existing cart or checkout (§How to work "Treat it like an existing codebase"); polishing mobile for a backend role. This skill's reference material records a submission to this brief whose race-safe usage limit (max_uses) was praised in the rejection email. The extra feature was a tiebreaker at best and bought nothing.
- **Timebox honesty** — §How to work "Please don't go much over". Commit timestamps and the session export both carry wall-clock time. "Time spent: ~3h" over a six-hour commit range will be noticed.
- **Sanitized transcript** — §PROMPTS.md "We'd rather see the raw session than a cleaned-up one". A cleaned transcript reads as curated, and it removes your voice along with the mess.
- **Graded-but-looks-optional** — §SUBMISSION.md template and §video. "Time spent: roughly, and on what" wants a breakdown. "AI tools used" is cross-checked against PROMPTS.md. "Promo codes to try" is the evaluator's test harness: without an expired code and a disabled code, they cannot test two of marketing's requirements. The video's order is specified.
- **Handoff folder shipped in the repo** — inferred from §Your code ("Push your work … to a private GitLab repo") and §PROMPTS.md ("all of the AI prompts you used to build this"). `docs/evaluator-expectations/` (this Lens and brief.md) must not be tracked or pushed. An evaluator who finds a model of their own rubric in the repo reads it as gaming, not diligence. Keep the folder in `.gitignore`. "All prompts" refers to the build session, not this analysis.
- **Tone** — §intro and §What we're leaving to you are warm and first-person. A clinical SUBMISSION.md reads as not having read the brief; write it the way the brief is written.
- **Defects in the stated requirements** (noticing them is the differentiator):
  - "end date" + "switch a code off early" + "see the discount and their new total before they check out" (§What marketing needs, §What shoppers need) collide: a code can die between apply and checkout, and nothing says when validation happens. Fix: validate at apply for feedback, and re-validate at checkout as the source of truth.
  - "the order reflects what they actually paid, and so does their order history" (§What shoppers need) is impossible if the order only references the live code, because disabling or editing the code would rewrite history. Fix: snapshot the code string, discount amount and paid total on the order.
  - "Only one code can be used per order" sits on a flow that lets a shopper "try a different code" (§What shoppers need), and a second apply could mean replace or reject; the brief doesn't say. Fix: one column, replace with a message.
  - A fixed amount larger than the subtotal (§What marketing needs "a fixed amount off") could produce a negative total, which the brief does not address. Fix: floor at zero.
  - "a percentage off" (§What marketing needs): off what? If the app has tax or shipping, the base is unspecified. Fix: the item subtotal, and say so.
  - The shopper enters the code "on their cart" (§What shoppers need) but the rule is "per order" (§What marketing needs). Fix: the code lives on the cart and moves to the order at checkout.

### Deal makers

**Differentiators:**
- Noticing more of the delegated decisions than the typical submission, validate-at-checkout and snapshot-on-order above all. §What we're leaving to you "There are plenty of things it doesn't cover"
- A three-line obstacle note: found / did / didn't do more because. §How to work "tell us what you found and what you did about it"
- One sentence on where admin CRUD and limits would plug in, with no code. §What marketing needs "eventually"; §What happens next "we may extend the feature together"

**Decisions to make / questions to ask** (decide, don't ask: §Questions? "make the call you'd make and write it down"; ordered by what the evaluator will ask about first; all Assume):
- **When a code is validated** → at apply (for feedback) and again at checkout (source of truth). "A code can expire or be switched off between cart and checkout; checkout is the moment money moves, so it re-checks and returns a clear error rather than honoring a dead code."
- **What the order stores** → a snapshot of the code string, discount_cents and total_cents at checkout, plus a nullable reference to the code. "Order history must show what was paid even after marketing disables or edits the code."
- **How one-code-per-order is enforced** → one nullable promo_code_id column on the cart (and the snapshot on the order), not a join table; applying a second code replaces the first, with a message. "A column can hold one value; a join table invites stacking. Replace keeps 'try a different code' one step."
- **Discount base and bounds** → applied to the item subtotal before any tax or shipping; fixed discount capped at the subtotal; totals never below zero; money as integer cents, round half up. "Shoppers read '10% off' as off the items; a negative total is a bug no customer should see."
- **How to try codes** → 4–6 seeded codes in db/seeds.rb (percent, fixed, expired, disabled, one far-future), listed in SUBMISSION.md; no admin UI. "db:seed is already in the run instructions, so it's the codebase's convention and costs minutes; admin CRUD is the brief's stated phase 2."
- **The off-switch** → an `active` boolean flipped via the console or seed. "Marketing's switch is a flag today; the screen for it is later."
- **Error messages** → distinct reasons: not found, expired, switched off (and any limit you add); never a bare "invalid". "The brief says they 'understand why'; one generic message fails that bullet."
- **Code normalization** → uppercase and strip on input; unique index on the normalized value. "SUMMER10 and summer10 are the same code to a shopper."
- **API shape** → `POST /cart/promo_code` and `DELETE /cart/promo_code`, both returning the cart with subtotal, discount and total. "Shoppers see the new total before checkout in one round trip; the existing cart serializer is extended, not replaced."
- **Mobile for a backend applicant** → if the build runs in under 20 minutes, a single input wired to the real endpoint; otherwise a clearly marked mocked hook/component and a note. "The brief's own ranking: working backend plus marked mock beats a half-configured build."
- **Tests** → one or two request specs on apply and checkout, covering a valid code, an expired code and the snapshot. "Same way you would on a real team; timeboxed to the branches the brief names."
- **Redemption limits, per-customer codes, first-order-only** → not built; named in next steps along with the seam. "The 'make-good' and 'welcome' examples imply these; a max_redemptions column and a redemptions count is where they plug in."

### Submission package

In the evaluator's reading order: SUBMISSION.md first, then PROMPTS.md, then the video, commits and code. The repo access and the Wellfound reply come before any reading can start.

| # | Item | Form | Must contain |
|---|---|---|---|
| P1 | SUBMISSION.md | Markdown at the repo root, short, from the template | The three fields (unlisted video link, per-phase time breakdown, AI tools matching PROMPTS.md); the four headings; one pushback on the AI in the first screen (AI direction); 6–10 decisions (reasoning); the obstacle note (obstacle); the cut list (scoping); codes to try (core flow) |
| P2 | PROMPTS.md | Markdown header of a few lines plus all prompts and the raw session export | The tools; "the moments where the AI got something wrong" and "the places where you changed direction", each cited by turn (AI direction, the veto) |
| P3 | Video walkthrough | 5–10 min, screen and voice, unlisted link that opens logged out | Feature working within 60s (valid → invalid → checkout → order history), then decisions, trade-offs, cuts (core flow, reasoning) |
| P4 | Commit history | 8–15 intent-named commits, no squash | Phase narrative and one `fix:` commit for the obstacle (communication, obstacle, timebox honesty) |
| P5 | Code | Rails backend changes, seeds, 1–2 request specs, mobile thin or clearly mocked | Apply/remove endpoints, re-validation at checkout, snapshot on the order (core flow gate; tiebreaker on quality) |
| P6 | Repo access and hand-off | Private GitLab, 3 Reporters, repo link in the Wellfound reply | Nothing public; `docs/evaluator-expectations/` not tracked (blocks review if wrong) |

**Proof per criterion:**

| Criterion | Surface | Proof moment | Anti-pattern |
|---|---|---|---|
| AI direction | PROMPTS.md header + raw export | At least 2 catches and 2 overrides cited by turn: "Turn 14: AI validated only at apply; I made checkout re-validate" | "AI was mostly right; no major changes" |
| Reasoning | SUBMISSION.md "Decisions and assumptions" | 6–10 entries as decision — alternative — why: "Snapshot discount on order, not FK to live code: disabling must not rewrite history" | "Added a PromoCode model with a type enum" |
| Scoping | "Time spent" + "What I didn't get to" | Per-phase breakdown totalling no more than 3h; cut list ordered by value, one reason each | "~3h"; the next step is "add tests" |
| Obstacle | SUBMISSION.md + one `fix:` commit | "Found: X on db:seed. Did: one-line fix. Didn't: refactor Y, out of scope" | Silent patch inside "add promo codes" |
| Core flow (gate) | Video first 60s + "Promo codes to try" | Valid → total drops → checkout → history shows the paid total; seeds cover percent, fixed, expired, disabled | The evaluator needs three commands and a config edit |
| Communication | Commits, video, GitLab, Wellfound | 8–15 intent-named commits; demo-then-why video; three Reporters; link in the Wellfound reply | Squashed commit; GitHub link; link sent only by email |

**Required-to-exist events:**
- "moments where the AI got something wrong" — log the first catch by turn number — first third
- "places where you changed direction" — set constraints before the first "implement"; reshape the AI's data model — first third
- "Decisions and assumptions" — a running list of 6–10 entries — from the first read
- "What I didn't get to, and what I'd do next" — cut list decided at the halfway mark — around 1h30
- "Promo codes to try" — seeds covering every validation branch — last third
- "Time spent: roughly, and on what" — start/stop times per phase — from minute one
- "tell us what you found and what you did" — obstacle note written when you hit it — setup

**Recommended shape:**

| Section (in reading order) | Share | Carries |
|---|---|---|
| Before starting | ~10 min | Read the brief twice; open the decisions list with the first five gaps (validation timing, snapshot, one-code enforcement, bounds, how-to-try); note the start time; write the first AI prompt as constraints in your own words (timebox, backend role, one code per order at the data level, snapshot on the order, re-validate at checkout, don't refactor cart/checkout) |
| First third | to ~1h | Setup; hit the break, fix it in one commit, note it; when the AI proposes the data model, review it against the brief and override at least one thing, noting the turn number |
| Halfway | ~1h30 | Lock scope; write the cut list; commit |
| Last third | to 3h | Checkout snapshot and order history; seeds and "Promo codes to try"; one or two request specs; mobile thin or mocked; stop |
| After work | untimed | SUBMISSION.md with the pushback in the first screen; PROMPTS.md header with turn references and the export; video, feature first; push to GitLab, add Reporters, test the video link logged out, reply on Wellfound |

**Pre-submission check:**
- [ ] Every package item present and populated with what its name promises: SUBMISSION.md at the root with all three fields and four headings; PROMPTS.md with the header and the raw export; video 5–10 min, unlisted, opens in an incognito window
- [ ] Veto-criterion proof is on the first surface the evaluator reads: the PROMPTS.md header names catches and overrides by turn; SUBMISSION.md's first screen mentions one pushback
- [ ] Every Critical and High requirement visibly met
- [ ] Every Matrix criterion has at least one quotable proof moment
- [ ] "Decisions and assumptions" has 6–10 entries in decision — alternative — why form, including validate-at-checkout and snapshot-on-order
- [ ] "What I didn't get to" lists what was cut on purpose, one reason each, ordered by value
- [ ] "Time spent" is a per-phase breakdown consistent with the commit timestamps
- [ ] Obstacle note exists: found / did / didn't do more because
- [ ] "Promo codes to try" covers percent, fixed, expired, disabled, invalid
- [ ] Video opens on the feature working (valid → invalid → checkout → order history) within 60 seconds, then decisions, trade-offs, cuts
- [ ] Commit log: 8–15 commits with intent in the messages; no squash; one `fix:` commit for the obstacle
- [ ] Mechanics: GitLab, private, @pbhepworth @skulikov112 @mshmykov as Reporter, repo link in the Wellfound reply, nothing public, `docs/evaluator-expectations/` not tracked
- [ ] Register matches the brief: warm, direct, honest about limits

**Saved to:** `docs/evaluator-expectations/` — expectations.md · brief.md (and `.gitignore` updated, when in a repo)
