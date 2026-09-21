# Angular reference for audit-test-coverage-and-ci

## Stack markers

`package.json` with `@angular/core`; unit runner is Karma + Jasmine (`karma.conf.js`,
`ng test`), Jest (`jest-preset-angular`, `jest.config.*`), or Vitest (`@analogjs/vitest-angular`,
Angular 20+ experimental). E2E: Cypress (`cypress.config.*`, `cypress/e2e/**`), Playwright
(`playwright.config.*`, `e2e/**`), legacy Protractor (`protractor.conf.js`, removed - a finding
in itself). Component harnesses: `@angular/cdk/testing`. Karma needs a browser in CI
(`ChromeHeadless`, `--watch=false`).

## Where the relevant code lives

`src/**/*.spec.ts` (CLI generates one per component/service/guard/pipe - many are the empty
"should create" stub), `karma.conf.js` (`coverageReporter.check`), `jest.config.*`
(`coverageThreshold`), `angular.json` `architect.test` (`codeCoverage`, `codeCoverageExclude`),
`cypress/`, `e2e/`, `.github/workflows/*.yml`. Production units: `core/services/*.service.ts`
(api, auth, storage, token), `core/guards/*.guard.ts`, `core/interceptors/*.interceptor.ts`,
`features/**/*.service.ts`, state stores, `shared/validations/*`, pipes with money/date logic.

## Dangerous / interesting APIs and patterns

- Skipped: `xit(`, `xdescribe(`, `xtest(`, `it.skip(`, `describe.skip(`, `test.skip(`,
  `pending('reason')` (Jasmine), `it.todo(`, `test.fixme(` (Playwright), `cy.skip` / `it.skip` in
  Cypress, `this.skip()` (Mocha-style in Cypress). Focused: `fit(`, `fdescribe(`, `it.only(` -
  `ng test` does not fail on focused specs; Karma `jasmine.random` + `failSpecWithNoExpectations`
  off hides empty tests.
- Empty stubs: `it('should create', () => { expect(component).toBeTruthy(); })` as the *only* test
  in a spec - counts as a file but covers nothing. `test_inventory.py` marks specs whose only
  assertion is `toBeTruthy()` as `stub`.
- Auth/token logic untested: `token.interceptor.ts` without a test for 401 -> logout, refresh
  concurrency, or the `PUBLIC_ENDPOINTS` list; `auth.guard.ts` with no redirect test; encrypted
  storage service without round-trip tests.
- HTTP tests hitting the network: `HttpClient` without `provideHttpClientTesting()` /
  `HttpTestingController`; `TestBed` importing the real `AppModule`.
- Hygiene: `setTimeout` in specs instead of `fakeAsync`/`tick`, `fixture.detectChanges()` loops,
  `jasmine.DEFAULT_TIMEOUT_INTERVAL = 60000`, spies on the component under test, shared
  `let` state across `describe`s, `Date` without `jasmine.clock()`.
- E2E: Cypress tests logging in through the UI for every spec (slow, flaky) instead of
  `cy.session`; no e2e for checkout/POS/login at all; `cy.wait(5000)` sleeps; tests against a
  shared staging backend with real data.
- CI: `ng test` without `--watch=false --browsers=ChromeHeadless` (hangs), `ng test` absent,
  `npm install` not `npm ci`, no `ng lint` (or lint configured but package missing - see
  `audit-frontend-best-practices`), no `npm audit`, no `codeCoverage` threshold, unpinned actions.

## What "good" looks like

```ts
// token.interceptor.spec.ts
it('logs out on 401 from a protected endpoint', () => {
  http.get('/api/orders').subscribe({ error: () => {} });
  httpMock.expectOne('/api/orders').flush(null, { status: 401, statusText: 'Unauthorized' });
  expect(auth.logout).toHaveBeenCalled();
});
it('does not attach a token to public endpoints', () => {
  http.post('/accountapi/login', {}).subscribe();
  expect(httpMock.expectOne('/accountapi/login').request.headers.has('Authorization')).toBeFalse();
});
```
```js
// karma.conf.js
coverageReporter: { dir: 'coverage', reporters: [{ type: 'text-summary' }, { type: 'lcov' }],
  check: { global: { statements: 70, branches: 60 }, each: { overrides: { 'src/app/core/**': { statements: 90 } } } } }
```
```yaml
- run: npm ci
- run: npx ng lint
- run: npx ng test --watch=false --browsers=ChromeHeadless --code-coverage
- run: npx cypress run --e2e --browser chrome      # against a locally served build + mocked API
- run: npm audit --audit-level=high
```

## Manual trace checklist

1. `core/`: interceptor, guards, auth/token/storage services - specs assert 401 handling,
   refresh, public-endpoint exclusion, encryption round trip, guard redirect.
2. Money/UI logic: price/tax/discount pipes and calculation services - boundary and rounding.
3. Forms that mutate data (order entry, stock adjustment): validation specs and a submit spec
   with `HttpTestingController` asserting the payload shape (`CompanyId`, `BranchId` present).
4. E2E: login, one full sale/checkout, one stock mutation; run against a served build in CI.
5. Stub ratio: count specs whose only assertion is `toBeTruthy()`; report as `stub`.

## Stack-specific false positives

- `xdescribe` on a spec for a component slated for removal with a TODO/issue link: Low.
- The CLI-generated "should create" stub *plus* real tests in the same file: not a stub.
- Karma coverage `check` absent but Jest `coverageThreshold` present: fine, cite it.
- E2E excluded from PRs but run nightly against staging: partial, cite the job.

## Tooling

`npx ng test --watch=false --browsers=ChromeHeadless --code-coverage` (writes `coverage/`),
`npx jest --listTests`, `npx cypress run --record false`, `npx playwright test --list`,
`grep -rlE "^\s*(xit|xdescribe|fit|fdescribe)\(" src`, `eslint-plugin-jasmine` / `eslint-plugin-jest`
(`no-focused-tests`, `no-disabled-tests`).

## References

- Angular testing guide: https://angular.dev/guide/testing
- `HttpTestingController`: https://angular.dev/guide/http/testing
- Karma coverage check: https://github.com/karma-runner/karma-coverage/blob/master/docs/configuration.md#check
- Cypress `cy.session`: https://docs.cypress.io/api/commands/session
- CWE-1120, ASVS-1.14.4, ASVS-14.1.x.
