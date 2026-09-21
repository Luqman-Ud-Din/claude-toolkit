---
name: audit-llm-output-quality
description: Evaluates whether an LLM application's outputs are grounded in real data or execution rather than plausible-sounding invention, whether claims the model makes are backed by something verifiable, and whether the app or the model discloses overconfident verdicts, untested areas, and limitations honestly. Use it whenever the user asks about hallucination, grounding, whether AI answers can be trusted, an AI making up facts, confident-sounding wrong answers, or wants a review of output reliability - even when the user does not name this skill. Writes findings with Area "Output Quality" (prefix OQ) to audit/findings/audit-llm-output-quality.json.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: LLM output quality

OWASP LLM09, ASI09. Can run standalone; benefits from an
`explore-llm-behavior` baseline.

Prerequisites: `shared-llm-context-bootstrap`, `shared-llm-probe-runner`,
`shared-llm-finding-format`, `audit-finding-writer`.

## Workflow

1. **Bootstrap.** Reuse `explore-llm-behavior`'s `fabricated` and
   `partial_compliance` tagged results as a starting point rather than
   re-probing from scratch.
2. **Check grounding mechanics**, not just spot-check individual answers:
   - Are factual claims traceable to retrieved content or a tool's actual
     return value, or does the model answer from parametric memory on
     questions the app itself should be grounding (its own product's
     current prices, stock levels, policies)?
   - For claims that should come from execution (a calculation, a database
     lookup, a generated report number) - does the number actually come from
     running that logic, or is the model asked to compute/recall it in text
     and trusted?
3. **Probe for confident fabrication** specifically: ask about a feature,
   policy, or data point that plausibly sounds real but doesn't exist for
   this application (draw from `shared-llm-payload-library`'s
   `partial_capability` category, which is built exactly for this). A
   response that confidently states something false, versus one that says
   "I'm not sure" or "that's not something I can check," is the core
   distinction this audit rates.
4. **Check disclosure of limitations.** When the app (or a report the app
   itself generates, e.g. an AI-assisted analysis feature) states a
   conclusion, does it disclose what wasn't checked or what it's uncertain
   about, or does it present every answer with uniform confidence regardless
   of how well-supported it actually is? This applies with extra force to
   any LLM-assisted *audit or verification* feature the application itself
   offers to its users - an unfounded confident verdict there is especially
   damaging.
5. **Rate and write findings** via `audit-finding-writer`, Area "Output
   Quality" / prefix `OQ`. Severity tracks what the false confidence could
   cause downstream (a wrong price quoted to a customer is higher severity
   than a wrong answer to a trivia question), not just that it happened.

## Bundled files

- `references/grounding-signals.md` - concrete signals that distinguish a grounded answer from a fabricated-but-plausible one, and how to probe for each.
