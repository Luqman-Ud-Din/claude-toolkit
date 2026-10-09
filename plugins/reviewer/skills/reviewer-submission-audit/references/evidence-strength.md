# Evidence Strength

The scale for rating what a submission proves about each rubric criterion, with examples per criterion type, the echo test, and the anti-patterns that look like proof but are not.

## The scale

| Rating | Factor | Meaning |
|---|---|---|
| **Strong** | 1.0 | A reviewer would quote it in a positive decision. Specific, located, on a surface they read in the normal pass, and in the form the Lens's proof moment asked for. |
| **Adequate** | 0.7 | Present and real, but one of: generic in places, buried deeper than the normal pass, fewer instances than the Lens asked for, or missing the "why". The reviewer finds it if they look. |
| **Weak** | 0.3 | A trace exists but would not persuade: a claim without an address, a single thin instance, an echo of the brief's wording, or evidence on a surface the reviewer does not open. |
| **Missing** | 0 | Nothing a reviewer could point at. Includes evidence that exists only in the submitter's head, the conversation, or a file not in the submission. |

Two rules sit above the scale:

**An address or it is Weak.** Strong and Adequate require a location: file and heading, line range, commit hash, turn number, slide, cell range, page. If you cannot write the address, write Weak.

**Depth discounts.** The same evidence is one notch weaker if it sits where the reviewer reaches only by searching — a decisions list in the eighth section of a README, a push-back in turn 71 of a transcript with no header pointing at it, the metric on page four of an estimate. The reviewer's reading order and time budget come from the Lens persona; use them.

## The echo test

A submission that uses the brief's own vocabulary to *claim* a criterion, without the thing, is echoing. Reviewers wrote the brief; they recognise their sentences coming back. Echo reads as "read the rubric, did not do the work", which is worse than silence.

Signs of echo:
- The claim uses the brief's phrase nearly verbatim ("I focused on how I reason", "I directed the AI rather than just using it").
- No instance follows the claim.
- The claim sits in a header, summary, or cover note rather than next to the work.
- The same claim could be pasted into any submission to this brief.

An echo caps the rating at Weak. If an echo is the *only* evidence for the criterion, record it as Weak and name it as echo in the ledger; the gap list then says "replace the claim with the instance".

## Per criterion type

### Reasoning visible and defended

- **Strong**: decisions listed in the form decision / alternative considered / why / what would change it; six to ten of them when the brief delegated that many; the hardest one explained in the video or walkthrough with the losing option named; commit messages that carry intent.
- **Adequate**: decisions with a why but no named alternative; or three or four good ones where the brief delegated eight; or the reasoning present in commits but not surfaced in the notes.
- **Weak**: "Decisions: used percentage and fixed types; stored in a table." Facts, no why. Or "I made several trade-offs" with none named.
- **Missing**: no decisions section; or the heading with nothing specific under it.

### Human direction of a tool (AI-graded briefs)

- **Strong**: a header citing turns; at those turns, the human states constraints before asking, rejects a proposal with a reason, redirects a drift, cuts scope the tool proposed, catches an error; direction turns are at least one in five human turns; the first human turn is a plan, not a pasted brief.
- **Adequate**: two or three real direction moments findable in the transcript, but the header does not cite them, or the ratio is low, or the first turn is a paste.
- **Weak**: the header says "I changed direction a few times" with no turns; or one rejection on naming; or the transcript shows direction only on trivia.
- **Missing**: human turns are "ok / continue / looks good / yes" throughout; the tool chose the design and the scope; the header says "the AI was very helpful".

Cross-check: a header claim with no matching turn is Weak regardless of wording. A transcript whose timestamps do not match the commits is sanitised; discount one notch.

### Scoping and time judgment

- **Strong**: honest hours with a breakdown that matches commit timestamps; a cut list decided mid-work (visible in a commit or a dated note) with reasons; next steps ordered by value; nothing built beyond the brief's floor.
- **Adequate**: hours stated without breakdown; cut list present but decided at the end; or one over-delivered item explained.
- **Weak**: "about 3 hours"; "didn't get to: tests"; or over-delivery with no acknowledgement.
- **Missing**: no time stated; "everything is done"; the timebox exceeded and unmentioned.

### Obstacle handling

- **Strong**: found / did / why not more, in the notes, with the fix in its own commit, proportionate (a line or a function).
- **Adequate**: the fix is there and mentioned, but no "why not more", or buried in a feature commit.
- **Weak**: a fix with no note; or a note with no fix ("setup didn't work so I mocked it").
- **Missing**: the obstacle is not mentioned and no commit touches it. If the Lens said an obstacle was planted, Missing here means the submitter either did not find it or hid it; both are findings.

### Post-launch trust and reliability (client briefs)

- **Strong**: a named breakage mechanism and what prevents it; a cadence ("short update every Friday"); a bounded after-care window; recurring costs named; a verification step the client can do themselves.
- **Adequate**: cadence and window present, mechanism vague; or mechanism present, nothing about after launch.
- **Weak**: "I'll make sure it's reliable" / "feel free to reach out anytime".
- **Missing**: nothing after "delivered".

### Problem understanding (client briefs, applications)

- **Strong**: the first paragraph restates the client's problem in their terms, sharper than they put it, with their numbers.
- **Adequate**: restated, but generic or later than the first paragraph.
- **Weak**: "I understand you need a dashboard."
- **Missing**: opens with the submitter's credentials.

### Metric alignment (PRDs, grants, internal proposals)

- **Strong**: the metric in the first line or first paragraph, stated as the reason the work exists; each listed goal tied to it as an instrument; an attribution or measurement plan; a leading indicator named.
- **Adequate**: the metric named, but after the number, or without a measurement plan.
- **Weak**: the metric appears once in passing; the proxy (a counter, a completion) is treated as the goal.
- **Missing**: the metric never appears.

### Compliance (RFPs, forms, format-limited calls)

- **Strong**: a matrix or explicit "complies" per requirement; every limit measured and inside; mandated headings in the mandated order.
- **Adequate**: all requirements addressed, but a reviewer must hunt; limits inside by a margin that was not measured.
- **Weak**: one mandatory addressed only implicitly; a limit exceeded by a little.
- **Missing**: a mandatory absent; a limit exceeded by a lot. (Usually a gate failure, not a rating.)

### Communication and presentation

- **Strong**: the first five lines of the first surface carry the veto proof; order matches the brief's request; register matches; many small commits with intent.
- **Adequate**: the important thing is there but in paragraph three; or the video order inverted but the content complete.
- **Weak**: formal report to a warm brief; one squashed commit; the demo at minute eight.
- **Missing**: the first surface is boilerplate; the reviewer cannot find the run path.

### Core function (gate)

Pass if the core flow the brief named works end to end and a reviewer can see it in under two minutes from the notes. Fail otherwise. Not weighted.

### Extension readiness

- **Strong**: one sentence in the notes about where the next thing plugs in, and no code for it.
- **Adequate**: the seam is visible in the code but unmentioned.
- **Weak**: the next thing half-built.
- **Missing**: a design that would need a rewrite for the extension the brief named.

### Community or stakeholder ownership (grants, co-design briefs)

- **Strong**: a named group, a dated relationship, their question quoted, a named custodian for each artefact after handover, a sample with the role split stated.
- **Adequate**: named group and relationship, handover generic.
- **Weak**: "the community" unnamed; "we will publish a report".
- **Missing**: the group appears only as users of the submitter's idea.

## Anti-patterns that look like proof

| Looks like | Is actually | Rate as |
|---|---|---|
| A long decisions section | Facts without alternatives | Weak |
| "I considered several approaches" | No approach named | Weak (echo) |
| A header listing tools used | Not direction | Irrelevant to the direction criterion |
| A transcript with one "no, rename that" | Direction on trivia | Weak |
| Many commits named "wip", "fix", "update" | No narrative | Weak for communication |
| A clean, polished transcript | Likely sanitised | Discount one notch; flag |
| "Time spent: ~3 hours" with a 9-hour commit span | Dishonest or unexplained | Weak for scoping; flag |
| A next-steps list of "add tests, refactor, improve UI" | Generic | Weak |
| Keywords from the rubric in the cover note | Echo | Weak |
| A risk section with one risk | The author's own risk restated | Weak |
| "We will open-source it" as a handover plan | Not a custodian | Weak |
| Price with no scope | Unbounded | Weak |
| A beautiful dashboard the brief said not to prioritise | Over-delivery | Scoping finding, not a credit |

## Writing the ledger entry

For every candidate:

```
### <criterion>
- Candidate: <what was found, one line>
  - Address: <file § heading / lines / commit / turn / slide / cell / page>
  - Strength: Strong | Adequate | Weak | Missing
  - Depth: first-pass | normal-read | search-only
  - Echo: yes | no
  - Anti-pattern: <name, if one applies>
  - Note: <one line, why this rating>
```

Keep every candidate, including the ones that do not count; the report takes the best per criterion, and the post-mortem wants to know what else was there.
