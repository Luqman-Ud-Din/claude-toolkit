---
name: explore-application
description: Orchestrates the three explore-* skills - architecture, schema, business-logic - against one repo, running them in parallel and producing a combined index that points at all three documents plus their key counts. Use it whenever the user asks to explore, map, or document the whole application/codebase, wants everything documented before running the propose-* skills, asks for architecture+schema+business-logic together, or asks to "explore everything" - even when they don't name the three skills individually. Each child skill still handles its own stack detection and multi-repo scoping.
---

## Plugin invocation

When invoking a skill from this bundle, use `explore-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Explore: application

Runs `explore-architecture`, `explore-schema` and `explore-business-logic` and hands back one
place to start: an index pointing at all three documents, with the key counts each one already
reports. This skill produces no analysis of its own - the three children are the evidence, this
is only the map to it.

The three children are independent. None reads another's output: `explore-business-logic` does
not need the schema or architecture documents to run, and neither of those needs the BLD. That
independence is what makes running them in parallel safe rather than merely convenient - there
is no ordering constraint to get wrong. It also means partial success is fine: if one child
fails, the other two are still complete, useful documents.

## Inputs

- Repository path (default: current working directory). If the directory holds more than one
  repository, pass it through as-is - do not split it up yourself. Each child skill already
  knows how to notice a multi-repo directory and cover every repo in it, and each states which
  repos it covered in its own output header. Your job is only to collect what they say, not to
  re-decide it.
- Optional: a module/subsystem to scope to, or specific flows/questions the user wants answered.
  Pass these through verbatim to every child that accepts them (all three do) rather than
  interpreting them yourself - each child's own scoping rules are more detailed than anything
  worth duplicating here.
- Optional: a "force refresh" instruction from the user. Absent that, treat today's existing
  documents as good enough to reuse (see below).

## Process

### 1. Resolve scope

Work out the repo path and any module scope or named flows, the same way the three children
already default (current working directory when nothing is named). State this once; you will
pass it identically to all three children.

### 2. Check what already exists

Before launching anything, look for today's date under each child's output folder:
`docs/analysis/explore-architecture/<today>.md`, `docs/analysis/explore-schema/<today>.md`,
`docs/analysis/explore-business-logic/<today>.md` (accounting for the `-2`, `-3`, ... suffixes
those skills use when a file already exists for the day). If a document from today is already
there and the user did not ask for a refresh, that child does not need to run again - reuse the
file. This is a plain lookup, not a state file: you are simply not paying to regenerate a
document that's already sitting on disk from earlier today. If the user asks to force a refresh
(of one child or all three), skip this check for the ones they named.

This same check is what makes re-running this skill after a partial failure cheap: only the
child that didn't produce a file today runs again.

### 3. Launch the three children in parallel

For each child that step 2 didn't already resolve, launch one subagent (the `Agent` tool,
`general-purpose` type) per child skill, all in the same message so they run concurrently - there
is no reason to wait for one before starting the next, since they touch nothing of each other's.
Each subagent's brief is narrow and identical in shape:

> Invoke the `<child-skill-name>` skill (`explore-app:<child-skill-name>` when installed as a plugin) against `<repo path>` (scope: `<module/flows or "none">`).
> When it finishes, report back exactly two things: the file path it wrote, and the one-line
> summary it ends its own reply with (the counts it already states - entities/modules/tables/etc,
> and issue counts by severity where it has them). Do not summarize the document's content beyond
> that; do not write to any file yourself.

Keep the subagents to that: invoke the skill, relay its own summary line and file path back. They
should not maintain shared state, coordinate with each other, or attempt to reconcile anything -
there is nothing to reconcile, since the three documents are disjoint by design.

### 4. Collect results

Wait for all three (or all remaining) subagents to report. For each child, you now have one of:

- **generated** - ran this turn, with a file path and summary line from the subagent
- **reused** - already existed from today (step 2), with the file path you found
- **failed** - the subagent reported the skill errored, refused, or produced nothing

A failure in one child does not block the other two. Write the index with whatever succeeded
(generated or reused), and say plainly in both the index and your reply which child failed and
why (as reported by the subagent). Re-running this skill later will only re-attempt the failed
one, per step 2 - there's no separate retry loop to build here.

### 5. Write the combined index

One file, pointing at the three documents rather than repeating their content:

```markdown
# Application exploration - <application name>

Source: <repo path> @ <date>; scope: <all | module>
Repos covered: <list, when the directory holds more than one repo>

## Documents produced
| Dimension | Document | Status | Key counts |
|---|---|---|---|
| Business logic | `docs/analysis/explore-business-logic/<date>.md` | generated \| reused \| failed | entities: n, workflows: n, rules: n (m not enforced), gaps: n |
| Architecture | `docs/analysis/explore-architecture/<date>.md` | generated \| reused \| failed | modules: n, deployable units: n, flows: n, issues: n by severity |
| Schema | `docs/analysis/explore-schema/<date>.md` | generated \| reused \| failed | tables: n, relationships: n, domains: n, discrepancies: n by severity |

## Next step
These three documents are the full input set for `propose-use-cases`,
`propose-architecture-changes` and `propose-schema-changes` (the business-logic document feeds
all three; architecture and schema each feed their matching propose-* skill).
```

A failed child still gets a row - status `failed`, key counts column stating what went wrong in
one short phrase (not the full error). There is no findings/issue section of its own here and no
new diagrams: everything except this index's own header and status table belongs to the three
children, not to this skill.

## Output location and summary

Write to `docs/analysis/explore-application/<YYYY-MM-DD>.md` relative to the current working
directory. If the user names a directory, treat it as the parent and keep
`explore-application/<YYYY-MM-DD>.md` under it; if they name a file, use that file. If the target
exists, use `-2`, `-3`, ... never overwrite.

End your reply with: which of the three children generated / were reused / failed this run, each
one's key counts, the file paths to all three child documents, and the path to the index.

## Self-check before writing

- Every child has exactly one status: generated, reused, or failed - never silently omitted.
- Every key-counts cell is copied verbatim from the child's own end-of-reply summary line (or, for
  a reused document, read from that document's own header/summary), never re-derived or guessed.
- The "Repos covered" line matches what the children actually reported covering, not an assumption
  made before they ran.
- The output path follows the same `-2`/`-3` versioning convention the three children use.
