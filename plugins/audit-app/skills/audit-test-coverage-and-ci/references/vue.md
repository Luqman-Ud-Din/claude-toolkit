# Vue reference for audit-test-coverage-and-ci

## Stack markers

`package.json` with `vue`; unit runner Vitest (`vitest.config.*`, Vite `test: {}`) or Jest
(`@vue/vue3-jest`, legacy); `@vue/test-utils` (`mount`, `shallowMount`), `@testing-library/vue`;
`@pinia/testing` (`createTestingPinia`); `msw`. E2E: Cypress (`cypress/`, also component
testing), Playwright (`e2e/**`), Nightwatch (`create-vue` option). Nuxt: `@nuxt/test-utils`
(`mountSuspended`, `setup({ server: true })`).

## Where the relevant code lives

`src/**/*.spec.ts`, `src/**/*.test.ts`, `src/**/__tests__/**`, `tests/unit/**`, `tests/e2e/**`,
`vitest.config.*` (`coverage.thresholds`), `cypress.config.*`, `playwright.config.*`,
`.github/workflows/*.yml`, `.gitlab-ci.yml`. Production units: `src/api/*.ts` / `src/services/*.ts`
(HTTP wrapper, auth), `src/stores/*.ts` (Pinia - business state), `src/composables/use*.ts`,
`src/router/guards.ts` (`beforeEach` auth), `src/utils/{money,price,date}.ts`, form schemas
(`vee-validate` + `zod`/`yup`).

## Dangerous / interesting APIs and patterns

- Skipped: `it.skip(`, `test.skip(`, `describe.skip(`, `xit(`, `xdescribe(`, `it.todo(`,
  `test.fixme(` (Playwright), `it.skip` in Cypress, `this.skip()`. Focused: `it.only(`,
  `describe.only(` - Vitest `allowOnly` is false in CI (`--run` with `CI=true`) but Jest is not.
- Snapshot-only suites (`toMatchSnapshot()` as the only assertion) on components with logic.
- `shallowMount` everywhere: child interactions never exercised; stores stubbed with
  `createTestingPinia({ stubActions: true })` in tests that are supposed to test the actions.
- Auth/API untested: HTTP wrapper 401 -> logout/refresh, token storage, router guard redirect
  (`router.beforeEach`), role-based rendering.
- Network in unit tests: real `fetch`/axios without `msw`/`vi.mock`; Nuxt `useFetch` without
  `registerEndpoint`.
- Hygiene: `await new Promise(r => setTimeout(r, N))` instead of `flushPromises()`/`nextTick`,
  `vi.useFakeTimers` missing for debounce tests, `vi.mock` of the component under test,
  `Date.now()` in assertions, global `config.global.mocks` hiding missing providers.
- E2E: UI login per test instead of `cy.session` / Playwright `storageState`, `cy.wait(5000)`,
  shared staging data, no e2e for login/checkout/order entry.
- CI: `npm install` not `npm ci`, missing `vitest run` (watch mode hangs), `continue-on-error`,
  no `eslint`/`vue-tsc --noEmit`, no `npm audit`, no coverage threshold, unpinned actions,
  Nuxt `nuxi build` skipped on PRs.

## What "good" looks like

```ts
// src/api/client.spec.ts (Vitest + msw)
const server = setupServer(http.get('/api/orders', () => HttpResponse.json(null, { status: 401 })));
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
it('logs out on 401', async () => {
  const auth = useAuthStore(createTestingPinia({ stubActions: false }));
  await expect(api.get('/api/orders')).rejects.toThrow();
  expect(auth.isLoggedIn).toBe(false);
});
// src/views/Checkout.spec.ts
it('submits company and branch ids', async () => {
  const w = mount(Checkout, { global: { plugins: [createTestingPinia({ stubActions: false })] } });
  await w.get('input[name=quantity]').setValue('3');
  await w.get('button[type=submit]').trigger('click'); await flushPromises();
  expect(lastRequestBody()).toMatchObject({ companyId: 7, branchId: 2, quantity: 3 });
});
```
```ts
// vitest.config.ts
test: { environment: 'jsdom', coverage: { thresholds: { lines: 70, 'src/api/**': { lines: 90 } } } }
```
```yaml
- run: npm ci
- run: npm run lint && npx vue-tsc --noEmit
- run: npx vitest run --coverage
- run: npx playwright install --with-deps && npx playwright test
- run: npm audit --audit-level=high
```

## Manual trace checklist

1. `src/api` and the auth store/guard: 401 handling, refresh, token storage, guard redirect.
2. Money: price/tax/discount utils and store getters - boundary and rounding; schemas reject
   negative/zero.
3. Data mutation: main store actions and views assert request payloads (msw) and rollback on
   failure.
4. E2E: login, checkout, one mutation flow against a built app with msw or a seeded backend.
5. Ratio of snapshot-only / `shallowMount`-only / `.todo` tests; focused tests guarded.

## Stack-specific false positives

- `it.todo(` as a planned list: Info.
- `shallowMount` for pure presentational components: fine.
- `createTestingPinia({ stubActions: true })` in *component* tests that assert an action was
  called (the action itself tested in the store spec): fine.
- Playwright `test.fixme` with a linked issue: Low, list it.

## Tooling

`npx vitest list`, `npx vitest run --coverage --coverage.reporter=text-summary`,
`npx playwright test --list`, `npx cypress run --component`, `npx eslint --rule 'vitest/no-focused-tests: error' src`,
`npm audit --json`, `npx stryker run` on `src/utils/money.ts`.

## References

- Vue Test Utils: https://test-utils.vuejs.org/guide/
- Pinia testing: https://pinia.vuejs.org/cookbook/testing.html
- Nuxt test utils: https://nuxt.com/docs/getting-started/testing
- Vitest coverage thresholds: https://vitest.dev/config/#coverage-thresholds
- CWE-1120, ASVS-1.14.4, ASVS-14.1.x.
