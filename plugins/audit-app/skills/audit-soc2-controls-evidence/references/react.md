# React reference for audit-soc2-controls-evidence

## Stack markers

`package.json` with `react` / `react-dom`; variants: Vite (`vite.config.*`),
Create React App (`react-scripts`), Next.js (`next.config.*`, `app/` or `pages/`).
Next.js has a server side (route handlers, middleware, server actions) - treat those
like the Node backend file for CC6/PI1; a pure SPA contributes only the SSO client,
the build pipeline and bundle hygiene. Hidden components and client route guards are
UX, not access control.

## Where the relevant code lives

- `src/auth/`, `src/main.tsx` / `src/index.tsx` - `MsalProvider`, `AuthProvider`.
- Next.js: `auth.ts` / `app/api/auth/[...nextauth]/route.ts`, `middleware.ts`,
  `app/**/route.ts`, server actions.
- `.env*`, `next.config.js`, `vite.config.ts` - public env vars, source maps.
- `public/index.html` / `index.html` - external scripts.
- `.github/workflows/`, `vercel.json`, `netlify.toml`, `jest.config.*`, `vitest.config.*`.

## Dangerous / interesting APIs and patterns

- CC6.1 SSO evidence: `@azure/msal-react` (`MsalProvider`, `useMsalAuthentication`),
  `oidc-client-ts` / `react-oidc-context`, `next-auth` / Auth.js providers
  (`AzureAD`, `Okta`, `Keycloak`). Bad: `Credentials` provider only when SSO is claimed.
- Next.js server authz: `middleware.ts` matcher only protecting pages while
  `app/api/**` route handlers skip `auth()` checks; server actions without a session check.
- C1: `NEXT_PUBLIC_*`, `VITE_*`, `REACT_APP_*` variables are compiled into the bundle -
  any secret there is public. Bad: `NEXT_PUBLIC_STRIPE_SECRET`, `VITE_API_SECRET`.
- Production build: `productionBrowserSourceMaps: true` (Next), `build.sourcemap: true`
  (Vite), `GENERATE_SOURCEMAP` not set to `false` (CRA) - source shipped publicly.
- CC8.1 / CC7.1: `npm ci`, `npm audit`, `vitest run` / `jest --ci`, `next build`,
  `next lint`.
- CC7.2: error boundaries reporting to Sentry (`Sentry.ErrorBoundary`) with
  `sendDefaultPii: false` vs `console.error` only.
- Supply chain: external `<script>` without `integrity`; `dangerouslySetInnerHTML`
  belongs to audit-frontend-xss-and-dom-safety.

## What "good" looks like

```tsx
const msal = new PublicClientApplication({ auth: { clientId: import.meta.env.VITE_CLIENT_ID,
  authority: import.meta.env.VITE_AUTHORITY, redirectUri: '/' }, cache: { cacheLocation: 'sessionStorage' } });
root.render(<MsalProvider instance={msal}><App /></MsalProvider>);
```

```ts
// Next.js route handler - server-side check, not just middleware
export async function DELETE(req: Request) {
  const session = await auth();
  if (session?.user?.role !== 'admin') return new Response(null, { status: 403 });
  ...
}
```

Pipeline shape: `npm ci` -> `npm run lint` -> `npx vitest run` (or `jest --ci`) ->
`npm audit --audit-level=high --omit=dev` -> `npm run build` -> immutable artefact /
preview deployment -> promotion to production gated by a protected environment.

## Manual trace checklist

1. List every public env var prefix in use; open each value source for secrets.
2. SSO provider configuration and which IdP it points at.
3. Next.js: every `app/api/**` handler and server action checks the session and role.
4. Build config: source maps off for production.
5. CI: tests and audit required on PRs; production deploys only from the pipeline
   (Vercel/Netlify "deploy from CLI" tokens are a direct-deploy path to check).
6. Depth on token storage: audit-client-auth-and-storage.

## Stack-specific false positives

- Public-by-design values in `NEXT_PUBLIC_*` / `VITE_*`: OIDC client id, Sentry DSN,
  analytics ids, publishable Stripe key (`pk_`).
- `sourcemap: 'hidden'` uploaded to Sentry and not served - acceptable.
- `npm audit` hits limited to devDependencies (build tooling).

## Tooling

```bash
npm ci && npm audit --audit-level=high --omit=dev
grep -rnE "NEXT_PUBLIC_|VITE_|REACT_APP_" --include=*.ts --include=*.tsx --include=.env* .
grep -rnE "productionBrowserSourceMaps|sourcemap|GENERATE_SOURCEMAP" next.config.* vite.config.* .env* package.json
grep -rnE "MsalProvider|NextAuth|AuthProvider|oidc-client-ts" src app
```

## References

- Next.js authentication and data security guides; MSAL React; Auth.js docs.
- Sibling skills: audit-client-auth-and-storage, audit-security-headers-and-middleware,
  audit-dependency-vulnerabilities.
- SOC2-CC6.1, CC7.1, CC8.1, C1.1; CWE-540, CWE-829.
