# Client auth flow checklist

Areas map to pattern-id prefixes in `scripts/patterns/*.json`: STORE, INTERCEPT,
REFRESH, LOGOUT, GUARD, SECRET, TRANSPORT.

## STORE - where the token lives

| Option | Readable by page script | Survives reload | Sent automatically | Main risk | Verdict |
|---|---|---|---|---|---|
| `localStorage` | yes | yes (forever) | no | any XSS exfiltrates it; shared across tabs and time | avoid for access and especially refresh tokens |
| `sessionStorage` | yes | tab only | no | same XSS exposure, shorter life | still readable; marginally better |
| IndexedDB / Cache API | yes | yes | no | same as localStorage, harder to audit | avoid |
| Cookie without HttpOnly | yes (`document.cookie`) | per flags | yes | XSS + CSRF | worst of both |
| Cookie `HttpOnly; Secure; SameSite=Lax/Strict` | no | per flags | yes | CSRF (needs SameSite or anti-forgery token), no bearer for other origins | preferred for browser apps with a same-site API |
| Memory (closure/service field) | yes, but not persisted | no | no | lost on reload -> needs silent refresh via HttpOnly refresh cookie | good access-token home |
| Native secure storage (Keychain / Keystore via Capacitor `SecureStorage`, RN `Keychain`) | app only | yes | no | plugin misconfig (`Preferences` is NOT secure) | required on mobile |

Rules: refresh tokens never in web storage; access tokens in memory or HttpOnly
cookie; if the team insists on `localStorage`, the finding stays and the severity
depends on whether an XSS sink exists. "We encrypt it before storing" with a key
in the bundle is not a control (key and ciphertext are both readable) - Info at best.

## INTERCEPT - who gets the credential

- Attach `Authorization` / `withCredentials` only when the request URL starts with the app's own API origin(s) (from environment config), or when the request targets a relative path proxied to the API.
- Third-party calls (maps, analytics, CDNs, payment providers, S3 pre-signed URLs) must not carry the token: separate client or explicit allow-list.
- Do not put tokens in query strings (logged by proxies, referrers).
- 401 handling: one place, triggers refresh (below) or logout; do not retry blindly on 403.
- The interceptor must skip its own login/refresh/public endpoints to avoid loops.

## REFRESH - staying logged in safely

- Expiry known from JWT `exp` (decode without verifying - the client cannot verify) or from the server's `expires_in`; refresh proactively before expiry or on first 401.
- Single-flight: concurrent 401s share one refresh (`shareReplay(1)`, a promise cached in the service, a `BehaviorSubject` gate); queued requests replay with the new token.
- Refresh token stored per STORE rules; rotation (new refresh token each time) with reuse detection is server-side - note it for the authz skill.
- Refresh failure -> full logout (below), never an infinite loop.
- No refresh at all: users are logged out at expiry (availability) or, worse, tokens have no expiry (session never ends) - check the JWT `exp` claim length in evidence.

## LOGOUT - leaving nothing behind

Logout must clear: every storage key the app wrote (tokens, user profile, tenant id, permissions, remembered filters that embed ids), in-memory state (stores, `BehaviorSubject`s, NgRx/Redux/Pinia state), timers (refresh timers, idle timers), service-worker/HTTP caches holding API responses, and server-side session/cookie via a logout endpoint (an HttpOnly cookie cannot be cleared by script). Then navigate to a public route. Multi-tab: broadcast logout (`storage` event or `BroadcastChannel`). "Remember me" must not mean a non-expiring token.

## GUARD - UX only

Route guards (`CanActivateFn`, `<PrivateRoute>`, `router.beforeEach`) decide what to show; they are bypassable by anyone with DevTools. They are Info in this report, cross-referenced to `audit-authz-and-access-control`, unless the server does not enforce the same rule (then that skill owns the High). Flag guards that decode the JWT to read roles: fine for UX; unsafe only if the same decode drives data access.

## SECRET - what ships in the bundle

Everything in `environment*.ts`, `.env` values prefixed `REACT_APP_`/`VITE_`/`NEXT_PUBLIC_`/`NUXT_PUBLIC_`, `runtimeConfig.public`, `capacitor.config`, and any imported JSON ends up in the bundle and is public.

`scripts/scan_secrets.py` pre-sorts hits with `audit-sensitive-data-catalog`: a value is
`public_id` when the catalog marks its format public by design (`exposure: public` or
`conditional`, for example Stripe `pk_`, Sentry DSN, GA id, Firebase app id, Google `AIza` keys)
or its key name carries a public-by-design hint. The table below is the reviewer's decision
guide; add new formats or hints to the catalog, not to the script.

| Public identifier (Info; verify restrictions) | Secret (High/Critical) |
|---|---|
| Firebase web config (`apiKey`, `appId`, `messagingSenderId`) | Firebase service-account JSON, `databaseSecret` |
| Google Maps browser key (referrer-restricted) | Google server key, OAuth client secret |
| Stripe `pk_live_...` publishable key | Stripe `sk_live_...`, webhook secret |
| Auth0/OIDC client id, authority URL | OIDC client secret |
| Sentry DSN, GA measurement id, Mixpanel token | SMS/email provider keys (Twilio SID+token, SendGrid) |
| Shopify storefront token (storefront-scoped) | Shopify Admin API token |
| Public VAPID key | VAPID private key, JWT signing key, DB connection strings, AWS access keys, `.pem`/`PRIVATE KEY` blocks |

A secret found in source but excluded from the production build (`fileReplacements`, `.env.local` in `.gitignore`) is still a repository secret - hand to `audit-secrets-and-config` and report here only what ships.

## TRANSPORT

`http://` API URLs in production config, `withCredentials: true` combined with a wildcard CORS origin (owned by headers skill; note it), tokens in `window.postMessage` without target origin, tokens in URL fragments for deep links, tokens logged to console.

## Severity anchors

- Critical: server-side secret (provider key, signing key, service account, DB string) in the production bundle or env file.
- High: JWT/refresh token in web storage with an XSS sink present; interceptor sends the token to third-party hosts that are actually called; tokens in query strings to third parties; OAuth client secret in the bundle.
- Medium: token in web storage with no sink found; logout leaves a token or refresh token behind; no single-flight refresh causing token races; `http://` API URL in prod.
- Low: no proactive refresh (users bounced at expiry); missing multi-tab logout; verbose auth logging.
- Info: guards (UX-only, server verified); public identifiers with restrictions to verify; encryption-of-localStorage with bundled key (no control, but no new exposure).
