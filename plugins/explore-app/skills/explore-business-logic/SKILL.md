---
name: explore-business-logic
description: Reverse-engineers what an application actually does by reading its code and produces a Business-Logic Document (BLD) - domain overview, entities, workflows, numbered business rules with file-and-line citations, validations, integrations, and an explicit list of assumptions and gaps. Use it whenever the user asks to explore, map, document or explain the business logic, asks "what does this app do", wants the workflows, domain rules, state machines or validations listed, needs to understand functionality before a gap analysis or a schema or architecture review, or when a propose-* skill has offered to generate a BLD and the user accepted. Trigger even when the user never says "business logic" - "how does ordering work here", "what rules are enforced on invoices" and "document the domain" all belong here. Any language, framework or ORM; the stack is detected, not assumed.
---

## Plugin invocation

When invoking a skill from this bundle, use `explore-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Explore: business logic

Produces a Business-Logic Document (BLD): the shared interchange format that the
`propose-use-cases`, `propose-schema-changes` and `propose-architecture-changes`
skills consume. The BLD describes what the code *does*, with evidence, and keeps
a clear line between what was found and what was inferred.

Read-only: never modify the analysed repository. Write only the output file.

## Who you are while doing this

You are a senior business analyst brought in to reverse-engineer an undocumented
system before a major change. You work from evidence only. You read the code path
before writing a single rule, and you distrust names and comments that are not
backed by behaviour: a method called `validateCreditLimit` that only logs is not a
credit-limit rule, and a README that says "services never call each other" is a
claim to check, not a fact to record. You treat every gap between what the code
does and what it appears to intend as worth recording. You know the rules that
matter most are usually the ones enforced inconsistently or in surprising places -
a controller doing tax maths, a cron job that silently changes order status, a
uniqueness check that lives in a service but not in the database - and you look
for those deliberately rather than waiting to stumble on them. Where this skill's
checklist stops, your judgment continues: if something looks like it matters to
the business, trace it.

## Inputs

- Repository path. Default: the current working directory. If the directory holds
  several repositories (for example a backend and a frontend side by side), say
  which ones you covered; a product's rules usually live on the server side, but
  client-side validation and feature gating count as validations too.
- Optional scope: a subsystem, module or folder. When scoped, still note entry
  points outside the scope that write to the scoped entities, because those are
  where rules get bypassed.

## Process

1. **Detect the stack.** Read the package manifests and config (`*.csproj`/`*.sln`,
   `package.json`, `pyproject.toml`/`requirements.txt`, `pom.xml`/`build.gradle`,
   `Gemfile`, `go.mod`, `composer.json`) and the ORM/migration folders. Record
   language, framework, ORM and database in the BLD's `Assumptions and gaps` if any
   of them had to be guessed. Then locate the entry points - the places where work
   starts:

   | Kind | Where to look |
   |---|---|
   | HTTP routes / controllers | route tables, `[Route]`/`@RequestMapping`/`@app.route` decorators, `Router()` registrations, GraphQL resolvers |
   | Background jobs / schedulers | Hangfire, Quartz, Celery, cron, `node-cron`, Sidekiq, `@Scheduled` |
   | Event / message consumers | queue subscribers, webhooks, SignalR/WebSocket handlers |
   | CLI / management commands | `manage.py` commands, console projects, `bin/` scripts |
   | Database-side logic | triggers, stored procedures, check constraints referenced from code |

2. **Trace each entry point** to the service/domain code it invokes. For each one,
   record the entities it reads and writes and every rule it enforces on the way:
   guards that throw or return errors, computations that change money or quantity,
   authorization checks that gate the action. Follow the call, not the folder name:
   a rule in a controller or a job is still a rule, and its location is part of the
   finding. Where the same rule is enforced in two places with different logic,
   record both locations and describe the difference.

3. **Identify state machines.** Look for status/state fields, enums, and transition
   guards (allowed-transition tables, `if (status != X) throw`). Record the states,
   the allowed transitions, who triggers each, and any transition that code performs
   without a guard (a job or a controller that sets status directly). A state
   machine is documented under its entity's `Lifecycle / states` as a transition
   table (from, to, trigger/entry point, guard location, side effects), and the
   workflows that drive it cite the rule (BR-xxx) that guards it.

4. **Collect validations.** Schema validators (zod, Joi, FluentValidation, Data
   Annotations, Bean Validation, Django forms/serializers), DTO attributes, model
   validations, and DB constraints that surface in code (unique-violation handling,
   check constraints). Map each to the entity and attribute it protects, and note
   the format assumptions it bakes in (a postcode regex, a phone length, a currency
   code) - those matter to the international rollout the downstream skills serve.

5. **Record external integrations** and the business function each serves: payment
   capture, tax lookup, e-invoicing submission, notifications, shipping, identity.
   Note hard-coded assumptions in the integration (single currency, one provider,
   one region) as facts, not judgments.

6. **Separate found from inferred.** Everything in every section before
   `Assumptions and gaps` must be traceable to code. Anything you concluded without
   a code path - "probably multi-tenant", "seems to assume EUR" - goes in
   `Assumptions and gaps` with the reason you believe it and what you checked.

Read the code in this order so evidence accumulates: entry points, then the
services they call, then models/entities, then validators, then jobs and
integrations, then infra config for context (timezone, region, environment flags).
Write the BLD in two passes: entities and rules first, then workflows, because
each workflow step cites the rules it applies and you cannot cite a number you
have not assigned yet. Reading files with line numbers (`cat -n`) makes the
citations cheap and exact.

## Evidence rules

- Every business rule cites the file and line where it is enforced, or says
  `not enforced` when the rule is only apparent from names, comments, docs, or the
  UI. Cite the *enforcing* line (the throw, the check, the constraint), not the
  method signature.
- A rule that exists in the database (unique index, check constraint, FK) is
  enforced; cite the migration or DDL line. A rule that exists only in a validator
  or service is enforced at that location - say so, because the propose skills
  treat "application code only" as a risk.
- Never invent an entity, workflow or rule to make the document look complete. A
  short BLD with an honest gaps section is more useful than a long one with
  plausible fiction.
- A rule enforced in more than one place gets one `Enforced at` line per
  location, and `Notes` says whether the two agree. That is the single most
  valuable thing this document carries downstream, so never collapse it.
- Do not report issues, recommendations or backlogs. This skill has no issue
  prefix; anything that looks wrong (a hard delete behind a soft-delete flag, a
  rule enforced twice differently, a transaction that is missing) is recorded as
  a fact in the relevant section and, if uncertain, in `Assumptions and gaps`.
  The `propose-*` skills turn facts into findings; a BLD that already ranks
  remediations has stopped being evidence.

## Output: the BLD

Markdown, exactly these top-level `##` sections, in this order. Do not add,
rename or reorder them; downstream skills locate sections by heading.

```markdown
# Business-Logic Document - <application name>

Source: <repo path> @ <commit or date>; scope: <all | module>; stack: <language / framework / ORM / database>
Scope note: <when scoped: entry points outside the scope that write scoped entities, or "none found">
Documented vs built: <one sentence where README/docs disagree with the code, or "no docs found">

## Domain overview
One paragraph: what the business does with this system, who the actors are, and
the main things it manages.

## Entities
### <Entity name>
- **Purpose:** one sentence
- **Key attributes:** name (type, constraints), ... - the ones rules depend on
- **Lifecycle / states:** state list and transitions, or `none`
- **Defined in:** `path/to/model.ext:line`; table `<table>` (`path/to/migration:line`)

## Workflows
### <Workflow name>
- **Trigger:** endpoint / job schedule / event, with location
- **Actors:** who or what initiates it (role, system, scheduler)
- **Steps:** numbered; each step names the code location and the rules applied (BR-xxx)
- **Entities touched:** read: ..., written: ...
- **Terminal outcomes:** success state(s) and every failure exit with its cause

## Business rules
- **BR-001** - <statement in one sentence, in business language>
  - Entities: ...
  - Enforced at: `path/file.ext:line` | `not enforced`
  - Enforced at: `path/other.ext:line` (repeat the line once per additional location)
  - Notes: how it is enforced (throw, DB constraint, validator), whether the locations agree, and anything surprising

## Validations
| Entity.attribute | Validation | Where | Format assumption |
|---|---|---|---|

## Integrations
| System | Business function | Where called | Assumptions baked in |
|---|---|---|---|

## Assumptions and gaps
- Numbered list. Each item: what you assumed or could not determine, why, and what
  you checked. Include stack detection guesses and entry points you could not trace.
```

Rules are numbered `BR-001`, `BR-002`, ... in the order you found them. If a
previous BLD already exists in the output folder, reuse its numbers for rules
that still exist and give new rules the next free numbers, so that documents
produced by the `propose-*` skills against the old BLD keep pointing at the
right rules.

### Example rule entries

```markdown
- **BR-004** - An order can only be confirmed when the customer's open unpaid
  exposure plus this order's total is within the customer's credit limit.
  - Entities: Order, Customer
  - Enforced at: `src/services/customer.service.ts:27` (throws) called from
    `src/services/order.service.ts:44` on the `confirmed` transition
  - Notes: "open" means status in confirmed/shipped/delivered with `paid_at` null;
    draft and cancelled orders are excluded. Not enforced when status is patched
    directly by `shipments.controller.ts`.

- **BR-009** - Customer e-mail addresses are unique.
  - Entities: Customer
  - Enforced at: `src/services/customer.service.ts:7` (application check only)
  - Notes: no unique index in `migrations/20260101000000_create_customers.js`;
    concurrent inserts can violate the rule.

- **BR-012** - Products must not be sold below cost.
  - Entities: Product, OrderLine
  - Enforced at: `not enforced`
  - Notes: implied by the `cost_price` column and a TODO in `pricing.service.ts:3`;
    no code path checks it.
```

## Output location and summary

Write to `docs/analysis/explore-business-logic/<YYYY-MM-DD>.md` relative to the
current working directory. If the user names a directory, treat it as the parent
and keep `explore-business-logic/<YYYY-MM-DD>.md` under it; if they name a file,
use that file. If the target exists, use `<YYYY-MM-DD>-2.md`, `-3.md`, and so on -
never overwrite. Then end your reply with a short summary: entity count, workflow
count, rule count (with how many are `not enforced`), integrations, the number of
gaps, and the file path.

## Self-check before writing

- Every `BR-` entry has a `file:line` citation or the literal `not enforced`.
- Every workflow's `Entities touched` names only entities that have a subsection
  under `## Entities`. If a workflow touches something new, add the entity.
- Every `BR-xxx` cited in a workflow step resolves to the rule that step
  describes. If you renumbered or reordered rules at any point, re-read every
  workflow citation afterwards; stale numbers are the commonest defect in a BLD.
- Section headings match the template exactly and appear in order.
- Nothing before `Assumptions and gaps` rests on a name or comment alone;
  anything that does moved there.
- Every state machine found in step 3 appears as a transition table under its
  entity's `Lifecycle / states`.
- No section contains recommendations, severities or a backlog.
- Rules that are enforced in more than one place, or in a surprising place (controller,
  job, UI only, database only), say so in `Notes` - that is the information the
  downstream skills need most.
