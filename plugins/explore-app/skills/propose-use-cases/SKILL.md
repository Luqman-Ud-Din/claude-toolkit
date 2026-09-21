---
name: propose-use-cases
description: Compares an application's business logic (from a Business-Logic Document, BLD) against what standard apps in the same domain provide and against a bundled international-readiness checklist (multi-currency, tax and invoicing compliance, locale formatting, time zones, translations and RTL, data residency and privacy, regional payments, shipping, legal documents, support, feature toggles), then lists missing and partial use cases in priority order as proposals with rationale and scope. Use it whenever the user asks "what are we missing", wants a gap analysis, asks for standard use cases for a domain, asks what competitors or similar apps have, asks "are we ready to go international", mentions internationalization or localization gaps, asks to propose or recommend features for an international launch, asks "what should we add", or compares the app against industry norms - even when they never say "use case". Requires a BLD; offers to generate one with explore-business-logic when none is given.
---

## Plugin invocation

When invoking a skill from this bundle, use `explore-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Propose: use cases

Turns a Business-Logic Document (BLD) into a prioritised list of use cases the
product lacks, with international readiness as the lens. Read-only on the
codebase; the input is the BLD, not the code.

## Who you are while doing this

You are a product lead who has taken applications in this domain into several
international markets and has seen the launches that went wrong: the invoice
that was not legally valid in the new country, the price that rounded the wrong
way in a zero-decimal currency, the customer data that could not legally leave
the region, the payment page with no local method so nobody paid. You prioritise
what would block or embarrass a launch - compliance, tax, payments, data
residency - over what would merely be nice to have. You distinguish three
things: features every product in the domain has (table stakes), features every
product in the *target markets* must have (compliance and local expectation),
and features that are genuinely optional. You treat the checklists below as a
floor. Your experience of comparable products supplies the rest, and you make
that contribution visible in `Beyond the checklist`.

## Inputs

- **A BLD** - a file path or pasted text in the BLD format (sections: Domain
  overview, Entities, Workflows, Business rules, Validations, Integrations,
  Assumptions and gaps). If none is supplied: if the `explore-business-logic`
  skill is available, offer to generate one and stop until the user answers;
  otherwise ask for the document. The offer is a reply only - write no analysis
  file - and it asks in the same message for what the generation will need
  (repository path, subsystem scope if any) and for the target markets if those
  are also unknown, so one answer unblocks the whole run. Never proceed without
  a BLD and never assume which version is meant - the BLD may describe planned
  rather than current logic, so state its source (path, date, and whether it
  was generated or hand-written) at the top of the output.
- Optional: target markets/countries. If none are given and you are not already
  stopping for the BLD, say so and apply the i18n checklist generically, noting
  which items are country-dependent.
- Optional: a domain label, used only if the BLD's `Domain overview` is
  ambiguous. Ask when unsure - a wrong domain checklist is worse than none.

## Process

1. **Confirm the domain** from the BLD's `Domain overview`, entities and
   workflows. Name it precisely (for example "multi-tenant inventory and
   point-of-sale SaaS for SMEs", not "inventory").

2. **Build two checklists and apply both in full.**
   - *Domain checklist:* from your knowledge of comparable products, list the
     use cases a standard application in this domain provides - typically 20-50
     items with stable IDs `DOM-01`, `DOM-02`, ... grouped by capability area
     (for an inventory/POS product: catalog, stock control, purchasing, sales,
     returns, pricing and promotions, customers, reporting, users and
     permissions, integrations). Include the items every competitor has, not
     just the interesting ones.
   - *i18n checklist:* read `references/i18n-checklist.md` and apply every item.
     Do not skip items because the target markets are unknown - classify them
     and note the dependency.

3. **Classify every item** in both checklists as `PRESENT` (cite the BLD
   workflow, rule or entity that provides it), `PARTIAL` (cite what exists and
   state what is missing - including "present but wrong for a target market",
   such as a hard-coded rate that is incorrect there) or `MISSING`. Evidence comes from the BLD only; if the
   BLD is silent, the item is `MISSING`, and if the BLD's `Assumptions and gaps`
   lists it as uncertain, say so in the finding's Location. Each `PARTIAL` and
   `MISSING` item becomes a finding in the issue format below.

4. **Prioritise** the `PARTIAL` and `MISSING` items:
   legal/compliance necessity for a target market > revenue or operational
   impact > user expectation only. This ordering also sets `Severity`.

5. **Group findings into proposal items** - one proposal can resolve several
   findings when they ship together (for example "multi-currency pricing"
   resolves currency storage, exchange rates and rounding). A proposal's
   priority basis is the highest severity among the findings it resolves, and a
   foundation that a legal item depends on (a currency model, a legal-entity
   model) inherits that legal basis, so the list stays ordered by priority while
   every `Depends on` points to an earlier P-item. Give each a rationale and a
   rough scope for a small team (S: days, M: weeks, L: a quarter or more), and
   name any external lead time (accreditation, provider onboarding) separately,
   because that is usually the real critical path. A thin BLD makes most items
   MISSING; keep one finding per checklist item but group them into a roadmap
   of roughly ten to twenty-five proposals the reader can act on.

## Finding format

Every `PARTIAL`/`MISSING` item uses this block with every field filled. Prefix
`UC`, three-digit sequence.

```markdown
- **ID:** UC-001
- **Label:** MISSING | PARTIAL
- **Severity:** High (legal/compliance necessity for a target market) | Medium (revenue or operational impact) | Low (user expectation only)
- **Area:** <capability area or checklist section>
- **BLD reference:** BR-xxx | workflow name | entity name | none
- **Location:** what exists today (BLD workflow/rule/entity) or `not present`
- **Impact:** what the business cannot do, or what goes wrong at launch, if left as is
- **Remediation:** the concrete capability to add, and the proposal item (P-xxx) that delivers it
```

`PRESENT` items are not findings; they appear only in the checklist tables with
their BLD citation. Fields are never omitted or "N/A": when something cannot be
determined from the BLD, say what you looked for and where.

## Output

Lead with what to do; put the evidence after it. Sections in this order:

```markdown
# Proposed use cases - <application name>

Domain: <confirmed domain>
Source BLD: <path or "pasted text">, <date>, <generated by explore-business-logic | hand-written | edited>
Target markets: <list or "not specified">

## Proposed use cases
Ordered by priority. Each item:
### P-001 - <use case name>
- **Resolves:** UC-003, UC-007
- **Priority basis:** legal/compliance | revenue/operational | user expectation
- **Rationale:** why this matters for the launch, in two or three sentences
- **Scope:** S (days) | M (weeks) | L (a quarter or more), with the main pieces of work and any external lead time
- **Depends on:** earlier P-items only, or none

## Country-specific items
For each stated target market: the items that apply only there (tax regime,
e-invoicing mandate, payment methods, legal documents, data residency), each
pointing at its UC finding. If no markets were stated, say what would change once
they are.

## Domain checklist results
| ID | Use case | Status | BLD evidence / what is missing | Finding |
|---|---|---|---|---|
(DOM-xx IDs)

## i18n checklist results
| ID | Item | Status | BLD evidence / what is missing | Finding |
|---|---|---|---|---|
(one row per item in references/i18n-checklist.md, same IDs)

## Findings
(all UC-xxx blocks, highest severity first)

## Beyond the checklist
Findings that came from your judgment rather than from an item in either
checklist - things you have seen break comparable launches. Same eight-field
format, continuing the UC sequence, each resolved by a P-item; the last sentence
of `Impact` says which checklist item would have had to exist to catch it.
Recurring items here should be promoted into the checklist.
```

Main findings are numbered after sorting (highest severity first), so the IDs
read in order; `Beyond the checklist` items take the numbers after the last main
finding. The summary counts in your reply include the Beyond-the-checklist
items. On the stop path (no BLD), none of the output, location or self-check
sections apply: the offer is the whole reply, and the checklist file is read
only when the analysis actually runs.

Proposal items and findings must agree: every `Remediation` cites a `P-` item
and every `P-` item lists the findings it resolves.

## Output location and summary

Write to `docs/analysis/propose-use-cases/<YYYY-MM-DD>.md` relative to the
current working directory. If the user names a directory, treat it as the parent
and keep `propose-use-cases/<YYYY-MM-DD>.md` under it; if they name a file, use
that file. If the target exists, use `-2`, `-3`, ... never overwrite. End your
reply with: domain, BLD source, counts of PRESENT/PARTIAL/MISSING per checklist,
number of proposals with the top three named, and the file path.

## Self-check before writing

- Every item in `references/i18n-checklist.md` has a row with a status.
- Every `PRESENT` row cites a BLD workflow, rule or entity by name.
- Every `PARTIAL`/`MISSING` row points to a UC finding with all eight fields.
- Proposals are ordered legal > revenue/operational > expectation, and each
  states its priority basis and rationale.
- `Beyond the checklist` is present, even if it has one item; if you genuinely
  have nothing beyond the checklists, say so and why.
- Every count you state (PRESENT/PARTIAL/MISSING per checklist, findings,
  proposals) was recounted from the final tables, not carried from a draft.

## Bundled files

- `references/i18n-checklist.md` - the international-readiness checklist, with
  stable item IDs used in the results table. Read it in full every run.
