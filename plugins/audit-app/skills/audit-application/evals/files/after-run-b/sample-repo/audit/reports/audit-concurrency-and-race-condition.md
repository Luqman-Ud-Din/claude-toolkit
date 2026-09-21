## audit-concurrency-and-race-condition findings

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| 0 | 0 | 1 | 0 | 0 |

### [Medium] RACE-001 - Order payment has no idempotency or concurrency token
- **Location:** `Inventory.Api/Controllers/OrdersController.cs:33`
- **Confidence:** confirmed
- **Evidence:**

```
Inventory.Api/Controllers/OrdersController.cs:33
```

- **Impact:** A double click can record the payment twice.
- **Remediation:** Add a rowversion column and handle DbUpdateConcurrencyException.
- **Reference:** CWE-362

### Not checked
- (nothing recorded; the skill should list what it could not verify)
