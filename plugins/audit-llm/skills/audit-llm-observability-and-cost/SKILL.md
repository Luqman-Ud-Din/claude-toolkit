---
name: audit-llm-observability-and-cost
description: Reviews whether every model call, tool call, and agent decision is traced, whether production quality signals (refusal rate, fallback rate, latency, error rate) are monitored, and assesses latency, token cost, prompt-caching usage, and whether cost/duration estimates shown to users are accurate. Use it whenever the user asks about LLM observability, tracing agent decisions, monitoring an AI feature in production, token cost, prompt caching, latency of AI features, or whether a shown cost/time estimate is accurate - even when the user does not name this skill. Writes findings with Area "Observability & Cost" (prefix OC) to audit/findings/audit-llm-observability-and-cost.json.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: LLM observability and cost

OWASP LLM10 (overlaps `audit-llm-resource-limits`'s cost-budget angle - that
skill checks caps exist; this one checks whether cost/latency/quality is
*visible* at all, and whether user-facing estimates are honest).

Prerequisites: `shared-llm-context-bootstrap`, `shared-llm-finding-format`,
`audit-finding-writer`.

## Workflow

1. **Bootstrap.** Use `explore-llm-architecture` for the loop structure -
   observability gaps are easiest to name precisely against known steps.
2. **Tracing coverage.** Is every model call, tool call, and (for a
   multi-step agent) each intermediate decision logged with enough detail to
   reconstruct what happened after the fact (prompt/response, tool
   arguments/results, timing), ideally via a standard mechanism
   (OpenTelemetry GenAI semantic conventions, a vendor LLM observability
   tool) rather than ad hoc prints? Cross-reference
   `audit-logging-and-observability` for the general logging review; add
   only what's specific to LLM/agent call structure here.
3. **Production quality signals.** Is anything tracking, in production, the
   things that indicate the feature is degrading: refusal rate, fallback-
   provider usage rate, average steps per run, user-reported "that's wrong"
   feedback rate? A feature with perfect uptime metrics but no visibility
   into *whether the answers are any good* has an observability gap specific
   to LLM features that generic infra monitoring won't catch.
4. **Latency and token cost.** Are per-call and per-run latency and token
   usage tracked (not just total spend at the end of the month)? Is prompt
   caching used where the provider supports it and the app has stable prefix
   content (a system prompt, few-shot examples) that would benefit -
   uncached repeated long system prompts are a common, easy cost/latency win
   worth flagging even without it being "broken".
5. **Estimate accuracy.** If the app shows users a cost or time estimate
   ("this will take about 30 seconds," "estimated cost: $0.02"), is that
   estimate derived from real historical data for this operation, or a
   guessed constant that drifts from reality as usage patterns or provider
   pricing change? A consistently wrong estimate is a trust/quality issue
   worth a finding, distinct from `audit-llm-output-quality`'s content-
   accuracy focus.
6. **Rate and write findings** via `audit-finding-writer`, Area
   "Observability & Cost" / prefix `OC`.

## Bundled files

- `references/genai-tracing-conventions.md` - the OpenTelemetry GenAI semantic convention field names to check for/recommend, so tracing recommendations are concrete rather than "add more logging".
