# Node / Express reference for audit-test-coverage-and-ci

## Stack markers

`package.json` with `express`/`fastify`/`@nestjs/core`; test runners `jest`, `vitest`, `mocha`,
`node:test` (`node --test`), `ava`, `tap`. Integration: `supertest` (in-process HTTP),
`@testcontainers/postgresql` / `testcontainers`, `pg-mem` / `mongodb-memory-server` /
`sqlite ':memory:'` (substitutes). E2E: Playwright, Cypress, `newman` (Postman). NestJS:
`@nestjs/testing` `Test.createTestingModule`.

## Where the relevant code lives

`test/**`, `tests/**`, `__tests__/**`, `*.spec.ts`, `*.test.ts`, `e2e/**`, `test/jest-e2e.json`
(Nest), `jest.config.*` / `vitest.config.*` (`coverageThreshold`, `testPathIgnorePatterns`),
`.mocharc.*`, `.nycrc` / `c8` config, `package.json` `scripts.test`, `.github/workflows/*.yml`,
`.gitlab-ci.yml`, `Jenkinsfile`. Production units: `*.controller.ts`, `*.service.ts`,
`routes/*.ts`, `controllers/*.js`, `handlers/`, `middleware/auth*.ts`, `jobs/`, `*.repository.ts`.

## Dangerous / interesting APIs and patterns

- Skipped: `it.skip(`, `test.skip(`, `describe.skip(`, `xit(`, `xdescribe(`, `xtest(`,
  `it.todo(`, `test.fixme(` (Playwright), `this.skip()` (mocha), `it.skip.each`, `{ skip: true }`
  (`node:test`). Focused: `it.only(`, `fit(`, `fdescribe(`, `test.only(` - in CI a focused test
  silently skips everything else; jest `--ci` does not fail on `.only` unless
  `eslint-plugin-jest/no-focused-tests` is enforced.
- Substitutes: `mongodb-memory-server`, `pg-mem`, `sqlite3 ':memory:'`, `knex` with sqlite in
  test config, `mock-knex`, Prisma with `DATABASE_URL=file:` in tests when prod is Postgres.
- Tests hitting shared infrastructure: `DATABASE_URL` pointing at a hostname in `.env.test`,
  `process.env.NODE_ENV !== 'test'` guards missing on destructive setup (`db.dropDatabase()`).
- Hygiene: `await new Promise(r => setTimeout(r, N))`, `jest.setTimeout(60000)`, `--forceExit`,
  `--detectOpenHandles` needed (leaks), `jest.mock` of the module under test, shared mutable
  fixtures across files, `Date.now()` in assertions without fake timers, `Math.random()` data.
- Auth: no test sends a request without a token or with another user's id and asserts 401/403/404;
  `authMiddleware` mocked to always pass in integration tests.
- CI: `npm install` instead of `npm ci` (non-reproducible), no lockfile committed,
  `"test": "echo \"Error: no test specified\" && exit 1"` (the npm default - no tests at all),
  test step with `continue-on-error: true` / `|| true`, `--passWithNoTests` hiding an empty
  suite, no `npm audit --audit-level=high` / `snyk` / `osv-scanner`, no `eslint` step,
  `actions/checkout@main` unpinned; artifacts without version (`npm version`, `semantic-release`)
  or provenance (`npm publish --provenance`, `cosign` for images).

## What "good" looks like

```ts
// test/orders.e2e-spec.ts (Nest + supertest + Testcontainers)
const pg = await new PostgreSqlContainer('postgres:16-alpine').start();
process.env.DATABASE_URL = pg.getConnectionUri();
const app = (await Test.createTestingModule({ imports: [AppModule] }).compile()).createNestApplication();
await app.init(); await runMigrations();
it('customer cannot read another tenant order', async () => {
  await request(app.getHttpServer()).get('/api/orders/123').set('Authorization', `Bearer ${tokenFor('bob', 'tenantB')}`).expect(404);
});
```
```json
// jest.config.json
{ "collectCoverageFrom": ["src/**/*.ts", "!src/**/*.module.ts"],
  "coverageThreshold": { "global": { "lines": 70 }, "src/payments/": { "lines": 90, "branches": 85 } } }
```
```yaml
- run: npm ci
- run: npm run lint
- run: npm test -- --ci --coverage
- run: npm audit --audit-level=high
```

## Manual trace checklist

1. Auth middleware/guards: tests for missing token, expired token, wrong role, other user's
   resource; guards not mocked away in e2e.
2. Money: pricing/payment services - decimal handling (`decimal.js`/integer cents), rounding,
   idempotency of webhooks (Stripe/PayPal handlers tested with replayed events).
3. Data mutation: DB tests on the production engine (Testcontainers) with migrations applied,
   not `pg-mem`/memory server.
4. Queues/cron (`bull`, `agenda`, `node-cron`): processors tested?
5. CI: `npm ci`, lockfile, test step gated, `.only` guarded, lint + audit present.

## Stack-specific false positives

- `it.todo(` documents planned tests: Info, list them, no severity.
- `mongodb-memory-server` for MongoDB is close to the real engine (same wire protocol, same
  server binary): acceptable, Low at most; `pg-mem` for Postgres is not.
- `--passWithNoTests` on a package in a monorepo that has no tests by design (types-only).
- `test.skip` with a linked issue in the reason string: still listed, Low.

## Tooling

`npx jest --listTests`, `npx jest --ci --coverage --coverageReporters=text-summary`,
`npx vitest run --coverage`, `npx eslint --rule 'jest/no-focused-tests: error' --rule 'jest/no-disabled-tests: warn' src test`,
`npm audit --json`, `npx stryker run` (mutation) on `src/payments`.

## References

- Jest `coverageThreshold`: https://jestjs.io/docs/configuration#coveragethreshold-object
- Testcontainers for Node: https://node.testcontainers.org
- NestJS testing: https://docs.nestjs.com/fundamentals/testing
- npm provenance: https://docs.npmjs.com/generating-provenance-statements
- CWE-1120, ASVS-1.14.4, ASVS-14.1.x, ASVS-14.2.1.
