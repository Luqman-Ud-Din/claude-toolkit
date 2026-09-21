---
name: audit-llm-application
description: Orchestrates the LLM/agentic-application audit phase - selects which of the 13 audit-llm-* skills actually apply based on the detected LLM stack (e.g. skips audit-llm-code-execution-and-multi-agent when there's no code execution and no multi-agent setup), runs them, and hands findings to audit-finding-writer and audit-findings-rollup. Uses explore-llm-* outputs when present, otherwise bootstraps each child skill's own minimum discovery. Use it whenever the user asks for a full LLM/AI security audit, wants "all the LLM audit skills" run, asks to audit an AI agent or chatbot feature end to end, or asks which LLM-specific checks apply to their app - even when the user does not name this skill. This is the LLM-specific counterpart to audit-application; run both together for an app that has both traditional and AI-specific surface.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: LLM application (orchestrator)

Mirrors `audit-application`'s role for the LLM-specific suite: detect once,
select applicable children, run them, consolidate. It does not replace
`audit-application` - a typical target has both traditional backend/frontend
surface (covered by the general `audit-*` suite) and an LLM/agent feature
(covered by this one); run this alongside or after the general audit,
sharing the same `audit/` output root.

Prerequisites: `shared-llm-stack-detection`, `shared-llm-context-bootstrap`,
`shared-llm-handoff-contract`, `audit-finding-writer`, `audit-findings-rollup`.

## Workflow

1. **Detect the LLM stack.** Run `shared-llm-stack-detection`. If nothing is
   found, confirm with the user before proceeding (per that skill's guidance
   on raw-HTTP integrations with no SDK marker) rather than reporting "no
   LLM audit needed" on a false negative.
2. **Ask scope questions once**, the same way `audit-application` asks about
   multi-tenancy:
   - Is a running instance available and in scope for live probing (gates
     `explore-llm-behavior` and every audit skill that sends probes)?
   - Full suite, or a subset (e.g. "just the security-relevant ones":
     prompt-injection, jailbreak-resistance, guardrails, excessive-agency,
     data-privacy-and-isolation, supply-chain, code-execution-and-multi-agent)?
3. **Select applicable children** using `references/selection-rules.md`:
   `audit-llm-code-execution-and-multi-agent` only if code execution or
   multi-agent is detected; every other audit-llm-* skill applies to any
   detected LLM feature by default.
4. **Prefer an explore pass first when none exists and the scope allows it** -
   offer to run `explore-llm-application` before the audit children, since
   several audits (excessive-agency, prompt-injection especially) are
   materially better with a tools/data-flow map in hand. Respect "no, just
   audit directly" - every child skill still works standalone via
   `shared-llm-context-bootstrap`.
5. **Run each selected child skill**, letting each write its own
   `audit/findings/audit-llm-<name>.json` via `audit-finding-writer`.
6. **Consolidate.** Run `audit-findings-rollup` across the LLM findings files
   to de-duplicate root causes that surfaced from more than one angle (a
   missing approval gate found by both excessive-agency and, via a
   successful probe, prompt-injection).
7. **Hand off.** Report per-skill status (ran / skipped-and-why / found N
   findings) and point at `audit-report-generator` for a combined report if
   the user is also running the general `audit-application` suite, or
   `propose-llm-application` if they want remediations next.

## Bundled files

- `references/selection-rules.md` - the exact condition for including/excluding each audit-llm-* skill given the detected stack and architecture.
