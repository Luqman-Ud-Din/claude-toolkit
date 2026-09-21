## audit-performance-and-scalability findings

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| 0 | 0 | 0 | 1 | 0 |

### [Low] PERF-001 - Order lookups have no response caching headers
- **Location:** `Inventory.Api/Controllers/OrdersController.cs:18`
- **Confidence:** confirmed
- **Evidence:**

```
Inventory.Api/Controllers/OrdersController.cs:18
```

- **Impact:** Repeated lookups hit the database each time.
- **Remediation:** Add short private caching where safe.
- **Reference:** CWE-1176

### Not checked
- load test - no running environment URL
