# Flow catalog: critical flows and the rules to verify

Pick every flow the audited app actually has. For each, draw the state and
sequence diagrams first, then walk the rules. "Enforced at" must be a
file:line in the backend; a rule enforced only in the UI counts as violated.
Rules marked (TIME) or (RACE) belong to the sibling skills - note them, hand
them off, and keep the business consequence here.

## 1. Payments (charge, capture, refund, webhook)

Entry points: checkout/pay endpoint, provider webhook, refund endpoint, admin "mark as paid".

| Rule | How to verify |
|---|---|
| Amount charged is computed server-side from persisted line items, never taken from the request | find where the gateway call gets its amount; trace back to source |
| Currency is carried with every amount and never mixed | one currency per order; conversion happens once, at a documented rate, with the rate stored |
| Money uses decimal/integer-minor-units, not float/double | grep hits `MONEY-FLOAT`; check DB column types too |
| Rounding is done once, at the end, with a stated mode (banker's vs half-up) and matches the invoice | look for `Math.Round`, `toFixed`, `setScale`, `quantize`; per-line vs total rounding must agree |
| Refund total never exceeds captured total; partial refunds are summed | refund handler must read existing refunds |
| Webhook is authenticated (signature) and idempotent by provider event id (RACE) | handler stores event id; replaying the same body is a no-op |
| Payment success only moves the order from an awaiting-payment state | see Orders state machine |
| Failed/declined payment does not leave the order half-paid | error path resets status or uses a transaction |
| Admin "mark as paid" is audited and cannot bypass amount check | who can call it, what it records |

Abuse cases: pay twice, pay less than total (tamper amount), pay with another user's order id, refund more than paid, replay webhook, call "confirm" before "create".

## 2. Orders (create, modify, cancel, fulfil, return)

| Rule | How to verify |
|---|---|
| Status transitions are defined in exactly one place and every handler consults it | find every assignment to the status field; count the places |
| No transition out of a terminal state (Cancelled, Refunded, Completed) except explicit, audited admin actions | diagram it; look for the illegal edge |
| Totals recalculated from line items on every change; stored total is derived, not incrementally mutated | search `Total +=`, `Total -=` |
| Quantity > 0, price >= 0, and both validated server-side per line | DTO validation attributes and service guards |
| Modifying a paid order re-runs pricing and either re-charges or blocks | modify handler must check status |
| Cancel releases reserved stock and voids/refunds payment atomically | one transaction, or a compensating job |
| Customer can only act on own orders; admin actions are logged | ownership filter (authz skill owns the check; here verify the *business* effect) |

Abuse cases: change line items after paying, cancel after shipping, set a negative quantity to get credit, submit an order with zero lines.

## 3. Discounts, coupons, credits

| Rule | How to verify |
|---|---|
| A coupon applies at most once per order and once per customer if single-use | grep hits `DISCOUNT-APPLY`; check for an "applied" flag/table |
| Discount is computed from the current subtotal, not subtracted from a running total | `Total -= discount` in a method that can run twice is a defect |
| Stacking rules are explicit (percent then fixed, or exclusive) | pricing service order of operations |
| Discount never drives total below zero; percent capped at 100 | guard exists |
| Expiry and usage limits enforced server-side (TIME for the expiry zone) | validation reads the coupon row, not the request |
| Store credit debits are transactional with the order (RACE) | credit balance check and debit in one transaction |

Abuse cases: apply the same code twice via two requests or via cart update; edit the cart after the coupon; use an expired code by clock skew; combine two exclusive codes.

## 4. Subscriptions and billing

| Rule | How to verify |
|---|---|
| Plan changes prorate correctly and the proration math is tested | find the proration function; hand the date arithmetic to TIME |
| Renewal cannot run twice for the same period (RACE) | idempotency by (subscription, period) |
| Cancel at period end keeps access until the end; immediate cancel revokes access now | status vs access check in the auth path |
| Trial-to-paid conversion charges once and only after the trial ends (TIME) | scheduler and boundary |
| Downgrade enforces new limits (seats, storage) or blocks | limit check reads the new plan |
| Feature entitlements are read from the subscription, not from a cached role | grep where features are gated |

Abuse cases: cancel and re-subscribe to restart a trial; downgrade while over the new limit; change plan during a pending invoice.

## 5. Inventory and stock

| Rule | How to verify |
|---|---|
| Stock cannot go negative unless backorders are explicitly allowed | decrement guarded by a check in the same transaction (RACE) |
| Reserved vs on-hand vs available are distinct and reconciled | three fields or a ledger; not one number mutated from many places |
| Every stock movement is a ledger row with a reason (sale, purchase, adjustment, transfer, return) | search for direct `Quantity =` writes that bypass the ledger |
| Transfers between branches/warehouses debit and credit atomically | one transaction |
| Unit conversions (pack of 12, kg to g) applied once | conversion factor multiplication sites |
| Cost method (FIFO/average) is applied consistently for COGS | costing function called from every sale path |
| Returns restock only when the item is resellable | return handler branches on condition |

Abuse cases: sell more than available from two carts; adjust stock without a reason; transfer to the same branch; return an item twice.

## 6. Approvals and workflows

| Rule | How to verify |
|---|---|
| Steps cannot be skipped by calling a later endpoint directly | each step verifies the previous step's state |
| Approver cannot be the requester (segregation of duties) | check in approve handler |
| Approval threshold (amount, count) enforced server-side | threshold read from config/DB, compared to the persisted amount |
| Editing a request after approval invalidates the approval | update handler resets status |
| Re-submitting a rejected item starts a new cycle with history retained | history table or status log |

Abuse cases: approve own request; approve twice; edit amount after approval; POST to /finalize on a draft.

## 7. Permissions and admin edge cases

| Rule | How to verify |
|---|---|
| Users cannot change their own role or the role of someone above them | role update handler compares ranks |
| Impersonation: actions are attributed to the admin, limited in scope, and cannot elevate | look for "impersonate", "login as", `sub`/`act` claims |
| Last admin cannot be deleted or demoted | guard in delete/update |
| Deactivated users lose access immediately (tokens invalidated) | auth path reads an `IsActive` flag or token version |
| Tenant/company switch re-checks membership | switch endpoint |

Abuse cases: impersonate a super-admin; demote yourself then re-promote via cached token; delete the only admin.

## 8. Anything else that moves value

Loyalty points, gift cards, wallet top-ups, commissions, quotas, rate plans,
tax calculation (rate lookup by jurisdiction and date - TIME), invoice
numbering (gapless, unique - RACE). Apply the money and state rules above.
