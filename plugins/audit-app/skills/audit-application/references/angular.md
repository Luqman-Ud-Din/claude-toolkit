# Angular reference for audit-application

What the orchestrator needs to know about an Angular (and Ionic/Capacitor) frontend
before it plans and runs the children. Topic detail lives in each child's own
`references/angular.md`.

## Stack markers

- `package.json` depending on `@angular/core` (detect_stack id `angular`); `angular.json`
  names the projects and build configurations.
- `@ionic/angular` + `capacitor.config.ts`: the same code also ships as a mobile app.
  client-auth then covers secure storage (`@capacitor/preferences` is not a keychain), and
  licensing treats distribution as `proprietary`.
- Nx workspaces (`nx.json`, `apps/`, `libs/`): pass each app root. A README claiming Nx
  does not make it one; trust `angular.json`.

## Where the relevant code lives

- `src/app/` (components, services, guards, interceptors), `src/environments/environment*.ts`
  (API base URLs, keys that ship in the bundle), `proxy.conf.json` (local backend ports,
  which help name the backend repo), `src/assets/i18n/*.json` (locales for accessibility and
  i18n), `ngsw-config.json` (service worker caching).
- Build output: `dist/<project>/` after `ng build --configuration production`.

## Dangerous / interesting APIs and patterns

Setup signals:

- **Where the backend is:** base URLs in `environment*.ts` and `proxy.conf.json`. A
  frontend-only repo means authz, tenant isolation, injection, orm and db-schema need the
  backend root. Ask for it at setup rather than letting those children run blind.
- **Multi-tenant hints on the client:** tenant/company/branch ids sent in headers or bodies by
  an interceptor, a company switcher in the layout. The isolation audit still happens on the
  backend; client hints only justify asking the question.
- **Token handling:** `localStorage`/`sessionStorage`, crypto-js "encrypted" storage, HTTP
  interceptors. client-auth and XSS apply (always, for an Angular app).
- **Locales:** `ar`, `ur`, `fa`, `he` files mean RTL, which accessibility and i18n needs to know.

## What "good" looks like

- Node version compatible with the Angular major (see the Angular version matrix), plus a
  lockfile.
- `npm ci` possible, then `npx ng build --configuration production` succeeds. frontend-best-
  practices (bundle report, budgets, source maps) and client-auth (scan of what actually
  ships) need `dist/`. Without it they record "bundle not checked".
- The lint builder may be configured without its package installed. frontend-best-practices
  records that; do not install it into the user's tree.
- A served build (or dev server) plus the backend running -> accessibility (axe) and
  frontend-memory-leak (heap snapshots). Chrome available for Karma.

## Manual trace checklist

Prerequisites to confirm at setup:

1. Node + lockfile -> dependency-vulnerabilities (`npm audit`), licensing.
2. Production build possible -> frontend-best-practices, client-auth, XSS (compiled template
   output). Missing: `--limited "no production build; bundle not checked"`.
3. **Backend root(s)** for a frontend-only repo -> authz, tenant isolation, injection,
   api-contract, db-schema, orm, logging correlation. Missing: those children run with
   `--limited "backend repo not provided"`, or are skipped by the user.
4. A running app + test account -> accessibility (axe, keyboard pass), frontend-memory-leak
   (heap procedure), performance (Core Web Vitals).
5. Required locales and RTL -> accessibility and i18n.
6. Mobile build targets (Capacitor) -> client-auth (native storage), licensing (distribution).

## Stack-specific false positives

Wrong applicability calls to avoid:

- **Frontend-only Angular repo:** async, orm and backend-resource-leak are genuinely n/a
  (`plan.py` skips them). api-contract is n/a in the plan too, but if the backend lives in a
  sibling repo, add that root and run it. **Do not** mark injection or authz n/a. Injection's
  frontend file covers client-built URLs and queries; authz confirms guards are cosmetic, which
  needs the backend.
- **db-schema on a frontend-only repo** will find nothing. It is planned as `any` and writes
  `skipped` itself, which is fine. Do not flag it as failed.
- **`environment.prod.ts` containing a Firebase or Maps key** is not automatically a secrets
  failure at setup. Leave the rating to client-auth and secrets.

## Tooling

```bash
node -v && npx ng version
npm ci --ignore-scripts                        # ask first
npx ng build --configuration production --source-map=false
npx ng test --watch=false --code-coverage      # needs Chrome
npm audit --json
npx @axe-core/cli http://localhost:4200        # optional, served build
```

## Child applicability for Angular repos

| Repo shape | n/a children |
|---|---|
| Frontend-only Angular | async-and-dependency-injection, orm-query-and-data-access, backend-resource-leak, api-contract (unless a backend root is added); db-schema self-skips |
| Angular + backend in one repo | none |
| Ionic/Capacitor app | none of the frontend children; client-auth also reviews native storage |

## References

- Child references: `../audit-client-auth-and-storage/references/angular.md`,
  `../audit-frontend-xss-and-dom-safety/references/angular.md`, `../audit-frontend-best-practices/references/angular.md`.
- Angular security guide, Angular version compatibility table, Capacitor security docs.
