---
name: propose-llm-application
description: Orchestrates the LLM/agentic-application propose phase - accepts findings from any source (audit-llm-* output, a manual review, an external pentest report), normalizes them to the shared finding format, and routes each to propose-llm-prompt-changes, propose-llm-controls, or propose-llm-eval-suite. Produces a single prioritized remediation plan with effort estimates. Use it whenever the user asks for a remediation plan for LLM/AI security or quality findings, wants to turn a batch of AI-related findings into concrete fixes, or asks "what do we actually do about all these AI audit findings" - even when the user does not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Propose: LLM application (orchestrator)

Mirrors `audit-application`'s and `explore-llm-application`'s role: run the
phase's children, merge the result, add no independent analysis beyond the
merge and prioritization. Can accept findings that never went through
`audit-llm-application` at all - a normalization step handles that per
design principle 1 (each phase's output can feed the next, but never
requires it).

Prerequisites: `shared-llm-finding-format`, `shared-llm-context-bootstrap`,
`shared-llm-handoff-contract`.

## Workflow

1. **Gather findings.** Prefer `audit/findings/audit-llm-*.json`. If the user
   instead hands you a manual review, an external pentest report, or a list
   of concerns in plain text, normalize each into the finding shape
   `shared-llm-finding-format` defines (Area, ID, severity, location,
   impact) before routing - ask for whatever's missing rather than guessing
   a severity with no basis.
2. **Route each finding** by Area:
   - `Prompt & Context Engineering`, and the wording half of
     `Intent Grounding & Adaptability` / `Jailbreak Resistance` findings ->
     `propose-llm-prompt-changes`.
   - `Excessive Agency`, `Guardrails`, `Resource Limits`,
     `Data Privacy & Isolation`, `Supply Chain`,
     `Code Execution & Multi-Agent`, and the structural half of
     `Prompt Injection` findings -> `propose-llm-controls`.
   - Every finding that got a proposal, once fixed conceptually, also gets a
     verification test -> `propose-llm-eval-suite`.
   A finding can route to more than one child (a jailbreak finding often
   gets both a prompt tweak and a code-level guardrail as defense in depth) -
   don't force a single owner where the audit itself found more than one
   contributing gap.
3. **Run the children**, each writing its own
   `audit/llm/proposals/propose-llm-*.json`.
4. **Merge and prioritize.** Build one remediation plan ordering by:
   finding severity first, then a rough effort-vs-impact read (a Critical
   fixable in an afternoon outranks a Medium that needs an infra change) -
   state the ordering logic rather than presenting an unexplained list.
5. **Write** the merged plan to
   `audit/llm/proposals/propose-llm-application.json` and present it as a
   readable, prioritized plan (not a JSON dump), grouped as
   "fix before shipping this feature" vs. "can follow as a fast-follow" -
   mirroring `audit-report-generator`'s must-fix vs. post-launch split so the
   two phases read consistently if both are used.

## Bundled files

- `references/plan-template.md` - the structure of the merged, prioritized remediation plan.
