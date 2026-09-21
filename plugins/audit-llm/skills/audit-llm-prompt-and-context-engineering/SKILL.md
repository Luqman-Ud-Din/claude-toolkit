---
name: audit-llm-prompt-and-context-engineering
description: Reviews prompt clarity and internal contradictions, whether instructions are goal-based or brittle step-by-step scripts, structured-output handling, context construction quality, and whether the model chosen for each step actually fits that step's difficulty and cost. Use it whenever the user asks for a prompt review, wants to know why a prompt behaves inconsistently, asks about goal-based vs scripted instructions, structured output/JSON mode reliability, context window usage, or whether a cheaper/faster model would work for a given step - even when the user does not name this skill. Writes findings with Area "Prompt & Context Engineering" (prefix PE) to audit/findings/audit-llm-prompt-and-context-engineering.json.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: LLM prompt and context engineering

No dedicated OWASP anchor - a quality/reliability audit, not primarily a
security one, though a badly engineered prompt often underlies a security
finding elsewhere (cross-reference rather than re-file).

Prerequisites: `shared-llm-context-bootstrap`, `shared-llm-finding-format`,
`audit-finding-writer`.

## Workflow

1. **Bootstrap.** Prefer `explore-llm-prompts.json`'s inventory; it already
   located every prompt and its variables.
2. **Clarity and contradiction check.** For each prompt: any internally
   contradictory instructions (one line says "always ask before acting," a
   later line says "resolve ambiguity yourself and proceed")? Any instruction
   that's vague enough that two reasonable readings would produce different
   behavior? Any instruction repeated with drift across multiple prompts
   (flagged already by `explore-llm-prompts` as "prompt sprawl" - confirm and
   rate it here rather than re-discovering it).
3. **Goal-based vs. script-based.** Is the model given a goal and the
   judgment to reach it, or a rigid step-by-step script that breaks the
   moment reality doesn't match the assumed sequence (e.g. "first check X,
   then do Y" with no branch for "what if X doesn't apply")? A script-based
   prompt is often *more* fragile for genuinely variable tasks - note where
   the app's actual task variability doesn't match how rigid the prompt is.
4. **Structured output handling.** If the app expects JSON/schema-conforming
   output: is a real structured-output/function-calling mode used (provider-
   enforced), or is the model asked in free text to "respond in JSON" with
   the app hoping and then parsing? The latter needs a documented fallback
   for malformed output - check it exists and doesn't silently swallow
   errors or crash the caller.
5. **Model-fit check.** For each distinct step in a multi-step pipeline
   (classification, extraction, final response generation), is the model
   used proportionate to the step's actual difficulty, or is an expensive,
   high-latency model used uniformly including for trivial sub-steps that a
   smaller/cheaper model would handle fine? This feeds
   `audit-llm-observability-and-cost` - cross-reference rather than
   duplicating its cost analysis.
6. **Rate and write findings** via `audit-finding-writer`, Area "Prompt &
   Context Engineering" / prefix `PE`. Most findings here are Low-Medium
   (quality/maintainability) unless the ambiguity has a security or
   business-logic consequence - in which case cite the specific downstream
   Area too.

## Bundled files

- `references/prompt-quality-checklist.md` - a fill-in checklist covering clarity, contradiction, goal- vs script-based framing, and structured output for one prompt at a time.
