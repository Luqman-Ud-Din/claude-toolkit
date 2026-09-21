# OWASP ASVS 4.0.3 chapters and sections

The complete section list the coverage matrix iterates over (mirrored in
`scripts/mapping.json` `asvs_sections`). A section with no finding *and* no completed
skill in `skill_coverage` is reported as **Not assessed** - never silently as a pass.
Section numbers with gaps (V1.3, V1.13) are intentionally empty in ASVS 4.0.3.

| Chapter | Section | Name | Typically assessed by |
|---|---|---|---|
| V1 Architecture, Design and Threat Modeling | V1.1 | Secure Software Development Lifecycle | audit-test-coverage-and-ci |
| | V1.2 | Authentication Architecture | (manual) |
| | V1.4 | Access Control Architecture | audit-authz-and-access-control |
| | V1.5 | Input and Output Architecture | (manual) |
| | V1.6 | Cryptographic Architecture | (manual) |
| | V1.7 | Errors, Logging and Auditing Architecture | (manual) |
| | V1.8 | Data Protection and Privacy Architecture | audit-gdpr-data-protection, audit-privacy-data-flow-mapper |
| | V1.9 | Communications Architecture | (manual) |
| | V1.10 | Malicious Software Architecture | (manual) |
| | V1.11 | Business Logic Architecture | (manual) |
| | V1.12 | Secure File Upload Architecture | (manual) |
| | V1.14 | Configuration Architecture | (manual) |
| V2 Authentication | V2.1 | Password Security | (manual; brute-force/policy findings land here) |
| | V2.2 | General Authenticator Security | (manual) |
| | V2.3 | Authenticator Lifecycle | (manual) |
| | V2.4 | Credential Storage | (manual; password-storage findings) |
| | V2.5 | Credential Recovery | (manual) |
| | V2.6 | Look-up Secret Verifier | (manual) |
| | V2.7 | Out of Band Verifier | (manual) |
| | V2.8 | One Time Verifier | (manual) |
| | V2.9 | Cryptographic Verifier | (manual) |
| | V2.10 | Service Authentication | audit-secrets-and-config |
| V3 Session Management | V3.1 | Fundamental Session Management Security | (manual) |
| | V3.2 | Session Binding | audit-client-auth-and-storage |
| | V3.3 | Session Termination | audit-client-auth-and-storage |
| | V3.4 | Cookie-based Session Management | audit-security-headers-and-middleware |
| | V3.5 | Token-based Session Management | audit-client-auth-and-storage |
| | V3.6 | Federated Re-authentication | (manual) |
| | V3.7 | Defenses Against Session Management Exploits | (manual) |
| V4 Access Control | V4.1 | General Access Control Design | audit-authz-and-access-control, audit-multi-tenant-isolation |
| | V4.2 | Operation Level Access Control | audit-authz-and-access-control, audit-multi-tenant-isolation |
| | V4.3 | Other Access Control Considerations | audit-authz-and-access-control |
| V5 Validation, Sanitization and Encoding | V5.1 | Input Validation | audit-injection-vulnerabilities, audit-api-contract |
| | V5.2 | Sanitization and Sandboxing | audit-injection-vulnerabilities |
| | V5.3 | Output Encoding and Injection Prevention | audit-injection-vulnerabilities, audit-frontend-xss-and-dom-safety, audit-orm-query-and-data-access |
| | V5.4 | Memory, String, and Unmanaged Code | (manual; rarely applicable to managed stacks) |
| | V5.5 | Deserialization Prevention | audit-injection-vulnerabilities |
| V6 Stored Cryptography | V6.1 | Data Classification | (manual) |
| | V6.2 | Algorithms | (manual; weak-crypto findings) |
| | V6.3 | Random Values | (manual) |
| | V6.4 | Secret Management | audit-secrets-and-config |
| V7 Error Handling and Logging | V7.1 | Log Content | audit-logging-and-observability |
| | V7.2 | Log Processing | audit-logging-and-observability |
| | V7.3 | Log Protection | audit-logging-and-observability |
| | V7.4 | Error Handling | audit-logging-and-observability |
| V8 Data Protection | V8.1 | General Data Protection | audit-gdpr-data-protection |
| | V8.2 | Client-side Data Protection | audit-client-auth-and-storage |
| | V8.3 | Sensitive Private Data | audit-gdpr-data-protection, audit-privacy-data-flow-mapper |
| V9 Communication | V9.1 | Client Communication Security | audit-security-headers-and-middleware |
| | V9.2 | Server Communication Security | audit-infra-and-deployment |
| V10 Malicious Code | V10.1 | Code Integrity | (manual) |
| | V10.2 | Malicious Code Search | (manual) |
| | V10.3 | Application Integrity | audit-dependency-vulnerabilities, audit-infra-and-deployment |
| V11 Business Logic | V11.1 | Business Logic Security | audit-business-logic, audit-concurrency-and-race-condition |
| V12 Files and Resources | V12.1 | File Upload | (manual) |
| | V12.2 | File Integrity | (manual) |
| | V12.3 | File Execution | (manual; path-traversal findings) |
| | V12.4 | File Storage | (manual) |
| | V12.5 | File Download | (manual) |
| | V12.6 | SSRF Protection | audit-injection-vulnerabilities |
| V13 API and Web Service | V13.1 | Generic Web Service Security | audit-api-contract |
| | V13.2 | RESTful Web Service | audit-api-contract, audit-security-headers-and-middleware |
| | V13.3 | SOAP Web Service | (manual; N/A for most) |
| | V13.4 | GraphQL | (manual; N/A unless GraphQL present) |
| V14 Configuration | V14.1 | Build and Deploy | audit-secrets-and-config, audit-infra-and-deployment, audit-test-coverage-and-ci |
| | V14.2 | Dependency | audit-dependency-vulnerabilities, audit-licensing-and-compliance |
| | V14.3 | Unintended Security Disclosure | audit-secrets-and-config, audit-production-readiness-checklist |
| | V14.4 | HTTP Security Headers | audit-security-headers-and-middleware, audit-frontend-xss-and-dom-safety |
| | V14.5 | HTTP Request Header Validation | audit-security-headers-and-middleware |

## Recording a manual check

A section marked "(manual)" becomes Verified when any findings.json lists it in
`scope.checked` using the exact spelling `ASVS-<n>.<m>` (section) or `ASVS-<n>.<m>.<k>`
(control), for example:

```json
"scope": {"checked": ["ASVS-2.1 verified: password policy in Identity options is 12+ chars, breached-password check via HIBP"]}
```

Marking a section N/A (SOAP, GraphQL, unmanaged code) is done the same way with the word
"N/A" in the text; the matrix shows it as Verified with the note visible in the report.

## Levels

- **L1** - opportunistic; every internet-facing app. Default listing in the matrix.
- **L2** - applications holding sensitive data (most SaaS). Run `map_findings.py --min-level 2`.
- **L3** - critical (medical, financial, high-value). `--min-level 3`.

Only controls named in `scripts/mapping.json` `controls` (about 70 L1/L2 controls that
findings commonly hit) are listed individually; the full 286-control checklist is at
https://github.com/OWASP/ASVS/tree/v4.0.3 and should be attached as evidence when a full
ASVS assessment is claimed.
