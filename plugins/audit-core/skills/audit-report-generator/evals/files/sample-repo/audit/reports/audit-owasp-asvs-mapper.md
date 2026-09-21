## audit-owasp-asvs-mapper findings

Generated 2026-09-10T12:00:00Z. Findings files: 3. Mapped findings: 5. Unmapped: 0. Findings files updated: 0.

### OWASP Top 10 (2021) coverage

| Category | Status | Linked findings |
|---|---|---|
| A01:2021 Broken Access Control | Failed | AUTHZ-002, AUTHZ-003 |
| A05:2021 Security Misconfiguration | Failed | HDR-001, HDR-002 |
| A07:2021 Identification and Authentication Failures | Failed | AUTHZ-001 |
| A03:2021 Injection | Not assessed | - |

### ASVS 4.0 coverage matrix (by section)

| Section | Name | Status | Linked findings | Assessed by |
|---|---|---|---|---|
| V4.1 | General Access Control Design | Failed | AUTHZ-001 | audit-authz-and-access-control |
| V4.2 | Operation Level Access Control | Failed | AUTHZ-002, AUTHZ-003 | audit-authz-and-access-control |
| V14.4 | HTTP Security Headers | Failed | HDR-001, HDR-002 | audit-security-headers-and-middleware |
| V5.3 | Output Encoding and Injection Prevention | Not assessed | - | - |

### ASVS controls (level <= 1, plus any control a finding names)

| Control | Level | Name | Status | Linked findings |
|---|---|---|---|---|
| ASVS-4.1.1 | L1 | Access control rules enforced on a trusted service layer | Failed | AUTHZ-001 |
| ASVS-4.2.1 | L1 | Sensitive data and APIs protected against IDOR | Failed | AUTHZ-002, AUTHZ-003 |
| ASVS-14.4.5 | L1 | Strict-Transport-Security header set on all responses | Failed | HDR-001 |
