# Angular reference for audit-multi-tenant-isolation

The frontend is **not** the isolation boundary. A SPA cannot enforce tenant
separation; it can only make requests. This file covers the one thing the
frontend contributes to tenant leaks: **building requests that carry a
client-controlled tenant id** that a weak backend then trusts. The real fix is
always server-side (see the backend stack file). Authz of the endpoints
themselves belongs to the sibling skill `audit-authz-and-access-control`.

## Stack markers
`package.json` with `@angular/core`, `angular.json`. In this codebase `core/services/api.service.ts` builds query params (`CompanyId`, `BranchId`) - note where the tenant id in a request comes from.

## Where the relevant code lives
`core/services/api.service.ts` (`buildHttpParams`), feature services that call the API, `core/interceptors/*.ts`, anywhere a `companyId`/`tenantId` is read from `localStorage`/route/user and put into a request.

## What to look for (mostly Info)
- The client sending `CompanyId`/`BranchId`/`tenantId` in the body or query string. This is fine ONLY if the server ignores it and re-derives tenant from the token. Flag the *server* if it trusts the value.
- A tenant id in the URL path (`/api/company/{id}/...`) that the server does not re-check against the token.
- Tenant id stored in `localStorage` and used to switch context client-side without a server re-check.

## What "good" looks like
The client may send `CompanyId` for filtering convenience, but the server derives the authoritative tenant from the JWT claim and rejects or ignores a mismatched client value. Note in the finding which server file was verified.

## Manual trace checklist
1. Find where each request's tenant id originates (token vs localStorage vs route).
2. For each, confirm the backend endpoint re-derives tenant from the token - if not, the finding is on the backend.

## Stack-specific false positives
Sending `CompanyId`/`BranchId` as a filter is expected in this app; it is only a finding when the server trusts it for authorization.

## Tooling
Inspect network requests in the browser to see what tenant identifiers the client sends; confirm server behavior with `scripts/tenant_probe.py`.

## References
CWE-639. OWASP A01:2021. See the backend stack file for the enforcement fix.
