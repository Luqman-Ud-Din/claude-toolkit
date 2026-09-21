# Node / Express reference for audit-privacy-data-flow-mapper

## Stack markers
`package.json` with `express`, `fastify`, `koa`, `@nestjs/core`, `hapi`.
Variants: TypeORM/Prisma/Sequelize/Mongoose models, `winston`/`pino`/`morgan`
logging, `ioredis`/`node-redis`/`cache-manager`, NestJS decorators
(`@Body()`, `@Query()`, `@Cron`), Bull/BullMQ queues (job data is stored in Redis).

## Where the relevant code lives
- Storage: `entities/*.entity.ts` (TypeORM `@Column`), `prisma/schema.prisma`,
  `models/*.js` (Mongoose `new Schema({...})`, Sequelize `define`), SQL
  migrations (`migrations/*.ts|js|sql`, knex), `uploads/` + `multer` destinations,
  Bull queue payloads in Redis.
- Collection: `routes/**`, `controllers/**`, NestJS `@Post()` handlers with
  `@Body() dto`, `req.body`/`req.query`/`req.params`, GraphQL resolvers/`input` types,
  socket.io handlers.
- Processors: `console.*`, `logger.*` (winston/pino), `morgan` format strings,
  `Sentry.setUser`, analytics SDKs (`analytics-node`, `mixpanel`), cache keys,
  Bull job data, CSV/PDF exporters.
- Transmission: `axios`/`fetch`/`got` calls, `nodemailer` transports, `@sendgrid/mail`,
  `twilio`, `@mailchimp/mailchimp_marketing`, `stripe`, webhooks sent out.
- Templates: `views/emails/**` (`.hbs`, `.ejs`, `.pug`, `.mjml`), i18n message files with placeholders.

## Dangerous / interesting APIs and patterns
- `console.log(req.body)` / `logger.info({ body: req.body })` - whole payload.
- `logger.info(\`User ${user.email} logged in\`)`; pino `logger.info({ user })` with the full document.
- `morgan('combined')` - full URL (query strings) and IP in access logs.
- `redis.set(\`session:${email}\`, ...)`, `cache.set(email, profile)`.
- `router.get('/users/:email')`, `req.query.email` on GET.
- `Sentry.setUser({ email, username, ip_address })`, `sendDefaultPii: true`.
- `axios.post('https://api.hubapi.com/...', user)` - whole model object sent.
- Mongoose `toJSON()` without `transform` deleting PII; TypeORM entity returned
  directly with no `@Exclude()` / `class-transformer`.
- `multer` storing uploads under `public/` (web-reachable storage location).
- Bull `queue.add({ email, phone })` - job data persisted in Redis with no TTL.

## What "good" looks like
```ts
logger.info({ userId: user.id }, 'user registered');           // pino: id only
const key = `session:${createHash('sha256').update(email).digest('hex')}`;
app.use(morgan(':method :url :status', { skip: () => false })); // and strip query strings in a custom token
@Exclude() nationalId: string;                                   // class-transformer
```

## Manual trace checklist
1. Logger transports (winston `transports`, pino `destination`, Datadog/Logtail
   tokens): where logs go, and retention if visible.
2. `morgan` format and whether URLs carry PII (`?email=`).
3. Each `axios.create({ baseURL })` / `fetch` to an external host -> vendor and payload.
4. `nodemailer` transport (SMTP host or SES/SendGrid), templates and merge fields.
5. Bull/BullMQ job data and Redis TTLs (`removeOnComplete`).
6. Mongoose/TypeORM serialisation of entities in responses (`toJSON`, `@Exclude`).
7. Uploads: `multer` destination and whether it is under a static route.

## Stack-specific false positives
- `console.log` in `scripts/` / `seed.js` with `example.com` addresses.
- `logger.info({ email: mask(email) })` - masked; confirm the mask function.
- `email` in `nodemailer` `from` config - sender, not subject.
- `req.user.id` logged - pseudonymous id, good pattern.

## Tooling
- `python scripts/pii_scan.py <repo> ...`; `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/node-express.json`
- `npx prisma format` / read `schema.prisma` for columns; `grep -rn "@Column\|new Schema" src`
- `npm ls --depth=0 | grep -i "sendgrid\|twilio\|mailchimp\|segment\|mixpanel\|sentry\|hubspot"`
- `grep -rn "https\?://" src --include=*.ts --include=*.js | grep -v localhost` for outbound hosts

## References
GDPR Art.5(1)(c), 5(1)(e), 28, 30, 32; CWE-532, CWE-359, CWE-598, CWE-922
(insecure storage); ASVS 8.3, 7.1.1; pino/winston redaction docs (`redact` paths),
Sentry Node `sendDefaultPii`.
