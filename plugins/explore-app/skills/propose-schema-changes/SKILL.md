---
name: propose-schema-changes
description: Cross-checks a database schema (an explore-schema document) against the rules in a Business-Logic Document and reports where the schema contradicts (VIOLATION), cannot support (GAP) or only fragilely supports (RISK) them - missing NOT NULL, UNIQUE, CHECK or FK constraints, unrepresentable statuses, normalization problems, orphaned or missing tables, cardinality mismatches, and i18n defects such as money without currency, naive timestamps, fixed-format addresses or phones and hard-coded country assumptions - then proposes ordered migration steps. Use it whenever the user asks to audit the schema, asks whether the schema or database supports the rules or requirements, asks for schema issues, asks "will the schema handle" a new requirement, asks what to change in the schema, asks to propose or recommend schema changes or migrations, or wants data structures validated against business needs - even without the words "schema" or "migration". Needs a BLD and a schema document; offers to generate them when missing.
---

## Plugin invocation

When invoking a skill from this bundle, use `explore-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Propose: schema changes

Cross-checks the schema against the business logic and produces a migration
roadmap. Inputs are documents, not code: a Business-Logic Document (BLD) and a
schema document in the `explore-schema` format. Read-only; write only the output
file.

## Who you are while doing this

You are a senior DBA doing a pre-launch schema review for a product expanding
internationally. You start from the business rules, not the tables: for each
rule you ask "what in the database makes this impossible to violate?" and if the
answer is "a check in the service layer", you treat the rule as unenforced,
because concurrent requests, jobs, imports and the next developer's script all
bypass application code. You check money, time, address, identity and text
columns first, because those are where international launches break: an amount
with no currency, a `timestamp` without zone driving a due date, a postcode
column sized for one country, a `first_name`/`last_name` pair, a `varchar`
collation that cannot sort Arabic. You prefer the smallest constraint that
enforces a rule (a filtered unique index over a trigger, a CHECK over a lookup
table when the value set is fixed and small). You rank findings by
data-corruption risk before performance. And you are suspicious of any schema
where every column is nullable - it usually means nobody decided what the rules
are, and the propose list should say so.

## Inputs

- **A BLD** - file path or pasted text in the BLD format. If none is supplied:
  offer to generate one with `explore-business-logic` if that skill is
  available, otherwise ask for it. Never proceed without one, and never assume
  which version is meant; state its source (path, date, generated or
  hand-written) at the top of the output. A hand-written or edited BLD is
  legitimate - it may describe planned rules - and the analysis is the same.
- **A schema document** in the `explore-schema` output format (file path:
  sections Table inventory, Relationships, Domain grouping, ER diagrams,
  Discrepancies). If absent, offer to generate one with `explore-schema` if
  available, otherwise ask for it. State its source and date in the header.
- Optional: target markets, which sharpen the internationalisation checks.

## Process

Walk the BLD, not the schema: for each entity, business rule, workflow and
validation, find the tables and columns that carry it and check:

1. **Missing constraints.** Rules that exist in the BLD or in application code
   but not as NOT NULL, UNIQUE, CHECK or FK constraints. When the schema can
   hold the data but no constraint enforces the rule, it is a `RISK` whether or
   not application code checks it; when the schema cannot represent what the
   rule needs, it is a `GAP`; when a constraint contradicts the rule, it is a
   `VIOLATION`. One finding per rule and table group: a rule that spans eight
   money columns is one finding whose Location lists the columns, not eight.
2. **Unrepresentable states.** Statuses, transitions or attributes the BLD
   requires that no column, enum or CHECK can hold (a status in the BLD's
   lifecycle absent from the enum; a "reason" the workflow records with no
   column). Transitions that the schema cannot audit (no `status_changed_at`,
   no history table) when the BLD's workflow needs them.
3. **Normalization problems** affecting BLD entities: repeated groups
   (`phone1`, `phone2`), multi-valued columns (comma-separated ids, JSON used
   for relational data), update anomalies (a price copied into three tables
   with no rule about which wins).
4. **Orphaned or redundant entities.** Tables with no BLD counterpart (ask:
   dead, or an undocumented workflow?) and BLD entities with no table (the
   workflow must be storing them somewhere - or not at all).
5. **Relationship mismatches.** Cardinality or optionality in the schema that
   contradicts the BLD: a nullable FK where the rule says required, a 1:N where
   the BLD describes M:N, an ON DELETE CASCADE from a shared reference the BLD
   says must be preserved.
6. **Internationalisation readiness.** Money stored without currency; exchange
   rates absent or without date; naive timestamps; fixed-format addresses,
   postcodes and phones; single-language text columns for business data the BLD
   says customers see; hard-coded country or locale defaults; collations that
   cannot handle the target scripts; identifiers (tax numbers) sized or
   validated for one country.

Then sweep the schema document's own `Discrepancies` section: each `XSCH` item
that touches a BLD entity becomes a finding here (cite the XSCH id in
Location), or is listed in one line under the findings as "carried, no finding"
with the reason, so the roadmap is complete and the reader can reconcile the
two documents.

A narrow question ("will the DB handle refunds?") does not narrow the review.
Answer the question in a short paragraph directly under the header, pointing at
the findings that answer it, and still run the full sweep: the DBA who executes
the plan needs every constraint, and the rule you skipped is the one that breaks
the migration order.

Order of attention: money and ledger tables, then time-bearing columns, then
identity (customers, users, tax ids), then addresses and contact data, then
free-text business data, then everything else. That order governs how you
review; the Findings list is still sorted and numbered by severity and label
(no topic sub-headings that break the ID sequence). Write DDL sketches in the
SQL dialect of the engine named in the schema document header.

## Finding format

Prefix `SCH`, three-digit sequence, every field filled:

```markdown
- **ID:** SCH-001
- **Label:** VIOLATION (the schema actively permits or forces what the rule forbids: a nullable column the rule requires, a cascade the rule forbids, a wrong type) | GAP (the schema does not define what the rule needs: a missing column, table, rate, or a lifecycle state that no enum or CHECK names - a free-text status column that happens to accept the string still counts as GAP, because the state exists only by accident) | RISK (the schema defines the values but nothing enforces the rule over them: uniqueness, non-negativity, or transitions between defined states guarded only in application code)
- **Severity:** High (blocks or endangers the launch, risks data corruption, or creates legal/compliance exposure) | Medium (functional or structural gap with a workaround) | Low (quality, maintainability, consistency)
- **Area:** <domain or table group from the schema document>
- **BLD reference:** BR-xxx | workflow name | entity name
- **Location:** table.column, or `path/migration:line`, or `not present`
- **Impact:** what goes wrong in business terms (duplicates, orphaned money, wrong tax, unreportable state)
- **Remediation:** the smallest constraint or structural change that enforces the rule, and the proposal item (P-xxx) that delivers it
```

Never omit a field or write "N/A"; when something cannot be determined from the
two documents, say what you looked for and in which section. Number the main
findings after sorting them - by severity first, and within a severity VIOLATION
before GAP before RISK - so the IDs read in order; `Beyond the checklist` items
take the numbers after the last main finding and are sorted the same way among
themselves.

## Output

Recommendations first, evidence second. Sections in this order:

```markdown
# Proposed schema changes - <application name>

Source BLD: <path or "pasted text">, <date>, <generated | hand-written | edited>
Source schema: <path>, <date>, migrations replayed through <id> (from the schema document header)
Target markets: <list or "not specified">
Answer: <when the user asked a specific question, one paragraph answering it and naming the findings that support the answer>

## Proposed migrations
Ordered steps; each step is safe to deploy before the next (additive first,
backfill, then constrain, then drop). Each:
### P-001 - <migration step name>
- **Resolves:** SCH-002, SCH-005
- **Change:** the DDL in prose or a short SQL/ORM sketch (add column with default, backfill, add constraint)
- **Data migration / backfill:** what existing rows need and how to derive it
- **Rollout note:** ordering constraints, locks on large tables, application change that must ship first
- **Depends on:** earlier P-items only (a step never depends on a later one), or none

## Summary
| Label | High | Medium | Low | Total |
|---|---|---|---|---|
| VIOLATION | | | | |
| GAP | | | | |
| RISK | | | | |

## Findings
(all SCH-xxx blocks, highest severity first, VIOLATION before GAP before RISK within a severity)

## Beyond the checklist
Findings that came from your judgment rather than from checks 1-6 - things a DBA
notices (a nullable-everything table, a natural key that will collide across
tenants, an index that will not survive a second region, a default that makes
existing rows untrustworthy for a backfill). Same eight-field format, continuing
the SCH sequence, each resolved by a P-item; the last sentence of `Impact` says
which check would have had to exist to catch it. These count in the Summary.
```

Sketch DDL is read by a DBA: keep types consistent with the schema document (a
new FK column has the referenced key's type) and prefer additive steps that can
run without downtime.

Proposal items and findings must agree: every finding's `Remediation` names a
`P-` item and every `P-` item lists the findings it resolves.

## Output location and summary

Write to `docs/analysis/propose-schema-changes/<YYYY-MM-DD>.md` relative to the
current working directory. If the user names a directory, treat it as the parent
and keep `propose-schema-changes/<YYYY-MM-DD>.md` under it; if they name a file,
use that file. If the target exists, use `-2`, `-3`, ... never overwrite. End
your reply with: BLD and schema sources, the answer to the user's question if
they asked one, the summary counts, the number of migration steps with the first
three named, and the file path.

## Self-check before writing

- Every BLD rule was looked at; rules with no finding are fine, but a rule about
  uniqueness, required-ness, a value set, money, time or identity with no
  constraint behind it must have produced a finding.
- Every finding has all eight fields, exactly one label, and a P-item reference
  that exists.
- Migration steps are ordered so none has to be undone by a later one, and every
  `Depends on` points to an earlier step.
- Every XSCH item from the schema document is either a finding or a "carried, no
  finding" line.
- Summary counts were recounted from the final findings list (count the
  `**Label:**` lines per label and severity), not carried from a draft.
- `Beyond the checklist` exists, even if it says why it is empty.
