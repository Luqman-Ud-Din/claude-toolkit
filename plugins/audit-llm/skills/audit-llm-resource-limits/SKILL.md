---
name: audit-llm-resource-limits
description: Checks an LLM/agentic application for step caps, token and cost budgets, timeouts, rate limits, and loop detection, and assesses how a failure in one tool call or reasoning step propagates through the rest of the run - does one failed step abort cleanly, retry sensibly, or can it spin the agent into an unbounded or runaway loop. Use it whenever the user asks about runaway agent loops, cost control, token budgets, request timeouts, rate limiting on an AI feature, or "what stops this agent from looping forever or racking up a huge bill" - even when the user does not name this skill. Writes findings with Area "Resource Limits" (prefix RL) to audit/findings/audit-llm-resource-limits.json.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: LLM resource limits

OWASP LLM10, ASI08. Can run standalone; strongly benefits from an
architecture map.

Prerequisites: `shared-llm-context-bootstrap`, `shared-llm-finding-format`,
`audit-finding-writer`.

## Workflow

1. **Bootstrap.** Prefer `audit/llm/explore/explore-llm-architecture.json` for
   the termination-condition data it already located. Absent, locate the
   agent loop directly and answer the same question narrowly.
2. **Check each control** exists and is actually enforced (not just configured
   somewhere unreachable):
   - **Step/iteration cap** - a hard max on how many tool-call or reasoning
     turns a single run can take.
   - **Token budget** - a cap on total tokens (input + output) per run or per
     user/session/time window, and what happens when it's hit (graceful stop
     vs. silent truncation vs. no cap at all).
   - **Cost budget** - is spend tracked and capped per user/tenant, or only
     visible after the fact in a provider bill?
   - **Timeout** - a wall-clock limit on the whole run, independent of step
     count (a tool that hangs, not just one that returns quickly N times).
   - **Rate limit** - per-user/per-tenant limits on how often a new run can
     start, so one user can't monopolize shared capacity or run up costs by
     spamming requests.
   - **Loop detection** - beyond a hard step cap, does anything detect the
     agent repeating the same tool call with the same arguments (a sign of a
     stuck reasoning loop) and intervene before the step cap is even hit?
3. **Failure propagation.** Trace what happens when one step in a multi-step
   run fails (a tool throws, a provider call times out, a rate limit is hit
   mid-run): does the agent retry with backoff and eventually give up
   cleanly, retry unboundedly, or treat the failure as a new reasoning
   input that can itself trigger more tool calls (a failure-driven loop)?
4. **Multi-agent specifically.** If multiple agents can trigger each other
   (per `explore-llm-architecture`'s agent map), check for a *global* run
   budget across all agents combined, not just a per-agent one - two agents
   each individually capped can still loop each other indefinitely if
   nothing caps the combined exchange.
5. **Rate and write findings** via `audit-finding-writer`, Area "Resource
   Limits" / prefix `RL`. A completely absent step cap or timeout on a
   production-facing agent is High severity by default - unbounded cost and
   availability risk - regardless of whether it's been observed to actually
   run away yet.

## Bundled files

- `references/limit-checklist.md` - a fill-in checklist of every control in step 2, with the file/config key to cite as evidence when present or absent.
