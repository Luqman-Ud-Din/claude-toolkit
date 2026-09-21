# Node / Express (and NestJS, Fastify, Koa) reference for audit-owasp-asvs-mapper

Express satisfies almost nothing by default; NestJS adds structure but not security
headers. This file lists what must be visibly present for an ASVS control to be
Verified and where the mapper should expect the evidence.

## Stack markers
`package.json` with `express`, `fastify`, `koa`, `@nestjs/core`, `hapi`; `app.ts|js`,
`main.ts` (Nest), `src/routes/*`, `src/controllers/*`. Variants: plain Express with
middleware chain; NestJS with guards/pipes/interceptors; Prisma / TypeORM / Sequelize / Mongoose.

## Where the relevant code lives
- App bootstrap: `app.use(helmet())`, `cors()`, `express.json({ limit })`, `cookie-session`, `passport`.
- Auth: `passport` strategies, `jsonwebtoken.verify` options, Nest `AuthGuard`, `@UseGuards`, `@Roles`.
- Data: `prisma.$queryRawUnsafe`, `sequelize.query` with template strings, Mongoose `find(req.query)`.
- Config: `.env`, `config/*.js`, `process.env.*` usage.
- Errors: error-handling middleware `(err, req, res, next)`, Nest exception filters.
- Logging: `morgan`, `pino`, `winston` config and redact lists.

## Controls with no default protection (Not assessed until code is seen)
| ASVS | Evidence that satisfies it | Failure shape |
|---|---|---|
| 14.4.3-14.4.7 headers | `app.use(helmet())` (sets nosniff, HSTS, frame-ancestors, referrer, CSP default) | No helmet; `helmet({ contentSecurityPolicy: false })` without a replacement CSP |
| 14.4.5 HSTS | `helmet.hsts({ maxAge: 31536000, includeSubDomains: true })` or reverse proxy | Missing; only on the proxy but proxy config not in repo -> Not assessed |
| 14.5.3 CORS | `cors({ origin: [allowList], credentials: true })` | `cors()` with no options (`*`) on authenticated routes; `origin: true` reflection |
| 4.2.2 CSRF | `csurf`/`csrf-csrf` when cookies carry the session; N/A for bearer tokens | Cookie session + state-changing POST with no token |
| 4.1.1 access control | Auth middleware mounted before routers, or Nest global guard | Route file mounted before `app.use(authenticate)`; `@Public()` decorator sprawl |
| 4.2.1 IDOR | `where: { id, ownerId: req.user.id }` | `findUnique({ where: { id } })` from a route param |
| 5.1.2 mass assignment | DTO allow-list (`class-validator` + `whitelist: true, forbidNonWhitelisted: true` in `ValidationPipe`) | `Model.create(req.body)`, `Object.assign(entity, req.body)` |
| 5.1.3 validation | `zod`/`joi`/`class-validator` schema per route | Unvalidated `req.body` reaching services |
| 5.3.4 parameterized queries | ORM builders, `$queryRaw` tagged template, `pg` `$1` params | `$queryRawUnsafe(\`... ${x}\`)`, `knex.raw("..." + x)` |
| 5.3.8 command injection | `execFile` with arg array | `exec(\`cmd ${userInput}\`)` |
| 12.1.1 upload size | `multer({ limits: { fileSize } })`, `express.json({ limit: '1mb' })` | No limits |
| 2.4.1 password storage | `bcrypt`/`argon2` with cost >= 10/12 | `crypto.createHash('sha256')` on passwords |
| 6.3.1 CSPRNG | `crypto.randomBytes`, `randomUUID` | `Math.random()` for tokens |
| 7.1.1 log content | `pino({ redact: ['req.headers.authorization', 'body.password'] })` | `console.log(req.body)` in login handler |
| 7.4.1 generic errors | Error middleware returning fixed message; `NODE_ENV=production` | `res.status(500).send(err.stack)` |
| 14.3.3 version disclosure | `app.disable('x-powered-by')` (helmet does this) | Header present |
| 3.5.3 JWT | `jwt.verify(token, key, { algorithms: ['HS256'], issuer, audience })` | `jwt.decode` used as verification; no `algorithms` pin |

## What "good" looks like
```ts
app.disable('x-powered-by');                                        // ASVS 14.3.3
app.use(helmet({ hsts: { maxAge: 31536000, includeSubDomains: true } })); // 14.4.x
app.use(cors({ origin: allowList, credentials: true }));            // 14.5.3
app.use(express.json({ limit: '1mb' }));                            // 12.1.1
app.use('/api', authenticate, apiRouter);                           // 4.1.1
router.get('/orders/:id', async (req, res) => {
  const order = await prisma.order.findFirst({ where: { id: req.params.id, ownerId: req.user.id } }); // 4.2.1
  if (!order) return res.sendStatus(404);
});
```

## Manual trace checklist
1. Middleware order in the bootstrap file: auth before routers, helmet before everything (V4.1, V14.4).
2. One route per resource traced to the query with the ownership predicate (V4.2.1).
3. `jwt.verify` options and where the secret comes from (V3.5.3, V2.10.4).
4. Every raw-query helper call site (V5.3.4).
5. Logger redact config and any `console.log` of request objects (V7.1).

## Stack-specific false positives
- `cors()` without options on a public, unauthenticated read-only API is a design choice; mark Low/Info.
- `$queryRaw` with a tagged template literal is parameterized; only `$queryRawUnsafe` concatenation fails.
- Missing helmet in a service that only sits behind an API gateway which sets headers: cite the
  gateway config as compensating control, or Not assessed if the config is outside the repo.

## Tooling
- `npm audit --json` / `pnpm audit` (CVE ids; V14.2.1). `npx retire` for bundled libs.
- `eslint-plugin-security` (rules map to CWE: `detect-child-process` = CWE-78, `detect-eval-with-expression` = CWE-94).
- `npx semgrep --config p/nodejs` emits CWE ids in `metadata.cwe`; copy them into `references`.

## References
- Express "Production Best Practices: Security"; helmet docs; OWASP NodeJS Security Cheat Sheet.
- ASVS 4.0.3 V4, V5.1, V5.3, V12.1, V14.4, V14.5; CWE-79, CWE-89, CWE-639, CWE-915, CWE-942, CWE-78.
