---
name: audit-multi-tenant-isolation
description: Finds every place a multi-tenant SaaS app could leak data across tenants - establishes the tenancy model and how the tenant is resolved, checks tenant id comes from the authenticated identity (never body/query/header), every query is tenant-scoped, lists queries that bypass the filter (raw SQL, filter-disabling calls, admin/aggregate paths), and checks writes, background jobs, queue consumers, webhooks, cache/session/search/blob keys, logs, cross-tenant admin tooling, tenant-scoped uniqueness, quotas, encryption, offboarding, and migrations. Use it whenever the user mentions multi-tenant, tenants, SaaS, tenant isolation, cross-tenant, data leakage between customers, row-level security, or tenant scoping, or asks to audit a SaaS/multi-customer app, and in any security audit of an app serving multiple organizations - even if the user does not name this skill. Produces the tenancy model, a tenant-context flow diagram, a data-access-path inventory flagging unscoped paths, findings, and a cross-tenant probe.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit multi-tenant isolation

In a multi-tenant SaaS product the worst outcome is one customer reading or
changing another customer's data. This skill maps how tenant context flows from
the token to the database and back, inventories every data-access path with its
scoping mechanism, flags the unscoped ones, and ships a probe that authenticates
as tenant A and tries to reach tenant B's data through every endpoint - including
with tampered tenant identifiers.

**Read-only rule:** never modify the audited code. Write only under `audit/`. The
probe script only runs when the user supplies a URL, and only against a
disposable environment seeded with two throwaway tenants (it does real writes).

## Inputs and prerequisites

- The repository to audit.
- Optional, for the dynamic probe: a **test** base URL and `tenants.json` with a
  token + resource ids for two tenants (A and B), plus the tenant-header name if
  the app resolves tenant from a header.
- `audit/stack.json` if the orchestrator wrote one; otherwise this skill detects
  the stack.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection`,
  `audit-code-scan` (grep pass, and the file walker `data_access_paths.py` imports),
  `audit-endpoint-inventory` (which itself needs `audit-sensitive-data-catalog`)
  and `audit-finding-writer`.

## Workflow

### 1. Resolve the stack
Run `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`. Open only the matching backend
`references/<stack>.md`, plus the frontend stack file (the frontend is not the
isolation boundary; it only builds requests) and keep
`references/tenancy-models.md` open throughout. If nothing matches use
`$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md` and say so.

### 2. Establish the tenancy model and context flow
Using `references/tenancy-models.md`:
- Name the model (shared-DB-with-column, schema-per-tenant, db-per-tenant, or
  hybrid) and how the current tenant is resolved (subdomain, path, header, token
  claim). State how you confirmed each.
- Draw the tenant-context flow diagram (resolution -> propagation -> enforcement)
  for the actual app, marking every break in the chain.

### 3. Automated pass
- Run `audit-endpoint-inventory` first, or reuse
  `audit/evidence/audit-endpoint-inventory/endpoints.json` when the orchestrator
  already produced it:
  `python "$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py" <repo>`.
  It gives the endpoint list, the probe input (`endpoints.probe.json`) and two
  read-only cross-checks for the manual trace: parameters with
  `identifier == "tenant"` (tenant ids taken from route, query or body) and, for
  jobs, `job.identity_context`. `data_access_paths.py` stays the source of the
  `background-job` category.
- Build the data-access-path inventory:
  `python scripts/data_access_paths.py <repo> --stack <id> --out audit/evidence/audit-multi-tenant-isolation/paths.json --md audit/evidence/audit-multi-tenant-isolation/paths.md`.
  It flags queries, raw SQL, filter-bypass calls, tenant-from-input, cache keys,
  blob paths, and background jobs, each with a scoping guess. Resolve every `?`
  and `NONE` by reading the code.
- Run the grep candidate pass:
  `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-multi-tenant-isolation/hits.json`.

### 4. Manual trace of the highest-risk flows
Work the checklist in `references/tenancy-models.md`. Priorities:
1. Every filter-bypass (`IgnoreQueryFilters`/`unscoped`/native SQL) - is a tenant
   predicate added? Build the explicit "queries that bypass the filter" list.
2. Every write path - is tenant id set from context, never from input?
3. Background jobs / queue consumers / webhooks - do they carry and enforce tenant?
4. Cache keys, blob/file paths, search indexes - tenant segment present?
5. Admin/impersonation/"switch tenant" tooling - authorized and audit-logged?
6. Tenant-scoped uniqueness, per-tenant quotas, offboarding, migrations.

### 5. Confirm dynamically (only if the user gave a URL)
Take `endpoints.probe.json` from audit-endpoint-inventory (it already has
`id_params` and `operation`) and add tamper `body`/`query` with `{tenant_b}` where
`tenant_params` lists a tenant field. Copy it to
`audit/evidence/audit-multi-tenant-isolation/endpoints.json` first, delete rows not
worth probing (for example `/health`), relabel `operation` by hand where the fixed
rule differs from what the endpoint does, and give `tenants.json` one id key per
`id_params` value. Then, against a disposable env only:
```
python scripts/tenant_probe.py --base-url <url> \
  --tenants tenants.json --endpoints audit/evidence/audit-multi-tenant-isolation/endpoints.json \
  --tenant-header X-Tenant-Id \
  --out audit/evidence/audit-multi-tenant-isolation/probe.json
```
It calls each endpoint as tenant A twice (untampered, then injecting tenant B's
id into body/query/header) across read/write/list/search/download/export. Every
FAIL is a confirmed cross-tenant leak; the deliverable must demonstrate at least
one cross-tenant read when a leak exists. If no URL is supplied, skip and record
it under "Not checked".

### 6. Write findings
`python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" init audit-multi-tenant-isolation`, then for each
confirmed issue write the finding block (below), save to a temp JSON, and
`python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" add audit/findings/audit-multi-tenant-isolation.json --from <finding.json>`.
Regenerate the report body with
`python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" md audit/findings/audit-multi-tenant-isolation.json --out audit/reports/audit-multi-tenant-isolation.md`,
then prepend the tenancy model, flow diagram, and inventory table from the
template below. Messy raw inputs can go through `audit-finding-writer`.

### 7. Record what was NOT checked
Add gaps to `scope.not_checked`: no test URL (probe skipped), backups/DR policy
(outside the repo), search-index internals, external analytics, data-residency
requirements not documented. Write
`audit/status/audit-multi-tenant-isolation.json`
(`{"skill":"audit-multi-tenant-isolation","status":"completed|failed|skipped","reason":...,"started_at":...,"finished_at":...}`).

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `TENANT`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Evidence:**

```lang
<the exact lines, or the probe command and its pass/fail output>
```

- **Impact:** Plain language - which tenant can reach which other tenant's data, read or write. One or two sentences with the severity justification.
- **Remediation:** The concrete fix in this stack, with a short example.
- **Reference:** CWE-nnn, ASVS-x.y.z, OWASP-A0n:2021

Maps to `findings.json` fields `title`, `severity`, `confidence`, `location`,
`evidence`, `impact`, `remediation`, `references`, optional `tags`/`root_cause_key`.
Recurring references: CWE-284, CWE-639, CWE-524, CWE-668; ASVS 4.1/4.2, 8.1;
OWASP-A01:2021.

## Output template (`audit/reports/audit-multi-tenant-isolation.md`)

```markdown
# Multi-tenant isolation audit

## Tenancy model
- Model: <shared-db-column | schema-per-tenant | db-per-tenant | hybrid>
- Tenant resolution: <subdomain | path | header | token claim> (how confirmed)

## Tenant-context flow
```
Resolution -> Propagation -> Enforcement
(paste the actual diagram, marking every break in the chain)
```

## Data-access-path inventory
| Category | Scoping | Risk | Location | Note |
|---|---|---|---|---|
| raw-sql | NONE | high | Controllers/InvoicesController.cs:28 | ignores query filter |
| ... | ... | ... | ... | ... |

## Queries that bypass the tenant filter
(the explicit list: raw SQL, IgnoreQueryFilters/unscoped, admin/aggregate paths.)

## Cross-tenant probe result
(paste the tenant_probe.py pass/fail table, or "Not run - no test URL supplied".)

## Findings
(generated by findings.py md.)

### Not checked
- <item> - <reason>
```

## Examples

**Input:** `InvoicesController.Report` runs
`_db.Invoices.FromSqlRaw("SELECT * FROM Invoices").IgnoreQueryFilters()`.
**Finding:** `[Critical] TENANT-001 - Invoice report returns every tenant's
invoices` - Impact "any signed-in user can read all customers' invoices; the raw
query ignores the tenant filter"; Remediation "add `WHERE TenantId = {tenant}`
with `FromSqlInterpolated`, or filter after the raw call"; Reference CWE-284,
OWASP-A01:2021.

**Input:** `CreateInvoiceDto` has a `TenantId` and `Create` sets
`inv.TenantId = dto.TenantId`.
**Finding:** `[High] TENANT-002 - Invoice creation trusts the tenant id from the
body` - Impact "a user can create invoices in another tenant by sending a
different tenantId"; Remediation "set `TenantId = _tenant.TenantId` and remove it
from the DTO"; Reference CWE-639.

## Bundled files

- `references/<stack>.md` - per-stack where-to-look, good/bad shapes, false positives (dotnet, java-spring, node-express, python-django, angular, react, vue; to add a stack, copy `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`).
- `references/tenancy-models.md` - tenancy models, the flow diagram, and the full leak-point checklist.
- `scripts/data_access_paths.py` - static inventory of data-access paths with tenant-scoping and unscoped flags (walks files with `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py`).
- `scripts/tenant_probe.py` - cross-tenant probe (read/write/list/search/download/export + tampered ids; reads audit-endpoint-inventory's `endpoints.probe.json` plus tamper values; needs a test URL; never runs on its own).
- `scripts/patterns/<stack>.json` - the grep candidate patterns.
- Atomic scripts this skill calls: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` (stack), `$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py` (endpoints and probe input), `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` (candidate pass), `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` (findings I/O).
- `evals/` - a sample .NET SaaS repo planting all five required issues plus negatives.
