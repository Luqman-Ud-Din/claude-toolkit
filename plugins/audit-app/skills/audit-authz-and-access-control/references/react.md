# React reference for audit-authz-and-access-control

Frontend authorization is **cosmetic**. A `PrivateRoute` and `{isAdmin && ...}`
only hide UI; anyone can call the API directly with a valid token. Confirm the
server enforces the rule; the finding belongs on the endpoint, not the
component. Token storage is the sibling skill `audit-client-auth-and-storage`.

## Stack markers
`package.json` with `react`/`next`. Routing via `react-router` (`<Route>`, `PrivateRoute`, `RequireAuth`) or Next.js middleware/`getServerSideProps`.

## Where the relevant code lives
Route definitions (`App.tsx`, `routes.tsx`), `PrivateRoute`/`RequireAuth` wrappers, conditional renders (`{user.role === 'admin' && ...}`), the API client that attaches the token, an auth context/hook (`useAuth`). Next.js: `middleware.ts` runs on the server and *can* be a real control - treat separately from client components.

## Dangerous / interesting patterns
- `<PrivateRoute>` / `RequireAuth` / role conditionals - Info; verify the backend re-checks.
- Next.js `getServerSideProps`/route handlers that fetch data using an id from the URL without an owner filter - this IS server code; trace it like a backend handler.
- Role read from a decoded JWT and trusted for more than showing/hiding UI.

## What "good" looks like
Client guards for UX; the API (or Next server handler) enforces role + ownership. In the finding, name the server file that was verified.

## Manual trace checklist
1. For each protected route, find the API call it makes and confirm the server enforces the same rule.
2. In Next.js, audit server handlers/`getServerSideProps` as backend code (ownership filter on id lookups).

## Stack-specific false positives
Client route guards and conditional rendering are expected; not findings alone.

## Tooling
Inspect the production bundle to show client roles are visible. Server checks: backend reference + `scripts/authz_probe.py`.

## References
CWE-602. OWASP A01:2021. See the backend stack file for the fix.
