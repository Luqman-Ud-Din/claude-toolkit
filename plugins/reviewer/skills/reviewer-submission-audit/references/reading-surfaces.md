# Reading Surfaces

How to open each kind of thing a submission can be, in the way the reviewer will, and what proof looks like in each. The reviewer does not read a submission the way its author does — they open the cheapest surface first, hunt for what they care about, and stop when they have a verdict. Reproduce that.

## Contents

1. Reading order by archetype
2. Code repository
3. Commit history
4. Transcript / prompts file
5. Notes: README, SUBMISSION, DESIGN, RESULTS
6. Prose document (md, docx, pdf)
7. Spreadsheet (xlsx, csv)
8. Slides (pptx, pdf)
9. Proposal, cover letter, application email
10. Q&A answers and forms
11. Estimate, plan, PRD review
12. RFP / tender response
13. Grant / fellowship application
14. Design and image files
15. Data analysis and notebooks
16. Surfaces you cannot read
17. Tools

---

## 1. Reading order by archetype

The Lens's archetype and persona set the order. Defaults when the Lens does not say:

| Archetype | Order the reviewer opens things |
|---|---|
| Technical take-home | cover note / SUBMISSION / README → mandated transcript or prompts file → commit log → video (or its script) → code → tests |
| Interview exercise | the answer as spoken → the notes |
| Job application | hard-requirement scan → embedded filters → first paragraph → evidence matched to the post → the rest |
| Client brief / freelance | first line → first paragraph → answers to embedded questions → price → samples → everything else |
| PRD review / estimate | the summary line → the number and its assumptions → risks and dependencies → scope boundaries → design |
| Internal ticket / PR | PR description → diff summary → tests → the diff |
| RFP | compliance matrix → mandatory sections → scored sections in published weight order → appendices |
| Grant | alignment with each stated priority → outcomes and measurement → budget against narrative → team and samples |
| Academic assignment | rubric lines in order → format compliance → the argument |
| Hackathon | the demo → the pitch → the repo |
| Design brief | the piece itself → the rationale → the constraints checklist |

The first item in the row is `first_surface` unless the Lens overrides it. Everything in Phase 2 depends on getting this right.

## 2. Code repository

**Open**: the file tree first (`ls -R` or `git ls-files`), then whatever the notes point at, then the rest. Reviewers rarely read every file; they read the files the notes name and the ones that touch the brief's core requirement.

**Proof lives in**: the module that implements the core flow; the test that exercises the brief's stated edge case; the constraint enforced at the right layer (DB vs UI); the seam left for the named future extension; the absence of the thing the brief said not to build.

**Checks**:
- Core flow traceable end to end from the entry point the notes name.
- The brief's explicit behaviours each have a locatable implementation (file:line) — list them.
- The planted obstacle, if the Lens named one: is there a fix, is it proportionate (a line or a function, not a rewrite), is it in its own commit.
- Over-delivery: files or modules the brief did not ask for (an admin UI, a generic engine). Each is a scoping cost.
- Conventions: does new code match the existing codebase's style, or did the submitter bring their own? "Treat it as an existing codebase" grades this.
- Tests: present for the stated edge cases? Test names mirror acceptance criteria? Do not grade test *volume* unless the Lens does.
- Runnable from the notes: do the README steps work on a clean checkout? Run them. If a dependency is missing, say which; a README that cannot be followed is a finding against the run-path requirement. Read them for completeness too (env vars, seeds, ports, a `__main__`).
- Run the tests. Count them against the brief's stated edge cases, and note any that pass trivially (a concurrency test that runs serially under a transactional fixture tests nothing).
- Run the verification harness the brief mandated, if one exists, and compare its output with what the notes claim. If none exists and the brief mandated one, that is a Missing on whichever criterion it served.
- Probe the invariant. When the brief states one ("never admits N+1", "totals reconcile", "never over-charges"), spend a few minutes trying to break it with the cheapest adversarial input you can construct — two concurrent workers, a boundary value, a duplicate key. Record the command, the input, and the result as evidence. State the consequence of any defect in the brief's own terms (over-admits vs over-rejects; loses data vs rejects; wrong total vs slow), because that is how the reviewer classifies it and because "a bug" and "the disqualifying bug" are different gaps.

**What is not proof**: elegance, cleverness, performance beyond what the brief asked. Note it in one clause if it is there; weight it as the Lens does.

## 3. Commit history

**Open**: `git log --format='%h %ad %s' --date=iso` for the narrative; `git log --stat` for shape; `git show <hash>` for anything the notes cite.

**Proof lives in**: messages that carry intent ("enforce at DB level, not UI — support creates orders by hand"), a visible course correction (a revert or a "drop X" commit), the obstacle fix as its own commit, timestamps that match the claimed time.

**Checks**:
- Count and span. One commit, or three, is "squashed" regardless of what the notes say. Ten-plus small commits with intent in the message is the narrative the brief asked for.
- Timestamps vs claimed hours. First-to-last span and gaps. A claimed 3h with a 9h span, or commits at 02:00, is a finding — not necessarily disqualifying, but the notes must explain it. Commits dated in the future, or outside the window the user said they worked in, are a finding too: reviewers read dates, and a wrong clock looks like a rewritten history.
- Tracked files that should not be there: the handoff folders (`docs/reviewer-requirements/`, `docs/submission-audit/`), credentials, `.env`, scratch notes to self. `git ls-tree -r HEAD --name-only | grep -E 'docs/(reviewer-requirements|submission-audit)'` is a one-line check. A tracked Lens is blocks-review.
- Does any commit message mention a decision or a rejection? Those are the reasoning proof moments in commit form.
- Does the history show the planted obstacle being hit and handled?
- Sanitisation: if a transcript exists, do its turn times and the commit times tell the same story?

## 4. Transcript / prompts file

**Open**: identify the format first — a Claude Code export, a Cursor chat export, a ChatGPT share, a hand-pasted log. Find the human turns. `scripts/inventory.py --transcript <file>` counts them and the short-approval ones.

**Proof lives in**: human turns that carry information the tool did not have — constraints stated before asking, rejections with reasons, redirections when the tool drifts, scope cuts the tool did not propose, errors caught, decisions to do something by hand and why. Each is a proof moment with a turn number.

**Checks**:
- Ratio: human turns that direct (constrain, reject, redirect, cut, catch) over all human turns. Under roughly one in five reads as approval-driven even if the final work is good.
- The first human turn: a plan with constraints, or the brief pasted plus "implement this"?
- Any rejection at all? Any scope cut? Any caught error? Find each by turn number — these are the required-to-exist events for AI-graded briefs.
- The mandated header, if the brief asked for one: does it cite turn numbers? Does the transcript at those turns show what the header claims? A header that says "changed direction on naming" is Thin.
- Sanitisation: a transcript with no hesitation, no dead ends, and a human who never types a typo is cleaned. Cross-check against commit timestamps.
- Echo: "I made sure to direct the AI carefully" in the header, with no turns to point at.

**When the brief forbids AI**: the proof inverts — idiosyncratic style, visible hand-edits, the submitter's own voice in comments. Uniform generated polish with no decision log is the finding.

## 5. Notes: README, SUBMISSION, DESIGN, RESULTS

**Open**: top to bottom, timing the first five lines separately. The first five lines are what the reviewer reads before deciding whether to read the rest.

**Proof lives in**: the mandated headings, each substantive; decisions in the form decision / alternative / why; honest time with a breakdown; a cut list with reasons; an obstacle note as found / did / why not more; the run path in one command; the extension seam in one sentence.

**Checks**:
- Every mandated heading present, in the mandated order, with content that names specifics. Count entries under "decisions"-type headings; three generic ones is Thin, six to ten with alternatives is Present.
- The first five lines carry the veto proof (role, time, the headline decision, the obstacle) — or they carry boilerplate.
- "Time spent" is a number with a breakdown, not "about 3 hours".
- "What I'd do next" is ordered by value and specific, not "add tests, refactor".
- Register matches the brief's voice.
- Leftover template placeholders (`<link>`, `<your name>`, `TBD`).

## 6. Prose document (md, docx, pdf)

**Open**: `.md` and `.txt` with `Read`; `.pdf` with `Read` (text) or the pdf skill (scanned); `.docx` with the docx skill or `python-docx`. Extract headings first to compare against any mandated structure, then read.

**Proof lives in**: the mandated sections, each addressing its point; proportion — section lengths tracking the rubric weights; the required claim in the first paragraph (the metric, the problem restated, the thesis); measurable statements where the brief asked for measurable ones.

**Checks**:
- Word or page count against any stated limit. Measure it (`wc -w`, page count from the PDF); do not estimate. Over the limit is a gate failure in most archetypes.
- Headings vs the brief's required points: present, in a findable order, named recognisably.
- Allocation: words per section against rubric weights. A 30%-weighted section with 8% of the words is a finding.
- The first paragraph: does it carry what the Lens says the first surface must carry?
- Generic vs specific: names, dates, numbers, quotes vs adjectives. Reviewers count specifics.
- Placeholder text, tracked changes, comments left in (docx), draft watermarks.
- Citations or references where the archetype expects them.

## 7. Spreadsheet (xlsx, csv)

**Open**: `.csv` with `Read`; `.xlsx` with the xlsx skill or `openpyxl` (load twice: once with `data_only=False` to see formulas, once with `data_only=True` to see values). List sheets, then headers, then the shape of each.

**Proof lives in**: a summary sheet or block that answers the brief's question directly; formulas rather than pasted values where calculation is the point; labelled assumptions; units stated; totals that reconcile.

**Checks**:
- Does the spreadsheet answer the question the brief asked, somewhere the reviewer will look first (first sheet, top-left)?
- Formulas vs hardcoded numbers in cells that should calculate. A budget with typed totals is a finding.
- Error values (`#REF!`, `#DIV/0!`, `#N/A`), hidden sheets, hidden rows, external links that will break.
- Constraints from the brief applied: a budget cap, a percentage ceiling on a category (compute it), a required line item.
- Assumptions labelled and placed where a reader finds them.
- Column headers and units present; a reviewer should not have to guess what a column is.

## 8. Slides (pptx, pdf)

**Open**: `.pptx` with the pptx skill or `python-pptx` (titles, body text, speaker notes per slide); exported PDF with `Read`.

**Proof lives in**: slide 1 stating the thesis; the order the brief requested (demo before explanation, problem before solution); speaker notes carrying the reasoning the slides compress; slide count within the limit.

**Checks**:
- Slide count vs limit. Measure.
- First slide: the claim, or a title and a logo?
- Requested order honoured.
- One idea per slide; text density; whether the reviewer could follow without the presenter (if the deck is read, not presented).
- Notes field used for the reasoning, if the archetype reads notes.

## 9. Proposal, cover letter, application email

**Open**: as plain text, and read the first line, then the first paragraph, as separate steps with a verdict after each.

**Proof lives in**: the first words (any embedded attention filter, exactly); the problem restated in the client's language sharper than they put it; the embedded questions answered in the order asked, labelled; an access or needs list specific enough to prove experience; a durability or reliability mechanism named; a cadence and a bounded support window; a price with included / excluded / recurring; two matched samples, each with one line on relevance.

**Checks**:
- Attention filter: literally the first characters? A greeting before it fails as written.
- First paragraph: about the client's problem, or about the submitter?
- Every embedded question answered, in order, findable by heading.
- Hard requirements ("must have X — show me"): shown with a link or named case, or merely claimed?
- Stack or framework lists where the brief said not to.
- Length: readable in the seconds the persona gives it?
- Price in range; scope stated; post-launch stated.
- Register matched; no disparagement of previous vendors.

## 10. Q&A answers and forms

**Open**: pair each question with its answer. If the form has character limits, measure each answer against its limit.

**Proof lives in**: every question answered; each answer specific to the question (not a pasted paragraph); length proportional to the question's weight; a concrete example per claim; the hardest question answered as fully as the easiest.

**Checks**:
- Unanswered, partially answered, or answered-with-the-wrong-question items.
- Generic answers that would fit any question of that type.
- The same paragraph reused across answers.
- Claims without an instance ("I have strong experience with X" vs "at Y I did X, which Z").
- Character or word limits respected.

## 11. Estimate, plan, PRD review

**Open**: the summary or the number first, then assumptions, then everything else — because that is the order the PM reads.

**Proof lives in**: the success metric named in the first paragraph; the listed goals tied back to it as instruments; a measurement or attribution plan; the estimate as a range with assumptions; a dependency decision with a rule; positions on every open question with a cost; a risk register beyond the author's; non-goals acknowledged; inline comments where asked for.

**Checks**:
- Does the first line name the metric the project exists to move?
- Is the number conditional on the dependencies the PRD listed, or unconditional?
- Every open question has a position, not a question back.
- Nothing proposed that the non-goals exclude.
- Risks: more than the PRD's own; each with a mitigation.
- Defects in the stated requirements flagged (a shortcut that collides with a browser default, an undefined role).

## 12. RFP / tender response

**Open**: the compliance matrix (or its absence) first; then each mandatory section for a clear "complies"; then scored sections.

**Proof lives in**: a matrix mapping every numbered requirement to a response location; explicit compliance statements; page lengths proportional to published weights; past-performance references matched to this scope with contactable names; a risk section that names real risks.

**Checks**:
- Matrix present and complete.
- Every "shall" addressed as a statement, not buried in prose.
- Page and format limits measured.
- References: number, relevance, contactability.
- Price within the stated ceiling, itemised.

## 13. Grant / fellowship application

**Open**: the narrative's headings against the call's numbered points; then the budget against the call's ceilings; then the sample and letters.

**Proof lives in**: a named community or partner with a dated relationship; the question in their words; a handover plan naming who keeps what; measurable outcomes (changes, not activities); a budget that matches the narrative and respects category caps; a work sample with the role split the call asked for.

**Checks**:
- Word limit measured.
- Each numbered point findable under a heading.
- Allocation vs published weights.
- Budget caps computed (tools as a share of total; time to participants).
- The call's "not looking for" list: any item present?
- Sample's two-sentence role split present and honest.
- Letters attached if the call invited them.

## 14. Design and image files

**Open**: images with `Read` (they render). Check against the brief's stated constraints, not against taste.

**Proof lives in**: the constraint checklist met (format, dimensions, brand elements, audience); the rationale document if one was asked for; the piece doing the job the brief named.

**Checks**:
- Format, size, aspect, file type as specified.
- Every named constraint visibly honoured.
- The brief's goal legible in the piece without the rationale.

## 15. Data analysis and notebooks

**Open**: `.ipynb` with `Read` (cells and outputs); scripts as code; outputs as data.

**Proof lives in**: a stated question and a stated answer; the method described; reproducibility (seeds, versions, a run command); outputs that match the claims; caveats stated.

**Checks**:
- Does the first cell or paragraph say what question is being answered?
- Can the result be reproduced from what is there?
- Are claimed numbers present in outputs?
- Are limitations stated?

## 16. Surfaces you cannot read

A video you cannot watch, a live link you cannot open, a demo that needs credentials, a physical artefact. Do not pass them silently.

- Record them in the inventory as `unverified`.
- Audit the stand-in: a video's script, outline, or chapter list; a link's description in the notes; screenshots.
- Check what *can* be checked: is the link where the brief said to put it? Is it unlisted/private as required? Does the notes file say what the video covers, in the requested order?
- Ask the user for the stand-in if none exists, and say in the report that the surface was not verified and what the reviewer will see there that you could not.

## 17. Tools

| Surface | Tool |
|---|---|
| Text, markdown, code, csv, json, PDF text, images, notebooks | `Read` |
| Scanned PDF | pdf skill (OCR) |
| `.docx` | docx skill, or `python-docx` for headings and paragraphs |
| `.xlsx` | xlsx skill, or `openpyxl` with `data_only` both ways |
| `.pptx` | pptx skill, or `python-pptx` for titles, body, notes |
| Repository | `git log --format='%h %ad %s' --date=iso`, `git log --stat`, `git show`, `git ls-files` |
| Word and line counts | `wc -w`, `wc -l`; `scripts/inventory.py` |
| Transcript statistics | `scripts/inventory.py --transcript` |
| Placeholders left in | `scripts/inventory.py` (flags `<…>`, `TODO`, `TBD`, `lorem`, `{{`) |
