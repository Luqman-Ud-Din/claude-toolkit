## audit-business-logic findings

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| 0 | 1 | 0 | 0 | 0 |

### [High] BIZ-001 - Pay moves an order to Paid from any status, including Cancelled
- **Location:** `Inventory.Api/Controllers/OrdersController.cs:32`
- **Confidence:** confirmed
- **Evidence:**

```
Inventory.Api/Controllers/OrdersController.cs:32
```

- **Impact:** Cancelled orders can be marked paid, so stock and revenue reports disagree with reality.
- **Remediation:** Guard the transition: only Confirmed -> Paid.
- **Reference:** CWE-841

### Not checked
- (nothing recorded; the skill should list what it could not verify)
