# Angular reference for audit-business-logic

## Stack markers
`package.json` with `@angular/core`, `angular.json`. Variants: NgModules vs standalone; Ionic/Capacitor shells; NgRx/signals stores.

## Where the relevant code lives
Business rules must live on the server; the frontend's role in this audit is (a) to reveal which rules the product *expects* (validators, disabled buttons, status badges) so you can check they exist server-side, and (b) to find places where the client computes or sends values the server should own. Look in `features/**/services/*.service.ts`, `*.component.ts` (`calculateTotal`, `applyDiscount`, `canCancel`), reactive-form validators, `shared/enums/*status*.ts`, `core/services/api.service.ts` (what is posted). Server-side rules are owned by the backend reference (`dotnet.md`, `node-express.md`, ...).

## Dangerous / interesting APIs and patterns
- Client computes money and sends it: `total`, `grandTotal`, `discountAmount`, `taxAmount`, `unitPrice` in a POST body. If the server trusts it, that is a BIZ finding on the server; cite the client site as evidence.
- Client sends `status`, `isApproved`, `roleId`, `companyId`, `branchId` in the payload of a normal user action.
- Status transition rules encoded only in the UI: `canCancel = status === 'Pending'`, `[disabled]="order.status !== 'Draft'"`, `*ngIf="isAdmin"`. Each one is a rule to verify server-side.
- Coupon apply button not disabled after success, or `applyCoupon()` called from `valueChanges` on every cart edit: shows how a double-apply is triggered in practice.
- Currency and rounding in the client (`toFixed(2)`, `Math.round`, `CurrencyPipe` with a different locale than the server) that disagree with the invoice.
- Impersonation/"login as" UI: what token it uses and whether the UI hides, rather than the server blocks, sensitive actions.
- Retry/resubmit logic (`retry(3)` on POST, double-click without debounce): evidence for the replay abuse case; hand the mechanics to RACE.

## What "good" looks like
```ts
// send intent, not computed money
this.api.post('/orders', { lines: lines.map(l => ({ productId: l.id, qty: l.qty })), couponCode });
// UI guard mirrors, does not replace, the server rule
canCancel = computed(() => ALLOWED_CANCEL_FROM.includes(this.order().status));
```
Totals displayed come from the server response; the client re-fetches after mutations rather than adjusting local totals.

## Manual trace checklist
1. List every POST/PUT body for order/payment/subscription/stock flows; mark fields the server should derive.
2. Collect UI-only rules (disabled buttons, hidden menu items, validators) into the flow's rules table and verify each on the server.
3. Coupon/discount UI: can the user trigger apply twice (no disabled state, no idempotent server response).
4. Admin/impersonation screens: which endpoints they call; hand the authorisation to authz, keep the business consequence here.

## Stack-specific false positives
- Client-side totals shown for preview when the server recomputes on submit (confirm on the server).
- `status` in a payload for admin-only screens where the server checks role and transition.
- `toFixed(2)` for display only.

## Tooling
`grep -rn "total\|discount\|status" src/app --include=*.ts | grep -i "post\|put\|patch"`; Angular DevTools / browser Network tab to watch payloads.

## References
OWASP Business Logic cheat sheet ("never trust client-side calculations"), CWE-602 (client-side enforcement of server-side security), CWE-840.
