---
name: explore-llm-application
description: Orchestrates the LLM-application explore phase - runs shared-llm-stack-detection, then each relevant explore-llm-* skill (architecture, prompts, tools and permissions, data flow, and behavior when a running instance is available), and assembles one merged inventory of the LLM application. Can run standalone for onboarding, architecture review, or documentation with no audit to follow. Use it whenever the user asks for an overview, map, inventory, or architecture review of an AI/LLM/agentic feature, wants to understand how an app's AI works before making changes, or asks to "explore" or "document" an AI feature - even when the user does not name this skill or ask for an audit.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Explore: LLM application (orchestrator)

Assembles the five `explore-llm-*` maps into one inventory. Each child skill
is independently useful and independently runnable (design principle 1) -
this orchestrator's only added value is running them together, in a sensible
order, and merging the result; it adds no analysis of its own.

Prerequisites: `shared-llm-stack-detection`, `shared-llm-handoff-contract`.

## Workflow

1. **Detect the stack.** Run `shared-llm-stack-detection`. If it finds no
   LLM/agent markers at all, say so plainly and ask whether to proceed anyway
   (a raw-HTTP integration with no SDK marker is still possible - see that
   skill's SKILL.md) rather than silently exploring nothing.
2. **Run the code-only child skills** (order doesn't matter functionally, but
   this order reads best in the assembled report):
   `explore-llm-architecture` -> `explore-llm-prompts` ->
   `explore-llm-tools-and-permissions` -> `explore-llm-data-flow`.
3. **Ask before the live-probe skill.** `explore-llm-behavior` touches a
   running application. Ask the user whether a running instance is available
   and in scope before invoking it - do not assume; skip it with a note if
   there's no live target or no authorization.
4. **Merge.** Read each `audit/llm/explore/explore-llm-*.json` written by the
   child skills and produce one inventory covering: what the app is for,
   architecture summary, prompt inventory summary, tool/permission summary
   (leading with the riskiest tools), data-flow summary (leading with
   untrusted inbound sources and any outbound-data concerns), and the
   behavioral baseline if gathered. Cross-reference between sections rather
   than just concatenating them - e.g. call out a tool from the tools map
   whose parameters come from an untrusted source per the data-flow map.
5. **Write** the merged inventory to
   `audit/llm/explore/explore-llm-application.json` and present it to the user
   as a readable summary, not a JSON dump.
6. **Hand off cleanly.** End by naming which `audit-llm-*` skills now have a
   head start because of this pass (excessive-agency and prompt-injection
   benefit most directly) - but do not auto-invoke the audit phase; that's
   the user's call, per design principle 1.

## Bundled files

- `references/merge-template.md` - the structure of the assembled inventory report.
