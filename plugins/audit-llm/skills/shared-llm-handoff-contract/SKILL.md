---
name: shared-llm-handoff-contract
description: Defines the shared file layout every llm-audit-* skill writes to and reads from - audit/llm-stack.json for detected stack, audit/llm/explore/<skill>.json for explore-phase maps, audit/findings/<skill>.json for audit-phase findings (via the existing audit-finding-writer contract, reused rather than duplicated), and audit/llm/proposals/<skill>.json for propose-phase output - plus file naming and the schema each downstream skill expects. This is a shared building block, not run standalone - every explore-llm-*, audit-llm-*, and propose-llm-* orchestrator and atomic skill follows it so phases stay decoupled while their outputs remain interchangeable. Use it whenever another llm-audit-* skill needs to know where to read or write its output, or whenever the user asks where LLM audit results are stored or how the explore/audit/propose phases hand off to each other.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Shared: LLM audit handoff contract

The explore, audit, and propose phases are independent (design principle 1 in
`llm-audit-skills.md`) - each can run alone. This skill is what makes that
possible without losing the ability to chain them: every phase writes to a
fixed, predictable path, and every phase that can use a prior phase's output
checks that path first via `shared-llm-context-bootstrap` before falling back
to its own minimum discovery.

## Directory layout

```
audit/
  llm-stack.json                     shared-llm-stack-detection output
  llm/
    explore/
      explore-llm-architecture.json
      explore-llm-prompts.json
      explore-llm-tools-and-permissions.json
      explore-llm-data-flow.json
      explore-llm-behavior.json
      explore-llm-application.json   the assembled inventory (orchestrator)
    proposals/
      propose-llm-prompt-changes.json
      propose-llm-controls.json
      propose-llm-eval-suite.json
      propose-llm-application.json   the prioritized remediation plan (orchestrator)
  findings/
    audit-llm-<name>.json            EXISTING audit-finding-writer contract - unchanged
  reports/
    audit-llm-<name>.md              EXISTING audit-finding-writer contract - unchanged
```

Findings and their Markdown reports are **not** a new contract - `audit-llm-*`
skills call `audit-finding-writer` exactly the way every other `audit-*` skill
does, so `audit-findings-rollup`, `audit-owasp-asvs-mapper`, and
`audit-report-generator` work on LLM findings with no special-casing. Only the
Area values and ID prefix differ, and those live in `shared-llm-finding-format`.

## Explore map schema (`audit/llm/explore/<skill>.json`)

```json
{
  "skill": "explore-llm-prompts",
  "generated_at": "ISO-8601",
  "root": "absolute path",
  "summary": "one paragraph, plain language",
  "items": [
    {
      "id": "stable short id, e.g. sys-prompt-support-agent",
      "location": "file path and line, or prompt/template name",
      "detail": { "...": "skill-specific fields" }
    }
  ],
  "open_questions": ["anything the skill could not resolve from source alone"]
}
```

Each `explore-llm-*` skill defines its own `detail` shape in its own SKILL.md;
this contract only fixes the envelope (`skill`, `generated_at`, `root`, `summary`,
`items[].id/location`, `open_questions`) so `explore-llm-application` can merge
five of these into one inventory without per-skill special-casing, and so an
`audit-llm-*` skill can consume just the `items` it needs.

## Proposal schema (`audit/llm/proposals/<skill>.json`)

```json
{
  "skill": "propose-llm-controls",
  "generated_at": "ISO-8601",
  "proposals": [
    {
      "id": "short id",
      "finding_refs": ["LLM-EA-003"],
      "title": "one clause",
      "change": "the concrete fix, code-level first",
      "trade_offs": "latency, cost, false refusals, etc.",
      "effort": "S | M | L"
    }
  ]
}
```

`finding_refs` is how `propose-llm-application` (or a human) traces a proposal
back to the finding that justified it - never propose a change with no
`finding_refs` entry unless the user asked for a proactive suggestion, and
label those `"finding_refs": []` explicitly rather than omitting the field.

## Workflow for a consuming skill

1. Check for the exact path this contract defines before gathering anything
   yourself - that is `shared-llm-context-bootstrap`'s job; call it rather than
   re-implementing the check.
2. If present, read it and say so ("using the explore-llm-prompts map from
   `audit/llm/explore/`, generated <date>") so the user knows stale input is
   possible and can ask for a re-run.
3. If absent, gather only the minimum your own SKILL.md declares, and do not
   write a partial file at another skill's path - write your own skill's path,
   or nothing if you were only asked for an in-context answer.

## Bundled files

- `references/schema-examples.md` - one filled-in example of each schema above, for a small sample app.
