---
name: audit-client-auth-and-storage
description: Reviews how a web or mobile frontend handles authentication - where access and refresh tokens are stored (localStorage/sessionStorage vs HttpOnly cookies vs memory), whether HTTP interceptors attach credentials only to the app's own API origin, refresh-token flow and expiry handling, whether logout clears all state, that route guards are UX only, and whether secrets or API keys ship in the production bundle or environment files - and draws the login-to-logout auth flow diagram. Use this whenever the user asks about token storage, JWT in the frontend, JWT in localStorage, access tokens, refresh tokens, HTTP interceptors, Authorization headers, route guards, CanActivate, session handling, session expiry, logout, remember-me, API keys in the bundle, environment.prod.ts secrets, frontend auth security, client-side auth, SPA authentication, or during any security audit or pre-production review with an Angular, React, Vue, Ionic, or React Native frontend - even when the user does not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: client-side authentication and storage

The frontend cannot enforce security, but it can lose the keys. This skill
follows the token from the login response to the storage slot, through the
interceptor that attaches it, the refresh path that renews it, and the logout
that is supposed to destroy it, and checks whether anything secret was baked
into the bundle along the way. Every claim in the report is tied to a file and
line; the auth-flow diagram is the map the reader uses to follow them.

Read-only rule: never edit the audited code. Write only under `audit/`
(`findings`, `reports`, `evidence`, `status`).

## Inputs and prerequisites

- Path to the repository root (frontend project, or full-stack repo).
- `audit/stack.json` if `audit-application` already ran; otherwise run
  `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>` (without `--write`).
- Python 3 (stdlib only) for the bundled scripts.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection`,
  `audit-code-scan` (grep pass and the shared file walker), `audit-sensitive-data-catalog`
  (provider key formats, secret key names, placeholders, public-by-design hints) and
  `audit-finding-writer` (findings I/O).
- Optional but valuable: a production build output (`dist/`, `build/`, `www/`,
  `.next/`, `out/`) so `scan_secrets.py` can check what actually ships; if it
  is absent, scan the environment files and say the bundle was not checked.
- Optional: findings from `audit-security-headers-and-middleware` (cookie
  flags, CORS) and `audit-authz-and-access-control` (server-side checks that
  make guards UX-only) to cross-reference instead of duplicating.

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`. Open only
   the matching `references/<stack>.md`: `angular.md`, `react.md`, `vue.md` for
   the client. If the backend is in the same repo also open its file
   (`dotnet.md`, `java-spring.md`, `node-express.md`, `python-django.md`) - it
   says what the server contributes (token TTLs, cookie issuance, refresh
   endpoint, revocation) and which sibling skill owns the rest. No match: use
   `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md` and say so in scope.
2. **Automated pass.**
   - `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-client-auth-and-storage/hits-<stack>.json --md audit/evidence/audit-client-auth-and-storage/hits-<stack>.md`
     finds storage writes, interceptor URL logic, refresh logic, logout calls,
     guards, and hard-coded credentials in source.
   - `python scripts/scan_secrets.py <repo> --out audit/evidence/audit-client-auth-and-storage/secrets.json --md audit/evidence/audit-client-auth-and-storage/secrets.md`
     greps environment files (`environment*.ts`, `.env*`, `config*.js|json`,
     `app.config.*`) and any built bundle it finds for secret-looking values
     (provider key prefixes, JWTs, private keys and credential key names from
     `audit-sensitive-data-catalog`, plus its own high-entropy check next to
     key-like names). Add `--bundle <dir>` when the build lives elsewhere.
   Pattern ids map to the checklist areas in `references/auth-flow-checklist.md`
   (STORE, INTERCEPT, REFRESH, LOGOUT, GUARD, SECRET, TRANSPORT).
3. **Manual trace of the auth flow.** Open the auth service, the interceptor,
   the storage wrapper, the guards, and the login/logout components, and fill
   in the diagram below with real symbol names. Answer, with file:line
   evidence: (a) what the login response contains and where each token goes;
   (b) the exact condition under which the interceptor adds `Authorization`
   or `withCredentials` - the app's API origin only, or any URL; (c) how
   expiry is detected (JWT `exp` decode, 401 response, timer) and how refresh
   is serialized (one in-flight refresh, queued requests) and what happens
   when refresh fails; (d) everything logout clears - storage keys, in-memory
   state, stores, timers, service-worker caches, cookies via the server, and
   whether it redirects before or after; (e) guards: confirm they only hide
   UI and that the server enforces the same rule (cross-reference the authz
   skill), and flag any guard that decodes the JWT to decide roles as UX-only
   in the report, not as a finding, unless the server does not check.
   (f) secrets: for each `scan_secrets.py` hit decide public identifier
   (Firebase web config, Google Maps key restricted by referrer, Stripe
   publishable key) versus secret (server API key, JWT signing key, service
   account, SMS provider credentials) - public identifiers are Info with the
   restriction to verify; secrets in the bundle are High or Critical.
4. **Write findings** with `python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py"`, id prefix `CAUTH`. Severity
   via `audit-finding-writer/references/severity-rubric.md`: a secret that
   grants server-side access in the bundle is Critical; long-lived JWT in
   `localStorage` with any XSS sink present (check `audit/findings/audit-frontend-xss-and-dom-safety.json`)
   is High, Medium when no sink was found; interceptor attaching the token to
   every host is High if any third-party URL is called through the same
   client, Medium otherwise; logout leaving the token in storage is Medium;
   missing refresh handling is Low-to-Medium (availability plus users staying
   logged in past expiry); guards are Info unless the server side is missing.
5. **Produce the outputs** (paths relative to the audited repo):
   - `audit/findings/audit-client-auth-and-storage.json`
   - `audit/reports/audit-client-auth-and-storage.md` (skeleton below, with the Mermaid diagram)
   - `audit/evidence/audit-client-auth-and-storage/hits-<stack>.json|md`, `secrets.json|md`
   - `audit/status/audit-client-auth-and-storage.json`:
     the status record defined in `audit-core:audit-finding-writer` (references/run-status.md)
6. **List what was not checked**: no production bundle available, native
   secure storage on iOS/Android not inspected at runtime, identity provider
   configuration (Azure AD/Auth0/Firebase console) outside the repo, backend
   token validation (owned by `audit-authz-and-access-control`), cookie flags
   and CORS (owned by `audit-security-headers-and-middleware`).

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `CAUTH`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Confidence:** confirmed | likely | false-positive

- **Impact:** Plain language. Who is affected, what they lose, how likely. One or two sentences, ending with the severity justification.
- **Remediation:** The concrete fix in this framework, with a short example. Name the file and the pattern to use.
- **Reference:** CWE-nnn, ASVS-x.y.z, OWASP-A0n:2021


JSON fields: `id`, `title`, `severity`, `confidence`, `location`, `evidence`,
`impact`, `remediation`, `references`, `tags` (area: `storage`, `interceptor`,
`refresh`, `logout`, `guard`, `secret`, `transport`). Full schema and prefix
table: `audit-finding-writer/references/findings-schema.md`.

## Output template - `audit/reports/audit-client-auth-and-storage.md`

```markdown
## audit-client-auth-and-storage findings

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| n | n | n | n | n |

### Scope
- Stack: angular 19 + ionic/capacitor (src/app); backend dotnet (token issuance only)
- Bundle scanned: dist/digital-inventory (yes/no - reason)
- Env files scanned: src/environments/environment.ts, environment.prod.ts, .env

### Auth flow (as implemented)
```mermaid
flowchart LR
    L[Login form<br/>login.component.ts] -->|POST /accountapi/auth/login| API[(Auth API)]
    API -->|accessToken + refreshToken in JSON body| S[AuthService.setSession<br/>auth.service.ts:42]
    S -->|localStorage 'access_token'| LS[(localStorage)]
    S -->|localStorage 'refresh_token'| LS
    LS --> I[TokenInterceptor<br/>token.interceptor.ts:18<br/>attaches to ALL urls]
    I --> API
    I -->|401| R[refreshToken()<br/>auth.service.ts:70<br/>no single-flight]
    R -->|POST /auth/refresh| API
    R -->|failure| LO[logout()<br/>auth.service.ts:95<br/>clears access_token only]
    G[AuthGuard<br/>auth.guard.ts] -.UX only.-> LS
    LO --> L
```
Mark each node with the finding id that applies (for example `I` -> CAUTH-002).

### Storage and flow summary
| Item | Where | Value | Assessment | Finding |
|---|---|---|---|---|
| Access token storage | `auth.service.ts:42` | localStorage | readable by any script | CAUTH-001 |
| Refresh token storage | `auth.service.ts:43` | localStorage | long-lived, readable | CAUTH-001 |
| Interceptor scope | `token.interceptor.ts:18` | all requests | leaks to third parties | CAUTH-002 |
| Expiry detection | `auth.service.ts:60` | JWT exp decode | ok | - |
| Refresh serialization | `auth.service.ts:70` | none | parallel refreshes | CAUTH-003 |
| Logout clears | `auth.service.ts:95` | access_token only | refresh token survives | CAUTH-004 |
| Route guards | `auth.guard.ts` | CanActivateFn | UX only, server enforces (AUTHZ report) | Info |

### Secrets in bundle / environment files
| File | Line | Key name | Looks like | Public identifier or secret? | Finding |
|---|---|---|---|---|---|
| `src/environments/environment.prod.ts` | 9 | smsApiKey | provider key | secret | CAUTH-005 |
| `src/environments/firebase-config.ts` | 3 | apiKey | Firebase web key | public identifier (verify restrictions) | Info |

### Findings
<one block per finding, Critical first>

### Not checked
- <item> - <reason>
```

## Examples

**Input (hit):** `src/app/core/interceptors/token.interceptor.ts:18: const authReq = req.clone({ setHeaders: { Authorization: \`Bearer ${token}\` } });` with no URL check above it.

**Output:**
```markdown
### [High] CAUTH-002 - Interceptor attaches the bearer token to every outgoing request
- **Location:** `src/app/core/interceptors/token.interceptor.ts:18` (tokenInterceptor)
- **Confidence:** confirmed
- **Evidence:**

```ts
const token = storage.get('access_token');
if (token) { req = req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }); } // no origin check
// ProductService calls https://maps.googleapis.com/... through the same HttpClient
```

- **Impact:** Every third-party endpoint the app calls receives the user's session token; a compromised or logged CDN/maps/analytics host can replay it against the API as that user. Rated High because a third-party call through the same HttpClient exists.
- **Remediation:** Guard the clone: `if (token && req.url.startsWith(environment.apiUrl))` (or a list of own origins), and keep third-party calls on a separate `HttpClient` created with `HttpBackend` so interceptors are skipped.
- **Reference:** CWE-522, ASVS-3.5.2, OWASP-A07:2021
```

**Input (secrets scan row):** `src/environments/environment.prod.ts:9: smsApiKey: 'sk_9f3a...'`

**Output:** a **Critical** finding tagged `secret` (server-side provider key
ships to every browser; rotate now and move the call server-side), plus a row
in the secrets table. A Firebase `apiKey` in the same file is an **Info** row
with "public identifier; verify HTTP referrer restriction in the console".

## Bundled files

- `references/auth-flow-checklist.md` - storage options compared, interceptor/refresh/logout/guard rules, public-identifier vs secret list, severity anchors.
- `references/<stack>.md` - per-framework APIs, file locations, safe idioms, trace checklist, false positives, tooling (`angular`, `react`, `vue`; `dotnet`, `java-spring`, `node-express`, `python-django` for the server side of the flow); to add a stack, copy `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `scripts/patterns/<stack>.json` - storage/interceptor/refresh/logout/guard/secret patterns per stack, run with `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`.
- `scripts/scan_secrets.py` - secret-looking values in environment files and built bundles: provider formats, key names, placeholders and public hints from `audit-sensitive-data-catalog`; the entropy heuristic stays in the script.
- Atomic scripts called: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` (honours `audit/stack.json`),
  `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`, `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`
  (init / add / validate / md / summary); imported: `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py`,
  `$AUDIT_CORE_ROOT/skills/audit-sensitive-data-catalog/scripts/catalog.py`.
- `evals/` - prompts, an Angular fixture (JWT in localStorage, interceptor for all hosts, API key in environment.prod.ts, partial logout), and expectations.
