# Angular (incl. Ionic/Capacitor) reference for audit-security-headers-and-middleware

Headers and middleware are set by whatever serves the SPA and by the API. This
file covers the frontend's share: the hosting configuration that emits headers
for `index.html`, what the app needs from a CSP, and what the SPA must do for
CSRF and cookies. The API pipeline is audited with the backend stack file.

## Stack markers
`package.json` with `@angular/core`; `angular.json`; hosting configs: `nginx.conf`/`default.conf` (Docker images), `firebase.json` (`hosting.headers`), `staticwebapp.config.json` (Azure SWA `globalHeaders`), `_headers` (Netlify/Cloudflare Pages), `vercel.json` (`headers`), `web.config` (IIS), `Caddyfile`, S3/CloudFront (outside the repo - not checked), `server.ts` (Angular SSR/Express - then also apply `node-express.md`), Capacitor (`capacitor.config.ts` `server.androidScheme`, `allowNavigation`).

## Where the relevant code lives
`src/index.html` (`<meta http-equiv="Content-Security-Policy">` - a fallback only; no `frame-ancestors`/reporting via meta), `angular.json` (`optimization`, `sourceMap` in prod, `outputHashing` - for cache headers), `ngsw-config.json` (service worker caching of API responses), `proxy.conf.json` (dev only; make sure prod does not depend on it), `src/environments/*.ts` (API origin -> CORS expectation), `core/interceptors/*` (`withCredentials`, `HttpClientXsrfModule`/`withXsrfConfiguration` for cookie auth), `server.ts` (SSR).

## What this skill checks on the frontend
- **Hosting headers**: the host config must emit CSP, HSTS, X-Content-Type-Options, X-Frame-Options (or `frame-ancestors`), Referrer-Policy, Permissions-Policy on `index.html` and assets; `Cache-Control: no-store` for `index.html` (so deploys propagate) and long `max-age, immutable` for hashed assets. Missing config file = headers come from the CDN/host defaults (usually none) - report Medium and note that the live check is the only proof.
- **CSP compatibility**: Angular production builds need no `'unsafe-inline'`/`'unsafe-eval'` for scripts; some setups need `style-src 'unsafe-inline'` (Angular component styles use inline `<style>` elements; Angular 16+ supports `ngCspNonce`/`CSP_NONCE` to avoid it). Flag `'unsafe-eval'` (JIT builds, some charting libs) and `script-src *`. Angular Material/CDK, Ionic, and Google Maps each add hosts to `script-src`/`style-src`/`img-src`/`connect-src` - the report lists the required allow-list.
- **Meta CSP**: `<meta http-equiv>` cannot set `frame-ancestors` and cannot report; if it is the only CSP, report Low and recommend the header.
- **CSRF on the client**: if the API uses cookie auth, the app must send the anti-forgery header (`provideHttpClient(withXsrfConfiguration({ cookieName: 'XSRF-TOKEN', headerName: 'X-XSRF-TOKEN' }))`) and the backend must issue the cookie; `withCredentials: true` must be scoped to the API origin (owned by `audit-client-auth-and-storage`).
- **Dev artefacts**: `proxy.conf.json` targets, `environment.ts` localhost URLs, `sourceMap: true` in the production configuration (exposes source), `ng serve --disable-host-check`.
- **Capacitor**: `server.cleartext: true`, `allowNavigation: ['*']`, `androidScheme: 'http'` - transport weaknesses on mobile.

## What "good" looks like
```nginx
# nginx default.conf for the SPA
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.example.com wss://api.example.com; object-src 'none'; base-uri 'self'; frame-ancestors 'none'" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
location = /index.html { add_header Cache-Control "no-store" always; }
location ~* \.(js|css|woff2)$ { add_header Cache-Control "public, max-age=31536000, immutable" always; }
```
`firebase.json`: `"hosting": { "headers": [{ "source": "**", "headers": [{ "key": "Content-Security-Policy", "value": "..." }, ...] }] }`. Azure SWA: `"globalHeaders": { "Content-Security-Policy": "...", ... }`. Angular 16+: `<app-root ngCspNonce="{{nonce}}">` with a server-generated nonce to drop `'unsafe-inline'` for styles.

## Manual trace checklist
1. Find the hosting config in the repo (`grep -ril "add_header\|globalHeaders\|\"headers\"" --include=*.conf --include=*.json`); if none, record "headers set outside the repo".
2. Compose the CSP the app needs from its third-party hosts (`grep -rho "https://[a-z0-9.-]*" src | sort -u`) and compare with the configured one.
3. `index.html` meta CSP presence and directives.
4. Cookie-auth apps: XSRF configuration in `provideHttpClient`/`HttpClientModule`.
5. `angular.json` production configuration: `sourceMap`, `optimization`, `outputHashing`.
6. Capacitor `server` settings.

## Stack-specific false positives
- `style-src 'unsafe-inline'` on Angular < 16 without nonce support - Low note, not a fail.
- `connect-src` including `wss://` for SignalR/WebSockets - required.
- `proxy.conf.json` with `http://localhost` - dev only, unless referenced by a production script.

## Tooling
- `python scripts/check_headers.py https://app.example.com` (bundled) - the live check is the authoritative test for SPA headers.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/angular.json` (hosting configs and meta CSP).
- Browser devtools console after enabling the CSP in staging: every violation is a required allow-list entry or a code fix.

## References
Angular Security guide (CSP, Trusted Types, `ngCspNonce`); MDN CSP; nginx `add_header` (`always`); Firebase/Azure SWA/Netlify header docs. CWE-693, CWE-1021, CWE-16; ASVS 14.4.x, 14.5.x; OWASP A05:2021. Sibling skills: `audit-frontend-xss-and-dom-safety` (inline scripts that block CSP), `audit-client-auth-and-storage` (withCredentials scope, token storage).
