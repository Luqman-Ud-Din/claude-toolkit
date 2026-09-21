# Vue reference for audit-multi-tenant-isolation

The frontend is **not** the isolation boundary. A Vue app only issues requests;
tenant separation is enforced server-side. The frontend's only contribution to
tenant leaks is **sending a client-controlled tenant id** a weak backend trusts.
Fix is server-side (backend stack file). Endpoint authz is the sibling skill
`audit-authz-and-access-control`.

## Stack markers
`package.json` with `vue`/`nuxt`. Nuxt `server/` routes run on the server - audit them as backend code.

## Where the relevant code lives
The API/fetch wrapper, Pinia/Vuex store holding the current tenant, components/composables that put `tenantId` in a payload or URL, Nuxt `server/api/*`.

## What to look for
- Client sending `tenantId`/`companyId` in a request - Info; server must re-derive and ignore it.
- Tenant id in a URL path not re-checked server-side.
- Nuxt `server/` handlers querying by id/tenant from the request without scoping to the session's tenant - a backend finding.

## What "good" looks like
Client may pass a tenant id for filtering; the server derives the authoritative tenant from the session/token. Name the verified server file in the finding.

## Manual trace checklist
1. Trace where each request's tenant id originates.
2. Audit Nuxt `server/` handlers as backend data-access paths.

## Stack-specific false positives
Passing a tenant id as a filter is fine; only a finding when the server trusts it.

## Tooling
Browser network inspection; `scripts/tenant_probe.py` for the server.

## References
CWE-639. OWASP A01:2021. See the backend stack file.
