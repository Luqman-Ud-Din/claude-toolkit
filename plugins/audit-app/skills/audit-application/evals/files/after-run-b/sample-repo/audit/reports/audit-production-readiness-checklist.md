## audit-production-readiness-checklist findings

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| 0 | 1 | 0 | 0 | 0 |

### [High] READY-001 - No health check endpoint is registered
- **Location:** `Inventory.Api/Program.cs:1`
- **Confidence:** confirmed
- **Evidence:**

```
Inventory.Api/Program.cs:1
```

- **Impact:** The hosting platform cannot tell when the API is down, so outages last longer.
- **Remediation:** Add AddHealthChecks().AddDbContextCheck and MapHealthChecks("/health").
- **Reference:** ASVS-14.1.1

### Not checked
- alert routing - outside the repo
