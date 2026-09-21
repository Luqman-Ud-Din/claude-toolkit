# Finding format and findings.json schema

This is the single contract every audit skill emits and `audit-report-generator`,
`audit-owasp-asvs-mapper`, `audit-technical-debt`, and
`audit-production-readiness-checklist` consume. Do not add required fields; add
optional ones under `tags` or `extra` instead so existing consumers keep working.

## File locations

| Artifact | Path |
|---|---|
| Machine-readable findings | `audit/findings/<skill-name>.json` |
| Markdown section | `audit/reports/<skill-name>.md` |
| Run status (orchestrator) | `audit/status/<skill-name>.json` |
| Evidence files | `audit/evidence/<skill-name>/...` |
| Stack detection | `audit/stack.json` |

All paths are relative to the audited repository root. `audit/` is the only
place a skill writes; the audited code is never modified.

## Markdown finding block

```markdown
### [High] AUTHZ-003 - Order lookup has no ownership check
- **Location:** `src/orders/orders.controller.ts:41` (getOrder)
- **Confidence:** confirmed
- **Evidence:**

```ts
const order = await this.repo.findOne(id); // id from route, no user filter
```

- **Impact:** Any authenticated customer can read every other customer's orders by changing the id in the URL.
- **Remediation:** Filter by the caller's identity: `findOne({ where: { id, customerId: req.user.id } })`, and return 404 (not 403) when the pair does not match.
- **Reference:** CWE-639, ASVS-4.2.1, OWASP-A01:2021
```

Field order is fixed so consumers can parse it; the wording inside each field is free.

## findings.json

```json
{
  "skill": "audit-authz-and-access-control",
  "generated_at": "2026-09-11T10:00:00Z",
  "target": {"root": "D:/repo", "commit": "abc123"},
  "stack": {"primary_backend": "dotnet", "primary_frontend": "angular"},
  "scope": {
    "checked": ["all controllers under Product.MicroAPI", "Ocelot routes"],
    "not_checked": [{"item": "Hangfire jobs", "reason": "no access to job server config"}]
  },
  "findings": [
    {
      "id": "AUTHZ-003",
      "title": "Order lookup has no ownership check",
      "severity": "High",
      "confidence": "confirmed",
      "location": {"file": "src/orders/orders.controller.ts", "line": 41, "symbol": "getOrder"},
      "evidence": "const order = await this.repo.findOne(id);",
      "impact": "Any authenticated customer can read every other customer's orders.",
      "remediation": "Filter by caller identity and return 404 on mismatch.",
      "references": ["CWE-639", "ASVS-4.2.1", "OWASP-A01:2021"],
      "tags": ["idor"],
      "root_cause_key": "orders.controller:missing-ownership-filter"
    }
  ],
  "summary": {"Critical": 0, "High": 1, "Medium": 0, "Low": 0, "Info": 0}
}
```

### Field rules

- `id`: `<PREFIX>-<NNN>`; prefix is the skill's short code (see the table below). Unique within the file.
- `severity`: exactly one of Critical, High, Medium, Low, Info. Use the rubric in `severity-rubric.md`.
- `confidence`: `confirmed` (traced to input, exploitable or definitely wrong), `likely` (pattern present, trace incomplete), `false-positive` (kept for transparency; excluded from counts and the report body).
- `location.line` may be omitted for repo-wide findings (for example "no CI security scan"); `file` then names the most relevant file or `.` for the repo.
- `references`: prefer `CWE-nnn`, `ASVS-x.y.z`, `OWASP-A0n:2021`, `WCAG-x.y.z`, `GDPR-Art.nn`, `SOC2-CCn.n`. Empty list is allowed only for non-security findings with no applicable standard; say so in `tags`.
- `root_cause_key`: optional, but set it when several findings share one fix so `audit-application` and `audit-report-generator` can de-duplicate across skills.

### Skill id prefixes

| Skill | Prefix |
|---|---|
| audit-authz-and-access-control | AUTHZ |
| audit-injection-vulnerabilities | INJ |
| audit-secrets-and-config | SEC |
| audit-security-headers-and-middleware | HDR |
| audit-frontend-xss-and-dom-safety | XSS |
| audit-client-auth-and-storage | CAUTH |
| audit-dependency-vulnerabilities | DEP |
| audit-multi-tenant-isolation | TENANT |
| audit-async-and-dependency-injection | ASYNC |
| audit-orm-query-and-data-access | ORM |
| audit-backend-resource-leak | LEAK |
| audit-frontend-best-practices | FEBP |
| audit-frontend-memory-leak | FELEAK |
| audit-accessibility-and-i18n | A11Y |
| audit-db-schema | DB |
| audit-concurrency-and-race-condition | RACE |
| audit-api-contract | API |
| audit-business-logic | BIZ |
| audit-datetime-and-timezone | TIME |
| audit-production-readiness-checklist | READY |
| audit-logging-and-observability | LOG |
| audit-test-coverage-and-ci | TEST |
| audit-infra-and-deployment | INFRA |
| audit-licensing-and-compliance | LIC |
| audit-owasp-asvs-mapper | MAP |
| audit-gdpr-data-protection | GDPR |
| audit-soc2-controls-evidence | SOC2 |
| audit-privacy-data-flow-mapper | PII |
| audit-finding-writer | FW |
| audit-report-generator | RPT |
| audit-performance-and-scalability | PERF |
| audit-application | APP |
| audit-system-design | ARCH |
| audit-technical-debt | DEBT |

## Atomic skills emit no findings

Six shared skills are infrastructure, not audit areas. They have no id prefix and never
write `audit/findings/<skill>.json`, `audit/reports/<skill>.md` or `audit/status/<skill>.json`;
they write only `audit/stack.json` or files under `audit/evidence/<skill>/`:

| Atomic skill | Writes |
|---|---|
| audit-stack-detection | `audit/stack.json` |
| audit-code-scan | `hits.json` / `hits.md` where the consumer points them |
| audit-endpoint-inventory | `audit/evidence/audit-endpoint-inventory/` |
| audit-findings-rollup | `audit/evidence/audit-findings-rollup/` (its `dedupe --write` only rewrites the file its caller names) |
| audit-sensitive-data-catalog | nothing (library and CLI) |
| audit-git-history | nothing, or the `--out` path its caller chooses |

Whatever they surface becomes a finding only when a consumer skill judges it and writes it
under its own prefix.

## Helper script

`scripts/findings.py` is owned by this skill (`audit-finding-writer`). It does `init`, `add`,
`validate`, `md`, and `summary`. Every other audit skill calls it as
`python ../audit-finding-writer/scripts/findings.py ...` rather than keeping a copy, so the
shape stays identical across skills.
