# Headers, cookies, middleware order, CSRF, rate limits - the checklist

`scripts/check_headers.py` implements the grading rules below; the manual pass
applies the same rules to what the code emits.

## Response headers

| Header | Expected (pass) | Misconfigured when | Missing = | Notes |
|---|---|---|---|---|
| Content-Security-Policy | present with `default-src` (or `script-src`) and `frame-ancestors`; no `*`, no `'unsafe-inline'`/`'unsafe-eval'` in `script-src`; `object-src 'none'`; `base-uri 'self'` | `script-src` contains `'unsafe-inline'` (without nonce/hash), `'unsafe-eval'`, `*`, `data:`, `http:`; only `-Report-Only` present; missing `frame-ancestors` (then X-Frame-Options must cover it) | Medium (High if the app renders user HTML) | Angular/React/Vue need `'unsafe-inline'` for **styles** only in some setups; that is a Low note, not a fail. Report-Only is a rollout step, not a control. |
| Strict-Transport-Security | `max-age` >= 15552000 (180 d); `includeSubDomains` recommended; `preload` optional | `max-age` < 15552000, or `max-age=0` | Medium | Only meaningful on HTTPS responses; check the redirect chain sets it on the final host. |
| X-Content-Type-Options | `nosniff` | any other value | Low | |
| X-Frame-Options | `DENY` or `SAMEORIGIN` | `ALLOW-FROM` (ignored by browsers) | Low (Medium if login/actions can be framed and no `frame-ancestors`) | Redundant when CSP `frame-ancestors` exists; pass either. |
| Referrer-Policy | `no-referrer`, `same-origin`, `strict-origin`, `strict-origin-when-cross-origin` | `unsafe-url`, `no-referrer-when-downgrade`, `origin-when-cross-origin` | Low | Tokens or ids in URLs raise this to Medium. |
| Permissions-Policy | present, disabling unused features (`camera=(), microphone=(), geolocation=(), payment=()`) | `*` allow-lists for sensitive features | Low | Formerly Feature-Policy. |
| Cross-Origin-Opener-Policy / -Resource-Policy / -Embedder-Policy | `same-origin` / `same-origin` (or `same-site`) | - | Info | Hardening; note only. |
| Cache-Control on authenticated API/HTML | `no-store` (or `private, no-cache`) | `public` on authenticated responses | Low/Medium | Shared caches and back button. |
| Server, X-Powered-By, X-AspNet-Version, X-AspNetMvc-Version | absent or generic | version strings present | Low | Information disclosure. |
| Access-Control-Allow-Origin | explicit origin list (echo of a validated origin) | `*` with `Access-Control-Allow-Credentials: true` (browser rejects, but signals reflected-origin code); reflected `Origin` without validation | n/a (only when cross-origin is needed) | Check `Vary: Origin`. |
| Set-Cookie (per cookie) | see below | | | |

## Cookie flags

| Flag | Rule |
|---|---|
| HttpOnly | required for session/auth/refresh cookies; absence = High for those, Low for others. |
| Secure | required everywhere on HTTPS sites; absence = High for auth cookies. |
| SameSite | `Strict` or `Lax` for auth cookies; `None` requires `Secure` and a CSRF defence; missing = browser default Lax (still report Low; explicit is better). |
| Path | scope refresh cookies to the refresh endpoint. |
| Expires/Max-Age | session cookies should not outlive the server session; 30+ day auth cookies are a note for `audit-client-auth-and-storage`. |
| `__Host-` prefix | bonus: forces Secure, no Domain, Path=/. |

## Middleware order

Canonical (from the spec): exception handling -> HSTS -> HTTPS redirect -> static files -> routing -> CORS -> authentication -> authorization -> rate limiting -> endpoints. `extract_middleware.py` ranks each registration against this table.

| Stage | .NET (`app.*`) | Express/Nest | Spring Security (`http.*` / filters) | Django `MIDDLEWARE` |
|---|---|---|---|---|
| exception | `UseExceptionHandler`, `UseDeveloperExceptionPage` (dev only) | error handler is registered **last** in Express (4-arg middleware) - that is correct for Express | `exceptionHandling()` | (framework built-in; custom error middleware near top) |
| hsts | `UseHsts` | `helmet.hsts` / `helmet()` | `headers().httpStrictTransportSecurity()` | `SecurityMiddleware` (`SECURE_HSTS_SECONDS`) |
| https | `UseHttpsRedirection` | `express-sslify` / proxy | `requiresChannel()` / proxy | `SecurityMiddleware` (`SECURE_SSL_REDIRECT`) |
| headers | header middleware, `NWebsec`, custom `app.Use` | `helmet()` | `headers()` | `SecurityMiddleware`, `XFrameOptionsMiddleware`, `django-csp` |
| static | `UseStaticFiles` | `express.static` | resource handlers | `WhiteNoiseMiddleware` |
| routing | `UseRouting` | (implicit) | (implicit) | (implicit) |
| cors | `UseCors` | `cors()` | `cors()` / `CorsFilter` | `CorsMiddleware` (must be above `CommonMiddleware`) |
| bodylimit | Kestrel `MaxRequestBodySize`, `[RequestSizeLimit]` | `express.json({ limit })`, `express.urlencoded({ limit })`, `multer` limits | `spring.servlet.multipart.max-*`, `server.max-http-request-header-size` | `DATA_UPLOAD_MAX_MEMORY_SIZE`, `FILE_UPLOAD_MAX_MEMORY_SIZE` |
| session | `UseSession` | `express-session` | `sessionManagement()` | `SessionMiddleware` (before Auth) |
| csrf | `UseAntiforgery` (.NET 8+), `[ValidateAntiForgeryToken]`, `AutoValidateAntiforgeryToken` | `csurf`/`csrf-csrf`, double-submit | `csrf()` (default on) | `CsrfViewMiddleware` |
| authentication | `UseAuthentication` | `passport.initialize()` / JWT middleware | `oauth2ResourceServer()`, `addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter)` | `AuthenticationMiddleware` (after Session) |
| authorization | `UseAuthorization` | route guards / `authorize` middleware | `authorizeHttpRequests()` | permission decorators / DRF permissions |
| ratelimit | `UseRateLimiter` (.NET 7+), `AspNetCoreRateLimit` `UseIpRateLimiting` | `express-rate-limit`, `rate-limiter-flexible`, Nest `ThrottlerGuard` | `bucket4j`, gateway filters | `django-ratelimit`, DRF throttling |
| endpoints | `MapControllers`, `MapGet`, `UseEndpoints`, `MapRazorPages`, `MapHub` | `app.use('/api', router)`, `app.get(...)` | (controllers) | (urls) |

Order issues to flag: `authentication` or `authorization` after `endpoints`; `authorization` before `authentication`; `cors` after `authentication` (preflights get 401); `static` after `authentication` when public assets must be anonymous (note only); `exception` not first (.NET); `hsts`/`https` after `endpoints`; `routing` after `endpoints` (.NET 6+ implicit - note only); Django `CorsMiddleware` below `CommonMiddleware`; `SessionMiddleware` after `AuthenticationMiddleware`; `CsrfViewMiddleware` absent with session auth.

Stack-specific caveats: .NET `UseRateLimiter` must come after `UseRouting` (endpoint-specific limits) - anywhere between routing and endpoints is fine; Express error handler last is correct; Spring order is inside the filter chain, `addFilterBefore/After` placements matter more than statement order.

## CSRF decision table

| Auth transport | State-changing routes | CSRF defence required? |
|---|---|---|
| Bearer token in `Authorization` header only, no auth cookies | any | No (browsers do not attach it cross-site). Report Info if a CSRF middleware is present anyway. |
| Session or token cookie (HttpOnly or not) | POST/PUT/PATCH/DELETE | Yes: synchronizer token (`[ValidateAntiForgeryToken]`, Django `CsrfViewMiddleware`, Spring `csrf()`), or double-submit + `SameSite=Strict/Lax` + Origin/Referer check. |
| Cookie auth with `SameSite=Lax` only | POST | Partial: Lax blocks cross-site POST but top-level GET navigations still carry it; GET must not change state. Medium if no token. |
| Cookie auth and CORS `credentials: true` with a broad origin list | any | Yes, and the CORS list itself is a High finding. |

## Rate limiting and body limits

Targets that need a limit: login, register, forgot/reset password, OTP/SMS/email send, token refresh, search/report/export, file upload, any endpoint calling a paid third party (SMS, maps, AI). Key on user id when authenticated, IP plus account for login (both), and never on a header the client controls (`X-Forwarded-For` unless set by a trusted proxy). Missing on login = Medium (High if no lockout exists either - cross-check with `audit-authz-and-access-control`).

Body limits: JSON 1-10 MB unless there is a reason; multipart sized to the largest legitimate upload; unbounded = Medium (DoS). Frameworks: Kestrel 30 MB default (pass with note), Express `express.json()` default 100 KB (pass), Spring multipart 1 MB file / 10 MB request default (pass), Django `DATA_UPLOAD_MAX_MEMORY_SIZE` 2.5 MB default (pass).

## Severity anchors

- Critical: authentication/authorization after endpoints (protected routes run unauthenticated); developer exception page enabled in production with a public route.
- High: session/refresh cookie without HttpOnly or Secure; cookie auth with no CSRF defence; CORS credentials with wildcard/reflected origin; CSP with `'unsafe-inline'` scripts on an app that renders user HTML.
- Medium: missing CSP; missing HSTS or max-age below 180 days; no rate limit on login/OTP; unbounded request body; authorization before authentication; CORS after authentication.
- Low: missing `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `X-Frame-Options` when `frame-ancestors` also absent; `Server`/`X-Powered-By` disclosure; non-auth cookie without flags.
- Info: documented deviations (CSP Report-Only during rollout with a dated plan); CSRF middleware present on a bearer-only API; hardening headers (COOP/CORP) absent.
