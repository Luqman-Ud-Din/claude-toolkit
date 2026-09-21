---
name: shared-llm-context-bootstrap
description: Checks for existing outputs from earlier llm-audit-* phases (audit/llm-stack.json, audit/llm/explore/*.json, audit/findings/audit-llm-*.json) at the paths shared-llm-handoff-contract defines, and loads whichever exist. When one is absent, runs only the minimum discovery the calling skill declares it needs - never the full explore pass - so every audit-llm-* and propose-llm-* skill can run standalone with no prior phase. This is a shared building block, not run standalone - called at the top of every explore-llm-*, audit-llm-*, and propose-llm-* skill (orchestrators and atomic skills alike) before they gather any context themselves. Use it whenever a skill needs to decide "do I already have this, or do I have to go find it" before starting its own analysis.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Shared: LLM context bootstrap

Design principle 2 in `llm-audit-skills.md`: optional inputs, graceful fallback.
This skill is what makes that principle mechanical rather than something every
skill re-derives. A calling skill declares two things and this skill returns
what's available:

- **What it wants**: a list of paths from `shared-llm-handoff-contract`
  (e.g. `audit/llm-stack.json`, `audit/llm/explore/explore-llm-prompts.json`).
- **What it needs at minimum if that's absent**: a short, explicit fallback
  the calling skill's own SKILL.md spells out - never "run the full explore
  phase", which defeats the point of an atomic skill.

## Workflow

1. **Check first.** For each declared path, check whether the file exists
   under the target repo's `audit/` directory. Do this with a plain filesystem
   check, not by re-running the skill that produces it.
2. **Freshness sanity check.** If a file exists, look at its `generated_at`
   (or `detected_at`) field. If the repo has commits newer than that timestamp
   touching the area the skill cares about (e.g. a `src/agent/` change after
   an `explore-llm-tools-and-permissions.json` was generated), say so and let
   the calling skill or the user decide whether to re-run the source skill
   rather than silently trusting stale input.
3. **Fall back to the minimum.** For every path that is absent, run exactly
   the fallback the calling skill declared - typically a narrow, single-purpose
   check (e.g. `audit-llm-guardrails` without an explore map falls back to
   `shared-llm-stack-detection` plus a grep for guardrail-library call sites,
   not a full architecture trace).
4. **Report provenance.** Tell the calling skill (and, through it, the user)
   which inputs came from a prior phase's file and which were freshly gathered
   in this fallback, so a finding's confidence can reflect that - a finding
   built on a fresh, narrow grep is `likely` more often than one built on a
   full explore map that already traced the code.

## What this skill does not do

- It does not run `explore-llm-*` skills on the caller's behalf "just in case" -
  that would turn every atomic skill into the orchestrator, which is exactly
  what design principle 1 rules out.
- It does not write anything - it only reads what other skills already wrote,
  per `shared-llm-handoff-contract`.
- It does not decide relevance - "does this repo even have LLM features" is
  `shared-llm-stack-detection`'s job, which most fallbacks call first.

## Bundled files

- `references/fallback-patterns.md` - the recommended minimal fallback for each explore-llm-* map, for skills that declare it.
