# Mapping table: finding -> OWASP Top 10 2021 -> ASVS 4.0 -> CWE

Human-readable twin of `scripts/mapping.json` (the script is authoritative; keep both
in sync when adding a rule). Each row is a rule. A finding is matched by scoring:
+3 when one of its existing `CWE-` references is in the rule's CWE list, +2 when one of
its `tags` is in the rule's tag list, +1 per keyword (max 2) found in title/impact/
evidence/remediation. Highest score wins; ties go to the earlier row.

Levels: L1 = every application, L2 = applications handling sensitive data, L3 = critical.
The mapper adds the rule's ASVS ids regardless of level and shows the level in the matrix.

| Rule | Match on (CWE / tags / keywords) | OWASP 2021 | ASVS 4.0 controls (level) | Canonical CWE |
|---|---|---|---|---|
| cross-tenant | CWE-284/285/863; `tenant`, `cross-tenant`; "another tenant", "tenant filter" | A01 | 4.1.3 (L1), 4.2.1 (L1), 4.1.2 (L1) | CWE-284 |
| idor | CWE-639/862; `idor`, `bola`, `ownership`; "ownership check", "other users'", "changing the id" | A01 | 4.2.1 (L1), 4.1.3 (L1) | CWE-639 |
| client-side-enforcement | CWE-602; `client-side-check`; "guard only", "enforced only in the browser" | A01 | 4.1.1 (L1) | CWE-602 |
| privilege-escalation | CWE-269/266/250; `privilege-escalation`, `role`; "escalate", "own role", "become admin" | A01 | 4.1.3 (L1), 4.1.2 (L1) | CWE-269 |
| missing-authentication | CWE-306/287; `unauthenticated`, `anonymous`; "allowanonymous", "permitall", "no authentication" | A07 | 4.1.1 (L1), 2.2.1 (L1) | CWE-306 |
| mass-assignment | CWE-915; `mass-assignment`, `overposting`; "binds the entity", "hidden field" | A04 | 5.1.2 (L1), 4.1.2 (L1) | CWE-915 |
| csrf | CWE-352; `csrf`; "antiforgery" | A01 | 4.2.2 (L1), 13.2.3 (L1) | CWE-352 |
| cors | CWE-942; `cors`; "allowanyorigin", "access-control-allow" | A05 | 14.5.3 (L1) | CWE-942 |
| open-redirect | CWE-601; `open-redirect`; "returnurl", "redirect_uri" | A01 | 5.1.5 (L1) | CWE-601 |
| sql-injection | CWE-89/564; `sqli`; "fromsqlraw", "raw sql", "concatenated into the query" | A03 | 5.3.4 (L1), 5.3.5 (L1) | CWE-89 |
| nosql-ldap-xpath-injection | CWE-943/90/643/91; "nosql injection", "$where", "ldap injection" | A03 | 5.3.4 (L1), 5.3.10 (L1) | CWE-943 |
| os-command-injection | CWE-78/77; `command-injection`, `rce`; "process.start", "child_process", "os.system" | A03 | 5.3.8 (L1) | CWE-78 |
| code-injection | CWE-94/95/1336; `eval`, `template-injection`; "eval(", "new function(" | A03 | 5.2.4 (L1), 5.2.5 (L1) | CWE-94 |
| path-traversal | CWE-22/23/98; `path-traversal`, `lfi`; "directory traversal", "../" | A01 | 12.3.1 (L1), 5.3.9 (L1) | CWE-22 |
| xss | CWE-79/80/116; `xss`, `dom-xss`; "innerhtml", "dangerouslysetinnerhtml", "bypasssecuritytrust", "v-html" | A03 | 5.3.3 (L1), 5.3.1 (L1) | CWE-79 |
| ssrf | CWE-918; `ssrf`; "user-controlled url" | A10 | 12.6.1 (L1), 5.2.6 (L1) | CWE-918 |
| deserialization | CWE-502; `deserialization`; "binaryformatter", "typenamehandling", "pickle.load" | A08 | 5.5.3 (L1), 5.5.1 (L1) | CWE-502 |
| xxe | CWE-611/776; `xxe`; "external entity", "dtdprocessing" | A05 | 5.5.2 (L1) | CWE-611 |
| hardcoded-key | CWE-321; `signing-key`, `crypto-key`; "signing key", "jwt key", "encryption key" | A02 | 2.10.4 (L2), 6.4.1 (L2) | CWE-321 |
| hardcoded-credential | CWE-798/259/540; `secret`, `credential`; "hard-coded", "api key", "connection string", "committed" | A07 | 2.10.4 (L2), 6.4.1 (L2) | CWE-798 |
| password-storage | CWE-916/256/257; `password-storage`; "plaintext password", "unsalted" | A02 | 2.4.1 (L1) | CWE-916 |
| weak-crypto | CWE-327/328/326/780; `weak-crypto`; "md5", "sha1", "3des", "ecb mode" | A02 | 6.2.2 (L2) | CWE-327 |
| insecure-randomness | CWE-330/338/331; `prng`; "math.random", "system.random", "new random(" | A02 | 6.3.1 (L2) | CWE-338 |
| hsts | (no CWE match); `hsts`; "strict-transport-security" | A05 | 14.4.5 (L1) | CWE-319 |
| cleartext-transmission | CWE-319/311/295; `tls`, `cleartext`; "plain http", "certificate validation", "rejectunauthorized: false" | A02 | 9.1.1 (L1), 9.2.1 (L2) | CWE-319 |
| csp | (no CWE match); `csp`; "content-security-policy", "unsafe-inline" | A05 | 14.4.3 (L1) | CWE-693 |
| clickjacking | CWE-1021; `clickjacking`; "x-frame-options", "frame-ancestors" | A05 | 14.4.7 (L1) | CWE-1021 |
| security-headers | CWE-693/16; `headers`, `nosniff`, `referrer-policy`; "x-content-type-options", "permissions-policy" | A05 | 14.4.4 (L1), 14.4.6 (L1) | CWE-693 |
| cookie-flags | CWE-614/1004/1275; `cookie`; "httponly", "samesite", "secure flag" | A05 | 3.4.1, 3.4.2, 3.4.3 (all L1) | CWE-614 |
| client-storage | CWE-922/312/315; `localstorage`, `client-storage`; "sessionstorage", "stored in the browser" | A02 | 3.2.3 (L1), 8.2.2 (L1) | CWE-922 |
| jwt-validation | CWE-347/345; `jwt`; "alg none", "validateissuer", "signature not verified" | A02 | 3.5.3 (L2), 3.5.2 (L2) | CWE-347 |
| session-management | CWE-613/384/1018; `session`, `logout`; "never expires", "not invalidated", "refresh token" | A07 | 3.3.1 (L1), 3.3.2 (L1), 3.2.1 (L1) | CWE-613 |
| brute-force | CWE-307/521/1391; `brute-force`, `lockout`; "credential stuffing", "password policy" | A07 | 2.2.1 (L1), 2.1.1 (L1) | CWE-307 |
| missing-mfa-admin | CWE-308; `mfa`, `2fa`; "multi-factor" | A07 | 4.3.1 (L1) | CWE-308 |
| vulnerable-dependency | CWE-1104/1395/937; `dependency`, `cve`, `outdated`; "cve-", "npm audit", "end of life" | A06 | 14.2.1 (L1) | CWE-1104 |
| integrity | CWE-353/494/829/830; `sri`, `supply-chain`; "subresource integrity", "unpinned action" | A08 | 14.2.3 (L1), 10.3.2 (L1) | CWE-829 |
| verbose-errors | CWE-209/215/550/497; `stack-trace`, `debug`; "developer exception page", "x-powered-by", "swagger exposed" | A05 | 14.3.2 (L1), 7.4.1 (L1), 14.3.3 (L1) | CWE-209 |
| information-disclosure | CWE-200/201/538; `info-disclosure`; "over-fetching", "returns all fields" | A01 | 8.3.4 (L1), 4.1.3 (L1) | CWE-200 |
| sensitive-data-in-logs | CWE-532; `pii-in-logs`, `secrets-in-logs`; "logs the password", "token in log" | A09 | 7.1.1 (L1), 7.1.2 (L1) | CWE-532 |
| insufficient-logging | CWE-778/223; `audit-log`, `monitoring`; "no audit log", "failed logins are not" | A09 | 7.2.1 (L2), 7.2.2 (L2) | CWE-778 |
| unhandled-exception | CWE-755/248/390; `exception-handling`; "empty catch", "no global exception handler" | A05 | 7.4.2 (L2), 7.4.1 (L1) | CWE-755 |
| input-validation | CWE-20/1284/129; `validation`; "not validated", "no length limit", "negative quantity" | A03 | 5.1.3 (L1) | CWE-20 |
| file-upload | CWE-434/646; `upload`; "file type check", "webshell" | A04 | 12.2.1 (L1), 12.1.1 (L1) | CWE-434 |
| resource-exhaustion | CWE-400/770/405/409/1050; `dos`, `pagination`, `rate-limit`; "no paging", "unbounded", "redos" | A04 | 12.1.1 (L1), 11.1.4 (L1) | CWE-770 |
| race-condition | CWE-362/367/366; `race`, `toctou`; "double spend", "check-then-act", "lost update" | A04 | 11.1.6 (L2) | CWE-362 |
| business-logic | CWE-840/841/799; `business-logic`, `workflow`; "step can be skipped", "price from the client" | A04 | 11.1.1, 11.1.2, 11.1.4 (all L1) | CWE-840 |
| privacy | CWE-359/212; `gdpr`, `pii`, `retention`, `consent`; "personal data", "right to erasure" | - (compliance) | 8.3.2 (L1), 8.3.4 (L1), 8.3.1 (L1) | CWE-359 |
| misconfiguration | CWE-1188/276/732; `config`, `misconfiguration`; "default credential", "allowedhosts", "wildcard" | A05 | 14.3.2 (L1) | CWE-1188 |
| resource-leak | CWE-401/772/404/459; `leak`, `disposal`; "not disposed", "subscription leak" | - (non-security) | - | CWE-772 |

## Deliberate choices worth knowing

- **HSTS is A05, not A02.** The official OWASP list puts CWE-319 under A02, but a missing
  header is a server misconfiguration and the industry (and the spec test) expects A05. A
  finding with CWE-319 and no HSTS tag/keyword (for example a cleartext DB connection) still maps to A02.
- **Hard-coded credentials are A07** (CWE-798 is in the official A07 list); hard-coded
  *cryptographic keys* (CWE-321) are A02. `audit-finding-writer`'s example rates a JWT signing
  key as A02 - that is the `hardcoded-key` rule, matched by the "signing key" keyword.
- **Unauthenticated endpoints are A07** (CWE-306) even though the fix lives next to A01 code.
- **Mass assignment is A04** per OWASP's CWE-915 placement, with ASVS 5.1.2 as the control.
- **Privacy and leak rules have no Top 10 category.** They still get ASVS/CWE ids so the report can cite them.

## Adding a rule

1. Add the row here and the object in `scripts/mapping.json` (`rules` array; order matters for ties).
2. If it names a control not yet in `controls`, add it with its level and one-line name.
3. Re-run `python scripts/map_findings.py evals/files/sample-repo --dry-run` and check the three fixture findings still map to A01/4.2.1/639, A03/5.3.3/79, A05/14.4.5/319.
