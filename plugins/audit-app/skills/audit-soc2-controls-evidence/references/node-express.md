# Node / Express reference for audit-soc2-controls-evidence

## Stack markers

`package.json` with `express`, `fastify`, `koa` or `@nestjs/core`. Sub-variants:
plain Express middleware vs NestJS guards/interceptors, Prisma vs TypeORM vs
Sequelize vs Mongoose, session cookies vs JWT. The `dependencies` block tells you
which auth, logging, validation and secrets libraries exist.

## Where the relevant code lives

- `src/app.(ts|js)`, `server.(ts|js)`, `main.ts` - middleware order: helmet,
  rate limiter, auth, routes, error handler.
- `src/auth/`, `src/middleware/auth*`, `src/guards/` - passport strategies,
  `express-jwt`, Nest `AuthGuard`/`RolesGuard`.
- `src/audit/`, `src/interceptors/` - audit log middleware or interceptors.
- `prisma/schema.prisma` + `prisma/migrations/`, `src/migrations/` (TypeORM).
- `src/logger.(ts|js)` - pino/winston transports; `src/health/` (terminus).
- `.github/workflows/`, `.gitlab-ci.yml`; `.env.example`; `.npmrc`.

## Dangerous / interesting APIs and patterns

- CC6.1 auth: `passport.use(new JwtStrategy|OIDCStrategy|SamlStrategy)`,
  `express-jwt` (`algorithms: ['RS256']`), `openid-client` `Issuer.discover`,
  `@nestjs/passport`. Bad: `jwt.decode` used instead of `jwt.verify`,
  `algorithms` missing, `ignoreExpiration: true`.
- MFA: `otplib`, `speakeasy`, WebAuthn (`@simplewebauthn/server`), or an IdP `amr`
  claim check; otherwise organisational.
- CC6.1 rbac: Nest `@Roles()` + `RolesGuard`, `casl` abilities, `requireRole('admin')`
  middleware. Bad: routers mounted before the auth middleware; role taken from the body.
- Brute force: `express-rate-limit` / `rate-limiter-flexible` on login routes.
- CC6.1 admin-log / PI1.3: audit middleware writing `{ actor, action, target, at }`,
  Prisma middleware/extension (`$extends` query hooks), TypeORM `EntitySubscriberInterface`.
- CC6.3 deprovisioning: `isActive: false`, refresh-token table deleted/revoked,
  `req.session.destroy()`, token version counter on the user.
- CC7.1: `npm audit --audit-level=high`, `npm audit signatures`, Dependabot,
  Snyk, `eslint-plugin-security`, Semgrep `p/javascript`.
- CC7.2: pino/winston transports to a collector (`pino-elasticsearch`,
  `winston-cloudwatch`, OTLP) vs `console.log` only; login failure logged.
- A1.1: `@nestjs/terminus` `HealthCheckService`, `/healthz` route with DB ping.
- C1: `dotenv` (local only) vs `@aws-sdk/client-secrets-manager`,
  `@azure/keyvault-secrets`, `node-vault`; field encryption via `crypto.createCipheriv`
  (`aes-256-gcm`) or `prisma-field-encryption`.
- PI1: `zod`, `joi`, `class-validator` + `ValidationPipe({ whitelist: true })`,
  `express-validator`; `Idempotency-Key` header stored with a unique index;
  `@@unique` in Prisma, `@Unique` in TypeORM.

## What "good" looks like

```ts
app.use(helmet());
app.use('/auth/login', rateLimit({ windowMs: 15 * 60_000, limit: 10 }));
app.use('/api', expressjwt({ secret: jwksRsa.expressJwtSecret({ jwksUri }), algorithms: ['RS256'] }));
app.use('/api/admin', requireRole('admin'), audit('admin'));

// NestJS
@UseGuards(AuthGuard('jwt'), RolesGuard) @Roles('admin')
@Post('users/:id/deactivate') deactivate(@Param('id') id: string, @Req() req) { return this.users.deactivate(id, req.user.sub); }
```

Pipeline shape: `npm ci` -> `npm test` -> `npm audit --audit-level=high` -> build ->
`npx prisma migrate deploy` (or `typeorm migration:run`) inside the deploy job for a
protected environment; never `prisma db push` against production.

## Manual trace checklist

1. Middleware order in `app.ts`: auth before routers, error handler last.
2. Admin/role-change/export routes: role guard server-side and an audit write.
3. User deactivation revokes refresh tokens and sessions immediately.
4. CI: audit/scan step fails the job; tests are a required check; deploy gated.
5. Data store backups (RDS/Atlas/Cloud SQL automated backups in IaC, `pg_dump` or
   `mongodump` jobs) and a dated restore-test record.
6. Secrets: `.env` gitignored, production values from a secret manager or CI secrets.

## Stack-specific false positives

- `dotenv` in `src/config.ts` when production injects real env vars (check deploy).
- `console.log` in `scripts/`, `seed.ts`, tests and CLI tools.
- `npm audit` findings limited to `devDependencies` of a build tool (lower priority).
- Unauthenticated `/health`, `/metrics` behind an internal-only ingress.

## Tooling

```bash
npm audit --audit-level=high --omit=dev
npm audit signatures
npx semgrep --config p/javascript --config p/nodejs src
grep -rnE "passport\.use|expressjwt|AuthGuard|RolesGuard|@Roles\(|rateLimit\(" src
grep -rnE "migrate deploy|migration:run|db push" .github package.json
```

## References

- Express security best practices; NestJS authentication/authorization/terminus docs.
- Prisma migrate in CI; OWASP Node.js cheat sheet.
- SOC2-CC6.1, CC6.3, CC7.1, CC7.2, CC8.1, A1.2, C1.1, PI1.1, PI1.3; CWE-284, CWE-307.
