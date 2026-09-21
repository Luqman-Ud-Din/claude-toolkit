# Angular reference for audit-owasp-asvs-mapper

The frontend half of the ASVS mapping. Angular findings almost always land in V5.3
(output encoding), V3.2/V8.2 (client-side token storage), V14.4.3 (CSP, which the
server must send but the SPA must be compatible with) and V14.2.3 (SRI). Server-side
controls (V4, V14.4, V9) are owned by the backend skills; the frontend can only supply
evidence that a control is *not* relied upon client-side.

## Stack markers
`package.json` with `@angular/core`, `angular.json`, `src/app/`, `environments/*.ts`.
Variants: NgModules vs standalone; Ionic/Capacitor (adds native storage and WebView
considerations); SSR (`@angular/ssr`) which moves some header duties into the Node server.

## Where the relevant code lives
- Templates: `[innerHTML]`, `bypassSecurityTrust*` in `*.component.ts`, `DomSanitizer` usage.
- Auth: `core/interceptors/token.interceptor.ts`, `core/services/auth.service.ts`, `storage.service.ts`.
- Guards: `core/guards/*.guard.ts` (`CanActivateFn`) - cosmetic only.
- Build: `angular.json` (`optimization`, `sourceMap`, `outputHashing`), `index.html` (`<meta http-equiv="Content-Security-Policy">`, `<script integrity=...>`).
- Environment: `environments/environment*.ts` (must not contain secrets).

## Controls Angular satisfies by default
| ASVS | Angular default | Fails when |
|---|---|---|
| 5.3.3 context-aware escaping | Interpolation `{{ }}` and property binding escape; `[innerHTML]` is sanitized | `bypassSecurityTrustHtml/Script/Url/ResourceUrl` on user input; `ElementRef.nativeElement.innerHTML =`; `Renderer2.setProperty(el, 'innerHTML', x)` |
| 5.2.4 no dynamic code | AOT compilation, no `eval` | `new Function`, `eval`, JIT compiler with user templates |
| 5.1.5 redirects | `Router.navigate` is app-internal | `window.location.href = param` from query string (open redirect) |
| 4.2.2 CSRF | `HttpClientXsrfModule` reads `XSRF-TOKEN` cookie and sends `X-XSRF-TOKEN` | Backend uses bearer tokens (N/A) or cookie names differ from the backend's |

## Controls that need explicit evidence on the client
- 3.2.3 / 8.2.2 token storage: JWT in `localStorage` = Failed (CWE-922); in-memory or HttpOnly cookie = Verified. Encrypted `localStorage` (crypto-js with a key shipped in the bundle) is still Failed - the key is public.
- 8.2.2 sensitive data in browser storage: cached PII lists, tenant lists, other users' data.
- 4.1.1: guards must not be the only control. Evidence for Verified is a backend `[Authorize]`, not the guard. Mark client-only findings with tag `client-side-check` (maps to CWE-602, A01).
- 14.4.3 CSP compatibility: no inline scripts/styles that force `'unsafe-inline'`; Angular emits inline styles unless `CSP_NONCE` / `ngCspNonce` is used.
- 14.2.3 SRI: `<script src="https://cdn...">` in `index.html` without `integrity`.
- 2.10.4: `environment.prod.ts` containing API keys/secrets (only public keys are acceptable; state which).
- 14.3.2: `sourceMap: true` in the production configuration ships readable source.
- 9.1.1: `environment.apiUrl` starting with `http://` for production.

## What "good" looks like
```ts
// product-detail.component.ts
this.safeDescription = DOMPurify.sanitize(product.description);    // keep [innerHTML], no bypass -> ASVS 5.3.3
// token.interceptor.ts
if (req.url.startsWith(environment.apiUrl)) req = req.clone({ setHeaders: { Authorization: `Bearer ${this.auth.token}` } }); // token in memory -> 3.2.3
// angular.json production config
"sourceMap": false, "optimization": true, "outputHashing": "all"   // 14.3.2
```

## Manual trace checklist
1. Grep `bypassSecurityTrust` and read each call: constant input (Info) vs user/API input (High, V5.3.3).
2. Where does the token live after login? Follow `storage.service.ts` to its backing store (V3.2.3).
3. `index.html`: CSP meta, third-party scripts, `integrity` attributes (V14.4.3, V14.2.3).
4. `environment.prod.ts`: every key classified public/secret (V2.10.4).
5. Guards list vs backend `[Authorize]` inventory from the authz skill (V4.1.1).

## Stack-specific false positives
- `bypassSecurityTrustResourceUrl` for a hard-coded iframe/PDF URL.
- `localStorage` for theme, language, column layout (no sensitive data - not 8.2.2).
- `[innerHTML]` on API HTML that is already sanitized server-side and Angular-sanitized again.
- Guards present *and* backend authorization verified: guards are Info at most.

## Tooling
- `npm audit --json` (V14.2.1). `ng build --configuration production --stats-json` to inspect what ships.
- `npx eslint --plugin @angular-eslint/template` rule `no-inline-styles`, `no-any`; `eslint-plugin-security`.
- Browser DevTools > Application > Storage to confirm where tokens are kept (screenshot into `audit/evidence/`).

## References
- Angular Security guide (sanitization, trusting safe values, CSP, XSRF).
- ASVS 4.0.3 V3.2.3, V5.3.3, V8.2, V14.4.3, V14.2.3; CWE-79, CWE-922, CWE-602, CWE-601.
- Sibling skills: `audit-frontend-xss-and-dom-safety` (V5.3), `audit-client-auth-and-storage` (V3, V8.2).
