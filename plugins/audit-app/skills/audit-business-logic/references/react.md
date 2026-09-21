# React (and Next.js) reference for audit-business-logic

## Stack markers
`package.json` with `react` or `next`. Variants: CRA/Vite SPA vs Next.js (server components and route handlers under `app/api/**/route.ts` or `pages/api/**`; those are backend code: audit them with `node-express.md`).

## Where the relevant code lives
- Client: `src/features/**`, `hooks/use*.ts`, `store/` (Redux/Zustand) reducers named `applyCoupon`, `updateTotal`, `setStatus`; form schemas (`zod`, `yup`, Formik validators); `services/api.ts` payload builders.
- Server (Next.js): `app/api/**/route.ts`, `pages/api/**`, server actions (`'use server'`), `lib/pricing.ts`; treat as backend.

## Dangerous / interesting APIs and patterns
- Reducers or hooks that compute money and send it: `total`, `discount`, `tax` in `fetch('/api/orders', { body })`; server trusting them is the finding.
- `status`, `role`, `isAdmin`, `tenantId` in mutation payloads of ordinary user actions (React Query `useMutation` bodies).
- UI-only transition rules: `disabled={order.status !== 'pending'}`, `{isAdmin && <ForceApprove/>}`; each is a rule to verify server-side.
- Coupon apply via `useEffect` on cart change (fires repeatedly) or a button without a pending/disabled state: demonstrates the double-apply path.
- Server actions / route handlers that read `formData.get('total')` or `body.total` and persist it; `prisma.order.update({ data: body })`.
- `Number(...)`/`parseFloat` money math in `lib/pricing.ts` used by both client preview and server (shared code is fine only if the server still recomputes from persisted prices).
- Retry wrappers (`retry: 3` in React Query on mutations): replay evidence for RACE.
- Impersonation UI: `useSession()` with an `impersonating` flag that only hides buttons.

## What "good" looks like
```ts
// client sends intent
mutate({ lines: cart.map(l => ({ productId: l.id, qty: l.qty })), couponCode });
// server (route handler) recomputes
const prices = await db.product.findMany({ where: { id: { in: ids } } });
const total = computeTotal(prices, lines, coupon);   // Decimal / integer cents
assertTransition(order.status, 'paid');
```
React Query `useMutation` with `retry: 0` for non-idempotent POSTs; `isPending` disables the apply/pay button.

## Manual trace checklist
1. Every mutation payload for order/payment/subscription/stock: which fields should the server derive.
2. UI-only rules -> rules table -> verify server-side.
3. Next.js route handlers/server actions: audit with `node-express.md` rules (float money, status writes, mass assignment).
4. Coupon/discount: can apply run twice; does the server dedupe.
5. Admin/impersonation screens: endpoints called; business consequence recorded here.

## Stack-specific false positives
- Preview totals in the cart when the server recomputes on checkout.
- `toFixed(2)` / `Intl.NumberFormat` for display.
- Shared `pricing.ts` imported by the server *and* the server fetches persisted prices (confirm).

## Tooling
`grep -rn "fetch(\|axios\.\|useMutation" src | grep -i "total\|status\|discount"`; React DevTools / Network tab payloads; `npx tsc --noEmit`.

## References
CWE-602, CWE-840, CWE-915, OWASP Business Logic cheat sheet; Next.js server actions security docs.
