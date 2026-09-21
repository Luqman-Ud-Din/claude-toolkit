## audit-authz-and-access-control findings

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| 1 | 1 | 0 | 0 | 0 |

### [Critical] AUTHZ-002 - JWT bearer registered without token validation parameters
- **Location:** `Inventory.Api/Program.cs:6`
- **Confidence:** likely
- **Evidence:**

```
Inventory.Api/Program.cs:6
```

- **Impact:** Tokens from any issuer may be accepted, so anyone could forge a login.
- **Remediation:** Configure TokenValidationParameters (issuer, audience, signing key, lifetime).
- **Reference:** CWE-287, ASVS-3.5.3, OWASP-A07:2021

### [High] AUTHZ-001 - Order payment is scoped by company but not by branch
- **Location:** `Inventory.Api/Controllers/OrdersController.cs:30`
- **Confidence:** confirmed
- **Evidence:**

```
Inventory.Api/Controllers/OrdersController.cs:30
```

- **Impact:** A user of one branch can mark another branch's orders as paid.
- **Remediation:** Filter by BranchId from the caller's claims as well as CompanyId.
- **Reference:** CWE-639, ASVS-4.2.1, OWASP-A01:2021

### Not checked
- dynamic probe - no test URL or tokens supplied
