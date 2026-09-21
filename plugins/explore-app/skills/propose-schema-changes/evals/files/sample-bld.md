# Business-Logic Document - Orderly (planned rules for international launch)

Source: hand-edited from the 2026-09-10 generated BLD to describe the rules the product must satisfy for the Germany, UAE and Pakistan launch. Stack: TypeScript / Express / Objection+Knex / PostgreSQL 16.

## Domain overview
Orderly is a B2B wholesale ordering and stock system. Trade customers place orders on credit; staff confirm (credit check + stock reservation), take payment, ship and deliver. For the international launch, each customer belongs to a market with its own currency and tax regime, refunds must be possible after delivery, and orders must be traceable per legal entity.

## Entities
### Customer
- **Purpose:** trade customer on credit
- **Key attributes:** name, email (unique), phone (E.164), address (country-specific structure), country, tax_registration_no, credit_limit with currency
- **Lifecycle / states:** none
- **Defined in:** `src/models/customer.model.ts:3`; table `customers`

### Product
- **Purpose:** sellable item
- **Key attributes:** sku (unique per legal entity), name (translatable), unit_price with currency, stock_on_hand, reorder_level, is_active
- **Lifecycle / states:** active -> inactive
- **Defined in:** `src/models/product.model.ts:3`; table `products`

### Order
- **Purpose:** customer purchase
- **Key attributes:** order_no (gapless per legal entity and year), customer (required), status, subtotal/tax/total with currency, placed_at (with time zone)
- **Lifecycle / states:** draft -> confirmed -> paid -> shipped -> delivered -> refunded; draft|confirmed -> cancelled
- **Defined in:** `src/models/order.model.ts:27`; table `orders`

### OrderLine
- **Purpose:** product at quantity, price captured at order time
- **Key attributes:** product (required, must exist), qty > 0, unit_price, line_total
- **Lifecycle / states:** none
- **Defined in:** `src/models/order.model.ts:7`; table `order_lines`

### Payment
- **Purpose:** payment attempt against an order, any provider
- **Key attributes:** provider, provider_ref, amount with currency, status (pending|succeeded|failed|refunded), paid_at
- **Lifecycle / states:** pending -> succeeded|failed; succeeded -> refunded
- **Defined in:** `src/models/payment.model.ts:4`; table `payments`

### Return
- **Purpose:** goods returned after delivery, leading to a refund and stock re-entry
- **Key attributes:** order, lines returned with qty, reason, received_at, refund payment
- **Lifecycle / states:** requested -> received -> refunded
- **Defined in:** not present in code (planned)

### Shipment
- **Purpose:** carrier consignment
- **Key attributes:** carrier, tracking_no, weight with unit, shipped_at, delivered_at
- **Lifecycle / states:** shipped -> delivered
- **Defined in:** `src/models/shipment.model.ts:3`; table `shipments`

## Workflows
### Place and confirm order
- **Trigger:** `POST /orders`, `POST /orders/:id/confirm`
- **Actors:** staff
- **Steps:** 1. create draft (BR-002); 2. compute tax by market rule (BR-003); 3. credit check (BR-004); 4. reserve stock (BR-005); 5. confirm
- **Entities touched:** read: Customer, Product; written: Order, OrderLine, Product
- **Terminal outcomes:** confirmed; credit limit exceeded; insufficient stock

### Take payment
- **Trigger:** `POST /orders/:id/pay`
- **Actors:** staff
- **Steps:** 1. require confirmed (BR-006); 2. charge in the order's currency (BR-012); 3. record Payment; 4. mark paid
- **Entities touched:** read: Order; written: Payment, Order
- **Terminal outcomes:** paid; payment failed

### Return and refund
- **Trigger:** `POST /orders/:id/returns` (planned)
- **Actors:** staff
- **Steps:** 1. only delivered orders (BR-013); 2. record Return with lines and reason; 3. on receipt, re-enter stock; 4. refund the Payment in the original currency; 5. order -> refunded
- **Entities touched:** read: Order, OrderLine, Payment; written: Return, Product, Payment, Order
- **Terminal outcomes:** refunded; rejected (not delivered)

### Payment reminder job
- **Trigger:** daily at 09:00 in the customer's time zone (BR-009)
- **Actors:** scheduler
- **Steps:** 1. select confirmed orders unpaid for more than 7 days; 2. e-mail in the customer's language
- **Entities touched:** read: Order, Customer; written: none
- **Terminal outcomes:** e-mails sent

## Business rules
- **BR-001** - Customer e-mail addresses are unique (case-insensitive).
  - Entities: Customer
  - Enforced at: `src/services/customer.service.ts:7` (application check only)
- **BR-002** - Volume discounts: 5% at 100+, 10% at 500+; rounding per currency's minor unit.
  - Entities: OrderLine
  - Enforced at: `src/services/pricing.service.ts:5-8` (cents only today)
- **BR-003** - Tax is computed from a rate table by customer market and date, with the rate stored on the order.
  - Entities: Order
  - Enforced at: not enforced (today a hard-coded conditional in `src/controllers/orders.controller.ts:20-24`)
- **BR-004** - Confirmation requires open exposure plus order total within credit limit, compared in the customer's currency.
  - Entities: Order, Customer
  - Enforced at: `src/services/customer.service.ts:27` (no currency awareness)
- **BR-005** - Confirmation reserves stock; stock never goes negative.
  - Entities: OrderLine, Product
  - Enforced at: `src/services/inventory.service.ts:8` (application check only)
- **BR-006** - Order status transitions are limited to the lifecycle above; every transition records who and when.
  - Entities: Order
  - Enforced at: `src/services/order.service.ts:8-15,40` (no who/when recorded)
- **BR-007** - Every order belongs to exactly one customer; an order line always references an existing product.
  - Entities: Order, OrderLine, Customer, Product
  - Enforced at: `migrations/20260103000000_create_orders.js:4` for customer; product reference not enforced
- **BR-008** - Order numbers are unique and gapless per legal entity and calendar year.
  - Entities: Order
  - Enforced at: not enforced (`order.service.ts:33` uses a timestamp)
- **BR-009** - Reminder timing uses the customer's time zone.
  - Entities: Order, Customer
  - Enforced at: not enforced
- **BR-010** - Quantities are whole numbers >= 1.
  - Entities: OrderLine
  - Enforced at: `src/validators/order.schema.ts:5`
- **BR-011** - Postcode and phone formats are validated per customer country.
  - Entities: Customer
  - Enforced at: not enforced (Dutch-only regex today)
- **BR-012** - Every amount carries a currency; payments are charged in the order's currency.
  - Entities: Order, OrderLine, Payment, Customer, Product
  - Enforced at: not enforced (EUR implied; `payment.gateway.ts:9` hard-codes eur)
- **BR-013** - Only delivered orders can be returned; a refund never exceeds the amount paid.
  - Entities: Order, Return, Payment
  - Enforced at: not enforced (planned)
- **BR-014** - Customers in the UAE and Pakistan must have a tax registration number on file before an order is confirmed.
  - Entities: Customer
  - Enforced at: not enforced

## Validations
| Entity.attribute | Validation | Where | Format assumption |
|---|---|---|---|
| OrderLine.qty | int >= 1 | order.schema.ts:5 | none |
| Customer.email | email | order.schema.ts:15 | none |
| Customer.phone | single regex | order.schema.ts:16 | one pattern for all countries |
| Customer.postcode | Dutch regex | order.schema.ts:19 | Dutch only |

## Integrations
| System | Business function | Where called | Assumptions baked in |
|---|---|---|---|
| Stripe | card payment | payment.gateway.ts:7 | EUR only |
| SMTP | e-mails | email.ts:5 | English only |

## Assumptions and gaps
1. "Legal entity" does not exist in code; assumed one per market for now.
2. Time zone per customer is not stored anywhere today.
3. Return entity and workflow are planned, not implemented.
