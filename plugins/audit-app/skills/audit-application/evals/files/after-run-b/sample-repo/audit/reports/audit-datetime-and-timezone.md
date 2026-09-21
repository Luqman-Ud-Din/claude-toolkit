## audit-datetime-and-timezone findings

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| 0 | 0 | 0 | 1 | 0 |

### [Low] TIME-001 - No timestamp is recorded when an order is paid
- **Location:** `Inventory.Api/Controllers/OrdersController.cs:33`
- **Confidence:** confirmed
- **Evidence:**

```
Inventory.Api/Controllers/OrdersController.cs:33
```

- **Impact:** Payment time cannot be reported per user time zone.
- **Remediation:** Store PaidAt as DateTimeOffset UTC.
- **Reference:** CWE-1339

### Not checked
- (nothing recorded; the skill should list what it could not verify)
