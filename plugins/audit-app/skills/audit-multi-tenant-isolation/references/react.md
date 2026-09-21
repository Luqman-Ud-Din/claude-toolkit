# React reference for audit-multi-tenant-isolation

The frontend is **not** the isolation boundary. A React app only issues
requests; tenant separation is enforced server-side. The frontend's only
contribution to tenant leaks is **sending a client-controlled tenant id** that a
weak backend trusts. Fix is server-side (backend stack file). Endpoint authz is
the sibling skill `audit-authz-and-access-control`.

## Stack markers
`package.json` with `react`/`next`. Note: Next.js `getServerSideProps`, route handlers, and `middleware.ts` run on the SERVER and can be real tenant boundaries - audit them as backend code.

## Where the relevant code lives
The API client (`fetch`/`axios` wrapper), hooks/context holding the current tenant, components that put `tenantId` in a payload or URL. Next.js server handlers under `app/api` / `pages/api`.

## What to look for
- Client sending `tenantId`/`companyId` in a request - Info; the server must re-derive and ignore it.
- Tenant id in a URL path not re-checked by the server.
- Next.js server handlers fetching by id/tenant from the request without scoping to the session's tenant - this IS a backend finding; trace like server code.

## What "good" looks like
Client may pass a tenant id for convenience; the server derives the authoritative tenant from the session/token. Name the verified server file in the finding.

## Manual trace checklist
1. Trace where each request's tenant id comes from.
2. Audit Next.js server handlers as backend data-access paths (tenant scope on every query).

## Stack-specific false positives
Passing a tenant id as a filter is fine; only a finding when the server trusts it.

## Tooling
Browser network inspection; `scripts/tenant_probe.py` for the server.

## References
CWE-639. OWASP A01:2021. See the backend stack file.
