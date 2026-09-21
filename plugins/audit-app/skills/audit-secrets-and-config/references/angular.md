# Angular reference for audit-secrets-and-config

The frontend has one hard rule: **everything you ship is public**. Anything in
`environment.*.ts`, an inlined env var, or a bundled JSON is readable by any user
who opens dev tools. So the frontend side of this topic is: no server-side
secret in the bundle, and CORS/headers are the server's job (see the backend
stack file). Client token storage is the sibling skill
`audit-client-auth-and-storage`.

## Stack markers
`package.json` with `@angular/core`, `angular.json`, `src/environments/environment*.ts`, `src/environments/firebase-config.ts`.

## Where the relevant code lives
`src/environments/environment.ts` + `.staging/.prod` variants, `firebase-config.ts`, any service with an inline key, `angular.json` (`sourceMap`, `fileReplacements`).

## What to look for
- A server-side secret (API secret, DB password, service-account private key, `client_secret`) in any `environment*.ts` or bundled file - Critical/High; it is exposed to every visitor.
- Firebase config: the web API key is public by design (not a secret) - do NOT flag it; a service-account `private_key` IS a secret - flag it.
- `sourceMap: true` for the production build (leaks original source).

## What "good" looks like
Only publishable values in `environment.prod.ts` (public API base URL, Firebase web config, publishable Stripe key `pk_live_...`). Real secrets stay server-side; the SPA calls the backend which holds them.

## Manual trace checklist
1. Read every `environment*.ts` - is any value a real secret rather than a public identifier?
2. Confirm production build has `sourceMap: false`.
3. CORS/HSTS findings belong on the server - point at the backend file.

## Stack-specific false positives
Firebase web API key, publishable payment keys, and public base URLs are meant to ship - not findings.

## Tooling
Inspect the built bundle (`ng build --configuration production`) and grep it for secrets. See `references/tool-candidates.md`.

## References
CWE-798. OWASP A05:2021, A02:2021. Server-side config is in the backend stack file.
