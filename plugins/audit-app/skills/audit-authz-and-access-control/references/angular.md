# Angular reference for audit-authz-and-access-control

Frontend authorization is **cosmetic**. This file tells you how to confirm that
the client only hides UI and that the real control lives on the server. The
finding is almost never "the guard is missing" - it is "the API trusts the
client". Storage of the token itself belongs to the sibling skill
`audit-client-auth-and-storage`.

## Stack markers
`package.json` with `@angular/core`, `angular.json`, `src/app`. Ionic/Capacitor wrappers common in this codebase.

## Where the relevant code lives
`core/guards/*.ts` (`CanActivateFn`/`AuthGuard`), `app.routes.ts`/`*-routing.module.ts` (`canActivate`, `data: { roles }`), `core/interceptors/token.interceptor.ts` (which requests get the JWT), component templates (`*ngIf="isAdmin"`), `core/services/auth.service.ts` (role source).

## Dangerous / interesting patterns (all Info unless they hide a real gap)
- `canActivate`/`canMatch` guards and `*ngIf="isAdmin"` - they improve UX but a user can call the API directly with a copied token. Every guarded route must map to a server endpoint that re-checks the same rule.
- Client-side role from a decoded JWT used for anything but display.
- A route with sensitive data behind only a guard (no server role check) - flag the *server* endpoint, not the guard.

## What "good" looks like
Guards for navigation only; the corresponding backend endpoint carries `[Authorize(Roles=...)]` (or the stack equivalent) and an ownership filter. Note in the finding: "guard is fine; the control is server-side and was verified in <file>".

## Manual trace checklist
1. List guarded routes and their `data.roles`; for each, find the backend endpoint it calls and confirm the server enforces the same role + ownership.
2. Check the interceptor only attaches the token to same-origin/api URLs.

## Stack-specific false positives
Guards and `*ngIf` role checks are expected and not findings on their own. Only raise a finding when the matching server endpoint lacks the control.

## Tooling
`ng build` + inspect the emitted bundle to prove client "secrets"/roles are visible. Server-side verification uses the backend reference and `scripts/authz_probe.py`.

## References
CWE-602 (client-side enforcement of server-side security). OWASP A01:2021. Cross-reference the backend stack file for the real fix.
