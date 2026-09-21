# Node / Express (and NestJS, Fastify, Koa) reference for audit-business-logic

## Stack markers
`package.json` with `express`, `@nestjs/core`, `fastify`, `koa`. Variants: JavaScript vs TypeScript; ORM (Prisma, TypeORM, Sequelize, Mongoose, Knex); queues (BullMQ, Agenda) and cron (`node-cron`).

## Where the relevant code lives
- Business rules: `services/`, `use-cases/`, `domain/`, NestJS `*.service.ts`; sometimes inline in route handlers (`routes/*.js`, `controllers/`).
- State: `enum OrderStatus` (TS) or string literals `'pending' | 'paid'`; `order.status = ...`; Mongoose `enum: [...]`.
- Money: JS `number` everywhere unless `decimal.js`, `big.js`, `dinero.js`, or integer cents are used; `toFixed(2)`, `Math.round(x * 100) / 100`.
- Entry points: `router.post(...)`, `@Post()`, webhook routes (`/webhooks/stripe`), queue processors, cron.
- Validation: `class-validator` DTOs (`@IsPositive`, `@Min`), `zod`/`joi`/`yup` schemas, `express-validator`.

## Dangerous / interesting APIs and patterns
- Money held in `number`: `price * qty`, `total - discount`, `parseFloat(req.body.amount)`; `.toFixed(2)` used for arithmetic (returns a string, then coerced).
- `Math.round(x * 100) / 100` (fails on 1.005); `Number.EPSILON` hacks.
- `order.status = 'paid'` in route handlers; `switch (order.status)` duplicated across routes; no `canTransition`.
- `order.total -= coupon.amount` or `cart.total = cart.total - discount` in an "update cart" or "apply coupon" route that can be called repeatedly.
- `Model.create(req.body)`, `Object.assign(order, req.body)`, `prisma.order.update({ data: req.body })`: status/total/role writable from the client.
- Mongoose `findOneAndUpdate` with `$inc` on balances without a guard (`{ balance: { $gte: amount } }` in the filter); hand to RACE.
- Webhook handlers without signature check (`stripe.webhooks.constructEvent`) or without event-id dedupe.
- `new Date()` / `moment()` in cutoff logic (hand to TIME).

## What "good" looks like
```ts
const TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
  pending: ['paid', 'cancelled'], paid: ['shipped', 'refunded'],
  shipped: ['completed', 'returned'], cancelled: [], completed: [], refunded: [], returned: [],
};
export function assertTransition(from: OrderStatus, to: OrderStatus) {
  if (!TRANSITIONS[from].includes(to)) throw new InvalidTransitionError(from, to);
}
// money in integer cents, derived total
const subtotalCents = lines.reduce((s, l) => s + l.unitPriceCents * l.qty, 0);
const discountCents = coupon ? Math.min(subtotalCents, couponValueCents(coupon, subtotalCents)) : 0;
order.totalCents = subtotalCents - discountCents + taxCents(subtotalCents - discountCents);
```
Coupon usage stored in an `order_coupons` table/array with uniqueness; DTO whitelist (`@Expose`, zod `.strict()`, `pick`) so only line items and coupon code come from the client.

## Manual trace checklist
1. Payment: where `amount` for the provider call comes from; is `order.status` checked before charge; webhook signature and dedupe.
2. `grep -rn "status = \|status: '" src`: map every write; find handlers that set terminal states or leave them.
3. Pricing: single `pricing.ts`? can `applyCoupon` run twice (route-level and cart-recalc); is total derived.
4. Stock: `$inc`/`decrement` sites and negative guards (hand to RACE).
5. Admin endpoints (`requireRole('admin')`) that force status/amount; audit log present.
6. Mass assignment: any `create(req.body)`/`update(req.body)`.

## Stack-specific false positives
- `number` for quantities, percentages, or already-integer cents (check the name: `amountCents` is fine).
- `.toFixed(2)` in a response formatter or template.
- Status switch in a label mapper inside the API (display only).
- `Object.assign` onto a DTO that was already validated with a strict schema.

## Tooling
`npx tsc --noEmit` (type of money fields); `grep -rn "toFixed\|parseFloat" src`; `npm ls dinero.js decimal.js big.js` to see whether a money library exists; `npx prisma format` then read column types (`Decimal` vs `Float`).

## References
CWE-840, CWE-841, CWE-682, CWE-915, ASVS 11.1.x, Stripe idempotency/webhook docs, `dinero.js` docs on why float money fails.
