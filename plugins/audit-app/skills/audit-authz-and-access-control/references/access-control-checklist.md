# Access-control review checklist (stack-agnostic)

Work top to bottom. Each item maps to a column in the endpoint inventory table
or to a manual trace. Record what you could not verify under `scope.not_checked`.

## 1. Enumerate every entry point
- [ ] HTTP endpoints (controllers, minimal APIs, route files).
- [ ] Background jobs, scheduled tasks, queue/topic consumers - they run with no HTTP identity.
- [ ] Webhooks and callback URLs (often unauthenticated by mistake).
- [ ] GraphQL resolvers / gRPC methods if present.
- [ ] Admin/reporting/export endpoints and file-download routes.
Build the inventory with `audit-endpoint-inventory` (`$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py`),
or reuse `audit/evidence/audit-endpoint-inventory/endpoints.json`, then verify every `unknown`.

## 2. Authentication (can an anonymous caller reach it?)
- [ ] Each endpoint is `auth.required: yes` unless it is deliberately public (login, register, forgot/reset password, health, public marketing/read APIs).
- [ ] Anonymous access is explicit (`[AllowAnonymous]`, `permitAll`, `AllowAny`) not accidental (missing attribute + permissive default).
- [ ] There is a deny-by-default fallback (global authorization policy / filter chain).

## 3. Authorization - roles/permissions (server-side)
- [ ] Role/permission checks exist on the server for every privileged action.
- [ ] They are enforced in the handler/middleware, not only in the UI.
- [ ] No relying on a client-supplied role/claim that the client can edit.

## 4. Object-level authorization (IDOR)
- [ ] Every lookup by an id from the request also filters by the caller's owner/tenant id.
- [ ] Mismatch returns 404 (not 403) so ids cannot be enumerated.
- [ ] Applies to reads AND writes (update/delete by id are the same risk).
- [ ] List endpoints return only the caller's rows.

## 5. Privilege escalation / mass assignment
- [ ] Request DTOs expose only editable fields; no `role`/`isAdmin`/`permissions`/`tenantId`.
- [ ] Domain entities are not bound directly from the request body.
- [ ] "Update self" endpoints cannot change role, tenant, or ownership.

## 6. Frontend guards are cosmetic
- [ ] Every client route guard / hidden button maps to a server endpoint that re-checks the rule.
- [ ] No secret or authorization decision lives only in the shipped bundle.

## 7. Verify dynamically (optional, test env only)
- [ ] Run `scripts/authz_probe.py` as user A with user B's ids; every row should be PASS (blocked). Any FAIL is a confirmed finding.
- [ ] Run with `--also-anon` to confirm auth_required endpoints reject no-token calls.

## Severity guidance (see audit-finding-writer/references/severity-rubric.md)
- Unauthenticated endpoint exposing/altering data -> Critical/High.
- IDOR on other users' data -> High (Critical if it spans all tenants).
- Privilege escalation via mass assignment -> High.
- Cosmetic-only client guard with the server control present -> Info.
