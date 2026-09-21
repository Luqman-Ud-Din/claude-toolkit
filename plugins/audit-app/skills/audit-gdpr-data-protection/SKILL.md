---
name: audit-gdpr-data-protection
description: Technical, code-level GDPR / UK GDPR review (not legal advice) - builds or consumes the personal-data inventory, verifies consent capture (timestamp, version, revocation), checks that data-subject rights actually have working code paths (access, export/portability, erasure including downstream systems and backups, rectification, restriction/objection), that retention is enforced by scheduled jobs, that PII stays out of logs, URLs, error trackers and analytics, encryption in transit/at rest and pseudonymisation, access logging for PII, the processor list and cross-border transfers, breach detection sufficient for 72-hour notification, and privacy-by-design triggers; separates paperwork gaps as "outside code scope - needs organisational owner". Use when the user asks about GDPR, personal data, PII, privacy, data protection, data subject rights, right to be forgotten, erasure, consent, data retention, DPA/DPIA, EU/UK privacy compliance, or "are we GDPR compliant" - even when the user does not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: GDPR data protection

Checks what the code can prove about GDPR (and UK GDPR) obligations and says
plainly what it cannot. The output is an engineering gap list, not a legal
opinion: every item is either a code finding with a file and line, or an
organisational item handed to a named owner role.

Read-only rule: never modify the audited code. Write only under `audit/`.

## Inputs and prerequisites

- Repo root (default `.`). Standalone runs read `audit/stack.json` if present,
  otherwise run `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>` (without `--write`).
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection`,
  `audit-code-scan` (grep pass and the shared file walker), `audit-sensitive-data-catalog`
  (personal-data names in log, analytics and URL lines) and `audit-finding-writer`
  (findings I/O). The sibling `audit-privacy-data-flow-mapper` produces the inventory.
- The personal-data inventory from `audit-privacy-data-flow-mapper`:
  `audit/evidence/audit-privacy-data-flow-mapper/data-inventory.json`. If it is
  missing, `scripts/gdpr_check.py` runs the sibling scanner
  (`../audit-privacy-data-flow-mapper/scripts/pii_scan.py`) to create it; pass
  `--no-run-mapper` to skip and record the gap instead.
- Optional context from the team, used only to fill the organisational list:
  processor/DPA list, retention schedule, DPIA records, breach playbook. Absence
  is recorded, never assumed.
- Backups, DR copies and vendor consoles are outside the repo; erasure coverage
  of those is always an organisational item unless a script in the repo proves it.

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`; open only the
   matching `references/<stack>.md`. It names the framework idioms for consent
   models, deletion/export endpoints, scheduled jobs, audit trails, encryption
   settings and log scrubbing, and the false positives to expect.
2. **Automated pass.**
   - `python scripts/gdpr_check.py <repo> --out audit/evidence/audit-gdpr-data-protection/gdpr-checks.json --md audit/evidence/audit-gdpr-data-protection/rights-matrix.md`
     loads (or produces) the inventory and evaluates each technical check in
     `references/gdpr-article-map.md`: rights endpoints/jobs, consent shape,
     retention jobs, PII in logs/URLs/analytics (personal-data names from
     `audit-sensitive-data-catalog`), transport and at-rest
     encryption markers, audit trail, processors and regions, breach-detection
     signals, privacy-by-design artefacts. Each check gets `implemented |
     partial | missing | not-checked` with the evidence lines it found.
   - `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-gdpr-data-protection/hits.json`
     adds framework-specific candidates (consent booleans, analytics `identify`
     with traits, `send_default_pii`, `ssl: false`, `fields = '__all__'`, ...).
   A `missing` status from the script means "no code matched"; confirm by hand
   before writing the finding - naming is not uniform (a `forget` job may be
   called `Purge`).
3. **Manual trace of the highest-risk flows.** In priority order:
   - **Erasure**: follow the delete path end to end. Does it delete or
     anonymise the row, the child rows, files/uploads, cache entries, search
     indexes, queued jobs, and does it call each vendor's delete API
     (`third_parties` in the inventory)? Backups: is there a documented
     re-deletion after restore? (organisational unless scripted).
   - **Consent**: find the consent field(s). A bare boolean cannot prove *when*
     and *to what text* the user agreed; look for timestamp + policy version +
     source, and a revocation path that stops the downstream use (marketing
     sends, analytics identify).
   - **Retention**: for each storage location in the inventory, find the job
     that enforces a lifetime; note logs and backups separately.
   - **Minimisation**: every `log`, `url`, `analytics` processor in the inventory
     is a candidate finding; confirm the value is the PII, not an id.
   - **Export/portability**: an endpoint that returns the subject's data in a
     machine-readable format, callable by the subject or support.
   - **Breach readiness**: failed-login / privilege-change / bulk-read events
     logged with timestamp, actor, and shipped somewhere someone watches.
   Use the "Manual trace checklist" in the stack file.
4. **Write findings** with `python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py"` (prefix `GDPR`). One finding
   per root cause. Severity per `audit-finding-writer/references/severity-rubric.md`,
   with the regulated-data adjustment: no erasure path for a table of customers
   is High; PII in logs shipped off-host is High; consent without timestamp is
   Medium (High if marketing sends depend on it); missing HSTS is Low here
   (`audit-security-headers-and-middleware` owns the detail). Do not rate
   organisational items; they go in their own list.
5. **Emit outputs** (relative to the audited repo):
   - `audit/findings/audit-gdpr-data-protection.json`
   - `audit/reports/audit-gdpr-data-protection.md` (template below: inventory
     table, rights-fulfilment matrix, findings, organisational list, not checked)
   - `audit/evidence/audit-gdpr-data-protection/` - `gdpr-checks.json`,
     `rights-matrix.md`, `hits.json`, copies of consent models / deletion handlers
   - `audit/status/audit-gdpr-data-protection.json` -
     `{"skill": "...", "status": "completed|failed|skipped", "reason": "...", "started_at": "...", "finished_at": "..."}`
6. **Not checked.** Always include: backups and DR copies, vendor-side
   deletion and retention, infrastructure encryption (TDE, disk, KMS) unless IaC
   is in the repo, legal basis and lawful-basis records, DPIA existence, staff
   training, contracts/DPAs. Add every `not-checked` from `gdpr-checks.json`
   and anything the inventory listed under its own `not_checked`.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `GDPR`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Location:** `path/to/file.ext:LINE` (symbol)  - or `.` for repo-wide absence
- **Evidence:**

```lang
<the consent model, the route table with no DELETE, the log line, the analytics call>
```

- **Impact:** Plain language. Which right or principle cannot be honoured, for whom, and what happens on a request or a breach.
- **Remediation:** Concrete change in this stack: the endpoint/job to add, the columns to add to the consent model, the log call to change, the vendor delete API to call.
- **Reference:** GDPR-Art.17, GDPR-Art.7(1), GDPR-Art.5(1)(c), GDPR-Art.32, CWE-532, ASVS-8.3.x


Same content goes to `findings.json`; put the article numbers in `references`
(`GDPR-Art.nn`), the affected field names in `tags`, and `root_cause_key` =
`gdpr:<check-id>` (e.g. `gdpr:right-erasure`).

## Output template (`audit/reports/audit-gdpr-data-protection.md`)

```markdown
## audit-gdpr-data-protection

**Target:** <repo> @ <commit> - **Run:** <date> - **Stack:** node-express
**Scope note:** technical review of the code; not legal advice.

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| n | n | n | n | n |

### Personal-data inventory (from audit-privacy-data-flow-mapper)

| Field | Classification | Storage locations | Processors | Third parties | Retention |
|---|---|---|---|---|---|
| email | contact | table users | log, analytics | Segment | unknown - no purge job |

### Rights-fulfilment matrix

| Right / obligation | Article | Implemented | Endpoint / job / evidence | Notes |
|---|---|---|---|---|
| Access | Art.15 | Partial | `GET /api/users/:id` (users.routes.ts:13) | admin read; no self-service copy |
| Portability / export | Art.20 | N | - | no export endpoint or job found |
| Erasure | Art.17 | N | - | `DELETE /sessions/:token` is logout, not erasure |
| Rectification | Art.16 | Y | `PUT /api/users/:id` (users.routes.ts:18) | |
| Restriction / objection | Art.18/21 | N | - | no opt-out / do-not-contact flag |
| Consent capture (timestamp, version) | Art.7(1) | Partial | `marketingConsent: boolean` (user.model.ts:22) | boolean only |
| Consent withdrawal | Art.7(3) | N | - | |
| Retention enforcement | Art.5(1)(e) | N | - | no scheduled purge job |
| Minimisation (no PII in logs/URLs/analytics) | Art.5(1)(c) | N | user.service.ts:24, :26 | |
| Encryption in transit | Art.32 | Partial | `ssl: false` (data-source.ts:5) | |
| Encryption at rest / pseudonymisation | Art.32 | Not checked | - | infra-level; bcrypt for passwords found |
| Access logging for PII | Art.30/32 | N | - | no audit trail |
| Processor list / transfers | Art.28/44 | Partial | Segment (US) | DPA and SCCs organisational |
| Breach detection / logging | Art.33 | Partial | winston file transport | no security events, no alerting |
| Privacy by design triggers | Art.25 | N | - | no DPIA/privacy checklist in repo |

### Findings
<finding blocks, most severe first>

### Outside code scope - needs organisational owner

| Item | Article | Suggested owner | Why it cannot be verified in code |
|---|---|---|---|
| DPA with Segment; transfer mechanism (SCCs/DPF) | Art.28, 44-46 | DPO / Legal | contracts |
| Backup re-deletion after restore | Art.17 | Ops | backup system outside repo |
| Retention schedule and records of processing | Art.5(1)(e), 30 | DPO | policy |
| 72-hour breach notification runbook | Art.33/34 | Security lead | process |
| DPIA for new features touching PII | Art.35 | Product + DPO | process |

### Not checked
- <item> - <reason>
```

## Examples

**Input (gdpr-checks.json):**
`{"id": "right-erasure", "status": "missing", "evidence": [{"file": "src/routes/users.routes.ts", "line": 23, "snippet": "router.delete('/sessions/:token', ...)", "note": "excluded: session/token resource"}]}`

**Output:**
```markdown
### [High] GDPR-001 - No erasure path for user records
- **Location:** `src/routes/users.routes.ts` (users router)
- **Confidence:** confirmed
- **Evidence:**

```ts
router.post('/users', ...); router.get('/users/:id', ...); router.put('/users/:id', ...);
router.delete('/sessions/:token', ...)   // logout only; no DELETE /users, no anonymise job
```

- **Impact:** A right-to-erasure request cannot be fulfilled without a manual database change, and nothing removes the same person from Segment or from log files; the one-month deadline (Art.12(3)) is at risk for every request.
- **Remediation:** Add `DELETE /api/users/:id` (self or admin) that anonymises the `users` row (`email`, `phone`, names -> null/hash), deletes dependent rows, calls Segment's user-deletion API, and records the request; add a job that re-applies pending deletions after any backup restore.
- **Reference:** GDPR-Art.17, GDPR-Art.12(3), GDPR-Art.19
```

**Input (consent model):**
`@Column({ default: false }) marketingConsent: boolean;`

**Output:** `[Medium] GDPR-002 - Marketing consent stored as a bare boolean` with
remediation adding `consentGivenAt`, `consentVersion`, `consentSource` and a
withdrawal endpoint that also stops `analytics.identify` traits.

## Bundled files

- `references/gdpr-article-map.md` - article -> technical check -> what the
  script looks for -> status rules -> typical finding.
- `references/organisational-checklist.md` - items that are never provable from
  code, with the owner role and the article.
- `references/<stack>.md` - dotnet, java-spring, node-express, python-django,
  angular, react, vue; to add a stack, copy `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `scripts/gdpr_check.py` - loads/produces the inventory, runs the checks,
  writes `gdpr-checks.json` and the rights matrix. Walks files with `audit-code-scan`'s
  `repo_walk`; personal-data names come from `audit-sensitive-data-catalog`.
- `scripts/patterns/<stack>.json` - framework-specific candidates, run with `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`.
- Atomic scripts called: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`,
  `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`, `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`;
  imported: `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py`, `$AUDIT_CORE_ROOT/skills/audit-sensitive-data-catalog/scripts/catalog.py`.
- `evals/` - prompts and a fixture with PII in logs, no deletion endpoint, a
  boolean-only consent flag, email sent to an analytics SDK, and a logout
  DELETE route that must not count as erasure.
