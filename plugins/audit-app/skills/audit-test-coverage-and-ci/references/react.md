# React reference for audit-test-coverage-and-ci

## Stack markers

`package.json` with `react`; unit runner Jest (`jest.config.*`, `react-scripts test`) or Vitest
(`vitest.config.*`, `vite.config.* test: {}`); `@testing-library/react` (+ `user-event`,
`jest-dom`); `msw` for API mocking. E2E: Playwright (`playwright.config.*`, `e2e/**`, `tests/**`),
Cypress (`cypress/`). Next.js: `next/jest` preset, Playwright against `next start`. Storybook
interaction tests (`@storybook/test-runner`).

## Where the relevant code lives

`src/**/*.test.tsx|ts`, `src/**/__tests__/**`, `src/setupTests.ts` (jest-dom, msw server),
`src/mocks/handlers.ts` (msw), `jest.config.*` / `vitest.config.*` (`coverageThreshold`,
`coverage.thresholds`), `e2e/**`, `playwright.config.*`, `.github/workflows/*.yml`.
Production units: `src/api/*.ts` / `src/services/*.ts` (fetch wrappers, auth token handling),
`src/hooks/use*.ts`, `src/store/**` (reducers, slices, Zustand stores), `src/utils/{money,price,date}.ts`,
route guards (`RequireAuth`), form schemas (`zod`/`yup`).

## Dangerous / interesting APIs and patterns

- Skipped: `it.skip(`, `test.skip(`, `describe.skip(`, `xit(`, `xtest(`, `xdescribe(`, `it.todo(`,
  `test.fixme(` (Playwright), `test.skip(condition, reason)`. Focused: `it.only(`, `test.only(`,
  `fit(` - Jest/Vitest run only those and report green; guard with
  `eslint-plugin-jest/no-focused-tests` or Vitest `allowOnly: false` (default false in CI mode).
- Snapshot-only suites: `expect(tree).toMatchSnapshot()` as the only assertion - snapshots are
  updated with `-u` without review; `test_inventory.py` marks files whose only assertions are
  snapshots as `snapshot-only`.
- Auth/API untested: the fetch wrapper's 401 -> logout / refresh path, token storage, the
  `RequireAuth` redirect, role-based rendering.
- Network in unit tests: real `fetch`/axios without `msw` or mocks; `msw` `onUnhandledRequest: 'bypass'`.
- Hygiene: `await new Promise(r => setTimeout(r, N))`, `act()` warnings suppressed
  (`console.error = jest.fn()`), `jest.setTimeout(60000)`, `waitFor` with huge timeouts,
  `jest.mock` of the component under test, `Date.now()` without fake timers, random data
  without a seed.
- E2E: Playwright without `storageState` reuse (UI login per test), `page.waitForTimeout(5000)`,
  tests against shared staging data, no test for checkout/login/order flows.
- CI: `npm install` not `npm ci`, `react-scripts test` without `CI=true` (watch mode hangs),
  test step `continue-on-error`, no `eslint`, no `npm audit`/`osv-scanner`, no coverage threshold,
  `actions/*@main`, artifacts not versioned, Next `next build` skipped on PRs (type errors reach main).

## What "good" looks like

```tsx
// src/api/client.test.ts (Vitest + msw)
const server = setupServer(http.get('/api/orders', () => HttpResponse.json(null, { status: 401 })));
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
it('logs out on 401', async () => {
  const logout = vi.fn(); const client = createClient({ onUnauthorized: logout });
  await expect(client.get('/api/orders')).rejects.toThrow();
  expect(logout).toHaveBeenCalled();
});
// src/components/Checkout.test.tsx
it('submits company and branch ids with the order', async () => {
  const user = userEvent.setup(); render(<Checkout />, { wrapper: Providers });
  await user.type(screen.getByLabelText(/quantity/i), '3');
  await user.click(screen.getByRole('button', { name: /confirm/i }));
  expect(await screen.findByRole('status')).toHaveTextContent(/order placed/i);
  expect(lastRequestBody()).toMatchObject({ companyId: 7, branchId: 2, quantity: 3 });
});
```
```ts
// vitest.config.ts
test: { coverage: { provider: 'v8', thresholds: { lines: 70, 'src/api/**': { lines: 90 } } }, allowOnly: false }
```
```yaml
- run: npm ci
- run: npm run lint && npx tsc --noEmit
- run: npx vitest run --coverage
- run: npx playwright install --with-deps && npx playwright test
- run: npm audit --audit-level=high
```

## Manual trace checklist

1. `src/api` / auth hooks: 401 handling, refresh, token storage, `RequireAuth` redirect tests.
2. Money: price/tax/discount utils and reducers - boundary and rounding; form schemas reject
   negative/zero.
3. Data mutation: the main mutation hooks/components assert request payloads (msw) and success/
   error UI; optimistic updates roll back on failure.
4. E2E: login, checkout, one mutation flow; run against a built app with msw or a seeded backend.
5. Ratio of snapshot-only and `.todo` tests; focused tests guarded by lint/`allowOnly`.

## Stack-specific false positives

- `it.todo(` as a planned-test list: Info.
- Snapshot tests for static presentational components alongside behavioural tests elsewhere:
  fine; the finding is snapshot-only coverage of logic.
- `onUnhandledRequest: 'bypass'` in Storybook only: fine.
- Playwright `test.fixme` with a linked issue: Low, list it.

## Tooling

`npx jest --listTests` / `npx vitest list`, `npx vitest run --coverage --coverage.reporter=text-summary`,
`npx playwright test --list`, `npx eslint --rule 'jest/no-focused-tests: error' src`,
`npx stryker run` on `src/utils/money.ts`, `npm audit --json`.

## References

- Testing Library guiding principles: https://testing-library.com/docs/guiding-principles
- msw: https://mswjs.io/docs/
- Vitest coverage thresholds: https://vitest.dev/config/#coverage-thresholds
- Playwright auth state: https://playwright.dev/docs/auth
- CWE-1120, ASVS-1.14.4, ASVS-14.1.x.
