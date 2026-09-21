# Critical paths: how to derive them and map tests onto them

A global coverage number hides the only question that matters before
production: are the paths where a bug costs money, leaks data, or locks users
out actually tested? This file defines those paths, how to find their units in
any stack, and how to rate each one covered / partial / none.

## The four default critical paths

| Path | What breaks in production | Unit name signals (class, file, folder) | Typical routes / jobs |
|---|---|---|---|
| Authentication and authorization | Users locked out, or let in as someone else; roles bypassed | `Auth`, `Login`, `Token`, `Jwt`, `Password`, `Session`, `Identity`, `Role`, `Permission`, `Claim`, `Otp`, `Mfa`, `Account`; guards and interceptors | `/login`, `/token/refresh`, `/forgot-password`, `/register`, role-check middleware |
| Payment and money | Over- or under-charging, double refunds, wrong tax, broken invoices | `Payment`, `Charge`, `Refund`, `Invoice`, `Billing`, `Checkout`, `Price`, `Discount`, `Tax`, `Vat`, `Ledger`, `Voucher`, `Subscription`, tax-authority integrations (FBR, ZATCA) | `/checkout`, `/payments/*`, webhooks from the payment provider, invoice generation jobs |
| Data mutation | Lost or corrupted records, stock going negative, wrong totals | `Order`, `Stock`, `Inventory`, `Product`, `Purchase`, `Sale`, `Manufacture`, `Import`, `Bulk`, `Sync`, repositories/managers with Create/Update/Delete, background jobs | POST/PUT/PATCH/DELETE routes, CSV imports, scheduled jobs, queue consumers |
| Tenant isolation (multi-tenant apps only) | One customer sees or changes another customer's data | `Tenant`, `Company`, `Organization`, `Workspace`, `Branch`, connection-string/DB-name resolvers, global query filters | every tenant-scoped read and write |

`scripts/test_inventory.py` assigns these categories from name tokens (unit
name first, then path). Treat its categories as a first draft: rename or add
paths the user names (for example "stock valuation" or "FBR invoice submission"),
and state in the report which list you used.

## Deriving the list for a specific repo

1. Ask the user if they have a list of critical flows; use it verbatim if so.
2. Otherwise start from the four defaults and confirm each against the code:
   open the route table (controllers, routers, urls.py) and mark endpoints that
   move money, change auth state, or write core entities.
3. Add background jobs and webhook handlers: they run without a user watching and
   are the least likely to be tested.
4. Drop a path only with a reason (for example "no payment handling; the app
   records sales but never charges"), and write that reason in the report.

## Mapping tests to units

- **By name:** a test file that mentions the unit's class/function name
  (`PaymentService`, `useCheckout`, `charge_order`). This is what the script does.
- **By route:** API/integration tests that call the unit's route
  (`client.PostAsync("/api/payments/charge")`, `request(app).post('/payments')`,
  `cy.visit('/checkout')`). Grep the test tree for the route strings when the
  name search finds nothing.
- **By behaviour:** open the test and confirm it asserts the risky case, not only
  that the object constructs. A `should create` stub or a snapshot-only test does
  not count.
- **Skipped tests do not count.** A unit whose only test is skipped is `none`.

## Rating each path

| Status | Rule |
|---|---|
| covered | Every unit on the path is referenced by a running test; the tests assert the failure cases below; at least one integration or e2e test exercises the path end to end (for data mutation: against a real database engine) |
| partial | Some units tested, or only happy-path unit tests, or integration tests only against an in-memory substitute, or relevant tests are skipped |
| none | No running test references any unit on the path |

Failure cases a path needs before it can be "covered":

- **Auth:** wrong password and unknown user return 401; expired and tampered
  tokens are rejected; a lower role gets 403 on an admin action; refresh cannot
  be replayed; public endpoints list is exact.
- **Payment:** boundary amounts (0, negative, max), rounding at the currency's
  minor unit, discount above 100% rejected, refund cannot exceed the charge,
  gateway failure and timeout leave no half-written state, webhook replay is
  idempotent.
- **Data mutation:** validation rejects bad input; concurrent updates handled
  (optimistic concurrency); soft-delete respected in reads; totals recomputed;
  the write is rolled back when a later step fails.
- **Tenant isolation:** a request authenticated for tenant A cannot read or
  update tenant B's record by id; list endpoints filter by tenant (and branch).

## Severity for coverage gaps

| Gap | Default | Raise to | Lower to |
|---|---|---|---|
| Payment/money path `none` | High | Critical when the code charges cards or submits tax invoices automatically | Medium when amounts are only displayed, never charged |
| Auth path `none` | High | Critical for custom token/password code (not a framework default) | Medium when auth is entirely delegated to a hosted IdP and only configuration exists |
| Data mutation path `none` | Medium | High for stock, ledger, or anything reconciled financially | Low for admin-only reference data |
| Tenant isolation `none` in a multi-tenant app | High | Critical when isolation depends on per-query filters written by hand | Medium when the database enforces row-level security |
| Any path `partial` | one level below the `none` rating | - | Info when the missing piece is only e2e |

## Report row example

| Critical path | Units | Unit tests | Integration (real DB) | E2E | Status |
|---|---|---|---|---|---|
| Payment / money | PaymentService, PaymentsController | none | none | none | none |
| Authentication | AuthController, TokenService | AuthControllerTests.cs (401 cases) | none | none | partial |
| Data mutation | OrderService | OrderServiceTests.cs (1 of 2 skipped) | none | none | partial |
