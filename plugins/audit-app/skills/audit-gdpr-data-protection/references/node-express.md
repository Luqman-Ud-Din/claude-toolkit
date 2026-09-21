# Node / Express reference for audit-gdpr-data-protection

## Stack markers
`package.json` with `express`/`fastify`/`koa`/`@nestjs/core`; TypeORM/Prisma/
Sequelize/Mongoose; `winston`/`pino`; `node-cron`/Bull/Agenda; `@segment/analytics-node`,
`@sentry/node`. Variants: NestJS decorators (`@Delete()`, `@Cron()`), Prisma
`schema.prisma` as the model source.

## Where the relevant code lives
- Consent: entity/schema fields (`marketingConsent: boolean`, Prisma `Boolean`), signup handlers, DTO validators (`class-validator`).
- Rights endpoints: `router.delete('/users/:id')`, `@Delete('me')`, `export`/`download` routes, `anonymize*` services.
- Retention: `cron.schedule(...)`, `new CronJob(...)`, `@Cron(...)`, Bull repeatable jobs, `agenda.define`.
- Minimisation: `logger.*`/`console.*`, `morgan` format, `Sentry.setUser`, `analytics.identify({ traits })`, `req.query.email`.
- Encryption: `helmet()`/`hsts`, `express-sslify`, DB `ssl: { rejectUnauthorized: true }` vs `ssl: false`, Prisma `sslmode`, field encryption (`typeorm-encrypted`, `mongoose-field-encryption`), KMS.
- Audit: TypeORM `EntitySubscriber`, Mongoose plugins (`mongoose-history`), `AuditLog` models.
- Breach signals: failed-login counters (`express-rate-limit`, `rate-limiter-flexible`), security-event logger, log shipping transports (Datadog, Logtail), alert webhooks.

## Dangerous / interesting APIs and patterns
- `marketingConsent: boolean` with no `consentGivenAt`/`consentVersion`.
- `@DeleteDateColumn` / `paranoid: true` soft delete with no purge.
- `logger.info(\`Created user ${user.email}\`)`, `logger.info({ body: req.body })`.
- `analytics.identify({ userId, traits: { email, firstName } })` - Segment gets contact data; is it consent-gated?
- `Sentry.init({ sendDefaultPii: true })`.
- `router.delete('/sessions/:token')` is logout - not erasure; `router.delete('/users/:id')` is.
- `ssl: false` / `rejectUnauthorized: false` on the DB connection.
- Erasure deleting the row but not: Redis sessions, Bull job data, S3 uploads, search index, Segment/Mailchimp records.

## What "good" looks like
```ts
@Entity() class Consent { userId: string; purpose: string; policyVersion: string; givenAt: Date; withdrawnAt?: Date; source: string; }
router.delete('/users/me', auth, async (req, res) => { await erasure.anonymise(req.user.id); res.status(202).end(); });
router.get('/users/me/export', auth, async (req, res) => res.json(await exporter.forUser(req.user.id)));
cron.schedule('0 3 * * *', () => retention.purgeInactive({ olderThanDays: 730 }));
logger.info({ userId: user.id }, 'user registered');
analytics.identify({ userId: user.id });          // no traits unless consented
ssl: { rejectUnauthorized: true }
```

## Manual trace checklist
1. Erasure: from the DELETE handler, follow the service: repository delete/anonymise,
   cascade relations, file storage, Redis keys, queue jobs, vendor delete APIs (Segment
   `/regulations`, Mailchimp archive, Sentry user scrub).
2. Consent: the boolean's writers and readers; whether `analytics.identify` /
   marketing sends check it.
3. Retention: every cron/queue job vs data category; winston `maxFiles`; Redis TTLs.
4. Logging: transports (file/Datadog) and whether PII lines reach them.
5. Transport: `helmet`/HSTS at the app or the reverse proxy; DB `ssl` config.

## Stack-specific false positives
- `export default router` / `export const` are JS module keywords, not export endpoints (the script excludes them).
- `router.delete` on sessions, carts, uploads is not erasure.
- `ssl: false` when the DB is on a private network with TLS terminated elsewhere: Low, needs infra evidence.
- `logger.debug` stripped in production builds: still list, rate Low.

## Tooling
- `python scripts/gdpr_check.py <repo> --out ... --md ...`
- `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/node-express.json`
- `grep -rn "router\.delete\|@Delete(\|anonymi" src`
- `grep -rn "cron\.\|@Cron\|CronJob\|repeat:" src`

## References
GDPR Art.5, 7, 12-22, 25, 28, 30, 32-35; CWE-532, CWE-359, CWE-312, CWE-319; ASVS 8.3, 7.1, 9.1;
Segment "User deletion and suppression" API; Sentry `sendDefaultPii`; TypeORM soft-delete docs.
