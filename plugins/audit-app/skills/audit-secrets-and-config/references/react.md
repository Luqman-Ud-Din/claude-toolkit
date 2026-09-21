# React reference for audit-secrets-and-config

The frontend rule: **everything you ship is public**. Any bundled value - and any
`REACT_APP_*` / `NEXT_PUBLIC_*` env var - is inlined into the client bundle and
readable by anyone. Frontend scope here: no server-side secret in the bundle.
CORS/headers are the server's job (backend stack file); token storage is the
sibling skill `audit-client-auth-and-storage`.

## Stack markers
`package.json` with `react`/`next`, `.env`/`.env.local`, `src/config`.

## Where the relevant code lives
`.env*` files, any module with an inline key, Next.js `next.config.js` (`env`), server-only code (`getServerSideProps`, route handlers) which MAY legitimately read secrets - distinguish it from client code.

## What to look for
- A secret in a `REACT_APP_*` or `NEXT_PUBLIC_*` variable, or a literal in client code - High; it ships to the browser.
- A secret only in a Next.js server file (`process.env.STRIPE_SECRET` in a route handler, not `NEXT_PUBLIC_`) is fine - that runs on the server; confirm it is not also inlined.
- Source maps enabled in prod.

## What "good" looks like
Client env vars hold only public values (`NEXT_PUBLIC_API_URL`, publishable keys). Secrets live in non-public env vars read only in server code, sourced from a secret manager.

## Manual trace checklist
1. Grep `.env*` and client code for secrets behind `REACT_APP_`/`NEXT_PUBLIC_`.
2. Confirm any real secret is used only in server-side files.
3. CORS/HSTS -> backend file.

## Stack-specific false positives
Publishable keys and public URLs in client env vars; secrets used exclusively in server code.

## Tooling
Inspect the production bundle for secrets. See `references/tool-candidates.md`.

## References
CWE-798. OWASP A05:2021, A02:2021. Server-side config is in the backend stack file.
