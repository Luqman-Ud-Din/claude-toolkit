# Control proposal template

```markdown
### Fix for LLM-EA-003: refund_order has no approval gate

**Change:** Split `refund_order` into `propose_refund(order_id, amount)` -
returns a `pending_id`, server-caps `amount` at the order's remaining
refundable total - and `confirm_refund(pending_id, operator_token)`, which
alone actually calls Stripe. The agent's tool list only exposes
`propose_refund`; `confirm_refund` requires an operator-issued token from a
separate approval queue/UI, not something the agent can construct.

**Code sketch** (this repo's stack: .NET):
```csharp
public async Task<PendingRefund> ProposeRefundAsync(int orderId, decimal amount)
{
    var order = await _orders.GetAsync(orderId);
    var cappedAmount = Math.Min(amount, order.RefundableTotal);
    return await _pendingRefunds.CreateAsync(orderId, cappedAmount);
}
// ConfirmRefundAsync lives behind [Authorize(Roles = "SupportLead")] and is
// never registered as an agent tool.
```

**Trade-offs:** Adds one operator review step before any refund completes;
acceptable for an irreversible financial action. Ops needs a lightweight
approval queue UI if one doesn't exist yet.

**Effort:** M (new endpoint + minimal approval UI; no schema migration needed
if `pending_refunds` can reuse an existing table shape).

**Follow-up beyond code:** none - this is fully an engineering change.
```
