# Tenancy models, context flow, and the full isolation checklist

Use this to (1) name the tenancy model, (2) draw the tenant-context flow diagram
the report requires, and (3) work the complete list of leak points the spec
enumerates.

## 1. Establish the tenancy model
Pick the one that matches the code, and say how you confirmed it:
- **Shared database, tenant column** - one DB, a `TenantId`/`CompanyId` on each
  tenant-owned table, isolation by query filter or row-level security. (This
  codebase's Product/Master DBs.)
- **Schema-per-tenant** - one DB, a schema per tenant, connection activates the
  schema (`django-tenants`, `SET search_path`).
- **Database-per-tenant** - a separate database/connection string per tenant
  (this codebase's `CustomConnectionString.DbName` selected from the token).
- **Hybrid** - e.g. shared master DB + per-tenant data DB.

## 2. How is the current tenant resolved?
Trace the resolution and record it: **subdomain**, **path segment**, **request
header**, or **token claim**. Only a value bound to the authenticated identity
(token claim, or a server-side lookup keyed by it) is trustworthy. A header or
path the client controls is not - it may only *select* among tenants the caller
is already authorized for, after a server check.

## 3. Tenant-context flow diagram (put this in the report)
```
Resolution                 Propagation                    Enforcement
-----------                -----------                    -----------
JWT claim  tenant_id  -->  ITenantContext / ThreadLocal   -->  global query filter
(NOT body/query/header)    request-scoped, set per call        + explicit predicates
                           |                                    + row-level security
                           +--> background job: set explicitly  + cache/blob key prefix
                           +--> queue/webhook: carry in message  + tenant-scoped uniqueness
```
Draw the ACTUAL path for the audited app and mark every point where the chain
breaks (input-derived tenant, job with no context, unscoped query, un-prefixed key).

## 4. The leak-point checklist (cover every item; record gaps in not_checked)
- [ ] Tenant id derived from the authenticated identity, never trusted from body, query string, or client header.
- [ ] Every data query scoped by tenant (global filter, RLS, or explicit predicate).
- [ ] A listed inventory of every query that BYPASSES the filter: raw SQL, filter-disabling calls, admin/reporting paths, aggregate queries.
- [ ] Write paths set tenant id from context, not input.
- [ ] Background jobs, scheduled tasks, queue consumers, webhooks carry and enforce tenant context.
- [ ] Cache keys, session stores, search indexes, file/blob paths include the tenant id.
- [ ] Logs, error trackers, analytics do not mix tenant data in ways that can be surfaced across tenants.
- [ ] Cross-tenant admin/support tooling (impersonation, "switch tenant") is explicitly authorized and audit-logged.
- [ ] Tenant-scoped uniqueness constraints; identifiers not sequential/guessable across tenants.
- [ ] Per-tenant rate limits/quotas so one tenant cannot starve others.
- [ ] Per-tenant encryption keys / data residency if required.
- [ ] Tenant offboarding deletes or exports all of a tenant's data, with a backups policy.
- [ ] Migrations and seed data do not cross tenants.

## 5. Confirm dynamically
Run `scripts/tenant_probe.py` as tenant A against tenant B's ids across read,
write, list, search, download, export, and with tampered tenant identifiers
(body/query/header). Any 2xx that reaches tenant B is a confirmed cross-tenant
finding - the deliverable requires demonstrating at least one cross-tenant read
when a leak exists.

## Severity guidance
- Cross-tenant read/write of another customer's data -> Critical (regulated data
  or all-tenants scope) or High. Move up one for multi-tenant crossing per the
  rubric. Un-prefixed cache/blob key or a job with no context -> High/Medium
  depending on whether a leak is demonstrable.
