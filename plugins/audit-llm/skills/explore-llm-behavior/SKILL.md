---
name: explore-llm-behavior
description: Black-box observation of a running LLM/agentic application, for reviews without full source access - records how the app responds to normal, ambiguous, out-of-scope, and "feature doesn't exist" requests, and any visible guardrail behavior, without judging whether the behavior is good or bad. Use it whenever the user wants to see how an AI feature actually behaves from the outside, has no source access but wants an AI app reviewed, asks to poke at a chatbot or agent to see what it does, or wants a behavioral baseline before or after a change - even when the user does not name this skill. Writes audit/llm/explore/explore-llm-behavior.json and feeds every audit-llm-* skill that probes a live app.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Explore: LLM behavior

The only explore skill that touches a live system, so it is the one place in
the explore phase that goes through `shared-llm-probe-runner`'s authorization
gate - never skip it because "this is just exploration, not an attack".

Prerequisites: `shared-llm-probe-runner`, `shared-llm-payload-library`,
`shared-llm-handoff-contract`.

## Workflow

1. **Authorization first.** Confirm scope and target with
   `shared-llm-probe-runner` before sending anything.
2. **Send a representative spread**, not just adversarial payloads - this
   skill's job is a baseline, not a security test (that's the `audit-llm-*`
   skills' job, reusing this same map):
   - **Normal requests** - the app's stated core use cases.
   - **Ambiguous requests** - underspecified in a way a careful assistant
     should ask about or state an assumption for.
   - **Out-of-scope requests** - clearly outside what the app is for.
   - **"Feature doesn't exist" requests** - adjacent to a real feature but not
     actually supported (draw from `shared-llm-payload-library`'s
     `partial_capability` category).
   - **A couple of light guardrail probes** (a paraphrase-variant or two from
     the payload library) - enough to note visible guardrail behavior exists
     at all; leave the adversarial depth to `audit-llm-jailbreak-resistance`
     and `audit-llm-guardrails`.
3. **Record, don't judge.** For each: the exact prompt, the exact response
   (or a faithful summary if very long), and a neutral behavioral tag
   (answered / refused / asked for clarification / stated a limitation /
   fabricated an answer / other) - "fabricated an answer" is a factual
   observation about what happened, not a severity call; `audit-llm-output-quality`
   or `audit-llm-intent-grounding-and-adaptability` rates it.
4. **Write the map** to `audit/llm/explore/explore-llm-behavior.json`, plus the
   raw evidence file `shared-llm-probe-runner` already wrote - reference its
   path rather than duplicating the transcripts.
5. **Note anything that looks broken**, not just anything adversarial - a
   normal-use request that got a wrong or nonsensical answer is exactly the
   kind of finding this exploratory pass is positioned to catch first.

## Bundled files

- `references/behavior-tags.md` - the fixed set of behavioral tags and when each applies, so tagging is consistent across runs and across reviewers.
