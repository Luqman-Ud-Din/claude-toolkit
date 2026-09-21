# Node / Express (NestJS, Fastify, Koa) reference for audit-security-headers-and-middleware

## Stack markers
`package.json` with `express`, `@nestjs/core` (+ `@nestjs/platform-express` or `-fastify`), `fastify`, `koa`; security packages: `helmet`/`@fastify/helmet`, `cors`/`@fastify/cors`, `express-rate-limit`/`rate-limiter-flexible`/`@nestjs/throttler`/`@fastify/rate-limit`, `csurf`/`csrf-csrf`/`@fastify/csrf-protection`, `cookie-parser`, `express-session`/`cookie-session`, `hpp`, `express-mongo-sanitize`.

## Where the relevant code lives
`src/app.ts`/`server.ts`/`index.js` (Express: every `app.use(...)`/`app.get(...)` in order), Nest `src/main.ts` (`app.use(helmet())`, `app.enableCors(...)`, `app.useGlobalGuards/Pipes/Filters`, `bodyParser` options) and `app.module.ts` (`ThrottlerModule`, `configure(consumer)` middleware), Fastify `app.register(...)` order, `routes/**` (per-router middleware), `middleware/**` (custom headers/auth/error), `.env` (`CORS_ORIGIN`, `COOKIE_SECURE`), `nginx.conf`/`vercel.json`/`serverless.yml` for the host in front, `next.config.js` `headers()` if Next.js API routes are the backend.

## Dangerous / interesting APIs and patterns
- Headers: no `helmet()` (or `@fastify/helmet`) and no custom header middleware; `helmet({ contentSecurityPolicy: false })` (CSP switched off - common); `helmet.contentSecurityPolicy({ directives: { scriptSrc: ["'self'", "'unsafe-inline'", "'unsafe-eval'", "*"] } })`; `hsts: false` or `maxAge` < 15552000; `app.disable('x-powered-by')` missing when helmet absent (`X-Powered-By: Express`); `frameguard: false`; `referrerPolicy` left at helmet default (`no-referrer` - pass) but overridden to `unsafe-url`; Next.js `headers()` in `next.config.js` missing for API routes.
- Order (Express): `app.use('/api', router)` or `app.get(...)` **before** `app.use(authenticate)` (routes registered earlier never see later middleware); `app.use(cors())` after auth (preflight 401); `helmet()` after routes (routes respond without headers); `express.json()` after routes (body undefined); error handler `(err, req, res, next)` **not** last; `express.static` after auth when assets must be public (note); Nest: `app.useGlobalGuards(new JwtAuthGuard())` versus `APP_GUARD` provider (fine), `@Public()` decorator gaps, `ThrottlerGuard` not global; Fastify: `register` order and encapsulation (plugin registered inside a scope does not apply globally).
- CORS: `cors()` with no options (`*`), `cors({ origin: true, credentials: true })` (reflects any origin **with** credentials), `origin: '*'` + `credentials: true`, `origin: (o, cb) => cb(null, true)`, `origin` from env with `localhost` in prod; Nest `app.enableCors()` with no options; Fastify `@fastify/cors` `origin: true`.
- Cookies: `res.cookie('token', ..., { })` without `httpOnly: true`/`secure: true`/`sameSite`; `httpOnly: false`; `sameSite: 'none'` without `secure`; `express-session({ cookie: { secure: false } })` in prod, `cookie.httpOnly: false`, `secret` hard-coded or short, `resave: true`/`saveUninitialized: true` (session fixation surface), no `store` in prod (MemoryStore), `app.set('trust proxy', 1)` missing behind a proxy (secure cookies never set).
- CSRF: cookie/session auth (`express-session`, `cookie-session`, `res.cookie('token')`) with no `csurf`/`csrf-csrf`/`@fastify/csrf-protection` and no `sameSite: 'strict'|'lax'`; `csurf` applied only to some routers; `ignoreMethods` including POST.
- Rate limiting: no limiter on `/auth/login`, `/auth/register`, `/auth/forgot`, `/otp`; global limiter only with generous `max`; `express-rate-limit` keyed on `req.ip` without `trust proxy` (all traffic shares the proxy IP - or attacker sets `X-Forwarded-For`); Nest `@Throttle()` missing on `AuthController`; `skipSuccessfulRequests: true` on login (allows unlimited valid attempts).
- Body limits: `express.json({ limit: '50mb' })`/`urlencoded({ limit })` huge; `bodyParser.json()` without limit is 100 KB (pass); `multer({ limits: { fileSize } })` missing; Nest `app.useBodyParser('json', { limit })`; Fastify `bodyLimit` default 1 MB (pass); `raw-body` unlimited.
- Errors: default Express error handler in prod (HTML stack trace when `NODE_ENV !== 'production'`); `res.status(500).json({ error: err.stack })`; Nest `HttpExceptionFilter` echoing `exception.stack`.

## What "good" looks like
```ts
// app.ts (Express) - order matters
const app = express();
app.set('trust proxy', 1);                                         // behind nginx/ingress
app.use(helmet({ contentSecurityPolicy: { directives: { defaultSrc: ["'self'"], scriptSrc: ["'self'"], objectSrc: ["'none'"], baseUri: ["'self'"], frameAncestors: ["'none'"] } },
                 hsts: { maxAge: 31536000, includeSubDomains: true }, referrerPolicy: { policy: 'strict-origin-when-cross-origin' } }));
app.use(cors({ origin: config.corsOrigins /* explicit array */, credentials: true }));
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: false, limit: '1mb' }));
app.use(cookieParser());
app.use(express.static('public'));
const loginLimiter = rateLimit({ windowMs: 15 * 60_000, max: 5, standardHeaders: true, legacyHeaders: false });
app.use('/api/auth/login', loginLimiter);
app.use('/api', authenticate);                                     // JWT / session check
app.use('/api', apiRouter);                                        // endpoints
app.use(errorHandler);                                             // last: (err, req, res, next) => res.status(500).json({ message: 'Unexpected error' })
// cookies: res.cookie('refresh_token', rt, { httpOnly: true, secure: true, sameSite: 'strict', path: '/api/auth/refresh', maxAge: 14 * 864e5 });
```
Nest: `app.use(helmet())`, `app.enableCors({ origin: [...], credentials: true })` in `main.ts`; `ThrottlerModule.forRoot([{ ttl: 60000, limit: 10 }])` + `APP_GUARD: ThrottlerGuard`; `@Throttle({ default: { limit: 5, ttl: 60000 } })` on login.

## Manual trace checklist
1. Entry file: list registrations in order (extractor), then open each router for router-level middleware.
2. Helmet options: CSP on/off and directives; HSTS max-age; what is disabled.
3. Auth model: bearer vs session/cookie -> CSRF decision; `trust proxy` for secure cookies.
4. Every `res.cookie` / session cookie options; `secret` source.
5. CORS options and origin source; `credentials`.
6. Rate limiting on auth endpoints and key source.
7. Body limits on JSON, urlencoded, multipart, raw.
8. Error handler position and content; `NODE_ENV` in the deploy config.

## Stack-specific false positives
- Express error handler registered last - correct, not "exception not first".
- `cors()` with no options on a bearer-only public API with no credentials - Low/Info.
- `helmet({ contentSecurityPolicy: false })` on a JSON-only API that never serves HTML - Low with a note (CSP still helps against reflected content types; set a minimal `default-src 'none'`).
- `express.json()` default 100 KB - pass.
- Nest `APP_GUARD` JWT guard with `@Public()` on health/login only.

## Tooling
- `python scripts/extract_middleware.py <repo> --stack node-express` (bundled).
- `python scripts/check_headers.py https://host` (bundled) when a URL is supplied.
- `npm ls helmet cors express-rate-limit csurf csrf-csrf @nestjs/throttler express-session`.
- `npx eslint-plugin-security`; `semgrep --config p/expressjs` (`express-cors-misconfig`, `express-session-hardcoded-secret`, `express-cookie-session-no-secure`).

## References
Express "Production Best Practices: Security"; helmet docs; NestJS Security (helmet, CORS, rate limiting, CSRF); OWASP HTTP Headers, CSRF, Session Management cheat sheets. CWE-306, CWE-1004, CWE-614, CWE-352, CWE-942, CWE-307, CWE-400, CWE-209; ASVS 1.4.4, 3.4.x, 4.2.2, 13.2.x, 14.4.x, 14.5.x; OWASP A01/A05/A07:2021.
