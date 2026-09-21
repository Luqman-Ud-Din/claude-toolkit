# pino and winston reference for audit-logging-and-observability

## pino

```ts
import pino from 'pino';
export const logger = pino({
  level: process.env.LOG_LEVEL ?? 'info',
  base: { service: 'orders-api', env: process.env.NODE_ENV },
  redact: {
    paths: ['req.headers.authorization', 'req.headers.cookie', 'password', '*.password', '*.token',
            '*.refreshToken', 'body.password', 'user.email'],
    censor: '[REDACTED]',          // or remove: true to drop the key entirely
  },
  serializers: { err: pino.stdSerializers.err },
});
```
- `redact.paths` use fast-redact syntax: `a.b`, `*.password` (one level), `a[*].b`.
  Wildcards do not recurse: `*.password` misses `body.user.password`. List the real shapes.
- Errors must be passed as `logger.error({ err }, 'msg')`. `logger.error(err.message)`
  loses stack and type; `logger.error('msg', err)` treats `err` as a format argument.
- A custom `serializers.req` that returns `req.body` or the raw `headers` undoes the default serializer's safety.
- Child loggers carry context: `const log = logger.child({ reqId, tenantId })`.
- Transports run in worker threads: `pino.transport({ targets: [{ target: 'pino/file', options: { destination: 1 } }, { target: 'pino-opentelemetry-transport' }] })`.
  `pino-pretty` in production is a smell (slow, not JSON).

### pino-http

```ts
app.use(pinoHttp({
  logger,
  genReqId: (req, res) => {
    const id = req.headers['x-correlation-id'] ?? randomUUID();
    res.setHeader('x-correlation-id', id);
    return id;
  },
  customLogLevel: (_req, res, err) => (err || res.statusCode >= 500 ? 'error' : res.statusCode >= 400 ? 'warn' : 'info'),
  customProps: (req) => ({ userId: req.user?.id }),
  autoLogging: { ignore: (req) => req.url === '/health' },     // no hot-path spam from probes
}));
```
Handlers then use `req.log.info(...)`, which carries `reqId`. A module-level
`logger.info` does **not** carry it unless `AsyncLocalStorage` supplies it.

## winston

```ts
const redact = winston.format((info) => {
  for (const k of ['password', 'token', 'authorization', 'cardNumber']) if (k in info) info[k] = '[REDACTED]';
  return info;
});
export const logger = winston.createLogger({
  level: process.env.LOG_LEVEL ?? 'info',
  format: winston.format.combine(winston.format.errors({ stack: true }), redact(), winston.format.timestamp(), winston.format.json()),
  defaultMeta: { service: 'orders-api' },
  transports: [new winston.transports.Console()],
});
```
- Without `format.errors({ stack: true })` an `Error` passed as meta serialises to `{}`.
- `format.simple()` / `printf` templates in production produce unstructured text.
- A custom format only sees top-level keys unless it walks the object; a nested
  `body.password` survives a shallow redactor.
- `transports.File` without `maxsize`/`maxFiles` (or `winston-daily-rotate-file`
  without `maxFiles: '14d'`) grows without bound.

### express-winston

- `requestWhitelist.push('body')` logs request bodies; the default whitelist does not include `body` - adding it is the leak.
- `bodyBlacklist: ['password', 'token']` is shallow; prefer never whitelisting the body.
- `headerBlacklist: ['authorization', 'cookie']` whenever `headers` is whitelisted.

## Request context with AsyncLocalStorage

```ts
export const als = new AsyncLocalStorage<{ reqId: string }>();
app.use((req, _res, next) => als.run({ reqId: req.id as string }, next));
export const log = () => logger.child({ reqId: als.getStore()?.reqId });
// winston: winston.format((info) => ({ ...info, reqId: als.getStore()?.reqId }))()
```
Libraries: `cls-rtracer`, `express-http-context`, NestJS `nestjs-cls`.

## NestJS

`nestjs-pino`: `LoggerModule.forRoot({ pinoHttp: { genReqId, redact, customLogLevel } })`
and `app.useLogger(app.get(Logger))`; inject `PinoLogger` so every call carries the
request id. The built-in `ConsoleLogger` prints unstructured text unless its `json` option (Nest 11+) is enabled.

## Levels

- `LOG_LEVEL` from the environment with a default of `info`; flag a hard-coded
  `level: 'debug'` or `LOG_LEVEL ?? 'debug'`.
- pino levels: `fatal, error, warn, info, debug, trace`; winston npm levels:
  `error, warn, info, http, verbose, debug, silly`.
- `.catch((err) => logger.debug(err))` is the classic swallowed failure.

## Grep recipes

```bash
grep -rnE '(logger|log|req\.log)\.(info|debug|warn|error)\(.*req\.(body|headers)' src
grep -rnE '(logger|log)\.(info|debug|warn|error)\(`[^`]*\$\{' src                       # template literals
grep -rnE "(logger|log)\.(info|debug|warn|error)\(['\"][^'\"]*['\"]\s*\+" src              # concatenation
grep -rnE 'catch\s*\(\w*\)\s*\{\s*(logger|log)\.(debug|trace)|\.catch\(\s*\(?\w*\)?\s*=>\s*(logger|log)\.debug' src
grep -rnE 'redact|genReqId|AsyncLocalStorage|cls-rtracer|requestWhitelist|format\.errors' src
```
