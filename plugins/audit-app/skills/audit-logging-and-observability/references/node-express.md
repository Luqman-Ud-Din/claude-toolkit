# Node / Express reference for audit-logging-and-observability

## Stack markers

`package.json` with `express`, `fastify`, `koa`, `@nestjs/core` or `hapi`.
Loggers: `pino` / `pino-http` / `nestjs-pino`, `winston` / `express-winston`,
`bunyan`, `morgan` (access log only), NestJS built-in `Logger`. Telemetry:
`@opentelemetry/sdk-node`, `@opentelemetry/auto-instrumentations-node`,
`dd-trace`, `newrelic`, `elastic-apm-node`, `prom-client`.

## Where the relevant code lives

- `src/logger.(ts|js)`, `src/lib/log*`, `src/config/logger*` - logger construction
  (level, format, transports, redaction).
- `src/app.(ts|js)` / `server.(ts|js)` / `main.ts` - middleware order: request id,
  access log, body parser, routes, error handler (Express error middleware has
  four arguments and must be last).
- `src/middleware/`, `src/interceptors/`, `src/filters/` (Nest) - correlation id,
  exception filters.
- `src/instrumentation.(ts|js)` / `tracing.js` - must be loaded before anything
  else (`node --require ./tracing.js` or `--import`) or auto-instrumentation misses modules.
- Route handlers / services - the log calls.

## Dangerous / interesting APIs and patterns

- `logger.info({ body: req.body })`, `logger.info('login', req.body)`,
  `console.log(req.body)`, `JSON.stringify(req.body)` in a log call.
- `express-winston` with `requestWhitelist.push('body')` or `bodyBlacklist` empty;
  `pino-http` with a custom `serializers.req` that returns `req.body` or the raw
  `headers` (carries `authorization` and `cookie`).
- `morgan('combined')` alone - access log with no correlation id, no user, not JSON.
- `catch (err) { logger.debug(...) }`, `logger.info(err.message)`,
  `.catch(() => {})`, `.catch(console.log)`; `logger.error(err.message)` without the
  error object (pino needs `logger.error({ err }, 'msg')` to serialize the stack).
- Template-literal messages: ``logger.info(`user ${user.email} logged in`)``.
- `console.log` / `console.error` as the only logger in server code.
- No `AsyncLocalStorage`, `cls-rtracer`, `express-request-id`, `pino-http genReqId`
  or Nest `ClsModule` - no way to attach a request id to deep log calls.
- `level: 'debug'` hard-coded, or `LOG_LEVEL` defaulting to `debug`.

## What "good" looks like

```ts
// logger.ts
export const logger = pino({
  level: process.env.LOG_LEVEL ?? 'info',
  redact: { paths: ['req.headers.authorization', 'req.headers.cookie', '*.password', '*.token', '*.refreshToken', '*.cardNumber'], censor: '[REDACTED]' },
});

// app.ts - first middleware
app.use(pinoHttp({
  logger,
  genReqId: (req, res) => { const id = req.headers['x-correlation-id'] ?? randomUUID(); res.setHeader('x-correlation-id', id); return id; },
  customLogLevel: (_req, res, err) => (err || res.statusCode >= 500 ? 'error' : res.statusCode >= 400 ? 'warn' : 'info'),
}));

// error middleware - last
app.use((err, req, res, _next) => { req.log.error({ err }, 'unhandled error'); res.status(500).json({ correlationId: req.id }); });
```

winston equivalent: `format.combine(format.timestamp(), redactFormat(), format.json())`
with a custom `format((info) => ...)` that deletes sensitive keys, plus
`AsyncLocalStorage` to inject the request id into every entry.

Security events: `logger.warn({ event: 'auth.login_failed', userId, ip: req.ip, reqId: req.id })`
- an `event` field makes alerting on it a one-line query.

## Manual trace checklist

1. `app.ts` order: request-id middleware before the access logger and before routes;
   error middleware last; `process.on('unhandledRejection'|'uncaughtException')` logs at error.
2. The login/register/reset-password handlers: what object reaches the logger?
3. Every `catch` and `.catch(` in services touching payments, stock, auth.
4. Outbound calls (`axios`, `fetch`, `got`): is `x-correlation-id` / `traceparent`
   forwarded (interceptor or OTel `http`/`undici` instrumentation)?
5. Queue consumers and cron jobs: id created per message/run and logged.
6. Transports: stdout JSON for a collector, or a local file that dies with the pod?

## Stack-specific false positives

- `console.log` in `scripts/`, `seed.ts`, `*.spec.ts`, CLI tools.
- `password` inside a message constant (`'password reset requested'`) with no value.
- `req.body` logged in a route where the body schema is proven non-sensitive
  (a webhook signature id); confirm the schema.
- `logger.debug` in a catch that immediately rethrows - the caller logs it.

## Tooling

```bash
npm ls pino winston bunyan morgan @opentelemetry/sdk-node prom-client
grep -rnE "(logger|log|console)\.(info|debug|warn|error|log|trace)\(" src --include=*.ts --include=*.js
grep -rnE "req\.body|req\.headers" src | grep -iE "log|console"
```
ESLint `no-console` (server code), `eslint-plugin-security`; Semgrep rule
`javascript.express.security.audit.express-check-*` and custom rules for
`logger.*(req.body)`.

## References

- pino: `redact`, serializers, `pino-http`; winston formats; Node `AsyncLocalStorage`.
- OpenTelemetry JS: `@opentelemetry/sdk-node`, auto-instrumentations, W3C propagator.
- CWE-532, CWE-117, CWE-778; ASVS 7.1-7.4; OWASP Logging Cheat Sheet; OWASP A09:2021.
