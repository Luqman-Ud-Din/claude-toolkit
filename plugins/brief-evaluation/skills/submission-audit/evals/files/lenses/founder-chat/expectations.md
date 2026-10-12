---
kind: evaluator-lens
version: 1
written: 2026-10-07
document: "Chat with Daniel Okafor (Tallyroom), LinkedIn"
archetype: message-thread
brief: brief.md
veto: "You went quiet and I had to find out for myself where it stood — that is exactly what our last two contractors did."
first_surface: "the reply message, first sentence"
submission_form: message reply
ai_receptiveness: 85
---

# Evaluator Lens — Chat with Daniel Okafor (Tallyroom), LinkedIn

## 1. Description

Daniel Okafor, founder of a 6-person booking + payments product for small fitness studios, needs someone to take over work from a contractor leaving at the end of October (msg 1 — Daniel).
The trial is a paid, ~6-hour prototype of the class waitlist promotion flow: when someone cancels, the next waitlisted person gets the spot automatically and a text, which may be logged instead of sent (msg 3 — Daniel; msg 6 — Daniel — "no real texts needed, just log them").
The waitlisted person must not be charged through Stripe until they actually get the spot, on Next.js + Postgres (Supabase) (msg 3 — Daniel).
Two people cancelling at the same time must never cause a double charge, and Daniel will test that first (msg 8 — Daniel — "That's the scenario I'll test first"). The user promised to handle it (msg 9 — me).
The submission is a reply message with the prototype link, a Loom of 5 min max that his non-technical cofounder can follow (what was built, what comes next), and an account of how the user works with AI and where they did not trust it (msg 10 — Daniel).
The prototype is due Fri 10 Oct. The full feature now targets mid-January instead of Black Friday (msg 11 — Daniel, which overrides msg 3 — "Ideally live before Black Friday").
The decision is whether to hire the user for the work after the trial. What weighs most is whether the user tells him early when something goes sideways (msg 4 — Daniel — "the bigger thing for me").

## 2. Context understanding

- **Type / archetype:** message-thread (LinkedIn DM); in effect a paid trial task wrapped in a client conversation, so it is a hybrid of a client brief and a take-home — msg 1, msg 6 — Daniel
- **Evaluator:** Daniel, founder, self-described as not technical (msg 4 — "I'm not technical enough to spot it myself"); a second evaluator is his cofounder, who watches the Loom only and "isn't technical either" (msg 10). One candidate in a paid trial, so there is no comparison set. He compares the user with the two contractors who disappeared (msg 4) and the one who is leaving (msg 1).
- **Decision:** hire for ongoing work (the full waitlist feature by mid-January, plus "a few things", msg 1) · **Filter or confirmation:** confirmation. He approached the user (msg 1) and agreed to pay for the trial (msg 6), so he is looking for a reason to say yes. One trust failure still ends it, given his history (msg 4).
- **Constraints:** ~6 paid hours (msg 6 — "Timebox it to about 6 hours, I'll pay your rate for 6"); due Fri 10 Oct (msg 11); Next.js + Postgres (Supabase) + Stripe (msg 3); texts logged, not sent (msg 6); no UI polish (msg 7); Loom ≤ 5 min (msg 10); delivered as a reply in this thread with links.
- **Stakes and tone:** short, warm, candid founder messages, often sent in pairs a minute apart (msg 3/4, msg 6/7). Daniel tells you what he worries about directly ("honestly the bigger thing for me"). A plain, short, direct reply matches. A formal report or a jargon-heavy changelog does not.
- **User's context:** freelance full-stack developer, approached because of a post about an inventory sync tool (msg 1). Already in the thread: asked to see the codebase before giving a timeline (msg 5), proposed the paid trial (msg 5), and **promised in msg 9 to handle concurrent cancellations** ("Got it, I'll make sure concurrent cancellations are handled."). The deliverable to audit is the user's Friday reply to Daniel, sent with a link to the prototype repo branch and a Loom link. Today is Tue 7 Oct, three days before the deadline.

## 3. Evaluator intent

**In their words (first person):** Two contractors in a row went dark on me for days, and I couldn't tell anything was wrong until it was too late. I can't read the code, so what I'm really buying is someone who tells me early and plainly where things stand. The first thing I'll do is cancel two bookings at once, because a studio owner got double-charged and I don't want to hear about that again. If the Loom makes sense to my cofounder and you're straight about where you didn't trust the AI, you're the one.

*Cofounder (Loom only):* Can I understand in five minutes what was built, whether it works, and what happens next, without the jargon?

**What they actually want:** a contractor he can trust without being able to check the work himself. The working prototype is how he tests that trust. The evidence: msg 4 calls communication "the bigger thing for me", and the scar tissue is the line about the last two contractors. Every later deliverable is a channel he can understand without code: a Loom for a non-technical cofounder (msg 10), an account of where the user *didn't* trust the AI (msg 10), and one scenario he will run himself (msg 8).

**Weightiest themes:**
- Proactive, legible communication; don't disappear — ×3 across 2 messages — msg 4 — "tells me early when something is going sideways"; msg 10 — Loom for a cofounder "who isn't technical either", "where you didn't trust them"
- No double charge on concurrent cancellations — ×2 in one message plus the user's own promise — msg 8 — "make sure that can't happen", "the scenario I'll test first"; msg 9 — me
- Charge only when promoted — msg 3 — "shouldn't be charged until they actually get the spot"
- Transparency about AI use and judgment — msg 10 — "how you work with them and where you didn't trust them"
- Timing as a moving target — msg 3 → msg 11 (Black Friday → mid-January; prototype Fri 10 Oct)

**Not graded (or tiebreaker only):** UI polish (msg 7 — "Don't worry about UI polish, our designer will redo it anyway"), real SMS delivery (msg 6 — "just log them"), feature completeness beyond the promotion flow, code elegance he cannot read, test coverage for its own sake.

## 4. Explicit requirements

| # | Requirement | Reference | Impact if missed | Severity |
|---|---|---|---|---|
| E1 | Two simultaneous cancellations never cause a double charge. This is the first scenario Daniel tests, and the user promised it | msg 8 — Daniel — "please make sure that can't happen in yours. That's the scenario I'll test first"; msg 9 — me — "I'll make sure concurrent cancellations are handled" | Fails his first test and breaks a promise the user made in writing. The trial ends there | Critical |
| E2 | Tell him early when something goes sideways; do not disappear | msg 4 — Daniel — "I need someone who tells me early when something is going sideways" | The stated reason the last two contractors failed; the veto | Critical |
| E3 | Prototype delivered by Fri 10 Oct | msg 11 — Daniel — "The prototype is still due this Friday (10 Oct) though" | A late prototype from a contractor on trial confirms his fear | Critical |
| E4 | Waitlist promotion flow: on cancellation the next waitlisted person gets the spot automatically and a text (logged, not sent) | msg 3 — Daniel; msg 6 — Daniel — "no real texts needed, just log them" | The core feature is missing | High |
| E5 | The waitlisted person is not charged until they actually get the spot (Stripe) | msg 3 — Daniel — "shouldn't be charged until they actually get the spot" | Charges people who never got a class, the same harm as the double charge | High |
| E6 | Loom of 5 min max: what you built and what you'd do next | msg 10 — Daniel — "a short Loom (5 min max) walking through what you built and what you'd do next" | A required deliverable is missing; the cofounder has nothing to see | High |
| E7 | Loom understandable by a non-technical cofounder | msg 10 — Daniel — "I'll forward it to my cofounder who isn't technical either" | The second evaluator cannot follow it; it reads as the opaque contractor again | High |
| E8 | Say what you used, how you work with Cursor/Claude, and where you didn't trust them | msg 10 — Daniel — "tell me what you used … how you work with them and where you didn't trust them" | An unanswered direct question; he reads it as evasive | High |
| E9 | ~6-hour timebox, paid for 6 | msg 6 — Daniel — "Timebox it to about 6 hours, I'll pay your rate for 6" | Large overrun billed: a budget surprise. Overrun not billed: unpaid work that hides the real cost | Medium |
| E10 | Built in their stack, on their repo: Next.js + Postgres (Supabase) + Stripe | msg 3 — Daniel; msg 6 — "I'll give you repo access today" | A prototype outside the stack can't be carried forward | Medium |
| E11 | Full feature now targets mid-January, not Black Friday. Any plan or next step must use the new date | msg 11 — Daniel — "let's aim the real version at mid-January", overriding msg 3 — "Ideally live before Black Friday" | Planning for Black Friday shows the user missed the change | Medium |
| E12 | No UI polish | msg 7 — Daniel — "Don't worry about UI polish" | Hours spent on something he said not to do | Low |

## 5. Implicit requirements

| # | Requirement | Reference | Impact if missed | Severity | Confidence |
|---|---|---|---|---|---|
| I1 | Proactive, plain-language status before he has to ask: lead the reply with the result, name anything that went sideways or is unfinished, and ideally send a short heads-up before Friday | "our last two contractors disappeared for days at a time" — msg 4 — Daniel; "I'm not technical enough to spot it myself" — msg 4 | The veto: a working prototype delivered silently still repeats the old pattern | Critical | Stated |
| I2 | Make the concurrency fix checkable by a non-technical founder: a script, button or step-by-step that fires two cancellations at once and shows one promotion and one charge | "That's the scenario I'll test first when I try it" — msg 8; "I'm not technical enough to spot it myself" — msg 4 | He can't run the test he announced, or runs it wrongly and can't tell the result | High | Strong |
| I3 | Reply confirms the msg 9 promise explicitly and says how it was verified, not just "handled" | "Got it, I'll make sure concurrent cancellations are handled." — msg 9 — me | An unconfirmed promise reads as forgotten | High | Strong |
| I4 | Say what happens when the promoted person's charge fails (declined card, off-session authentication) or they never confirm: who gets the spot next, and when | "shouldn't be charged until they actually get the spot" — msg 3; the charge happens later than signup (inference) | The same studio complaints come back as a lost spot or a stuck waitlist | Medium | Inferred |
| I5 | The AI account is about judgment: concrete places the AI was wrong or not trusted (e.g. the race condition, Stripe idempotency) and how the user checked it | "where you didn't trust them" — msg 10 | A generic "I used Claude for boilerplate" answers the wrong question | High | Stated |
| I6 | "What you'd do next" is a concrete plan to mid-January and names what the user needs from him (codebase review done, estimate, decisions) | "what you'd do next" — msg 10; "mid-January" — msg 11; "I'd want to look at the codebase before giving a timeline" — msg 5 — me | No next step means no hire. Ignoring the msg 5 promise of a timeline leaves a gap | High | Strong |
| I7 | Report hours actually spent against the 6 and what was cut to fit | "Timebox it to about 6 hours" — msg 6 | Hidden overrun or silent scope cuts are exactly the "going sideways" he wants told early | Medium | Strong |
| I8 | Acknowledge the timing change and what it means. Mid-January is after the outgoing contractor leaves at the end of October | msg 11; "leaving at the end of October" — msg 1 | Shows the user tracks his changes; missing it reads as answering only the latest message | Medium | Inferred |
| I9 | Logged texts visible somewhere he can see them (log output, admin list) so he can verify "got a text" without SMS | "just log them" — msg 6 | He can't see that the notification part works | Low | Inferred |

## 6. AI receptiveness

| | |
|---|---|
| **Receptiveness** | 85% — Expects |
| **Is AI use examined?** | graded — msg 10 — Daniel — "we use Cursor and Claude every day here, I just want to know how you work with them and where you didn't trust them" |
| **Recommended AI involvement** | ~60–80% of the code — scaffolding, Supabase/Stripe wiring, test harness. The concurrency design (locking/idempotency) and its verification, the reply message, and the Loom narration should visibly stay human |
| **If asked "how much AI did you use?"** | Your actual share, e.g. "~70%" — "Claude/Cursor wrote most of the code; I designed how promotions are locked so two cancellations can't charge twice, didn't trust its first version of that (it [name the real flaw]), and checked it myself with a test that fires two cancellations at once." State your real share; if it is far from this band, change how you work, not what you say. |
| **Evidence** | msg 10 — the team uses Cursor and Claude "every day"; the question is about *how* and *where you didn't trust them*, not whether. The non-technical evaluator (msg 4) relies on the user's judgment about where the AI is wrong |
| **Confidence** | 85% — explicit, first-person statement of daily AI use and a direct question about workflow and distrust |

## 7. Understanding

### Matrix

| Criterion | Weight | Conf. | Failing looks like |
|---|---|---|---|
| Proactive, plain communication; tells him early, doesn't disappear | 30% | Stated | Silence until Friday evening, then a link and "let me know what you think" |
| No double charge on concurrent cancellations, shown and testable by him | 25% | Stated | He cancels two bookings at once and someone is charged twice, or he can't tell whether it worked |
| Promotion flow works; charge only on getting the spot; texts logged | 12% | Stated | Waitlisted person charged at signup; no log of the text |
| Loom ≤ 5 min a non-technical cofounder can follow: built + next | 10% | Stated | 9-minute code walkthrough of files and functions |
| How you work with AI, including where you didn't trust it | 10% | Stated | "Used Claude for some boilerplate," no example of distrust |
| Concrete next step aimed at mid-January | 8% | Strong | "Happy to continue!", or a plan for Black Friday |
| Timebox respected and reported | 5% | Strong | 14 hours of work, unmentioned or billed without warning |

**Not graded (or tiebreaker only):** UI polish (msg 7), real SMS (msg 6), features beyond promotion, code style.

**Simulated verdict (if the plan is followed):** *"He told me midweek where he was, the first line said the double charge can't happen and I checked it myself, my cofounder got the Loom, and he told me where he didn't trust Claude — let's do January."*
**Simulated verdict (link-and-Loom with no status):** *"Probably works, but I heard nothing all week and I can't tell if the double charge is fixed — same feeling as last time."*

### Deal breakers

**Veto criterion:** You went quiet and I had to find out for myself where it stood — that is exactly what our last two contractors did. The evidence: msg 4 — Daniel calls it "the bigger thing for me" and gives the scar tissue ("disappeared for days at a time", "tells me early when something is going sideways"). msg 10 repeats it as deliverables he can understand without code (a Loom for a non-technical cofounder, "where you didn't trust them"). The concurrency scenario (msg 8) is the Critical explicit test he runs first. Failing it, or failing to tell him plainly whether it holds, triggers the veto.

- **Concurrent cancellations** (planted obstacle, announced) — msg 8; promise msg 9 — two cancellations racing can promote the same waitlisted person twice or create two charges. Guard the promotion in one Postgres transaction with a row lock (e.g. `FOR UPDATE SKIP LOCKED`) or a uniqueness constraint, and give the Stripe charge an idempotency key per waitlist entry. Prove it with a test that fires both at once.
- **Charge timing** (planted obstacle) — msg 3 — "shouldn't be charged until they actually get the spot": the charge happens later than signup, so an off-session charge can fail. Decide and state what happens next.
- **Changed requirement** (ignored-change trap) — msg 3 → msg 11 — Black Friday is gone and mid-January is the target. A next step that still says Black Friday shows the user didn't read msg 11.
- **Over-delivery** — msg 6 "about 6 hours"; msg 7 "Don't worry about UI polish" — polishing UI, sending real SMS, or building admin screens burns the timebox on things he said not to grade.
- **Unanswered question** — msg 10 — "tell me what you used … where you didn't trust them" is a direct question. Leaving it out of the reply and the Loom is an unforced miss.
- **Blocks-review mechanics** — the branch link must be accessible to him (repo access, pushed branch, not a local-only branch), the Loom link must be shareable without sign-in so the cofounder can open it, and the reply must go out in this thread by Fri 10 Oct.
- **Tone** — msg 3/4/6/7 are short and candid. A long formal report, or a technical changelog he cannot read (msg 4 — "not technical enough"), mismatches the register.
- **Loom length** — msg 10 — "5 min max" is a hard limit. Going over, or making it a code tour, fails the cofounder audience.

### Deal makers

**Differentiators:**
- A short status message before Friday (e.g. Wed/Thu: "on track; concurrency test passing; one question") demonstrates the veto criterion before he can ask — msg 4
- A one-command or one-click way for Daniel to run the double-charge test himself, with the expected result in plain words — msg 8
- A specific AI-distrust story tied to the concurrency or Stripe code — msg 10

**Decisions to make / questions to ask** (ordered by stakes; asking is possible in the thread):
- **Concurrency guard** → Decide: lock the waitlist row in one transaction plus a Stripe idempotency key per entry — "Two cancellations at the same moment can only ever promote and charge one person each; I tested it by firing both at once."
- **When the charge happens** → Decide: save the card at waitlist signup without charging; charge only at promotion — "Nobody pays until they're in the class."
- **Failed charge on promotion** → Assume and state: skip to the next person after one failed attempt (or a short confirmation window), log a text to both — "If a card fails, the spot goes to the next person instead of sitting empty." Ask whether studios want a confirmation window.
- **Hours** → Decide: stop near 6; report the actual hours and what was left out — "I spent ~6h; I left X out on purpose to stay in the timebox."
- **Next step** → Decide: propose a concrete step toward mid-January (e.g. a short call next week, an estimate for the real version after the codebase review promised in msg 5, and the handover from the contractor leaving end of October) — "Here's what I'd do between now and mid-January, and what I need from you."
- **Ask (1):** should a promoted person have to confirm the spot before being charged, or is automatic promotion final? (msg 3 says "automatically")

### Submission package

| # | Item | Form | Must contain |
|---|---|---|---|
| P1 | Reply message to Daniel | LinkedIn reply in this thread, short, his register | First sentence states the result and answers his most recent ask: the prototype is done and the double-charge case cannot happen (msg 8/9, veto + concurrency). Then: anything that went sideways or is unfinished; hours spent vs 6; acknowledgement of mid-January (msg 11) |
| P2 | Link to the prototype | Repo branch link he can open | Waitlist promotion flow, charge only on promotion, logged texts, plus plain steps (or one command) for him to run the two-cancellations test and what he should see |
| P3 | Loom | ≤ 5 min, shareable link, non-technical narration | What was built (shown working, including the concurrency test), what comes next; understandable by his cofounder (msg 10) |
| P4 | How I worked with AI | A few lines in the reply and/or a segment of the Loom | Tools used (Cursor/Claude or others), what they did, and where the user did not trust them and checked by hand (msg 10) |
| P5 | Concrete next step | One or two lines closing the reply | A dated proposal toward mid-January (call, estimate, start date), not "let me know" |

**Proof per criterion:**

| Criterion | Surface | Proof moment | Anti-pattern |
|---|---|---|---|
| Proactive communication | P1 (and a mid-week message) | "Done — and one thing to flag: …" in the first two lines; hours reported | A bare link; problems only discoverable in the code |
| No double charge | P1 first sentence + P2 test steps + P3 | "I fired two cancellations at the same instant 50 times; each time one person was promoted and charged once" | "Concurrency should be handled" |
| Promotion + charge on promotion + logged texts | P2 + P3 | Demo: cancel → next person promoted → log line "Text to Sam: you got the 7am spot" → single charge | Charge at waitlist signup; no visible text log |
| Loom for the cofounder | P3 | Plain words: "When someone cancels, the next person gets the spot and a text, and is only charged then" | Scrolling through files and function names |
| AI workflow and distrust | P4 | "Claude's first version checked the waitlist and then promoted in two steps — two cancellations could slip between them; I rewrote it as one locked step" | "I used AI for boilerplate" |
| Next step to mid-January | P5 | "Call Tue 14 Oct to agree on scope; estimate for the January version by Fri 17 Oct" | "Happy to keep going!" / a Black Friday plan |
| Timebox | P1 | "~6h spent; left out X on purpose" | Silent 12-hour build |

**Required-to-exist events:**
- "make sure that can't happen" / "I'll make sure concurrent cancellations are handled" (msg 8, msg 9) — a concurrency test actually run, with a result to quote — before recording the Loom
- "where you didn't trust them" (msg 10) — at least one real moment of rejecting or correcting AI output, noted when it happens — during the build
- "what you'd do next" (msg 10) — a plan against mid-January — before writing the reply
- "tells me early" (msg 4) — a status message before the deadline if anything slips, ideally regardless — by Thu 9 Oct

**Pre-submission check:**
- [ ] Every package item present and populated with what its name promises
- [ ] Veto-criterion proof is on the first surface the evaluator reads
- [ ] Every Critical and High requirement visibly met
- [ ] Every Matrix criterion has at least one quotable proof moment
- [ ] First sentence of the reply states the result, including that the double charge cannot happen
- [ ] The msg 9 promise is confirmed with how it was verified
- [ ] Daniel can run the two-cancellations test himself from the steps given
- [ ] No charge before promotion; failed-charge behaviour stated
- [ ] Loom ≤ 5:00, shareable without sign-in, no jargon; covers built + next
- [ ] AI account names a specific place the AI was not trusted
- [ ] Next step dated and aimed at mid-January; no Black Friday framing
- [ ] Hours vs 6 reported; no UI polish time
- [ ] Branch pushed and accessible to Daniel; sent in this thread by Fri 10 Oct
