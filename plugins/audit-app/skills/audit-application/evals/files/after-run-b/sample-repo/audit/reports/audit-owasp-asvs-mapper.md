## audit-owasp-asvs-mapper findings

Generated 2026-09-11T12:23:35.264491+00:00. Findings files: 11. Mapped findings: 9. Unmapped: 0. Findings files updated: 5.

### OWASP Top 10 (2021) coverage

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

### ASVS 4.0 coverage matrix (by section)

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

### ASVS controls (level <= 1, plus any control a finding names)

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

### Per-finding mapping

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

### Unmapped findings (no security standard applies, or the rule table needs a new entry)

- none

### ASVS sections not assessed

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

### Not checked

- Statuses come from audit/status/*.json and the presence of findings files; a skill that ran but did not write a status file is treated as completed.
- 'Verified' means a covering skill completed without a failing finding; it is not a claim that every control in the section was individually tested. Check the skill's own scope.checked list.
- ASVS levels 2 and 3 controls are listed only when a finding names them (raise --min-level to list more).
