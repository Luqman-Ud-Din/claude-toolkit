# Pre-production audit report: Inventory

Generated 2026-09-11 12:23 UTC. Commit: n/a. Stack: dotnet / angular.

## 1. Executive summary

**Recommendation: NO-GO.** 1 Critical and 3 High findings are open. Each is a launch blocker: an attacker or an ordinary user can cause data exposure, data loss or account takeover without special skill. Caveat: 1 audit area(s) did not complete (secrets and config); the verdict covers only what was assessed.

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| 1 | 3 | 2 | 2 | 1 |

### Top three risks

1. **JWT bearer registered without token validation parameters** (Critical, AUTHZ-002). Tokens from any issuer may be accepted, so anyone could forge a login.
2. **Order payment is scoped by company but not by branch** (High, AUTHZ-001). A user of one branch can mark another branch's orders as paid.
3. **Pay moves an order to Paid from any status, including Cancelled** (High, BIZ-001). Cancelled orders can be marked paid, so stock and revenue reports disagree with reality.

Audit areas run: 31; completed: 11; skipped: 19; failed: 1. Findings after de-duplication: 9 (from 10; 1 false positives excluded, see Appendix C).

## 2. Scope and methodology

Each area was reviewed in two passes: an automated grep/script pass over the repository (scripts listed in Appendix B) followed by a manual trace of the highest-risk flows. The audited code was never modified; all artefacts live under `audit/`.

| Audit area | Status | Checked | Not checked (reason) |
|---|---|---|---|
| accessibility and i18n | skipped - not in scope profile 'pre-launch' | - | - |
| api contract | skipped - not in scope profile 'pre-launch' | - | - |
| async and dependency injection | skipped - not in scope profile 'pre-launch' | - | - |
| authz and access control | completed | all controllers under Inventory.Api; Program.cs pipeline | dynamic probe (no test URL or tokens supplied) |
| backend resource leak | skipped - not in scope profile 'pre-launch' | - | - |
| business logic | completed | order payment flow; order cancellation flow; stock reservation flow | - |
| client auth and storage | skipped - not in scope profile 'pre-launch' | - | - |
| concurrency and race condition | completed | order payment flow | - |
| datetime and timezone | completed | order entity dates | - |
| db schema | skipped - not in scope profile 'pre-launch' | - | - |
| dependency vulnerabilities | completed | NuGet (dotnet list package --vulnerable); npm audit (web) | - |
| frontend best practices | skipped - not in scope profile 'pre-launch' | - | - |
| frontend memory leak | skipped - not in scope profile 'pre-launch' | - | - |
| frontend xss and dom safety | completed | web/src/app templates | - |
| gdpr data protection | skipped - not in scope profile 'pre-launch' | - | - |
| infra and deployment | skipped - not in scope profile 'pre-launch' | - | - |
| injection vulnerabilities | completed | EF Core queries in Inventory.Api | - |
| licensing and compliance | skipped - not in scope profile 'pre-launch' | - | - |
| logging and observability | skipped - not in scope profile 'pre-launch' | - | - |
| multi tenant isolation | completed | OrdersController data access paths | cross-tenant probe (no tenants.json supplied) |
| orm query and data access | skipped - not in scope profile 'pre-launch' | - | - |
| owasp asvs mapper | completed | 11 findings files under audit\findings; 11 completed skills counted toward Verified | ASVS level 2/3 controls without findings (listed only when named; run with --min-level 3 to see all) |
| performance and scalability | completed - limited access: no running environment URL for the load test | endpoint inventory; EF query shapes | load test (no running environment URL) |
| privacy data flow mapper | skipped - not in scope profile 'pre-launch' | - | - |
| production readiness checklist | completed | Program.cs; deployment descriptors (none present) | alert routing (outside the repo) |
| secrets and config | failed - simulated failure (--simulate-failure audit-secrets-and-config) | - | - |
| security headers and middleware | skipped - not in scope profile 'pre-launch' | - | - |
| soc2 controls evidence | skipped - not in scope profile 'pre-launch' | - | - |
| system design | skipped - not in scope profile 'pre-launch' | - | - |
| technical debt | skipped - not in scope profile 'pre-launch' | - | - |
| test coverage and ci | skipped - not in scope profile 'pre-launch' | - | - |

## 3. Findings

Sorted by severity. Evidence is abbreviated here; Appendix A has the full text. Findings sharing a root cause are merged (merged ids shown).

### Critical (1)

#### [Critical] AUTHZ-002 - JWT bearer registered without token validation parameters
- **Area:** authz and access control
- **Location:** `Inventory.Api/Program.cs:6`
- **Confidence:** likely
- **Evidence:**

```
Inventory.Api/Program.cs:6
```

- **Impact:** Tokens from any issuer may be accepted, so anyone could forge a login.
- **Remediation:** Configure TokenValidationParameters (issuer, audience, signing key, lifetime).
- **Reference:** CWE-287, ASVS-3.5.3, OWASP-A07:2021, ASVS-4.1.1, ASVS-2.2.1

### High (3)

#### [High] AUTHZ-001 - Order payment is scoped by company but not by branch
- **Area:** authz and access control
- **Location:** `Inventory.Api/Controllers/OrdersController.cs:30` (+1 more, see Appendix A)
- **Confidence:** confirmed - merged with TENANT-001
- **Evidence:**

```
Inventory.Api/Controllers/OrdersController.cs:30
```

- **Impact:** A user of one branch can mark another branch's orders as paid.
- **Remediation:** Filter by BranchId from the caller's claims as well as CompanyId.
- **Reference:** CWE-639, ASVS-4.2.1, OWASP-A01:2021, ASVS-4.1.3

#### [High] BIZ-001 - Pay moves an order to Paid from any status, including Cancelled
- **Area:** business logic
- **Location:** `Inventory.Api/Controllers/OrdersController.cs:32`
- **Confidence:** confirmed
- **Evidence:**

```
Inventory.Api/Controllers/OrdersController.cs:32
```

- **Impact:** Cancelled orders can be marked paid, so stock and revenue reports disagree with reality.
- **Remediation:** Guard the transition: only Confirmed -> Paid.
- **Reference:** CWE-841, OWASP-A04:2021, ASVS-11.1.1, ASVS-11.1.2, ASVS-11.1.4

#### [High] READY-001 - No health check endpoint is registered
- **Area:** production readiness checklist
- **Location:** `Inventory.Api/Program.cs:1`
- **Confidence:** confirmed
- **Evidence:**

```
Inventory.Api/Program.cs:1
```

- **Impact:** The hosting platform cannot tell when the API is down, so outages last longer.
- **Remediation:** Add AddHealthChecks().AddDbContextCheck and MapHealthChecks("/health").
- **Reference:** ASVS-14.1.1

### Medium (2)

#### [Medium] DEP-001 - Transitive System.Text.Json with a known DoS advisory
- **Area:** dependency vulnerabilities
- **Location:** `Inventory.Api/Inventory.Api.csproj:1`
- **Confidence:** confirmed
- **Evidence:**

```
Inventory.Api/Inventory.Api.csproj:1
```

- **Impact:** A crafted request could slow the API down.
- **Remediation:** Pin the patched version in Directory.Packages.props.
- **Reference:** CWE-400, OWASP-A06:2021, ASVS-12.1.1, ASVS-11.1.4

#### [Medium] RACE-001 - Order payment has no idempotency or concurrency token
- **Area:** concurrency and race condition
- **Location:** `Inventory.Api/Controllers/OrdersController.cs:33`
- **Confidence:** confirmed
- **Evidence:**

```
Inventory.Api/Controllers/OrdersController.cs:33
```

- **Impact:** A double click can record the payment twice.
- **Remediation:** Add a rowversion column and handle DbUpdateConcurrencyException.
- **Reference:** CWE-362, OWASP-A04:2021, ASVS-11.1.6

### Low (2)

#### [Low] PERF-001 - Order lookups have no response caching headers
- **Area:** performance and scalability
- **Location:** `Inventory.Api/Controllers/OrdersController.cs:18`
- **Confidence:** confirmed
- **Evidence:**

```
Inventory.Api/Controllers/OrdersController.cs:18
```

- **Impact:** Repeated lookups hit the database each time.
- **Remediation:** Add short private caching where safe.
- **Reference:** CWE-1176

#### [Low] TIME-001 - No timestamp is recorded when an order is paid
- **Area:** datetime and timezone
- **Location:** `Inventory.Api/Controllers/OrdersController.cs:33`
- **Confidence:** confirmed
- **Evidence:**

```
Inventory.Api/Controllers/OrdersController.cs:33
```

- **Impact:** Payment time cannot be reported per user time zone.
- **Remediation:** Store PaidAt as DateTimeOffset UTC.
- **Reference:** CWE-1339

### Info (1)

#### [Info] MAP-001 - 51 ASVS 4.0 sections were not assessed by any audit skill
- **Area:** owasp asvs mapper
- **Location:** `audit/findings (coverage matrix)`
- **Confidence:** confirmed
- **Evidence:**

```
V1.1 Secure Software Development Lifecycle
V1.2 Authentication Architecture
V1.5 Input and Output Architecture
V1.6 Cryptographic Architecture
... (47 more lines in Appendix A)
```

- **Impact:** The audit cannot claim ASVS coverage for these areas; a reader could mistake silence for a pass. Rated Info because it is a gap in the audit, not in the product.
- **Remediation:** Run the skill that owns each section (see skill_coverage in scripts/mapping.json), or record a manual check in that skill's scope.checked as 'ASVS-x.y verified: <how>'.
- **Reference:** ASVS-1.1.2

## 4. Pass/fail matrix by audit area

| Audit area | Run status | Critical | High | Medium | Low | Info | Result |
|---|---|---|---|---|---|---|---|
| accessibility and i18n | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| api contract | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| async and dependency injection | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| authz and access control | completed | 1 | 1 | 0 | 0 | 0 | FAIL |
| backend resource leak | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| business logic | completed | 0 | 1 | 0 | 0 | 0 | FAIL |
| client auth and storage | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| concurrency and race condition | completed | 0 | 0 | 1 | 0 | 0 | WARN |
| datetime and timezone | completed | 0 | 0 | 0 | 1 | 0 | WARN |
| db schema | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| dependency vulnerabilities | completed | 0 | 0 | 1 | 0 | 0 | WARN |
| frontend best practices | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| frontend memory leak | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| frontend xss and dom safety | completed | 0 | 0 | 0 | 0 | 0 | PASS |
| gdpr data protection | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| infra and deployment | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| injection vulnerabilities | completed | 0 | 0 | 0 | 0 | 0 | PASS |
| licensing and compliance | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| logging and observability | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| multi tenant isolation | completed | 0 | 0 | 0 | 0 | 0 | PASS |
| orm query and data access | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| owasp asvs mapper | completed | 0 | 0 | 0 | 0 | 1 | PASS |
| performance and scalability | completed | 0 | 0 | 0 | 1 | 0 | WARN |
| privacy data flow mapper | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| production readiness checklist | completed | 0 | 1 | 0 | 0 | 0 | FAIL |
| secrets and config | failed | 0 | 0 | 0 | 0 | 0 | FAILED (skill error) |
| security headers and middleware | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| soc2 controls evidence | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| system design | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| technical debt | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |
| test coverage and ci | skipped | 0 | 0 | 0 | 0 | 0 | NOT RUN |

## 5. OWASP Top 10 / ASVS coverage

#### audit-owasp-asvs-mapper findings

Generated 2026-09-11T12:23:35.264491+00:00. Findings files: 11. Mapped findings: 9. Unmapped: 0. Findings files updated: 5.

##### OWASP Top 10 (2021) coverage

| Category | Status | Linked findings |
|---|---|---|
| A01:2021 Broken Access Control | Failed | AUTHZ-001, TENANT-001 |
| A02:2021 Cryptographic Failures | Not assessed | - |
| A03:2021 Injection | Verified | - |
| A04:2021 Insecure Design | Failed | BIZ-001, RACE-001 |
| A05:2021 Security Misconfiguration | Verified | - |
| A06:2021 Vulnerable and Outdated Components | Failed | DEP-001 |
| A07:2021 Identification and Authentication Failures | Failed | AUTHZ-002 |
| A08:2021 Software and Data Integrity Failures | Verified | - |
| A09:2021 Security Logging and Monitoring Failures | Not assessed | - |
| A10:2021 Server-Side Request Forgery | Verified | - |

##### ASVS 4.0 coverage matrix (by section)

| Section | Name | Status | Linked findings | Assessed by |
|---|---|---|---|---|
| V1.1 | Secure Software Development Lifecycle | Not assessed | - | - |
| V1.2 | Authentication Architecture | Not assessed | - | - |
| V1.4 | Access Control Architecture | Verified | - | audit-authz-and-access-control |
| V1.5 | Input and Output Architecture | Not assessed | - | - |
| V1.6 | Cryptographic Architecture | Not assessed | - | - |
| V1.7 | Errors, Logging and Auditing Architecture | Not assessed | - | - |
| V1.8 | Data Protection and Privacy Architecture | Not assessed | - | - |
| V1.9 | Communications Architecture | Not assessed | - | - |
| V1.10 | Malicious Software Architecture | Not assessed | - | - |
| V1.11 | Business Logic Architecture | Not assessed | - | - |
| V1.12 | Secure File Upload Architecture | Not assessed | - | - |
| V1.14 | Configuration Architecture | Not assessed | - | - |
| V2.1 | Password Security | Not assessed | - | - |
| V2.2 | General Authenticator Security | Failed | AUTHZ-002 | - |
| V2.3 | Authenticator Lifecycle | Not assessed | - | - |
| V2.4 | Credential Storage | Not assessed | - | - |
| V2.5 | Credential Recovery | Not assessed | - | - |
| V2.6 | Look-up Secret Verifier | Not assessed | - | - |
| V2.7 | Out of Band Verifier | Not assessed | - | - |
| V2.8 | One Time Verifier | Not assessed | - | - |
| V2.9 | Cryptographic Verifier | Not assessed | - | - |
| V2.10 | Service Authentication | Not assessed | - | - |
| V3.1 | Fundamental Session Management Security | Not assessed | - | - |
| V3.2 | Session Binding | Not assessed | - | - |
| V3.3 | Session Termination | Not assessed | - | - |
| V3.4 | Cookie-based Session Management | Not assessed | - | - |
| V3.5 | Token-based Session Management | Failed | AUTHZ-002 | - |
| V3.6 | Federated Re-authentication | Not assessed | - | - |
| V3.7 | Defenses Against Session Management Exploits | Not assessed | - | - |
| V4.1 | General Access Control Design | Failed | AUTHZ-001, AUTHZ-002, TENANT-001 | audit-authz-and-access-control, audit-multi-tenant-isolation |
| V4.2 | Operation Level Access Control | Failed | AUTHZ-001, TENANT-001 | audit-authz-and-access-control, audit-multi-tenant-isolation |
| V4.3 | Other Access Control Considerations | Verified | - | audit-authz-and-access-control |
| V5.1 | Input Validation | Verified | - | audit-injection-vulnerabilities |
| V5.2 | Sanitization and Sandboxing | Verified | - | audit-injection-vulnerabilities |
| V5.3 | Output Encoding and Injection Prevention | Verified | - | audit-frontend-xss-and-dom-safety, audit-injection-vulnerabilities |
| V5.4 | Memory, String, and Unmanaged Code | Not assessed | - | - |
| V5.5 | Deserialization Prevention | Verified | - | audit-injection-vulnerabilities |
| V6.1 | Data Classification | Not assessed | - | - |
| V6.2 | Algorithms | Not assessed | - | - |
| V6.3 | Random Values | Not assessed | - | - |
| V6.4 | Secret Management | Not assessed | - | - |
| V7.1 | Log Content | Not assessed | - | - |
| V7.2 | Log Processing | Not assessed | - | - |
| V7.3 | Log Protection | Not assessed | - | - |
| V7.4 | Error Handling | Not assessed | - | - |
| V8.1 | General Data Protection | Not assessed | - | - |
| V8.2 | Client-side Data Protection | Not assessed | - | - |
| V8.3 | Sensitive Private Data | Not assessed | - | - |
| V9.1 | Client Communication Security | Not assessed | - | - |
| V9.2 | Server Communication Security | Not assessed | - | - |
| V10.1 | Code Integrity | Not assessed | - | - |
| V10.2 | Malicious Code Search | Not assessed | - | - |
| V10.3 | Application Integrity | Verified | - | audit-dependency-vulnerabilities |
| V11.1 | Business Logic Security | Failed | BIZ-001, DEP-001, RACE-001 | audit-business-logic, audit-concurrency-and-race-condition |
| V12.1 | File Upload | Failed | DEP-001 | - |
| V12.2 | File Integrity | Not assessed | - | - |
| V12.3 | File Execution | Not assessed | - | - |
| V12.4 | File Storage | Not assessed | - | - |
| V12.5 | File Download | Not assessed | - | - |
| V12.6 | SSRF Protection | Verified | - | audit-injection-vulnerabilities |
| V13.1 | Generic Web Service Security | Not assessed | - | - |
| V13.2 | RESTful Web Service | Not assessed | - | - |
| V13.3 | SOAP Web Service | Not assessed | - | - |
| V13.4 | GraphQL | Not assessed | - | - |
| V14.1 | Build and Deploy | Failed | READY-001 | audit-production-readiness-checklist |
| V14.2 | Dependency | Verified | - | audit-dependency-vulnerabilities |
| V14.3 | Unintended Security Disclosure | Verified | - | audit-production-readiness-checklist |
| V14.4 | HTTP Security Headers | Verified | - | audit-frontend-xss-and-dom-safety |
| V14.5 | HTTP Request Header Validation | Not assessed | - | - |

Control-level detail and the per-finding mapping are in Appendix D.

## 6. Compliance status

### GDPR

`audit-gdpr-data-protection` was skipped (not in scope profile 'pre-launch'); no compliance statement can be made for this framework.

### SOC 2

`audit-soc2-controls-evidence` was skipped (not in scope profile 'pre-launch'); no compliance statement can be made for this framework.

## 7. Remediation plan

### Must fix before launch (Critical and High)

| Priority | Id | Finding | Where | Fix summary |
|---|---|---|---|---|
| 1 | AUTHZ-002 | JWT bearer registered without token validation parameters | `Inventory.Api/Program.cs:6` | Configure TokenValidationParameters (issuer, audience, signing key, lifetime). |
| 2 | AUTHZ-001 | Order payment is scoped by company but not by branch | `Inventory.Api/Controllers/OrdersController.cs:30` | Filter by BranchId from the caller's claims as well as CompanyId. |
| 3 | BIZ-001 | Pay moves an order to Paid from any status, including Cancelled | `Inventory.Api/Controllers/OrdersController.cs:32` | Guard the transition: only Confirmed -> Paid. |
| 4 | READY-001 | No health check endpoint is registered | `Inventory.Api/Program.cs:1` | Add AddHealthChecks().AddDbContextCheck and MapHealthChecks("/health"). |

### Ticket for post-launch (Medium and Low)

| Id | Severity | Finding | Suggested window |
|---|---|---|---|
| DEP-001 | Medium | Transitive System.Text.Json with a known DoS advisory | first release after launch (30 days) |
| RACE-001 | Medium | Order payment has no idempotency or concurrency token | first release after launch (30 days) |
| PERF-001 | Low | Order lookups have no response caching headers | next quarter |
| TIME-001 | Low | No timestamp is recorded when an order is paid | next quarter |

### Record only (Info)

- MAP-001 - 51 ASVS 4.0 sections were not assessed by any audit skill

---

## Appendix A. Full evidence

### AUTHZ-002 - JWT bearer registered without token validation parameters
- Area: authz and access control; severity Critical; confidence likely
- Location: `Inventory.Api/Program.cs:6`

```
Inventory.Api/Program.cs:6
```

### AUTHZ-001 - Order payment is scoped by company but not by branch
- Area: authz and access control; severity High; confidence confirmed
- Location: `Inventory.Api/Controllers/OrdersController.cs:30`
- Location: `Inventory.Api/Controllers/OrdersController.cs:30`

```
Inventory.Api/Controllers/OrdersController.cs:30
```

### BIZ-001 - Pay moves an order to Paid from any status, including Cancelled
- Area: business logic; severity High; confidence confirmed
- Location: `Inventory.Api/Controllers/OrdersController.cs:32`

```
Inventory.Api/Controllers/OrdersController.cs:32
```

### READY-001 - No health check endpoint is registered
- Area: production readiness checklist; severity High; confidence confirmed
- Location: `Inventory.Api/Program.cs:1`

```
Inventory.Api/Program.cs:1
```

### DEP-001 - Transitive System.Text.Json with a known DoS advisory
- Area: dependency vulnerabilities; severity Medium; confidence confirmed
- Location: `Inventory.Api/Inventory.Api.csproj:1`

```
Inventory.Api/Inventory.Api.csproj:1
```

### RACE-001 - Order payment has no idempotency or concurrency token
- Area: concurrency and race condition; severity Medium; confidence confirmed
- Location: `Inventory.Api/Controllers/OrdersController.cs:33`

```
Inventory.Api/Controllers/OrdersController.cs:33
```

### PERF-001 - Order lookups have no response caching headers
- Area: performance and scalability; severity Low; confidence confirmed
- Location: `Inventory.Api/Controllers/OrdersController.cs:18`

```
Inventory.Api/Controllers/OrdersController.cs:18
```

### TIME-001 - No timestamp is recorded when an order is paid
- Area: datetime and timezone; severity Low; confidence confirmed
- Location: `Inventory.Api/Controllers/OrdersController.cs:33`

```
Inventory.Api/Controllers/OrdersController.cs:33
```

### MAP-001 - 51 ASVS 4.0 sections were not assessed by any audit skill
- Area: owasp asvs mapper; severity Info; confidence confirmed
- Location: `audit/findings (coverage matrix)`

```
V1.1 Secure Software Development Lifecycle
V1.2 Authentication Architecture
V1.5 Input and Output Architecture
V1.6 Cryptographic Architecture
V1.7 Errors, Logging and Auditing Architecture
V1.8 Data Protection and Privacy Architecture
V1.9 Communications Architecture
V1.10 Malicious Software Architecture
V1.11 Business Logic Architecture
V1.12 Secure File Upload Architecture
V1.14 Configuration Architecture
V2.1 Password Security
V2.3 Authenticator Lifecycle
V2.4 Credential Storage
V2.5 Credential Recovery
V2.6 Look-up Secret Verifier
V2.7 Out of Band Verifier
V2.8 One Time Verifier
V2.9 Cryptographic Verifier
V2.10 Service Authentication
V3.1 Fundamental Session Management Security
V3.2 Session Binding
V3.3 Session Termination
V3.4 Cookie-based Session Management
V3.6 Federated Re-authentication
V3.7 Defenses Against Session Management Exploits
V5.4 Memory, String, and Unmanaged Code
V6.1 Data Classification
V6.2 Algorithms
V6.3 Random Values
V6.4 Secret Management
V7.1 Log Content
V7.2 Log Processing
V7.3 Log Protection
V7.4 Error Handling
V8.1 General Data Protection
V8.2 Client-side Data Protection
V8.3 Sensitive Private Data
V9.1 Client Communication Security
V9.2 Server Communication Security
V10.1 Code Integrity
V10.2 Malicious Code Search
V12.2 File Integrity
V12.3 File Execution
V12.4 File Storage
V12.5 File Download
V13.1 Generic Web Service Security
V13.2 RESTful Web Service
V13.3 SOAP Web Service
V13.4 GraphQL
V14.5 HTTP Request Header Validation
```

## Appendix B. Scripts and tools used

- **authz and access control**: `../audit-stack-detection/scripts/detect_stack.py`, `../audit-code-scan/scripts/grep_scan.py`, `../audit-finding-writer/scripts/findings.py`; evidence: `audit/evidence/audit-authz-and-access-control/hits.json`
- **business logic**: `../audit-stack-detection/scripts/detect_stack.py`, `../audit-code-scan/scripts/grep_scan.py`, `../audit-finding-writer/scripts/findings.py`; evidence: `audit/evidence/audit-business-logic/hits.json`
- **concurrency and race condition**: `../audit-stack-detection/scripts/detect_stack.py`, `../audit-code-scan/scripts/grep_scan.py`, `../audit-finding-writer/scripts/findings.py`; evidence: `audit/evidence/audit-concurrency-and-race-condition/hits.json`
- **datetime and timezone**: `../audit-stack-detection/scripts/detect_stack.py`, `../audit-code-scan/scripts/grep_scan.py`, `../audit-finding-writer/scripts/findings.py`; evidence: `audit/evidence/audit-datetime-and-timezone/hits.json`
- **dependency vulnerabilities**: `../audit-stack-detection/scripts/detect_stack.py`, `../audit-code-scan/scripts/grep_scan.py`, `../audit-finding-writer/scripts/findings.py`; evidence: `audit/evidence/audit-dependency-vulnerabilities/hits.json`
- **frontend xss and dom safety**: `../audit-stack-detection/scripts/detect_stack.py`, `../audit-code-scan/scripts/grep_scan.py`, `../audit-finding-writer/scripts/findings.py`; evidence: `audit/evidence/audit-frontend-xss-and-dom-safety/hits.json`
- **injection vulnerabilities**: `../audit-stack-detection/scripts/detect_stack.py`, `../audit-code-scan/scripts/grep_scan.py`, `../audit-finding-writer/scripts/findings.py`; evidence: `audit/evidence/audit-injection-vulnerabilities/hits.json`
- **multi tenant isolation**: `../audit-stack-detection/scripts/detect_stack.py`, `../audit-code-scan/scripts/grep_scan.py`, `../audit-finding-writer/scripts/findings.py`; evidence: `audit/evidence/audit-multi-tenant-isolation/hits.json`
- **performance and scalability**: `../audit-stack-detection/scripts/detect_stack.py`, `../audit-code-scan/scripts/grep_scan.py`, `../audit-finding-writer/scripts/findings.py`; evidence: `audit/evidence/audit-performance-and-scalability/hits.json`
- **production readiness checklist**: `../audit-stack-detection/scripts/detect_stack.py`, `../audit-code-scan/scripts/grep_scan.py`, `../audit-finding-writer/scripts/findings.py`; evidence: `audit/evidence/audit-production-readiness-checklist/hits.json`

## Appendix C. Excluded false positives

| Id | Area | Title | Why excluded |
|---|---|---|---|
| XSS-001 | frontend xss and dom safety | Inline template in AppComponent flagged as innerHTML-like | Static template, no user data; not exploitable. |

## Appendix D. ASVS control detail and per-finding mapping

#### ASVS controls (level <= 1, plus any control a finding names)

| Control | Level | Name | Status | Linked findings |
|---|---|---|---|---|
| ASVS-2.1.1 | L1 | Passwords are at least 12 characters | Not assessed | - |
| ASVS-2.2.1 | L1 | Anti-automation controls against credential stuffing and brute force | Failed | AUTHZ-002 |
| ASVS-2.4.1 | L1 | Passwords stored with an approved one-way key derivation function | Not assessed | - |
| ASVS-3.2.1 | L1 | New session token generated on authentication | Not assessed | - |
| ASVS-3.2.3 | L1 | Session tokens stored in the browser using secure methods | Not assessed | - |
| ASVS-3.3.1 | L1 | Logout and expiration invalidate the session token | Not assessed | - |
| ASVS-3.3.2 | L1 | Re-authentication or idle timeout enforced | Not assessed | - |
| ASVS-3.4.1 | L1 | Cookie-based session tokens have the Secure attribute | Not assessed | - |
| ASVS-3.4.2 | L1 | Cookie-based session tokens have the HttpOnly attribute | Not assessed | - |
| ASVS-3.4.3 | L1 | Cookie-based session tokens use SameSite | Not assessed | - |
| ASVS-3.5.3 | L2 | Stateless session tokens are signed and integrity-protected | Failed | AUTHZ-002 |
| ASVS-4.1.1 | L1 | Access control rules enforced on a trusted service layer | Failed | AUTHZ-002 |
| ASVS-4.1.2 | L1 | Attributes used by access control cannot be manipulated by end users | Verified | - |
| ASVS-4.1.3 | L1 | Principle of least privilege | Failed | AUTHZ-001, TENANT-001 |
| ASVS-4.1.5 | L1 | Access controls fail securely | Verified | - |
| ASVS-4.2.1 | L1 | Sensitive data and APIs protected against Insecure Direct Object Reference | Failed | AUTHZ-001, TENANT-001 |
| ASVS-4.2.2 | L1 | Application enforces strong anti-CSRF mechanism | Verified | - |
| ASVS-4.3.1 | L1 | Administrative interfaces use appropriate multi-factor authentication | Verified | - |
| ASVS-5.1.2 | L1 | Frameworks protect against mass parameter assignment | Verified | - |
| ASVS-5.1.3 | L1 | All input is validated using positive validation | Verified | - |
| ASVS-5.1.5 | L1 | URL redirects and forwards only allow allow-listed destinations | Verified | - |
| ASVS-5.2.4 | L1 | Dynamic code execution (eval) is avoided | Verified | - |
| ASVS-5.2.5 | L1 | Template injection attacks are prevented | Verified | - |
| ASVS-5.2.6 | L1 | SSRF prevented by validating untrusted data | Verified | - |
| ASVS-5.3.1 | L1 | Output encoding is relevant for the interpreter and context | Verified | - |
| ASVS-5.3.3 | L1 | Context-aware output escaping protects against XSS | Verified | - |
| ASVS-5.3.4 | L1 | Data selection or database queries use parameterized queries | Verified | - |
| ASVS-5.3.5 | L1 | Where parameterization is not possible, interpreter-specific escaping is used | Verified | - |
| ASVS-5.3.8 | L1 | Application protects against OS command injection | Verified | - |
| ASVS-5.3.9 | L1 | Application protects against local/remote file inclusion | Verified | - |
| ASVS-5.3.10 | L1 | Application protects against XPath and XML injection | Verified | - |
| ASVS-5.5.1 | L1 | Serialized objects use integrity checks or are encrypted | Verified | - |
| ASVS-5.5.2 | L1 | XML parsers configured to prevent XXE | Verified | - |
| ASVS-5.5.3 | L1 | Deserialization of untrusted data is avoided or protected | Verified | - |
| ASVS-7.1.1 | L1 | Application does not log credentials or payment details | Not assessed | - |
| ASVS-7.1.2 | L1 | Application does not log other sensitive data | Not assessed | - |
| ASVS-7.4.1 | L1 | Generic message shown on unexpected error | Not assessed | - |
| ASVS-8.2.2 | L1 | Data stored in browser storage does not contain sensitive data | Not assessed | - |
| ASVS-8.3.1 | L1 | Sensitive data sent in HTTP body or headers, not query string | Not assessed | - |
| ASVS-8.3.2 | L1 | Users can remove or export their personal data | Not assessed | - |
| ASVS-8.3.4 | L1 | Sensitive data identified, classified and protected | Not assessed | - |
| ASVS-9.1.1 | L1 | TLS used for all client connectivity | Not assessed | - |
| ASVS-10.3.2 | L1 | Application uses integrity protections such as code signing or SRI | Verified | - |
| ASVS-11.1.1 | L1 | Business logic flows processed only in sequential step order | Failed | BIZ-001 |
| ASVS-11.1.2 | L1 | Business logic flows require realistic human timing | Failed | BIZ-001 |
| ASVS-11.1.4 | L1 | Anti-automation controls protect business logic | Failed | BIZ-001, DEP-001 |
| ASVS-11.1.6 | L2 | Sensitive operations are thread safe and TOCTOU-resistant | Failed | RACE-001 |
| ASVS-12.1.1 | L1 | Large file uploads are rejected | Failed | DEP-001 |
| ASVS-12.2.1 | L1 | Uploaded files match their expected type | Not assessed | - |
| ASVS-12.3.1 | L1 | User-submitted file metadata cannot be used for path traversal | Not assessed | - |
| ASVS-12.6.1 | L1 | Web or application server has an allow list for outbound connections (SSRF) | Verified | - |
| ASVS-13.2.3 | L1 | RESTful web services that use cookies are protected from CSRF | Not assessed | - |
| ASVS-14.1.1 | L? | (not in catalogue; see ASVS 4.0.3) | Failed | READY-001 |
| ASVS-14.2.1 | L1 | All components are up to date | Verified | - |
| ASVS-14.2.3 | L1 | Externally hosted assets use Subresource Integrity | Verified | - |
| ASVS-14.3.2 | L1 | Debug modes disabled in production | Verified | - |
| ASVS-14.3.3 | L1 | HTTP headers or responses do not expose component versions | Verified | - |
| ASVS-14.4.3 | L1 | Content-Security-Policy header set | Verified | - |
| ASVS-14.4.4 | L1 | X-Content-Type-Options: nosniff set | Verified | - |
| ASVS-14.4.5 | L1 | Strict-Transport-Security header set on all responses | Verified | - |
| ASVS-14.4.6 | L1 | Referrer-Policy header set | Verified | - |
| ASVS-14.4.7 | L1 | X-Frame-Options or CSP frame-ancestors set | Verified | - |
| ASVS-14.5.3 | L1 | CORS Access-Control-Allow-Origin uses a strict allow list | Not assessed | - |

#### Per-finding mapping

| Finding | Skill | Severity | OWASP Top 10 | ASVS | CWE | Rule | Matched by |
|---|---|---|---|---|---|---|---|
| AUTHZ-002 | audit-authz-and-access-control | Critical | OWASP-A07:2021 | ASVS-3.5.3, ASVS-4.1.1, ASVS-2.2.1 | CWE-287 | missing-authentication | cwe:CWE-287 |
| AUTHZ-001 | audit-authz-and-access-control | High | OWASP-A01:2021 | ASVS-4.2.1, ASVS-4.1.3 | CWE-639 | idor | cwe:CWE-639 |
| BIZ-001 | audit-business-logic | High | OWASP-A04:2021 | ASVS-11.1.1, ASVS-11.1.2, ASVS-11.1.4 | CWE-841 | business-logic | cwe:CWE-841 |
| READY-001 | audit-production-readiness-checklist | High | - | ASVS-14.1.1 | - | - |  |
| TENANT-001 | audit-multi-tenant-isolation | High | OWASP-A01:2021 | ASVS-4.2.1, ASVS-4.1.3 | CWE-639 | idor | cwe:CWE-639 |
| DEP-001 | audit-dependency-vulnerabilities | Medium | OWASP-A06:2021 | ASVS-12.1.1, ASVS-11.1.4 | CWE-400 | resource-exhaustion | cwe:CWE-400 |
| RACE-001 | audit-concurrency-and-race-condition | Medium | OWASP-A04:2021 | ASVS-11.1.6 | CWE-362 | race-condition | cwe:CWE-362 |
| PERF-001 | audit-performance-and-scalability | Low | - | - | CWE-1176 | - |  |
| TIME-001 | audit-datetime-and-timezone | Low | - | - | CWE-1339 | - |  |

#### Unmapped findings (no security standard applies, or the rule table needs a new entry)

- none

#### ASVS sections not assessed

- V1.1 Secure Software Development Lifecycle
- V1.2 Authentication Architecture
- V1.5 Input and Output Architecture
- V1.6 Cryptographic Architecture
- V1.7 Errors, Logging and Auditing Architecture
- V1.8 Data Protection and Privacy Architecture
- V1.9 Communications Architecture
- V1.10 Malicious Software Architecture
- V1.11 Business Logic Architecture
- V1.12 Secure File Upload Architecture
- V1.14 Configuration Architecture
- V2.1 Password Security
- V2.3 Authenticator Lifecycle
- V2.4 Credential Storage
- V2.5 Credential Recovery
- V2.6 Look-up Secret Verifier
- V2.7 Out of Band Verifier
- V2.8 One Time Verifier
- V2.9 Cryptographic Verifier
- V2.10 Service Authentication
- V3.1 Fundamental Session Management Security
- V3.2 Session Binding
- V3.3 Session Termination
- V3.4 Cookie-based Session Management
- V3.6 Federated Re-authentication
- V3.7 Defenses Against Session Management Exploits
- V5.4 Memory, String, and Unmanaged Code
- V6.1 Data Classification
- V6.2 Algorithms
- V6.3 Random Values
- V6.4 Secret Management
- V7.1 Log Content
- V7.2 Log Processing
- V7.3 Log Protection
- V7.4 Error Handling
- V8.1 General Data Protection
- V8.2 Client-side Data Protection
- V8.3 Sensitive Private Data
- V9.1 Client Communication Security
- V9.2 Server Communication Security
- V10.1 Code Integrity
- V10.2 Malicious Code Search
- V12.2 File Integrity
- V12.3 File Execution
- V12.4 File Storage
- V12.5 File Download
- V13.1 Generic Web Service Security
- V13.2 RESTful Web Service
- V13.3 SOAP Web Service
- V13.4 GraphQL
- V14.5 HTTP Request Header Validation

#### Not checked

- Statuses come from audit/status/*.json and the presence of findings files; a skill that ran but did not write a status file is treated as completed.
- 'Verified' means a covering skill completed without a failing finding; it is not a claim that every control in the section was individually tested. Check the skill's own scope.checked list.
- ASVS levels 2 and 3 controls are listed only when a finding names them (raise --min-level to list more).

## Appendix E. Source files

- `audit/findings/audit-authz-and-access-control.json` (2 findings, generated 2026-09-11T12:23:24.541732+00:00)
- `audit/findings/audit-business-logic.json` (1 findings, generated 2026-09-11T12:23:30.044621+00:00)
- `audit/findings/audit-concurrency-and-race-condition.json` (1 findings, generated 2026-09-11T12:23:31.045839+00:00)
- `audit/findings/audit-datetime-and-timezone.json` (1 findings, generated 2026-09-11T12:23:32.002277+00:00)
- `audit/findings/audit-dependency-vulnerabilities.json` (1 findings, generated 2026-09-11T12:23:26.790645+00:00)
- `audit/findings/audit-frontend-xss-and-dom-safety.json` (1 findings, generated 2026-09-11T12:23:28.686310+00:00)
- `audit/findings/audit-injection-vulnerabilities.json` (0 findings, generated 2026-09-11T12:23:27.802215+00:00)
- `audit/findings/audit-multi-tenant-isolation.json` (1 findings, generated 2026-09-11T12:23:25.453358+00:00)
- `audit/findings/audit-owasp-asvs-mapper.json` (1 findings, generated 2026-09-11T12:23:35.264491+00:00)
- `audit/findings/audit-performance-and-scalability.json` (1 findings, generated 2026-09-11T12:23:32.891415+00:00)
- `audit/findings/audit-production-readiness-checklist.json` (1 findings, generated 2026-09-11T12:23:33.932701+00:00)
- `audit/status/audit-accessibility-and-i18n.json` (skipped)
- `audit/status/audit-api-contract.json` (skipped)
- `audit/status/audit-async-and-dependency-injection.json` (skipped)
- `audit/status/audit-authz-and-access-control.json` (completed)
- `audit/status/audit-backend-resource-leak.json` (skipped)
- `audit/status/audit-business-logic.json` (completed)
- `audit/status/audit-client-auth-and-storage.json` (skipped)
- `audit/status/audit-concurrency-and-race-condition.json` (completed)
- `audit/status/audit-datetime-and-timezone.json` (completed)
- `audit/status/audit-db-schema.json` (skipped)
- `audit/status/audit-dependency-vulnerabilities.json` (completed)
- `audit/status/audit-frontend-best-practices.json` (skipped)
- `audit/status/audit-frontend-memory-leak.json` (skipped)
- `audit/status/audit-frontend-xss-and-dom-safety.json` (completed)
- `audit/status/audit-gdpr-data-protection.json` (skipped)
- `audit/status/audit-infra-and-deployment.json` (skipped)
- `audit/status/audit-injection-vulnerabilities.json` (completed)
- `audit/status/audit-licensing-and-compliance.json` (skipped)
- `audit/status/audit-logging-and-observability.json` (skipped)
- `audit/status/audit-multi-tenant-isolation.json` (completed)
- `audit/status/audit-orm-query-and-data-access.json` (skipped)
- `audit/status/audit-owasp-asvs-mapper.json` (completed)
- `audit/status/audit-performance-and-scalability.json` (completed)
- `audit/status/audit-privacy-data-flow-mapper.json` (skipped)
- `audit/status/audit-production-readiness-checklist.json` (completed)
- `audit/status/audit-secrets-and-config.json` (failed)
- `audit/status/audit-security-headers-and-middleware.json` (skipped)
- `audit/status/audit-soc2-controls-evidence.json` (skipped)
- `audit/status/audit-system-design.json` (skipped)
- `audit/status/audit-technical-debt.json` (skipped)
- `audit/status/audit-test-coverage-and-ci.json` (skipped)
