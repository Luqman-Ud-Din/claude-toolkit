# Node.js / Express reference for audit-technical-debt

## Stack markers

`package.json` with `express`, `@nestjs/core`, `fastify` or `koa`; `engines.node`,
`.nvmrc`, `tsconfig.json`. Variants: plain JS CommonJS (`require`), TypeScript ESM,
NestJS (decorator modules - DI hides references), serverless handlers (`handler.ts`).

## Where the relevant code lives

- Hotspots: `routes/` files with every handler inline, `controllers/`, `services/`,
  `jobs/` / `workers/`, `utils/helpers.js` (the grab-bag that grows forever).
  `complexity.py` names inline route handlers `POST /orders` so they show up in the ranking.
- Suppressions: `// eslint-disable*`, `/* eslint-disable */` at file top, `// @ts-ignore`,
  `// @ts-nocheck`, `/* istanbul ignore next */`, `"rules": {"x": "off"}` in `.eslintrc*`,
  `eslint.config.js` overrides, `"strict": false` (owned by frontend/backend best-practice reviews).
- Currency: `engines.node`, `.nvmrc`, `Dockerfile FROM node:<v>`, CI `node-version:`,
  `express` major, deprecated packages (`request`, `tslint`, `node-sass`, `moment`).

## Dangerous / interesting APIs and patterns

Mirrored in `scripts/patterns/node-express.json`.
- **Deprecated Node APIs** (DEP codes): `new Buffer()` (DEP0005), `url.parse()` (DEP0169),
  `fs.exists()` (DEP0034), `domain` (DEP0032), `crypto.createCipher` (DEP0106, removed in
  22), `util.isArray` and friends (removed in 23).
- **Express 4 -> 5**: `req.param()`, `res.send(status)`, `res.json(status, body)`,
  `res.sendfile`, regex route strings; Express 4 end of life is announced for no earlier
  than 2026-10-01 - check the support page.
- **EOL markers**: Node 16 (2023-09-11), 18 (2025-04-30), 20 (2026-04-30); odd majors end
  after about eight months; `engines: ">=16"` is a floor, not a requirement.
- **Suppressions**: file-level `eslint-disable` with no rule list (blanket), repeated
  `eslint-disable-next-line @typescript-eslint/no-explicit-any`, `@ts-ignore` without a
  reason (prefer `@ts-expect-error -- reason`), `security/detect-*` rules disabled.
- **Inconsistent patterns**: CommonJS beside ESM; callbacks + `.then` chains + `await`
  in one module; axios + fetch + got; Prisma + TypeORM + raw `pg`; `console.log` beside
  winston/pino.
- **Complexity shapes**: callback pyramids, 200-line route arrows mixing validation, SQL
  and response shaping, `switch (req.body.type)` dispatchers, middleware with nested
  `if (req.user && req.user.roles && ...)`.

## What "good" looks like

Routers only wire handlers; handlers call services; one HTTP client, one ORM, one
logger; `async`/`await` throughout with a central error middleware; ESLint with
`complexity` and `max-lines-per-function` as warnings in CI; suppressions explained:

```js
// eslint-disable-next-line no-await-in-loop -- sequential by design: API rate limit is 1 req/s
```

## Manual trace checklist

1. Top hotspot route or service: list the branches and the tests that pin them.
2. `engines.node` vs the Docker image vs CI `node-version`: three places, often three
   versions. The oldest one is the effective runtime.
3. Dead-code candidates: search for dynamic loading (`require(path.join(dir, file))`,
   plugin folders, `fs.readdirSync(routesDir)`), `bin` scripts, migration and seed files.
4. File-level `eslint-disable` and `@ts-nocheck`: each marks a file nobody wanted to fix.
5. Mixed families: is there a `lib/http.ts` wrapper most code uses, with stragglers? The
   stragglers are quick wins; two competing wrappers are a long-term item.

## Stack-specific false positives

- NestJS providers and controllers are referenced from `@Module({ providers: [...] })`,
  so they count as used; dynamic modules loaded by string are not.
- Serverless handlers referenced only from `serverless.yml` / `template.yaml`, Express
  routers loaded by directory scan, Knex/Sequelize migrations run by the CLI.
- `await` in a loop, `.then` in a top-level script, and `console.log` in CLI tools are
  usually intentional.

## Tooling

- Complexity: `npx eslint . --rule '{"complexity": ["warn", 15], "max-lines-per-function": ["warn", 80], "max-depth": ["warn", 4]}' -f json -o eslint-debt.json`;
  cognitive complexity with `eslint-plugin-sonarjs` (`sonarjs/cognitive-complexity`).
- Dead code and unused dependencies: `npx knip --reporter json` (preferred; ts-prune is in
  maintenance mode), `npx depcheck --json`.
- Duplicates: `npx jscpd --min-lines 6 --reporters json --output <evidence-dir> src`.
- Currency: `npm outdated --json`, `npx npm-check-updates` (lists only unless `-u`),
  `@typescript-eslint/no-deprecated`, `node --pending-deprecation --trace-deprecation app.js`
  in a test run.
- Never run `npm install` or `ncu -u` in the audited repo; use a scratch copy.

## References

CWE-1121, CWE-1080, CWE-561, CWE-1041, CWE-477, CWE-1104, CWE-546. Node deprecations:
https://nodejs.org/api/deprecations.html ; release schedule: https://github.com/nodejs/Release ;
Express 5 migration: https://expressjs.com/en/guide/migrating-5.html ; knip: https://knip.dev
