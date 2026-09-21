## audit-dependency-vulnerabilities findings

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| 0 | 0 | 1 | 0 | 0 |

### [Medium] DEP-001 - Transitive System.Text.Json with a known DoS advisory
- **Location:** `Inventory.Api/Inventory.Api.csproj:1`
- **Confidence:** confirmed
- **Evidence:**

```
Inventory.Api/Inventory.Api.csproj:1
```

- **Impact:** A crafted request could slow the API down.
- **Remediation:** Pin the patched version in Directory.Packages.props.
- **Reference:** CWE-400, OWASP-A06:2021

### Not checked
- (nothing recorded; the skill should list what it could not verify)
