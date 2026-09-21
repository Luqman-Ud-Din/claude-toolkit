# Severity rubric

Severity = exploitability × impact, in the spirit of CVSS but without the
arithmetic. Pick the row that fits, then write the one-line justification into
the Impact field so a reader can challenge it.

| Severity | Exploitability | Impact | Typical examples |
|---|---|---|---|
| **Critical** | Anyone (unauthenticated, or any tenant/user) can trigger it with no special conditions | Full compromise: all data, admin control, money movement, or total outage | Committed signing key or DB password; unauthenticated admin endpoint; SQL injection on a public route; cross-tenant read of all records; RCE via deserialization |
| **High** | An authenticated user, or an attacker who can get one, with little skill | Large-scale exposure or modification of other users' data; bypass of a core control | IDOR on customer records; role escalation via mass assignment; stored XSS in a shared page; missing tenant filter on a common query; secrets in logs shipped to a third party |
| **Medium** | Needs a specific precondition, a race, user interaction, or an already-privileged account | Limited data exposure, single-user impact, degraded availability, or a control that is weak rather than absent | Missing CSRF on a low-value form; unbounded list endpoint; reflected XSS needing a crafted link; N+1 on a hot path; timestamps stored in local time driving a billing cutoff |
| **Low** | Hard to exploit or requires chaining with another issue | Minor information leak, hardening gap, maintainability risk | Missing `X-Content-Type-Options`; verbose error pages behind auth; deprecated package with no known CVE; commented-out code |
| **Info** | Not exploitable | Observation, deviation from best practice, or a justified exception worth recording | Justified sanitizer bypass with prior sanitization; documentation drift; a suppression with a written reason |

## Adjustments

- Move **up one** when the affected data is regulated (payment, health, identity documents), when the flow moves money, or when the app is multi-tenant and the issue crosses tenants.
- Move **down one** when a compensating control exists and you verified it (WAF rule, network isolation, feature flag off in production). Name the control in Impact.
- Do not move down because "it is unlikely anyone would try". Attackers automate.
- `confidence: likely` does not lower severity; it flags that the trace is incomplete. Report the severity the finding would have if confirmed and ask the reviewer to confirm.

## Non-security skills

Quality, performance, accessibility, and debt skills use the same scale with
"impact" read as production risk or user harm:

- **Critical**: will cause an outage, data loss, or legal exposure at production load (unbounded memory growth in a singleton, a migration that drops a column, WCAG failure blocking a legally required flow).
- **High**: will visibly degrade the service or block a class of users (N+1 on the main list page, keyboard trap in checkout, DI captive dependency serving stale tenant data).
- **Medium**: measurable degradation or maintenance cost (missing index on a filtered column, subscription leak on a rarely visited page, 400-line function that changes weekly).
- **Low / Info**: as above.

## Words to avoid in Impact

"Could potentially", "may possibly", "theoretically". Say what happens, and if
you are unsure, say what you could not verify in `scope.not_checked`.
