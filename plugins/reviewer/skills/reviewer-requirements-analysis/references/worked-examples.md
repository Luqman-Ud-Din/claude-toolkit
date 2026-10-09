# Worked Examples

Three documents from different archetypes, each with the analysis this skill should produce and the veto it should find. One (the take-home) has a real outcome on record. Use these to calibrate depth, and to check that your readings of different documents arrive at *different* vetoes for document-specific reasons.

The vetoes here are, respectively: **process visibility** (a transcript that shows a human steering), **post-launch trust** (durability plus reachability), and **an unstated metric** (the number the project exists to move). Nothing about the method changed between them; the documents did.

## Contents

1. Technical take-home — promo codes feature (real rejection on record)
2. Freelance client brief — Shopify analytics dashboard
3. Internal PRD — saved replies for a support inbox
4. What the three have in common

---

## 1. Technical take-home — promo codes (real outcome)

### The document (abridged; meta-sentences intact)

A hiring take-home for a backend or mobile role. A small shopping app (Rails API + React Native) needs a promo-code feature: shoppers apply a code on the cart, see the discount, and the order reflects what they paid; marketing needs percentage and fixed codes, end dates, a manual off-switch, one code per order, and "a way to try out a few working codes — how you do that is up to you."

Meta-sentences, nearly all of them:

> "This is a product brief, not a spec, on purpose. … Wherever that happens, make the decision you'd make if this were shipping to real customers, then tell us what you decided and why. We don't have a hidden checklist of right answers. What we care about is how you reason."
> "Timebox: about 2–3 hours of hands-on work. Writing notes and recording the video don't count toward that. Please don't go much over. Deciding what fits in the time is part of the exercise, so tell us what you'd do next if you had more."
> "Use AI. We expect it, because that's how our team works. Any tools are fine. We're interested in how you direct them, not in whether you used them."
> "Treat it like an existing codebase. We don't promise that everything runs cleanly out of the box. If you run into something that's broken, fix it or work around it, and tell us what you found and what you did about it."
> "Commit as you go. Your real history is more useful to us than one squashed commit."
> Deliverables: a private repo; **PROMPTS.md** — "all of the AI prompts you used … If your tool can export the whole session, include that export. We'd rather see the raw session than a cleaned-up one. At the top, add a few lines covering which tools you used, the moments where the AI got something wrong, and the places where you changed direction."; a 5–10 minute **video** — "First show the feature working. Then walk us through what you built and why: your key decisions, the trade-offs you made, what you chose not to do"; **SUBMISSION.md** with mandated headings: How to run · Promo codes to try · Decisions and assumptions · What I didn't get to, and what I'd do next.
> "Expect questions about your decisions and your prompts, and we may extend the feature together."

### What the submitter did

Read it as a feature spec. Built a clean promo-code model, apply/remove endpoints, a race-safe per-code usage limit (which the reviewers later praised), clear error messages, order persistence. The AI session was productive; PROMPTS.md held the export with a short header.

### The actual rejection

> *"The code itself was careful (the race-safe usage limit stood out), but the session mostly shows the AI proposing and you approving the next step, and we'd have liked to see more of your own reasoning steering it, for example reshaping or pushing back on its design and scope."*

### The analysis the skill should produce

**Phase 0.** Technical take-home, hiring filter, three engineer-reviewers who would be teammates, ~1 hour each. Warm first-person voice: a team that wants a colleague.

**Phase 2–3, the count.** *Reasoning / tell us why*: six sentences across four sections. *AI direction*: four sentences across three sections, plus two mandated PROMPTS.md headings, plus the interview preview. *Scoping / time*: four. *Obstacle*: two. *History*: one. *Code quality*: zero. *Tests*: zero. *UI*: zero. Communication imperatives ("tell us" ×6, "walk us through", "write it down", "add a few lines covering") outnumber build imperatives roughly 3:1.

**Phase 4, persona.** *"Everyone hands me a working promo feature now; the tool can write one. What I can't tell from the code is whether this person would push back on me in a design review. So I open PROMPTS.md first and skim the human turns."*

**Phase 5, rubric.**

| Criterion | Weight | Conf. | Failing looks like |
|---|---|---|---|
| Human direction visible in the session | 30% | Stated | Approval-only transcript; empty "changed direction" header |
| Reasoning visible and defended | 25% | Stated | Decisions without alternatives or why |
| Scoping under the timebox | 15% | Stated | Overrun, or no cut list |
| Obstacle noticed, handled, reported | 10% | Stated | Silent fix, or rewrite, or gave up |
| Core flow works (gate) | 10% | Stated | Can't apply a code and see a total |
| Communication (notes, commits, video order) | 5% | Strong | Squashed commit; video opens on code |
| Code quality | 5% | Inferred, tiebreaker | — |

**Veto: human direction of the AI.** Stated as a value, reinforced by two mandated headings that assume it happened, previewed as an interview topic, backed by "raw session." Four surfaces, one criterion. Found by counting — not because take-homes "usually" grade this.

**Phase 6, required-to-exist events.** The PROMPTS.md headings demand ≥1 caught error and ≥1 override; "Decisions and assumptions" demands 6–10 entries; "What I didn't get to" demands a cut list decided mid-session; the obstacle sentence demands a found/did/why-not-more note. None can be retrofitted.

**Phase 9, verdicts.** Plan followed: *"Clear thinking, pushed back in the right places, scoped honestly. Bring them in."* Feature-spec reading: the real rejection, nearly verbatim.

### The gap

The submitter allocated roughly 80% of effort to code and 20% to communication; the rubric was the inverse. Every signal was stated in plain text; none was labeled as a rubric. The specific miss was reading the mandated PROMPTS.md headings as *sections to write* rather than *events to cause*, so the events never happened and the header had nothing to say.

**Lesson:** when a document tells you what to write about, it is telling you what to do.

---

## 2. Freelance client brief — Shopify analytics dashboard

### The document (abridged)

A marketplace post, $1,500 fixed, "Intermediate," 20–50 proposals, posted three days ago.

> "We run a mid-size Shopify store … selling home fitness gear. We are drowning in spreadsheets. Every Monday I spend 4 hours pulling numbers from Shopify, our ad accounts (Meta + Google) and Klaviyo into a Google Sheet so I can see what's actually making money."
> Feature list: revenue/orders/AOV by period; ad spend and ROAS per channel; Klaviyo email revenue; top 10 products; refund rate. "It should update itself. I don't want to click anything on Monday morning except 'open'."
> "Honestly I don't care what it's built with. We tried a freelancer last year who built something in Looker Studio that broke every time Shopify changed something and then he stopped answering messages. So what I actually need is something that keeps working, and someone who will tell me if it's going to break."
> "I'm not technical. Please don't send me a list of frameworks. Tell me what you'd build, roughly how long, and what you'd need from me to get started."
> "Must have: done at least one Shopify integration before (show me). Nice to have: experience with Klaviyo API."
> "To make sure you read this, start your proposal with the name of a fitness product you'd sell to someone who hates the gym."
> "Timeline: I'd love to have this before our Black Friday push. That's about 5 weeks out. I'll pick someone by end of this week."

### The analysis the skill should produce

**Phase 0.** Client brief; the buyer is a non-technical owner-operator reading at ~30 seconds per proposal; hard filter; decision within days. Scars visible: fragility and ghosting.

**Phase 2–3, the count.** *Durability / keeps working*: four sentences (the Looker story, "keeps working," "update itself," "don't click anything"). *Reachability / won't ghost*: two ("stopped answering," "someone who will tell me"). *Plain language*: two. *Three mandated answers*: one sentence, three required-to-exist parts. *Show, don't claim*: one, marked "must have." *Stack*: explicitly ungraded. *Visual polish*: zero. Two gates planted: the attention filter and "(show me)."

**Phase 4, persona.** *"If your first line isn't a fitness product you didn't read this; no real Shopify thing to look at, same. I already paid for a dashboard that fell over and watched the guy stop replying, so I'm reading for whether you'll still answer me in February."*

**Phase 5, rubric.**

| Criterion | Weight | Conf. | Failing looks like |
|---|---|---|---|
| Opener is a fitness product | Gate | Stated | "Hi, I'm a full-stack developer with 8 years…" |
| Shopify integration shown, not claimed | Gate + 15% | Stated | "Extensive Shopify experience," nothing to click |
| Keeps working + will warn you | 30% | Stated | No sentence about after launch or platform changes |
| Plain-language what / how long / what I need, in order | 20% | Stated | Tool list; "let's hop on a call" |
| Problem restated in their terms | 15% | Strong | "I can build your dashboard," none of their numbers |
| Timeline before the push; starts next week | 10% | Stated | "Done in 3 days" or "free in two weeks" |
| Price at $1,500 with scope and running costs | 10% | Inferred | Lowball, upsell, or no scope |

**Veto: post-launch trust** — durability plus reachability. The sentence introduced by "what I actually need" names exactly those two things, and the post's only story is about losing both. A proposal that is technically fluent and silent on what happens after launch fails on the thing the client said they actually need.

**Phase 6, proof moments.** Word one: a home-fitness product. Lines 2–4: a named Shopify build with a link. "What I'd build": one plain sentence on what breaks (platform retires API versions) and what you do before it does. Closing: a cadence ("short update every Friday"), a bounded after-care window, recurring costs named even if zero. Three labeled parts in the client's order.

**Phase 7, traps.** Filter placed late in the post to catch skimmers. "Simple" and $1,500 against four live integrations: a scope-definition test. Fixed fee against "tell me whenever it's going to break" with no end date: the exact collision that produced the last ghosting — bound it in writing. Attribution: Meta, Google and Klaviyo each claim the same sales; the client will notice on the first Monday. "Before the Black Friday push" is ~Nov 8, not Nov 27; land a week earlier and parallel-run against their Sheet.

**Phase 9, verdicts.** Plan followed: *"Started with the product, showed me a real Shopify build, explained it in English, and was the only one who said what happens when Shopify changes — this one."* Standard proposal: *"Another developer who listed twelve tools and didn't start with a fitness product — closed after two lines."*

### What generalizes

The veto was found in a sentence the client marked themselves ("what I actually need") and confirmed by the one story in the post. No archetype prior was needed. The attention filter and "(show me)" are gates, not vetoes: they decide whether the proposal is read, not whether it wins.

---

## 3. Internal PRD — saved replies for a support inbox

### The document (abridged)

Draft v2, "ready for eng review." Owner: a PM. Eng lead: **TBD**. Target Q1.

> *Background:* "~1,800 tickets a week … agents re-typing the same five or six answers … Average first-response time has crept from 2h10 to 3h40 over the last two quarters while ticket volume grew 30%. Leadership has asked us to get FRT back under 2h30 by end of Q1 without adding headcount."
> *Goals:* insert a saved reply in under 3 seconds; replies shared across the team; managers can see which are used most.
> *Non-goals:* AI-generated replies (Q2); routing changes; rich media ("text and links only for v1").
> *Requirements R1–R6:* personal CRUD; search + one-click insert; manager promotes to team scope; `{{customer_first_name}}` / `{{order_number}}` placeholders filled from the ticket; per-insert usage counter visible to managers; Cmd/Ctrl+Shift+R opens the panel.
> *Open questions (4):* replace or append on insert (design "leans append"); folders/tags or search-only; team reply ownership when the author leaves; empty placeholder — leave, blank, or block.
> *Success metrics:* "TBD — Priya to confirm with Support leadership."
> *Dependencies:* composer refactor landing mid-January; "the panel should build on the new composer, not the old one." Serializer change "small."
> *Risks (one entry):* if the refactor slips, block or build against the old composer and migrate. "Need a call by Jan 10."
> *Timeline:* design handoff Jan 6; **eng estimate by Jan 9**; beta with 5 agents Feb 3; GA Feb 24.
> "Please review and leave comments inline. We'll go through open questions in Thursday's sync."

### The analysis the skill should produce

**Phase 0.** Internal PRD; the PM reads line by line within a day; design and the refactor owner read their parts; leadership never reads the PRD — they see the estimate and, in April, the FRT number. Confirmation mode for the PM (she wants a yes), inverse for leadership (in April they hunt for why the target was missed).

**Phase 2–3, the count.** *The metric*: four mentions in Background (2h10 → 3h40, +30%, "back under 2h30 by end of Q1," "without adding headcount"), zero under "Success metrics." The absence is the loudest signal in the document. *Composer dependency*: three mentions across Dependencies, Risks, Timeline, with a dated decision one day after the estimate is due. *Restraint*: "simple" ×2, "for v1" ×2, three explicit non-goals. *Open questions*: four, scheduled. *Ownership*: "Eng lead: TBD." Fixed dates precede the estimate request — the estimate is a fit-to-date, not a discovery. Architecture, tests, search sophistication: zero.

**Phase 4, personas (two).** PM: *"Leadership handed me a number and this feature is my plan. By Jan 9 I need a number I can defend, a yes/no on Feb 3, a position with eng cost on each open question, and someone to find what I missed before leadership does."* Leadership: *"We don't care about saved replies; we care whether 3h40 becomes 2h30, and whether you can show it was this."*

**Phase 5, rubric.**

| Criterion | Weight | Conf. | Failing looks like |
|---|---|---|---|
| Names the real metric; prices how impact is measured | 25% | Strong | Estimate never mentions FRT |
| Estimate fits the fixed dates, or names the cut | 20% | Strong | One number, no assumptions |
| Composer call made with information by Jan 10 | 15% | Stated | "Let's see where Tom is on the 10th" |
| Positions with eng cost on all four open questions | 15% | Stated | "Whatever design prefers" |
| Scope restraint; phase-2 seams without phase-2 code | 10% | Stated | Proposes folders, rich text, an AI hook |
| Risk register beyond the PM's one entry | 10% | Inferred | Only the composer risk |
| Engagement form: inline, owns the TBD slot | 5% | Stated | A chat reply: "~4 weeks, looks fine" |
| R1–R6 on the new composer at beta | Gate | Stated | Panel on the old composer |

**Veto: the unstated success metric.** "Success metrics: TBD" is the hole; Background fills it four times. An estimate that prices R1–R6 and never says "first-response time" tells the PM the reviewer did not read the first paragraph, and leaves leadership with no way to know in April whether it worked. Everything else on the table is additive.

**Phase 6, proof moments.** First inline comment and first line of the estimate: "This exists to get FRT from 3h40 to under 2h30 by Mar 31 without headcount; here is how we'll know." A measurement plan: per-ticket insert events (not R5's counter, which proves adoption, not time), a cohort comparison, a leading indicator for the Feb 3 beta. A two-track estimate split by dependency so a refactor slip costs days, not the beta. A position on each open question with a cost. Risks the PM did not write: a raw `{{order_number}}` reaching a customer; "manager" undefined so R3 is secretly a permissions feature; an empty library on beta day one; the metric is mostly queue time and this feature cuts handle time.

**Phase 7, defects in the stated requirements.** R6's Cmd/Ctrl+Shift+R is browser hard-reload in Chrome, Firefox and Edge — a mis-hit discards the draft, inverting the 3-second goal. R5 counts inserts where the goal is a time metric. "Manager" is never defined. Promotion semantics (copy or flip?) are unspecified.

**Phase 9, verdicts.** Plan followed: *"Named the number, split the estimate by the dependency, came to Thursday with positions and costs — taking it upstairs as-is."* Requirements-only estimate: *"Priced a panel. We'll find out in March whether it did anything."*

### What generalizes

The PRD never says "we care about the metric." The veto was found by counting (four mentions in one section), by absence (an empty template heading), and by the archetype (PRD authors have a number from above). The requirements-defect audit found things the PM had not — which is the differentiator in a confirmation-mode review.

---

## 4. What the three have in common

| | Take-home | Client brief | PRD |
|---|---|---|---|
| Veto | Process visibility | Post-launch trust | Unstated metric |
| How it was found | Repetition (4 surfaces) + mandated headings | A self-marked sentence ("what I actually need") + the only story | Repetition in Background + absence under the template heading |
| What the submitter would naturally optimize | Code quality | Stack and features | Accurate sizing of R1–R6 |
| Mentions of that in the document | 0 | 0 ("don't care") | 0 |
| Required-to-exist events | PROMPTS.md headings; decisions list; cut list | Three labeled answers; access list; a shown sample | Positions on four open questions; a risk register |
| Gate (separate from veto) | Core flow works | Attention filter; "(show me)" | R1–R6 on the new composer |

Three documents, three different vetoes, one method. If your analyses of different documents keep landing on the same veto, you are reading the case, not the document.
