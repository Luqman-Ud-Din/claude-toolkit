# Angular reference for audit-privacy-data-flow-mapper

The frontend is where personal data is *collected* (forms), *cached in the
browser* (localStorage/IndexedDB/service-worker caches), *displayed*, and
*sent to client-side vendors* (analytics tags, error trackers, chat widgets).
It never owns the system of record; the backend stack file owns storage,
server logs and server-to-vendor flows. Encryption/expiry of browser storage
belongs to `audit-client-auth-and-storage`; XSS to `audit-frontend-xss-and-dom-safety`.

## Stack markers
`package.json` with `@angular/core`, `angular.json`. Variants: Ionic/Capacitor
(native storage plugins `@capacitor/preferences`, `@ionic/storage`, push tokens
via Firebase), PWA (`ngsw-config.json` caches API responses), SSR.

## Where the relevant code lives
- Collection: reactive forms (`FormControl`, `formControlName="email"`),
  template-driven `[(ngModel)]`, file upload components, `@shared/models/*.ts` interfaces mirroring DTOs.
- Browser storage: `core/services/storage.service.ts` (localStorage with
  crypto-js), `sessionStorage`, IndexedDB (`ngx-indexed-db`), `@capacitor/preferences`,
  `ngsw-config.json` `dataGroups` (cached API responses containing PII).
- Client-side processors: `console.*`, `core/services/notification|analytics.service.ts`,
  `environment.ts` keys for GA/Firebase/Sentry/Hotjar, `index.html` script tags,
  `@angular/fire` analytics, `@sentry/angular` `setUser`.
- Transmission: `core/services/api.service.ts` (all backend calls - the *one*
  place to see what fields leave the browser), direct `HttpClient` calls to
  third-party hosts (maps, address lookup, payment iframes), Capacitor push tokens.
- Templates: HTML that renders PII (`{{ user.email }}`) - display, not a flow, but
  note pages that print lists of people (exports, printable reports).

## Dangerous / interesting APIs and patterns
- `console.log(user)` / `console.error(err.response)` shipped to production (no `console` stripping in `angular.json` optimisations).
- `localStorage.setItem('user', JSON.stringify(profile))` - profile with email/phone persisted unencrypted or with a hard-coded key.
- `gtag('event', 'signup', { email })`, `mixpanel.identify(email)`, `Sentry.setUser({ email })`.
- `HttpParams().set('email', email)` on GET - PII in URL, cached by proxies and service worker.
- `ngsw-config.json` `dataGroups` caching `/api/customers/**` with long `maxAge`.
- Third-party tags in `index.html` (GTM, Hotjar, Clarity, Intercom) - session recording captures typed PII unless inputs are masked (`data-hj-suppress`, `data-clarity-mask`).
- Direct calls to `maps.googleapis.com` with full addresses; address autocomplete widgets.
- Ionic: `@capacitor/preferences` storing tokens/profile; Firebase push token registration (device id -> Firebase).

## What "good" looks like
```ts
// storage.service.ts: store the minimum, with expiry
this.storage.set('session', { userId, roles, exp });
// analytics: pseudonymous id only
this.analytics.identify(user.id);
Sentry.init({ sendDefaultPii: false, beforeSend: scrubPii });
// ngsw-config.json: never cache PII endpoints, or use maxAge: "1m" with freshness strategy
```

## Manual trace checklist
1. `api.service.ts` + `@shared/models`: list every PII field that appears in a request model (collection) and response model (display).
2. Storage service: what is persisted, encrypted how, cleared on logout?
3. `environment*.ts` and `index.html`: every vendor key/tag -> third party; what does each SDK receive (`identify`, `setUser`, event props)?
4. `ngsw-config.json` data groups vs PII endpoints.
5. Session-recording tags: are PII inputs masked?
6. Capacitor plugins: native storage and push token flows.

## Stack-specific false positives
- `console.log` inside `if (!environment.production)` guards - Low, still note.
- `email` form controls on login pages - collection is expected; the finding is only about where it goes next.
- `{{ customer.email }}` display bindings - not a flow edge.

## Tooling
- `python scripts/pii_scan.py <repo> ...`; `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/angular.json`
- `grep -rn "localStorage\|sessionStorage\|Preferences\." src/app`
- `grep -rn "https\?://" src/app src/environments | grep -v localhost` for direct third-party hosts
- Browser: DevTools > Application > Storage on a logged-in session (outside the repo; note as manual evidence)

## References
GDPR Art.5(1)(c), Art.25 (privacy by design/default), Art.28; ePrivacy (cookies/tags);
CWE-532, CWE-359, CWE-922, CWE-598; ASVS 8.2 (client-side data protection), 8.3.
Sibling skills: `audit-client-auth-and-storage`, `audit-frontend-xss-and-dom-safety`.
