# Vue (and Nuxt) reference for audit-business-logic

## Stack markers
`package.json` with `vue` or `nuxt`. Variants: Vue 2 Options API vs Vue 3 Composition API; Pinia/Vuex stores; Nuxt `server/api/**` and `server/routes/**` (Nitro) are backend code: audit with `node-express.md`.

## Where the relevant code lives
- Client: `src/stores/*.ts` (Pinia actions `applyCoupon`, `updateTotal`, getters `total`), `composables/use*.ts`, `components/**/*.vue` (`:disabled`, `v-if="isAdmin"`), form validation (`vee-validate`, `vuelidate`, `zod`), `services/api.ts` payloads.
- Server (Nuxt): `server/api/**`, `server/utils/pricing.ts`, `server/middleware/`.

## Dangerous / interesting APIs and patterns
- Store getters compute money and actions send it: `total`, `discountAmount`, `tax` in `$fetch('/api/orders', { method: 'POST', body })`.
- `status`, `role`, `companyId` in payloads of ordinary user actions.
- UI-only transition rules: `:disabled="order.status !== 'pending'"`, `v-if="can('approve')"`; rules to verify server-side.
- `watch(cart, () => applyCoupon())` or `watchEffect` re-applying a discount on every change; apply button with no loading/disabled state: shows the double-apply path.
- Nuxt server routes using `readBody(event)` and persisting `body.total`/`body.status`; `prisma.order.update({ data: body })`.
- `Number`/`parseFloat` money math in shared `utils/pricing.ts` used by the server without re-reading persisted prices.
- `$fetch` with `retry: 3` on non-idempotent POSTs (replay evidence for RACE).
- Impersonation stored as a Pinia flag that only toggles UI.

## What "good" looks like
```ts
// Pinia action sends intent
await api.post('/orders', { lines: cart.value.map(l => ({ productId: l.id, qty: l.qty })), couponCode: code.value });
// Nuxt server route recomputes and guards transition
const order = await db.order.findUnique({ where: { id } });
assertTransition(order.status, 'paid');
const total = computeTotal(await pricesFor(lines), lines, coupon);
```
Buttons bound to `pending` state; server responses drive displayed totals.

## Manual trace checklist
1. Mutation payloads for order/payment/subscription/stock flows: fields the server should derive.
2. UI-only rules -> flow rules table -> verify server-side.
3. Nuxt server routes: apply `node-express.md` rules.
4. Coupon/discount: double-apply via watcher or double click; server dedupe.
5. Admin/impersonation UI: endpoints called; business consequence here, authorisation to authz.

## Stack-specific false positives
- Cart preview totals when the server recomputes on submit.
- `toFixed(2)`, `Intl.NumberFormat`, currency filters for display.
- `status` in admin-screen payloads where the server enforces role and transition.

## Tooling
`grep -rn "\$fetch\|axios\.\|useFetch" src server | grep -i "total\|status\|discount"`; Vue DevTools (Pinia tab) to watch state and payloads; `npx vue-tsc --noEmit`.

## References
CWE-602, CWE-840, CWE-915, OWASP Business Logic cheat sheet; Nuxt server routes docs.
