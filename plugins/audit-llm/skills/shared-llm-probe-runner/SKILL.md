---
name: shared-llm-probe-runner
description: Safe procedure for sending test inputs to a running LLM/agentic application and recording the responses - confirms authorization and scope before sending anything, keeps requests within an explicit target and rate limit, and captures every request/response pair as evidence. This is a shared building block, not run standalone - explore-llm-behavior, audit-llm-prompt-injection, audit-llm-jailbreak-resistance, audit-llm-guardrails, and audit-llm-intent-grounding-and-adaptability all send test inputs through this procedure instead of hand-rolling their own HTTP calls. Use it whenever a skill is about to send test prompts, payloads, or probe requests to a live application, and refuse to send anything until this skill's authorization gate has been satisfied.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Shared: LLM probe runner

Every skill that black-box tests a running application funnels through here so
authorization, scope, and evidence capture are enforced once, not re-decided
(and possibly skipped) by each caller.

## Authorization gate - before anything else

1. **Confirm this is an authorized test.** The calling context should already
   establish this (a pentest engagement, the user's own application, a CI
   eval run) - if it is not clear the person directing the probe owns or is
   authorized to test the target, stop and ask rather than proceeding. Never
   probe a third party's production application without explicit evidence of
   authorization.
2. **Prefer a non-production target.** If a staging/test environment exists,
   use it. Probing production is acceptable when that is the only environment
   available and the user confirms it, but say so explicitly in the evidence
   record so a reviewer knows real user-facing behavior was touched.
3. **Scope to the target.** Only send requests to endpoints/conversations the
   user named or that a prior explore map identified as part of this
   application - never expand scope to "let's also try the endpoint next to
   it" without asking.

## Sending probes

4. **Rate limit.** Default to no more than one request every 2-3 seconds
   against a shared/production-adjacent target unless the user says higher
   throughput is fine (e.g. an isolated eval environment). Back off
   immediately on 429s or any sign of a shared rate limit being hit.
5. **No destructive payloads.** A probe proves a behavior exists; it does not
   need to actually complete a real refund, send a real email, or delete real
   data to prove a tool-call vulnerability. Use dry-run/sandbox modes,
   test-account data, or a payload that would need a second confirmed step to
   cause real-world effect, and say in the evidence record whether the probe
   was "observed the model attempt/request the action" vs. "action executed".
6. **No real PII in payloads.** Use synthetic data for anything resembling a
   name, account number, or document.

## Evidence capture

7. Record every probe as one entry: `{id, category, payload, timestamp, response, observed_behavior}` and write the set to `audit/llm/evidence/<calling-skill>.json`. `observed_behavior` is the reviewer's plain-language read (refused / complied / partially complied / ambiguous), not just the raw response, so `audit-finding-writer` can cite it directly.
8. Never discard a probe result because it didn't find anything - a full
   coverage record (including probes that the app correctly refused) is what
   lets `audit-llm-evals-and-red-teaming` later confirm the suite is
   representative, and what lets a finding say "resisted 8 of 10 jailbreak
   categories" instead of only listing the 2 that worked.

## Bundled files

- `references/abort-conditions.md` - signs a probe run should stop (account lockouts, unexpected real-world side effects, rate-limit bans) and what to do when one triggers.
- `scripts/probe_runner.py` - rate-limited HTTP sender that logs each request/response pair to the evidence JSON shape above; import or run standalone.
