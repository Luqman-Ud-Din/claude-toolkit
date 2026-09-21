---
name: propose-llm-eval-suite
description: Generates test cases proving each LLM-audit fix actually works, drawn from shared-llm-payload-library and tailored to specific findings - each test is designed to fail on the pre-fix behavior and pass on the post-fix behavior. Use it whenever the user asks for regression tests for an AI/LLM fix, wants to turn an audit finding into a permanent eval case, asks "how do we prove this fix actually works and stays fixed", or wants to build out an eval/red-team suite from audit results - even when the user does not name this skill. Reads findings via shared-llm-finding-format and writes to audit/llm/proposals/propose-llm-eval-suite.json per shared-llm-handoff-contract.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Propose: LLM eval suite

Turns a one-off audit probe into a permanent regression test, closing the
loop `audit-llm-evals-and-red-teaming` opens when it finds confirmed
findings with no corresponding eval case.

Prerequisites: `shared-llm-payload-library`, `shared-llm-finding-format`,
`shared-llm-handoff-contract`.

## Workflow

1. **Start from a finding**, not a blank page. Read the finding's Evidence
   (the exact probe/payload that demonstrated it, if one exists) - the test
   case should reproduce that exact scenario, not a generic version of the
   category.
2. **Write the test as fail-before/pass-after**: the input (a specific
   prompt, or a specific tool-call scenario), the pre-fix expected result
   (what happened, matching the finding), and the post-fix expected result
   (what should happen once the proposed fix from `propose-llm-controls` or
   `propose-llm-prompt-changes` lands) - a test with only a post-fix
   assertion can't prove it was ever actually broken, so include both.
3. **Draw additional coverage from `shared-llm-payload-library`** for the
   same category as the finding, not just the one exact reproduction - a
   fix that only passes the literal probe that found it can still be brittle
   to a slightly different phrasing of the same underlying issue.
4. **Prefer an automatable assertion** (a specific tool was or wasn't called,
   a specific string is or isn't present, a response matches an expected
   schema) over "looks right" - when the correct behavior genuinely needs
   judgment (e.g. "did it ask a reasonable clarifying question"), use an
   LLM-as-judge assertion but say so explicitly and recommend validating
   that judge per `audit-llm-evals-and-red-teaming`'s guidance rather than
   trusting it uncalibrated.
5. **Write the proposal** to
   `audit/llm/proposals/propose-llm-eval-suite.json` per
   `shared-llm-handoff-contract`'s schema, with `finding_refs` set, in a
   format that could be dropped into the app's actual eval runner
   (promptfoo config, a pytest case, etc.) if the user asks to materialize it -
   don't materialize test files into the app's own test suite unless asked.

## Bundled files

- `references/eval-case-template.md` - the fail-before/pass-after test case format, with a worked example per finding Area.
