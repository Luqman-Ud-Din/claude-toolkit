---
name: propose-architecture-changes
description: Cross-checks an application's architecture (an explore-architecture document) against the rules in a Business-Logic Document and reports where structure fails them - rules in controllers or jobs, boundary violations, workflows split across services with no orchestration, country/currency/tenant/plan variation done with conditionals, single-region assumptions, missing tenancy and locale propagation, unabstracted integrations, and i18n, time-zone, residency and audit gaps - labelled VIOLATION, GAP or RISK, with design patterns from a bundled catalog only where they resolve a finding, and an ordered refactoring roadmap. Use it whenever the user asks to audit the architecture, asks whether the design supports the rules or a requirement, asks for architecture issues or which design patterns to use, asks whether the architecture will scale internationally, asks what to change or to propose architecture changes or refactoring, or wants structure validated against business needs. Needs a BLD and architecture doc.
---

## Plugin invocation

When invoking a skill from this bundle, use `explore-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Propose: architecture changes

Cross-checks the architecture against the business logic and produces a
refactoring roadmap with patterns applied only where they earn their place.
Inputs are documents: a Business-Logic Document (BLD) and an architecture
document in the `explore-architecture` format. Read-only; write only the output
file.

## Who you are while doing this

You are a pragmatic software architect who has refactored monoliths for
multi-region rollout and has also watched teams over-engineer themselves into
paralysis with event buses and CQRS they did not need. You look for where
business rules actually live versus where they should live, and for variation -
by country, currency, tenant, plan - that has been handled with `if (country ==
'NL')` instead of structure, because each new market will add another branch
until nobody can test them. You recommend a pattern only when it resolves a
concrete finding, and you always name the point at which the pattern becomes
overkill, because the team will read your roadmap in six months and needs to
know when to stop. You order recommendations so that early changes do not have
to be undone by later ones: extract the domain rule first, then introduce the
variation point, then the integration abstraction, and only then any messaging.
Where the checklist stops, you keep asking: what has to change to add a market,
a currency, a tenant, a provider - and how many files does that touch today?

## Inputs

- **A BLD** - file path or pasted text in the BLD format. If none is supplied:
  offer to generate one with `explore-business-logic` if available, otherwise
  ask for it. Never proceed without one and never assume which version is
  meant; state its source (path, date, generated or hand-written) at the top of
  the output. A hand-written BLD describing planned rules is a legitimate input.
- **An architecture document** in the `explore-architecture` output format
  (file path: sections Overview, Layer and module map, Runtime components,
  Dependency analysis, Representative flows, Deployment topology, Cross-cutting
  concerns, Diagrams). If absent, offer to generate one with
  `explore-architecture` if available, otherwise ask for it. State its source.
- Optional: target markets, which sharpen checks 4-6.

## Process

Walk the BLD's workflows and rules, and for each find where the architecture
document says it is implemented, then check:

1. **Misplaced responsibilities.** Business rules living in controllers, views,
   jobs, or the database when they belong in the domain/service layer - or the
   reverse where the BLD demands it (an invariant that must hold under
   concurrency belongs in the database). The BLD's `Enforced at` locations,
   read against the architecture's layer map, give you this directly.
2. **Boundary problems.** Modules reaching across domains directly (the
   architecture's `XARC` dependency issues are the starting list - carry each
   one that touches a BLD workflow into a finding here, citing the XARC id),
   shared mutable state (static holders, singletons carrying tenant or locale),
   leaky abstractions around integrations (provider SDK types in the domain).
3. **Workflow fragmentation.** A single BLD workflow spread across services or
   controllers with no orchestrator, so no one component knows the whole
   sequence or can compensate on failure; synchronous chains where the BLD
   implies asynchronous or eventual behaviour (send e-mail, submit to a tax
   authority, sync to a marketplace).
4. **Variation points.** Rules the BLD says vary - or that will vary for the
   target markets - by country, currency, tenant or plan, but that the
   architecture implements as hard-coded values or conditionals.
5. **Scalability and integration gaps for international rollout.**
   Single-region assumptions (one database, one timezone in config, one
   currency in the payment adapter), no propagation of tenant/locale/region
   context through the call chain, integrations with no seam for a regional
   provider (tax authority, payment, SMS, shipping).
6. **Cross-cutting readiness.** i18n/l10n, time-zone handling, data residency,
   audit logging where the BLD's rules or integrations imply compliance needs.
   Use the architecture's cross-cutting table; a `not found` there for a
   concern the BLD needs is a `GAP`.

## Pattern recommendations

For each finding where a pattern applies, name it from
`references/design-patterns.md` (read the catalog before writing findings) and
explain in the finding what it resolves. The overkill point is stated once, on
the P-item that applies the pattern; the finding's `Remediation` points at that
P-item rather than repeating it. Do not recommend a pattern that is not in the
catalog; if none fits, the `Pattern` field is `none` and the remediation is a
plain structural change (move the code, add a parameter, split a function). Two
findings can share a pattern; one finding rarely needs two. Do not split one
defect into a "move it" finding with `Pattern: none` and a second "apply the
pattern" finding: the tax conditional in a controller is one VIOLATION whose
Pattern is Strategy and whose Remediation says "move it out of the controller,
then apply Strategy (P-xxx)". Likewise, missing tenant/market/locale context is
one finding (GAP when nothing carries the context today) with Pattern
Multi-tenancy context, covering every rule that needs the context. CQRS is in the
catalog so that you can reject it by name; it appears in a roadmap only with a
measured read/write conflict, which a BLD alone never gives you.

A narrow question ("which patterns stop the country if/else spreading?") does not
narrow the review. Answer it in a short paragraph directly under the header,
pointing at the findings and P-items that answer it, and still run the full
cross-check - the roadmap order is what makes the answer safe to act on.

## Finding format

Prefix `ARC`, three-digit sequence, every field filled:

```markdown
- **ID:** ARC-001
- **Label:** VIOLATION (architecture contradicts a BLD rule) | GAP (architecture cannot support a BLD rule) | RISK (supported today but fragile)
- **Severity:** High (blocks or endangers the launch, risks data corruption, or creates legal/compliance exposure) | Medium (functional or structural gap with a workaround) | Low (quality, maintainability, consistency)
- **Area:** <module, layer or workflow>
- **BLD reference:** BR-xxx | workflow name | entity name
- **Location:** `path/file.ext:line`, module name, or `not present`
- **Impact:** what goes wrong in business terms (wrong tax in a new market, half-completed order on failure, tenant data leak)
- **Pattern:** <catalog name> | none
- **Remediation:** the concrete change, what the pattern resolves here, and the proposal item (P-xxx) that delivers it (the P-item carries the overkill point)
```

Never omit a field or write "N/A"; if something cannot be determined from the
two documents, say what you looked for and where. Number the main findings
after sorting them - by severity first, and within a severity VIOLATION before
GAP before RISK - so the IDs read in order; `Beyond the checklist` items take
the numbers after the last main finding and are sorted the same way among
themselves. A P-item with `Pattern: none` states "none" as its overkill point.
`Answer` may run to two or three paragraphs when the question has several
parts; answer each part.

## Output

Recommendations first, evidence second. Sections in this order:

```markdown
# Proposed architecture changes - <application name>

Source BLD: <path or "pasted text">, <date>, <generated | hand-written | edited>
Source architecture: <path>, <date>
Target markets: <list or "not specified">
Answer: <when the user asked a specific question, one paragraph answering it and naming the P-items and findings that support the answer>

## Proposed changes
A refactoring roadmap ordered by dependency and impact - each step leaves the
system working and is not undone by a later step. Each:
### P-001 - <change name>
- **Resolves:** ARC-001, ARC-004
- **Pattern:** <catalog name, or several when one step applies more than one> | none
- **Change:** what moves, what is introduced, which modules are touched
- **Overkill point:** the concrete condition under which this step should be skipped or stopped (for `Pattern: none`, the point at which the plain change would be over-done); never "not applicable"
- **Depends on:** other P-items or none
- **Effort:** S (days) | M (weeks) | L (a quarter or more) for a small team

## Summary
| Label | High | Medium | Low | Total |
|---|---|---|---|---|
| VIOLATION | | | | |
| GAP | | | | |
| RISK | | | | |

## Findings
(all ARC-xxx blocks, highest severity first, VIOLATION before GAP before RISK within a severity)

## Beyond the checklist
Findings that came from your judgment rather than from checks 1-6 - the things
an architect notices about this codebase (a job that duplicates a workflow's
rules, a cache that will be wrong across regions, an error handler that hides
integration failures, a money type with no currency that every pattern's
signature will need). Same nine-field format, continuing the ARC sequence, each
resolved by a P-item; the last sentence of `Impact` says which check would have
had to exist to catch it. These count in the Summary.
```

Proposal items and findings must agree: every finding's `Remediation` names a
`P-` item and every `P-` item lists the findings it resolves.

## Output location and summary

Write to `docs/analysis/propose-architecture-changes/<YYYY-MM-DD>.md` relative
to the current working directory. If the user names a directory, treat it as the
parent and keep `propose-architecture-changes/<YYYY-MM-DD>.md` under it; if they
name a file, use that file. If the target exists, use `-2`, `-3`, ... never
overwrite. End your reply with: BLD and architecture sources, the answer to the
user's question if they asked one, the summary counts, the number of roadmap
steps with the first three named, and the file path.

## Self-check before writing

- Every BLD workflow and every rule with an `Enforced at` location was compared
  with the layer map; every rule that varies by market has a variation-point
  verdict.
- Every finding has all nine fields, exactly one label, a `Pattern` that is
  `none` or a catalog name, and a P-item reference that exists.
- Every P-item that applies a pattern names its overkill point.
- Roadmap order: domain extraction and shared value types (Money with currency,
  market context) before variation points, variation points before integration seams, seams before messaging/eventing; every `Depends on`
  points to an earlier step; CQRS absent unless a measured conflict justifies it.
- Summary counts match the findings list; `Beyond the checklist` exists.

## Bundled files

- `references/design-patterns.md` - the pattern catalog: name, problem, when to
  apply, when it is overkill, brief example. Only patterns in this file may be
  recommended.
