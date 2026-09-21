---
name: shared-llm-payload-library
description: Curated test inputs for LLM/agentic application security testing, grouped by category - direct and indirect prompt injection, jailbreak techniques (roleplay, encoding, multi-turn escalation, persona attacks), system prompt extraction, paraphrase and synonym variants of a blocked request, and partial-capability / "feature doesn't exist" cases. This is a shared building block, not run standalone - audit-llm-prompt-injection, audit-llm-jailbreak-resistance, audit-llm-intent-grounding-and-adaptability, explore-llm-behavior, and propose-llm-eval-suite all draw test cases from here instead of inventing ad hoc payloads per audit. Use it whenever a skill needs a representative, categorized set of adversarial or edge-case test inputs for an authorized security review, red-team pass, or eval suite - never to generate novel, more effective attack content than what's cataloged here.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Shared: LLM payload library

A fixed catalog beats an improvised one for two reasons: coverage (every audit
uses the same categories, so results are comparable across skills and across
runs of the same app over time) and restraint (this skill's job is to hand
callers well-known, illustrative test categories for *authorized* defensive
testing - not to research or generate new bypass techniques on demand).

## Categories (`references/payloads.json`)

| Category | What it tests | Consumed by |
|---|---|---|
| `direct_injection` | Explicit "ignore previous instructions" style overrides in user input | audit-llm-prompt-injection |
| `indirect_injection` | The same intent, hidden inside a document, web page, tool output, or image the model retrieves rather than typed by the user | audit-llm-prompt-injection, explore-llm-data-flow findings |
| `jailbreak_roleplay` | Persona/roleplay framing asking the model to act as an entity without the app's constraints | audit-llm-jailbreak-resistance |
| `jailbreak_encoding` | Obfuscation (base64, leetspeak, translation, token splitting) to slip a blocked request past a keyword filter | audit-llm-jailbreak-resistance, audit-llm-guardrails |
| `jailbreak_multiturn` | Gradual escalation across several turns rather than one obvious request | audit-llm-jailbreak-resistance |
| `system_prompt_extraction` | Requests aimed at getting the model to reveal its system prompt or internal configuration | audit-llm-jailbreak-resistance |
| `paraphrase_variants` | Semantically identical requests reworded to test whether a guardrail keys on surface phrasing | audit-llm-guardrails, audit-llm-evals-and-red-teaming |
| `partial_capability` | Requests for something adjacent to a real feature, or a feature that doesn't exist, to test honest scoping | audit-llm-intent-grounding-and-adaptability |

Each entry in `payloads.json` has `{id, category, text, intent, expected_safe_behavior}` -
`expected_safe_behavior` is what a well-behaved application should do (usually
refuse, or state the limitation honestly), so a probe result can be graded
against it directly.

## Workflow for a consuming skill

1. Load `references/payloads.json` (or `scripts/payloads.py` for filtered
   access by category) rather than writing new payload text inline.
2. Select the categories relevant to the finding area being audited - don't
   send the whole library if only `jailbreak_roleplay` is in scope.
3. Send selected payloads through `shared-llm-probe-runner`, never directly.
4. When a category doesn't fit the application at hand (e.g. `indirect_injection`
   payloads for an app with no retrieval or tool-output path), say so and skip
   it rather than forcing an irrelevant probe.
5. **Extending the library**: when a new, useful test case comes up during an
   audit, add it back to `payloads.json` with the same shape so future audits
   benefit - don't let good test cases live only in one audit's throwaway
   notes.

## Bundled files

- `references/payloads.json` - the full catalog.
- `scripts/payloads.py` - loads and filters `payloads.json` by category; `python payloads.py --category jailbreak_roleplay` prints matching entries.
