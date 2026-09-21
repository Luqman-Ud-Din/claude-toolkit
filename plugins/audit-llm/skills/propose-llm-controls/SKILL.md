---
name: propose-llm-controls
description: Designs code-level remediations for LLM/agentic-application findings - guardrail layers, tool permission scoping, human approval gates, resource/cost budgets, navigation or capability restrictions, and credential handling - treating prompt changes as defense in depth rather than the primary fix. Use it whenever the user asks how to actually fix an excessive-agency, guardrail, resource-limit, or prompt-injection finding at the code level, wants an approval-gate design, credential-scoping plan, or rate-limit/budget design for an AI agent, or asks "what's the real fix, not just a prompt tweak" - even when the user does not name this skill. Reads findings via shared-llm-finding-format and writes to audit/llm/proposals/propose-llm-controls.json per shared-llm-handoff-contract.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Propose: LLM controls

The primary-fix skill for `Excessive Agency`, `Guardrails`, `Resource
Limits`, `Data Privacy & Isolation`, `Supply Chain`, and
`Code Execution & Multi-Agent` findings, and the defense-in-depth layer for
`Prompt Injection`/`Jailbreak Resistance` findings whose primary fix is
structural separation rather than wording.

Prerequisites: `shared-llm-finding-format`, `shared-llm-owasp-mapping`,
`shared-llm-handoff-contract`, `audit-finding-writer` (for the stack's own
remediation idiom reference).

## Workflow

1. **Read the finding(s)**, and the underlying tool/prompt/architecture
   detail from whichever `explore-llm-*` map covers it, so the proposal is
   concrete to this codebase, not generic advice.
2. **Pick the pattern** from the relevant reference (approval gates from
   `audit-llm-excessive-agency`'s `references/approval-gate-patterns.md`,
   enforcement classification from `audit-llm-guardrails`'s
   `references/enforcement-classification.md`, sandboxing from
   `audit-llm-code-execution-and-multi-agent`'s
   `references/sandbox-checklist.md`) rather than inventing a new shape per
   finding - consistency across proposals for similar findings makes the
   whole remediation plan easier to review and implement.
3. **Write the concrete change** in the app's own stack idiom - call
   `audit-finding-writer`'s stack reference (`$AUDIT_CORE_ROOT/skills/audit-finding-writer/references/<stack>.md`)
   via `shared-llm-stack-detection`/`audit-stack-detection`'s output so a
   .NET app gets a .NET-shaped proposal (e.g. a policy/middleware pattern)
   and a Python app gets a Python-shaped one, not a pseudocode-only
   suggestion.
4. **State trade-offs explicitly**: added latency (an approval round trip),
   added operational load (someone has to review pending approvals), false
   refusals (a stricter guardrail blocking legitimate requests), and cost
   (a sandboxing layer, a second verification model call).
5. **Flag when a fix needs a decision beyond engineering** - a credential-
   scoping fix might require provisioning a new, narrower service credential
   through infra/ops, not just a code change; say so rather than presenting
   it as a pure code diff.
6. **Write the proposal** to `audit/llm/proposals/propose-llm-controls.json`
   per `shared-llm-handoff-contract`'s schema, with `finding_refs` set and
   `effort` (S/M/L) estimated against the actual change described, not a
   generic guess.

## Bundled files

- `references/control-proposal-template.md` - the structure a single control proposal should follow (change, code sketch, trade-offs, effort, follow-up ops work if any).
