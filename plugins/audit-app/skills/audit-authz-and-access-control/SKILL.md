---
name: audit-authz-and-access-control
description: Reviews every API endpoint, route, page, and background job for authentication and authorization gaps - enumerates endpoints, flags unauthenticated or anonymous ones, checks per-user/per-tenant ownership (IDOR), verifies role and permission enforcement server-side, hunts privilege escalation (self role edits, hidden DTO fields, mass assignment), and confirms frontend guards are cosmetic. Use it whenever the user asks to audit, review, or check authorization, authentication, access control, permissions, roles, IDOR, broken access control, privilege escalation, mass assignment, or "who can call this endpoint", and as part of any general security audit or pre-production review - even when the user does not name this skill. Produces an endpoint inventory table, findings in the standard format, and a runnable authz-probe script.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit authorization and access control

Broken access control is the top web risk (OWASP A01). This skill enumerates
every way into the application and checks four things per entry point: can an
anonymous caller reach it, is the right role required server-side, is per-object
ownership enforced (IDOR), and can a caller escalate privileges through the data
they send. It then ships a probe that proves the answer against a running test
instance.

**Read-only rule:** never modify the audited code. Write only under `audit/`
(findings, reports, evidence, status). The probe script only runs when the user
supplies a URL and points at a disposable environment.

## Inputs and prerequisites

- The repository to audit (source only is enough for the static passes).
- Optional, for the dynamic probe: a base URL of a **test** environment, two
  accounts' bearer tokens (user A and user B), and user B's resource ids.
- `audit/stack.json` if the orchestrator wrote one; otherwise this skill detects
  the stack itself.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection`,
  `audit-code-scan`, `audit-endpoint-inventory` (which itself needs
  `audit-sensitive-data-catalog`) and `audit-finding-writer`.

## Workflow

### 1. Resolve the stack
Run `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>` (it returns
`audit/stack.json` if the orchestrator already wrote it). Open only the matching `references/<stack>.md`
for the backend, plus the frontend stack file to confirm client guards are
cosmetic. If nothing matches, use
`$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md` and say so. Keep
`references/access-control-checklist.md` open throughout.

### 2. Automated pass
- Run `audit-endpoint-inventory` first, or reuse
  `audit/evidence/audit-endpoint-inventory/endpoints.json` when the orchestrator
  already produced it:
  `python "$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py" <repo>`.
  It writes `endpoints.json` (facts per endpoint, job and client route),
  `endpoints.md` (the table) and `endpoints.probe.json` (probe input) under
  `audit/evidence/audit-endpoint-inventory/`; this skill does not write its own
  copy. Per record read `auth.required` (yes/no/unknown), `auth.source`,
  `auth.roles` plus `auth.policies`, `ownership.check` (yes/no/unknown/n/a) with
  its evidence, `file`/`line`, `auth.client_guards` for client routes, and
  `job.identity_context` for jobs. `request.has_body` with
  `request.body_type_named_as_dto` false is a mass-assignment candidate.
  Every `ownership.check: unknown` and `auth.required: unknown` MUST be resolved
  by reading the handler - static extraction is a skeleton, not a verdict.
- Run the grep pass for candidates:
  `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-authz-and-access-control/hits.json`.
  Hits are candidates, not findings.

### 3. Manual trace of the highest-risk flows
Follow the checklist in `references/access-control-checklist.md`, in this order
(highest value first):
1. Endpoints marked not-authenticated that are not login/register/health.
2. Every handler that loads a resource by an id from the request - confirm the
   query also filters by the caller's owner/tenant id (IDOR). This is the single
   most valuable trace.
3. "Update self"/profile/settings endpoints - confirm the bound shape cannot set
   role, permission, tenant, or ownership (mass assignment / privilege escalation).
4. Background jobs, queue consumers, and webhooks - they carry no HTTP identity;
   confirm they set and enforce user/tenant context.
5. Frontend guards - confirm each maps to a server control that re-checks.

### 4. Confirm dynamically (only if the user gave a URL)
Copy `audit/evidence/audit-endpoint-inventory/endpoints.probe.json` to
`audit/evidence/audit-authz-and-access-control/endpoints.probe.json`. It already
has `method`, `path`, `auth_required`, `ownership_check` and `id_params`; add a
`body` with privilege fields (`role`, `isAdmin`, tenant ids) to the rows that
should be probed for mass assignment, because the projection never invents
tamper payloads. Generate `ids-b.json` with user B's ids, one key per distinct
`id_params` value (the inventory names the resource: `{"id": "order"}`), e.g.
`{"order": 1002, "profile": 2}`. A row whose key is missing is reported as SKIP.
Then, against a disposable environment only:
```
python scripts/authz_probe.py --base-url <url> \
  --token-a <A> --token-b <B> --ids-b ids-b.json \
  --endpoints audit/evidence/audit-authz-and-access-control/endpoints.probe.json --also-anon \
  --out audit/evidence/audit-authz-and-access-control/probe.json
```
Every FAIL row is a confirmed finding (a 2xx reaching user B's data, or a
no-token 2xx on an auth-required endpoint). If no URL is supplied, skip this and
record it under "Not checked".

### 5. Write findings
Initialize once:
`python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" init audit-authz-and-access-control`.
For each confirmed issue write the finding block (below), save it to a temp JSON,
and append with
`python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" add audit/findings/audit-authz-and-access-control.json --from <finding.json>`.
Regenerate the report body with
`python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" md audit/findings/audit-authz-and-access-control.json --out audit/reports/audit-authz-and-access-control.md`,
then prepend the inventory table and flow notes from the output template below.
For messy raw inputs, hand off to `audit-finding-writer`; the format is identical.

### 6. Record what was NOT checked
Add every gap to `scope.not_checked` with a reason: no test URL (dynamic probe
skipped), gateway/reverse-proxy rules not in the repo, endpoints behind feature
flags, external identity-provider policies, etc. Write
`audit/status/audit-authz-and-access-control.json`
(`{"skill":"audit-authz-and-access-control","status":"completed|failed|skipped","reason":...,"started_at":...,"finished_at":...}`).

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `AUTHZ`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Evidence:**

```lang
<the exact lines, or the probe command and its output>
```

- **Impact:** Plain language - who is affected, what they can read/change. One or two sentences with the severity justification.
- **Remediation:** The concrete fix in this stack, with a short example.
- **Reference:** CWE-nnn, ASVS-x.y.z, OWASP-A0n:2021

The same content maps to `findings.json` fields `title`, `severity`,
`confidence`, `location`, `evidence`, `impact`, `remediation`, `references`, and
optional `tags`/`root_cause_key`. Recurring references for this topic: CWE-306,
CWE-862, CWE-863, CWE-639, CWE-915, CWE-602; ASVS 4.1/4.2; OWASP-A01:2021.

## Output template (`audit/reports/audit-authz-and-access-control.md`)

```markdown
# Authorization & Access Control audit

## Endpoint inventory
| Method | Route | Auth required | Roles | Ownership check | Location |
|---|---|---|---|---|---|
| GET | /api/orders/{id} | Yes | - | N | Controllers/OrdersController.cs:26 |
| ... | ... | ... | ... | ... | ... |

Built from `audit/evidence/audit-endpoint-inventory/endpoints.json` (or cite its
`endpoints.md`). Auth required = `auth.required`; Roles = `auth.roles` plus
`policy:<name>` for each policy; Ownership check = `ownership.check`: Y = yes
(handler references caller identity, confirmed filtered by caller id), N = no
(id used without owner filter), ? = unknown (only owner/tenant key names seen;
resolve by reading the handler), - = n/a (no id parameter).

## Dynamic probe result
(paste the authz_probe.py pass/fail table, or "Not run - no test URL supplied".)

## Findings
(generated by findings.py md - the finding blocks and the severity table.)

### Not checked
- <item> - <reason>
```

## Examples

**Input:** `OrdersController.cs:26` - `var order = _db.Orders.Find(id);` in an
`[Authorize]` action with route `{id}`, no owner filter.
**Finding:** `[High] AUTHZ-002 - Order lookup has no ownership check` -
Evidence the line; Impact "any signed-in customer can read any other customer's
order by changing the id"; Remediation "filter by `o.Id == id && o.CustomerId ==
caller.Id`, return 404 on mismatch"; Reference CWE-639, ASVS-4.2.1, OWASP-A01:2021.

**Input:** `UpdateProfileDto` exposes `Role`, and `ProfileController.Update`
copies `dto.Role` onto the user entity.
**Finding:** `[High] AUTHZ-003 - Self-service profile update can set the caller's
role` - Impact "a normal user can promote themselves to Admin by adding a role
field to the request body"; Remediation "remove Role/IsAdmin from the request
DTO; set roles only through an admin-authorized path"; Reference CWE-915.

## Bundled files

- `references/<stack>.md` - per-stack where-to-look, good/bad shapes, false positives (dotnet, java-spring, node-express, python-django, angular, react, vue; to add a stack, copy `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`).
- `references/access-control-checklist.md` - the stack-agnostic review checklist.
- `scripts/authz_probe.py` - cross-account IDOR/authz probe reading `endpoints.probe.json` from audit-endpoint-inventory (needs a test URL; never runs on its own).
- `scripts/patterns/<stack>.json` - the grep candidate patterns.
- Atomic scripts this skill calls: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` (stack), `$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py` (endpoint inventory and probe input), `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` (candidate pass), `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` (findings I/O).
- `evals/` - a sample .NET repo planting the three required issues plus negatives.
