---
name: audit-llm-evals-and-red-teaming
description: Checks whether an LLM application has representative eval datasets, an adversarial/red-team suite covering paraphrase and partial-capability cases, and a validated LLM-as-judge setup, and whether evals actually gate every prompt or model change rather than running informally or not at all. Use it whenever the user asks about eval suites, regression testing for prompts, LLM-as-judge, red-teaming process, or "how do we know a prompt change didn't break something" - even when the user does not name this skill. Writes findings with Area "Evals & Red-Teaming" (prefix ER) to audit/findings/audit-llm-evals-and-red-teaming.json.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: LLM evals and red-teaming

No dedicated OWASP anchor - a process-maturity audit. This is the audit that
turns every ad hoc probe the other `audit-llm-*` skills ran into a question
of *permanence*: did this become a regression test, or does the same gap
have to be rediscovered by hand next release?

Prerequisites: `shared-llm-payload-library`, `shared-llm-finding-format`,
`audit-finding-writer`.

## Workflow

1. **Locate the eval setup**, if any: a test directory with prompt/expected-
   output pairs, a promptfoo/PyRIT/garak config, a CI step that runs evals
   before merge, or nothing at all.
2. **Representativeness.** Does the eval set cover the application's actual
   core use cases with real variety, or is it a handful of happy-path
   examples? Does it include cases from
   `shared-llm-payload-library`'s categories (paraphrase variants,
   partial-capability, jailbreak/injection probes) or only positive
   examples?
3. **LLM-as-judge validation**, if the app uses a model to grade another
   model's output (for evals, for content moderation, for a quality score
   shown to users): has the judge itself been validated against a human-
   labeled sample to confirm it agrees with human judgment at an acceptable
   rate, or is its verdict trusted with no calibration check at all? An
   unvalidated judge can rubber-stamp bad outputs indefinitely.
4. **Gating.** Does a prompt or model change actually require the eval suite
   to pass before it ships (a CI gate, per `audit-test-coverage-and-ci`'s
   general CI-gate checks, applied specifically to prompt/model changes), or
   can a prompt be edited and deployed with no automated check at all?
5. **Feed findings from other audits back into the suite as a
   recommendation** (not by writing test files yourself unless asked) -
   every confirmed finding from `audit-llm-prompt-injection`,
   `audit-llm-jailbreak-resistance`, etc. is a candidate regression test;
   note which ones have no corresponding eval case yet, since that's exactly
   what `propose-llm-eval-suite` will build from.
6. **Rate and write findings** via `audit-finding-writer`, Area "Evals &
   Red-Teaming" / prefix `ER`. "No evals at all" on a production LLM feature
   is a High finding on its own - it means every other audit's findings will
   silently regress with no automated warning.

## Bundled files

- `references/eval-maturity-levels.md` - a rough maturity ladder (none / manual spot-check / static eval set / gated CI / adversarial + gated) to place the app on and justify severity.
