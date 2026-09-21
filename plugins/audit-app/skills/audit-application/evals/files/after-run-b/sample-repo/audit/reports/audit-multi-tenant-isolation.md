## audit-multi-tenant-isolation findings

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| 0 | 1 | 0 | 0 | 0 |

### [High] TENANT-001 - Tenant filter applied by hand per query; payment path misses BranchId
- **Location:** `Inventory.Api/Controllers/OrdersController.cs:30`
- **Confidence:** confirmed
- **Evidence:**

```
Inventory.Api/Controllers/OrdersController.cs:30
```

- **Impact:** One branch can change another branch's data.
- **Remediation:** Add a global query filter on CompanyId and BranchId in the DbContext.
- **Reference:** CWE-639, ASVS-4.2.1

### Not checked
- cross-tenant probe - no tenants.json supplied
