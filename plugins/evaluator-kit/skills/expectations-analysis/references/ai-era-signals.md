# AI-Era Signals

What evaluators are testing when a document mentions AI tools, and how to recognize the markers they look for in transcripts, prompts, and notes. Read this in Phase 4 for documents that permit, require, or forbid AI assistance.

## First: is AI direction actually graded here?

Before reading further, check the document's own count. AI direction is a **graded criterion** when the brief asks for transcripts, prompts, a session export, or a write-up of how the tool was used — those artifacts exist for no other reason. It is a **candidate veto** when the brief also phrases it as a value ("how you direct them", "your own reasoning", "where you changed direction") on two or more surfaces. It is a **tiebreaker at most** when the brief says "feel free to use AI" once and asks for nothing that would reveal how.

Finding "steer the AI" as the veto in a brief that mentions AI once and emphasizes something else ten times is a mis-read, and a costly one — the submitter will spend effort on a transcript nobody will open. Count first.

## The question behind an AI-graded brief

**Can the evaluator tell a human with opinions was steering?**

The thing a technical evaluator cannot learn from a résumé, a portfolio, or even a finished codebase is whether the candidate can *direct* a capable tool or merely *operate* it. A finished feature no longer proves judgment on its own, because the tool can produce a finished feature from a vague prompt. So evaluators who care about judgment move the test to the process: they ask for transcripts, prompts, session exports, and commit histories, and they read them for the human's voice.

When a brief does this, the phrases to look for are "how you direct them", "your own reasoning", "where you changed direction", "the moments where the AI got something wrong", "we'd rather see the raw session", "expect questions about your prompts". Each of those is the steering question in disguise.

## What "direction" looks like in a transcript

Evaluators skim a transcript for the ratio and character of human turns. They are not counting words; they are looking for whether the human's turns *carry information the AI did not already have.*

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
- Errors in the AI's output make it into the final code (evaluators check the transcript against the diff).
- The transcript has been cleaned to remove the human's hesitation — which also removes the human's voice.

### The ratio heuristic

An evaluator's rough rule: in a healthy session, at least one in four or five human turns should carry a constraint, a rejection, a redirection, or a scope decision in the human's own words. Below that, the session reads as approval-driven even if the final code is excellent. (The take-home case in `worked-examples.md` had careful code and a session the evaluators described as "the AI proposing and you approving.")

## What the mandated headings are really asking

When a brief requires a PROMPTS.md, session export, or similar with headers like:

- **"Which tools you used"** — low weight; they are checking honesty, not choice.
- **"The moments where the AI got something wrong"** — a required-to-exist event. They expect at least one caught error, because they know the tool makes them. A submission that reports none is reporting that the human was not checking.
- **"The places where you changed direction"** — a required-to-exist event. They expect the human to have overridden the AI on design or scope at least once. None means the human had no opinion, or did not express it.
- **"We'd rather see the raw session than a cleaned-up one"** — a test of authenticity. Sanitized transcripts are noticed; the evaluator may compare the transcript to the commit timestamps.

The evidence plan must schedule these events. They cannot be retrofitted. The way to make them happen is to work the way a lead works with a strong junior: write the constraints before asking, review every proposal against the brief before accepting, and keep a running note of each catch and each override with its turn number.

## Prompt quality as a secondary signal

When a brief says "expect questions about your prompts", the evaluator will also read the prompts themselves for:

- **Specificity**: does the prompt carry the brief's constraints (timebox, one code per order, existing codebase, role focus)?
- **Sequencing**: does the human break the work into steps that reflect a plan, or ask for "implement promo codes" in one go?
- **Verification**: does the human ask the AI to check its own work against the brief, or run tests, or explain a trade-off?
- **Restraint**: does the human stop the AI from doing more than asked?

Good prompts read like instructions to a capable junior engineer who has not read the brief: they transfer context, set boundaries, and ask for a reviewable unit of work.

## When AI is forbidden

"Please complete this without AI assistance" makes independence the veto. The evaluator will look for idiosyncratic style, the ability to explain every line live, and the absence of tell-tale generated patterns. Any evidence of undisclosed AI use is disqualifying regardless of quality. The evidence plan here is the inverse: hand-written, commented in the candidate's own voice, with a note on where they looked things up.

## When the document is silent on AI

Assume AI use is tolerated and will not be examined, but the steering question is still in the evaluator's head when they read the commit history and notes. Do not volunteer a transcript, but make sure the notes and commits carry human judgment anyway. If the code has the uniform polish and generic structure of unedited generation, an evaluator will wonder; a decision log in the candidate's voice answers the wonder.

## Converting this into proof moments

| Evaluator question | Surface | Proof moment |
|---|---|---|
| Did the human set direction? | Transcript, first ten turns | Human-written plan or constraints before the first "implement" |
| Did the human reject anything? | Transcript | ≥2 explicit rejections with reasons |
| Did the human catch an error? | Transcript + PROMPTS.md header | ≥1 catch, referenced by turn number |
| Did the human cut scope? | Transcript + SUBMISSION.md | ≥1 cut the AI did not propose |
| Can the human explain the prompts? | Interview | Prompts specific enough to defend |
| Is the transcript authentic? | Transcript vs. commits | Timestamps and messiness consistent |

## How to tell the user this without discouraging AI use

The point is not to use AI less. The point is to be visible in the session. Users sometimes hear "show direction" as "do more by hand". The better framing: *work the way you would with a strong junior — give them context, review their proposals against the brief, say no when they drift, and keep notes on where you did.* Those notes are the submission.

## Gauging receptiveness

The sections above ask *whether AI direction is graded*. Phase 4b asks a wider question that every input needs answered, including ones that never mention AI: **where does this evaluator stand on AI-assisted work, and what should the user say when asked how much they used?** Opinion is split — some evaluators expect AI and read its absence as inefficiency, others read any AI as a shortcut — and guessing wrong in either direction costs the submission.

### Signals and where they push the estimate

| Signal in the input | Pushes receptiveness | Typical band |
|---|---|---|
| Requires AI, or asks for transcripts / prompts / a session export | Up, and AI use is graded | 80–95% |
| "Use whatever tools you like", "AI welcome", lists AI tools in the stack | Up | 70–85% |
| AI mentioned once, neutrally ("feel free to use AI") | Slightly up | 55–70% |
| Silent on AI, modern tech context (startup, product team, AI-adjacent role) | Neutral | 45–60% |
| Silent on AI, traditional context (academic, legal, government, craft, writing-centric) | Slightly down | 30–45% |
| Stresses originality, "in your own words", "we want to see *you*", personal voice | Down | 20–40% |
| Warns about generic or templated responses, "we can tell" | Down, and AI use may be checked | 15–35% |
| Forbids AI, requires a declaration of no AI use, live or proctored work | Strongly down; AI is a veto | 0–10% |

Combine signals; the most specific one wins over the archetype default. The user's own context counts — a recruiter's message that says "our team ships with Copilot daily" outweighs a job post that is silent. Note the evaluator's tone too: a founder who writes in short, AI-forward startup register reads differently from a committee writing in procurement language.

### Recommended AI involvement

How much of the work to do with AI follows from the band *and* from what is graded. At high receptiveness, using AI heavily is fine as long as the human direction is visible (see the markers above). At neutral, use AI for the mechanical parts and keep the parts the evaluator will read most closely — the reasoning, the cover note, the decisions — in the user's own voice. At low receptiveness, keep AI to what any careful professional would use (spell-check, lookup) and say so if asked. When AI is forbidden, there is no involvement to recommend.

### "How much AI did you use?" — the recommended answer

The answer is the user's **actual** share, stated plainly. What the skill recommends is the *framing* and the *band this evaluator will accept*, never a number to claim that does not match the work. A stated percentage is checkable — against a transcript, a commit history, a writing style, a live follow-up — and an evaluator who is wary of AI is precisely the one who checks. An honest 70% framed around the decisions the user made lands better than an implausible 20%.

Give the user:

- **The band**: e.g. "~60% — the scaffolding and tests; the design and trade-offs were mine."
- **The sentence**: one or two lines they can say or write, leading with the human decisions and verification, then the tool use.
- **The mismatch warning**, when it applies: if the user's real usage is well above what the evaluator will accept, the fix is to change the process (redo the parts the evaluator will scrutinise by hand, or decide not to apply), not to understate.

### Confidence

State it as a percentage with a reason. Explicit statements about AI give high confidence (80%+). Indirect signals (originality language, tone, archetype) give medium (50–70%). Silence gives low (under 50%): say "no signal; defaulting to the <archetype> norm" rather than presenting a precise-looking number as knowledge.
