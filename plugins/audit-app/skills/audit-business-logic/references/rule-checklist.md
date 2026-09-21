# Cross-flow rule checklist

Walk this list for every traced flow after the flow-specific rules in
`flow-catalog.md`. Record each item as verified / violated / not traceable
with a file:line. The "how tools miss it" column explains why the item is
worth manual time.

## Money

| Check | How tools miss it |
|---|---|
| Amounts are `decimal`, `BigDecimal`, integer minor units, or `Decimal` - never `float`/`double`/JS `number` for stored money | type looks fine; the bug is 0.1+0.2 |
| Rounding happens once, at a documented step, with a stated mode; line-level and total-level rounding agree with the invoice | both roundings are "correct" alone |
| Currency travels with the amount; no arithmetic across currencies without an explicit, stored rate | compiler cannot see currency |
| Tax and discount ordering is explicit (tax on discounted price or on gross?) and matches the legal requirement | both orders compile |
| Totals are derived from line items on read or recomputed on every write; never `Total += x` in a re-runnable method | idempotent-looking code that is not |
| Negative or zero amounts are rejected where they make no sense (price, quantity, payment) | DTO says `int`, not `> 0` |
| Client-supplied totals, prices, discounts are ignored; server recomputes | mass assignment looks like a normal bind |

## State

| Check | How tools miss it |
|---|---|
| The set of allowed transitions is written down once and every status write goes through it | each `status = X` looks valid alone |
| Terminal states have no outgoing edges except explicit admin/compensation with audit | the enum has no "terminal" marker |
| Status and side effects (stock, payment, email) change in one unit of work or via an outbox | partial success is silent |
| Reading a status before acting (`if (order.Status == Pending)`) is done in the same transaction as the write (RACE) | correct in single-user tests |
| Re-entrancy: calling the same handler twice is either rejected or a no-op | tests never call twice |

## Validation vs business rules

| Check | How tools miss it |
|---|---|
| DTO validation covers ranges and relationships (end after start, quantity <= available, discount <= subtotal), not only types and required | `[Required]` is present so scanners are happy |
| Cross-entity rules read persisted data, not request data (coupon valid? plan allows? stock exists?) | request-only validation passes unit tests |
| Enum values from the client are checked against the allowed set for *this* action (a customer cannot set `Status=Shipped`) | enum binding succeeds |
| Frontend validation is duplicated server-side; if only the UI checks it, mark violated | UI has the check so it "works" |

## Admin, impersonation, roles

| Check | How tools miss it |
|---|---|
| Admin override paths (mark paid, force approve, adjust stock) require a reason, are logged, and cannot exceed normal limits by more than policy allows | they are authorised, so authz skill passes them |
| Impersonation records the real actor and blocks role/permission changes and payouts | token is valid |
| Self-service role change is impossible; role rank is compared | endpoint is authorised for "Admin" |
| Deactivation/deletion revokes access now, not at token expiry | flag exists but is never read |

## Replay and skip

| Check | How tools miss it |
|---|---|
| Multi-step flows verify the previous step server-side (create -> pay -> confirm -> ship) | each endpoint is authorised |
| Replaying a success callback / webhook / "confirm" is a no-op (RACE for the key mechanics) | first call works |
| Time-limited actions (cancel within 24h, return within 30 days) use the stored timestamp in the correct zone (TIME) | logic is right in the developer's zone |
| Background jobs that mutate state are idempotent per item and cannot overlap (RACE) | cron runs once in dev |

## Severity guidance for this skill

- Critical: unauthenticated or any-customer path that creates money, credit, or stock out of nothing, or moves an order out of a terminal state at scale.
- High: an authenticated customer can obtain goods/credit they did not pay for, or corrupt ledger/stock integrity; any illegal transition on a money flow.
- Medium: wrong rounding, inconsistent tax ordering, admin-only bypass without audit, rule enforced only in UI with no direct financial gain.
- Low/Info: naming or documentation drift, dead transitions, redundant validation.
