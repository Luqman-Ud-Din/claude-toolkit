# AI-Era Signals

What reviewers are testing when a document mentions AI tools, and how to recognize the markers they look for in transcripts, prompts, and notes. Read this in Phase 4 for documents that permit, require, or forbid AI assistance.

## First: is AI direction actually graded here?

Before reading further, check the document's own count. AI direction is a **graded criterion** when the brief asks for transcripts, prompts, a session export, or a write-up of how the tool was used — those artifacts exist for no other reason. It is a **candidate veto** when the brief also phrases it as a value ("how you direct them", "your own reasoning", "where you changed direction") on two or more surfaces. It is a **tiebreaker at most** when the brief says "feel free to use AI" once and asks for nothing that would reveal how.

Finding "steer the AI" as the veto in a brief that mentions AI once and emphasizes something else ten times is a mis-read, and a costly one — the submitter will spend effort on a transcript nobody will open. Count first.

## The question behind an AI-graded brief

**Can the reviewer tell a human with opinions was steering?**

The thing a technical reviewer cannot learn from a résumé, a portfolio, or even a finished codebase is whether the candidate can *direct* a capable tool or merely *operate* it. A finished feature no longer proves judgment on its own, because the tool can produce a finished feature from a vague prompt. So reviewers who care about judgment move the test to the process: they ask for transcripts, prompts, session exports, and commit histories, and they read them for the human's voice.

When a brief does this, the phrases to look for are "how you direct them", "your own reasoning", "where you changed direction", "the moments where the AI got something wrong", "we'd rather see the raw session", "expect questions about your prompts". Each of those is the steering question in disguise.

## What "direction" looks like in a transcript

Reviewers skim a transcript for the ratio and character of human turns. They are not counting words; they are looking for whether the human's turns *carry information the AI did not already have.*

### Markers of human direction

- **Constraints before proposals.** The human states the shape of the solution before asking for it: "Extend the orders table, don't add a join table. One code per order is a DB constraint, not a UI check."
- **Rejections with reasons.** "No — that lets two codes stack if they're applied in the same request. Add a uniqueness constraint on (order_id) in promo_redemptions."
- **Scope cuts the AI did not suggest.** "Drop the admin screen. Seed via rake task. Note it in SUBMISSION as deferred."
- **Catching errors.** "You've computed the discount on the subtotal including tax. The brief says the order reflects what they actually paid — discount before tax."
- **Redirecting when the AI drifts.** "You're refactoring the cart serializer. Stop. That's not in scope; revert and stay on the promo endpoint."
- **Questions that change the design.** "What happens if the code expires between cart and checkout? Make the check happen at checkout, not at apply."
- **Choosing not to use the AI** for a piece and saying why: "I wrote the migration by hand — it's three lines and I want to be sure of the index."
- **Prompts that encode the brief's priorities**: "Timebox is 3h. Prefer the smallest change that satisfies the four shopper requirements. Flag anything that would take more than 20 minutes."

### Markers of passive use

- Human turns are mostly "ok", "continue", "yes", "looks good", "go ahead", "do that", "next".
- The AI proposes the data model, the endpoint shape, the error handling strategy, and the scope — and the human accepts each.
- No rejection in the entire session.
- The only human-authored content is the initial paste of the brief.
- Scope grows because the AI suggested additions and nothing cut them.
- Errors in the AI's output make it into the final code (reviewers check the transcript against the diff).
- The transcript has been cleaned to remove the human's hesitation — which also removes the human's voice.

### The ratio heuristic

A reviewer's rough rule: in a healthy session, at least one in four or five human turns should carry a constraint, a rejection, a redirection, or a scope decision in the human's own words. Below that, the session reads as approval-driven even if the final code is excellent. (The take-home case in `worked-examples.md` had careful code and a session the reviewers described as "the AI proposing and you approving.")

## What the mandated headings are really asking

When a brief requires a PROMPTS.md, session export, or similar with headers like:

- **"Which tools you used"** — low weight; they are checking honesty, not choice.
- **"The moments where the AI got something wrong"** — a required-to-exist event. They expect at least one caught error, because they know the tool makes them. A submission that reports none is reporting that the human was not checking.
- **"The places where you changed direction"** — a required-to-exist event. They expect the human to have overridden the AI on design or scope at least once. None means the human had no opinion, or did not express it.
- **"We'd rather see the raw session than a cleaned-up one"** — a test of authenticity. Sanitized transcripts are noticed; the reviewer may compare the transcript to the commit timestamps.

The evidence plan must schedule these events. They cannot be retrofitted. The way to make them happen is to work the way a lead works with a strong junior: write the constraints before asking, review every proposal against the brief before accepting, and keep a running note of each catch and each override with its turn number.

## Prompt quality as a secondary signal

When a brief says "expect questions about your prompts", the reviewer will also read the prompts themselves for:

- **Specificity**: does the prompt carry the brief's constraints (timebox, one code per order, existing codebase, role focus)?
- **Sequencing**: does the human break the work into steps that reflect a plan, or ask for "implement promo codes" in one go?
- **Verification**: does the human ask the AI to check its own work against the brief, or run tests, or explain a trade-off?
- **Restraint**: does the human stop the AI from doing more than asked?

Good prompts read like instructions to a capable junior engineer who has not read the brief: they transfer context, set boundaries, and ask for a reviewable unit of work.

## When AI is forbidden

"Please complete this without AI assistance" makes independence the veto. The reviewer will look for idiosyncratic style, the ability to explain every line live, and the absence of tell-tale generated patterns. Any evidence of undisclosed AI use is disqualifying regardless of quality. The evidence plan here is the inverse: hand-written, commented in the candidate's own voice, with a note on where they looked things up.

## When the document is silent on AI

Assume AI use is tolerated and will not be examined, but the steering question is still in the reviewer's head when they read the commit history and notes. Do not volunteer a transcript, but make sure the notes and commits carry human judgment anyway. If the code has the uniform polish and generic structure of unedited generation, a reviewer will wonder; a decision log in the candidate's voice answers the wonder.

## Converting this into proof moments

| Reviewer question | Surface | Proof moment |
|---|---|---|
| Did the human set direction? | Transcript, first ten turns | Human-written plan or constraints before the first "implement" |
| Did the human reject anything? | Transcript | ≥2 explicit rejections with reasons |
| Did the human catch an error? | Transcript + PROMPTS.md header | ≥1 catch, referenced by turn number |
| Did the human cut scope? | Transcript + SUBMISSION.md | ≥1 cut the AI did not propose |
| Can the human explain the prompts? | Interview | Prompts specific enough to defend |
| Is the transcript authentic? | Transcript vs. commits | Timestamps and messiness consistent |

## How to tell the user this without discouraging AI use

The point is not to use AI less. The point is to be visible in the session. Users sometimes hear "show direction" as "do more by hand". The better framing: *work the way you would with a strong junior — give them context, review their proposals against the brief, say no when they drift, and keep notes on where you did.* Those notes are the submission.
