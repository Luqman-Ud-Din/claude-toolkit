# Angular reference for audit-soc2-controls-evidence

## Stack markers

`angular.json`, `package.json` with `@angular/core`; Ionic/Capacitor variants
(`capacitor.config.ts`). The frontend holds few SOC 2 controls on its own - route
guards, menus and hidden buttons are UX, not access control. The server-side
evidence lives in the backend stack file. What the SPA does contribute: the SSO
client, the build and supply-chain pipeline for the shipped bundle, and proof that
no secrets or debug artefacts reach production.

## Where the relevant code lives

- `angular.json` - `configurations.production` (`sourceMap`, `optimization`,
  `budgets`, `fileReplacements`).
- `src/environments/environment*.ts` - API URLs, IdP settings, feature flags.
- `src/app/core/auth/`, `*.guard.ts`, `*.interceptor.ts` - OIDC client config,
  token attachment.
- `src/index.html` - third-party scripts (SRI), CSP meta tag if any.
- `ngsw-config.json`, `firebase.json`, `staticwebapp.config.json`, `nginx.conf` -
  hosting headers.
- `.github/workflows/`, `azure-pipelines.yml`, `karma.conf.js`, `package-lock.json`.

## Dangerous / interesting APIs and patterns

- CC6.1 SSO evidence: `angular-auth-oidc-client` (`provideAuth({ config: { authority,
  clientId, responseType: 'code', usePkce... } })`), `@azure/msal-angular`
  (`MsalGuard`, `MsalInterceptor`), `keycloak-angular`. Bad: implicit flow
  (`responseType: 'id_token token'`), a home-grown login form posting passwords
  to a custom endpoint when the org claims SSO.
- CC6.1 rbac (UX only): `canActivate` guards, `*ngIf="isAdmin"`. Never credit these
  as the control; confirm the matching backend policy.
- C1: `environment.prod.ts` containing API keys, client secrets, connection strings,
  or private keys - anything in the bundle is public.
- CC8.1 / CC7.1: `npm ci` (lockfile respected) vs `npm install`; `npm audit` step;
  `ng test --watch=false --browsers=ChromeHeadless`; `ng build --configuration production`.
- Production build: `"sourceMap": true` in the production configuration ships source;
  `"optimization": false` suggests a debug build is deployed.
- CC7.2: global `ErrorHandler` sending errors to Sentry / Application Insights
  (monitoring evidence) vs `console.error` only.
- Supply chain: `<script src="https://cdn...">` without `integrity=` in `index.html`.

## What "good" looks like

```ts
provideAuth({ config: { authority: environment.idp.authority, clientId: environment.idp.clientId,
  responseType: 'code', scope: 'openid profile api', silentRenew: true, useRefreshToken: true } });
```

```json
"production": { "sourceMap": false, "optimization": true, "outputHashing": "all",
  "budgets": [{ "type": "initial", "maximumError": "2mb" }] }
```

Pipeline shape: `npm ci` -> `npx ng lint` (when configured) -> `npx ng test
--watch=false --browsers=ChromeHeadless` -> `npm audit --audit-level=high --omit=dev`
-> `npx ng build --configuration production` -> artefact uploaded with the commit SHA
-> deploy job in a protected environment deploys that exact artefact.

## Manual trace checklist

1. `environment.prod.ts` and the built `main*.js`: no secrets, no localhost URLs.
2. OIDC/MSAL configuration: code flow + PKCE, the authority is the corporate IdP.
3. For each admin route guard, find the backend endpoint and its server-side policy.
4. CI: tests and audit run on PRs; the deployed artefact is the one CI built (SHA
   traceable), not a build from a developer laptop.
5. Hosting config sets CSP/HSTS (depth: audit-security-headers-and-middleware).
6. Token storage and logout (depth: audit-client-auth-and-storage).

## Stack-specific false positives

- Public identifiers in environment files: OIDC `clientId`, Firebase `apiKey`,
  Application Insights connection string - not secrets, but note the restriction
  settings (API key HTTP referrer limits).
- `sourceMap: true` in `development` or `staging` configurations only.
- `npm audit` findings in dev-only build tooling (`karma`, `webpack-dev-server`).

## Tooling

```bash
npm ci && npm audit --audit-level=high --omit=dev
npx ng build --configuration production && grep -l "sourceMappingURL" dist/**/*.js
grep -rnE "clientSecret|client_secret|apiSecret|privateKey" src/environments
grep -rnE "provideAuth|MsalModule|MsalGuard|KeycloakService" src
grep -nE "<script[^>]+src=\"https?://" src/index.html
```

## References

- Angular security guide; angular-auth-oidc-client and MSAL Angular docs.
- Sibling skills: audit-client-auth-and-storage (token storage, guards),
  audit-security-headers-and-middleware (CSP/SRI), audit-dependency-vulnerabilities.
- SOC2-CC6.1, CC7.1, CC8.1, C1.1; CWE-540, CWE-829.
