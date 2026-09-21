# SOC 2 Trust Services Criteria -> controls -> checks -> evidence

The control ids below are exactly the ids `scripts/soc2_matrix.py` emits, so the
matrix, the findings (`tags` and `root_cause_key` = `soc2:<control-id>`) and the
report line up. Criteria references follow the AICPA 2017 Trust Services Criteria
(revised points of focus 2022). This is a technical readiness map, not an
attestation; the service auditor decides what is sufficient.

## Status vocabulary

| Status | Meaning |
|---|---|
| implemented | Code/config in the repo (or an API snapshot) shows the control operating as designed; evidence artefact exported. |
| partial | Part of the control is visible (e.g. backups exist but no restore test; auth exists but MFA not visible). |
| missing | The repo or snapshot proves the control is absent or switched off (e.g. `protection: null`, no scan step in any pipeline). |
| organisational | The control is a process, policy or record outside code; it goes to the organisational-gaps list with an owner, never into findings. |
| not-checked | The evidence source was not reachable (gh not installed or not authenticated, no settings-as-code file, managed service console, sibling audit not run). |

**Never report `not-checked` as `missing`.** Branch protection with `gh` unavailable
and no `.github/settings.yml` / rulesets file is `not-checked`: say what evidence to
export, do not raise a finding. A finding needs proof of absence.

## Severity guidance for findings

| Gap proven by the repo | Severity |
|---|---|
| Branch protection off (no required review/status checks) on the production branch | High |
| No security scan (dependency/SAST/container) in any CI pipeline | Medium |
| Backups configured but no documented restore test | Medium (High if the app is the system of record and no DR plan exists) |
| Console-only logging in production with no central sink evidenced | Medium |
| Deploy job triggers on push to an unprotected production branch | High (root cause shared with branch protection; one finding, two locations) |
| Credential literals committed | High/Critical per audit-secrets-and-config |
| Organisational items (policies, reviews, training, vendor reports) | Not findings - organisational-gaps list |

Use `SOC2-CCn.n` / `SOC2-A1.n` in `references`; add CWE ids where the gap is technical.

## CC1-CC5 entity-level criteria

| Control id | Control | Technical check | Acceptable evidence artifact | Status rules |
|---|---|---|---|---|
| CC1-CC5-entity | Control environment, communication, risk assessment, monitoring activities, control activities | None - not visible in code | Board/management minutes, org chart, policy set, code of conduct acknowledgements | Always organisational |

## CC6 Logical and physical access

| Control id | Control | Technical check | Acceptable evidence artifact | Status rules |
|---|---|---|---|---|
| CC6.1-auth | Authentication with SSO and MFA for workforce/admin access | Open auth bootstrap (`Program.cs`, `SecurityFilterChain`, passport/NestJS guards, `AUTHENTICATION_BACKENDS`); grep for OIDC/SAML/IdP and MFA symbols | Auth config snapshot; IdP MFA/Conditional Access policy export | implemented: auth + SSO or MFA visible; partial: auth only, MFA not visible (IdP export requested); missing: no auth config |
| CC6.1-rbac | Role-based authorization enforced on endpoints (least privilege) | Grep role/policy attributes and guards; sample admin endpoints; check fallback/default deny | Controller/route listing with policies (audit-authz-and-access-control inventory) | implemented: role/policy checks across admin paths; partial: authenticated-only or sparse; missing: no guards |
| CC6.1-admin-log | Administrative and data-change actions logged (audit trail) | Grep `AuditLog`, SaveChanges interceptors, Envers `@Audited`, simple-history, subscribers | Audit-trail code + sample audit rows (Type 2) | implemented: mechanism covers admin actions; missing: none found |
| CC6.1-secrets | Secrets kept out of source control and managed centrally | Grep credential literals; find Key Vault/Secrets Manager/Vault/CI secrets usage | Secret-store config snapshot; gitleaks/trufflehog CI output | missing: credential literals committed; implemented: secrets from env/vault only; not-checked: no markers |
| CC6.1-key-rotation | Keys and credentials rotated on a schedule | Grep rotation logic, key versioning, KMS rotation in IaC (`rotation_period`, `enable_key_rotation`) | KMS/Key Vault rotation policy export; rotation log | partial: rotation config in IaC/code; organisational: none in repo |
| CC6.2-provisioning | User provisioning approved and documented | None in code beyond invite/registration flows | Access request tickets with approvals | organisational |
| CC6.2-access-review | Periodic user access reviews with sign-off | Optional: `gh api repos/{slug}/collaborators` snapshot to seed the review | Signed quarterly review records | organisational |
| CC6.3-deprovisioning | Timely removal of access on role change/offboarding | Grep deactivate/lockout/token revocation paths; confirm sessions/tokens die immediately | Deactivation code + HR-triggered offboarding tickets | partial: code path exists; organisational: none in code |
| CC6.7-transit | Data encrypted in transit | Grep `UseHttpsRedirection`/`UseHsts`, `Encrypt=True`, `sslmode=require`, TLS listeners in IaC | Config snapshot; TLS scan of public endpoints | implemented: markers found; not-checked: TLS terminated outside repo (infra evidence) |

## CC7 System operations and monitoring

| Control id | Control | Technical check | Acceptable evidence artifact | Status rules |
|---|---|---|---|---|
| CC7.1-scan | Vulnerability/dependency/SAST scanning in CI | Read every pipeline file for `npm audit`, `dotnet list package --vulnerable`, `pip-audit`, dependency-check, trivy, CodeQL, Semgrep, Snyk; check Dependabot/Renovate config | Pipeline definition snapshot; scan run logs; Dependabot config | implemented: scanner step in CI (confirm it blocks); partial: Dependabot/Renovate only; missing: nothing |
| CC7.1-known-vulns | Known vulnerabilities remediated within patch SLA | Read `audit/findings/audit-dependency-vulnerabilities.json` summary | Dependency audit report; tickets closing advisories | partial: Critical/High open; implemented: none open; not-checked: sibling not run |
| CC7.1-pentest | Periodic penetration test with tracked remediation | Grep docs for pen-test records | Pen-test report and remediation tracker | partial: mentioned in docs; organisational otherwise |
| CC7.1-patch-sla | Documented patch SLA by severity | None | Vulnerability management policy | organisational |
| CC7.2-logging | Logs centralised, retained, protected from tampering | Logging config (Serilog sinks, logback appenders, `LOGGING` handlers, pino/winston transports); retention and immutable storage in IaC | Logging config snapshot; sink retention setting export; immutable bucket/workspace policy | implemented: central sink + retention; partial: console-only or no retention/immutability visible; not-checked: no config |
| CC7.2-alerting | Security events monitored with alerting | Grep failed-login/lockout/denied logging; alert rules (Prometheus, Azure Monitor, CloudWatch, Datadog) | Alert rule definitions; alert routing (PagerDuty/Opsgenie) export | implemented: security events + alert rules; partial: one of the two; missing: neither |
| CC7.3-incident | Incident response process (CC7.3-CC7.5) | Grep docs for incident runbook, on-call, severity levels, post-mortems | IR plan, on-call rota, post-mortem records | partial: runbook in repo; organisational otherwise |

## CC8 Change management

| Control id | Control | Technical check | Acceptable evidence artifact | Status rules |
|---|---|---|---|---|
| CC8.1-branch-protection | PR review and status checks enforced on the production branch | `gh api repos/{slug}/branches/{default}/protection` (+ rulesets); else `.github/settings.yml` / committed rulesets | API JSON snapshot (a 404 "Branch not protected" is evidence of the gap); settings-as-code file | implemented: required reviews + checks; missing: protection null/disabled or reviews/checks null; not-checked: no API access and no settings file |
| CC8.1-codeowners | Code ownership / required reviewers defined | Look for `CODEOWNERS` (root, `.github/`, `docs/`) | CODEOWNERS snapshot + `require_code_owner_reviews` | implemented: file present; missing: absent |
| CC8.1-ci-gate | Build and automated tests before merge/deploy | Pipeline has build + test steps; tests are required checks | Pipeline snapshot; required-checks list; run history (Type 2) | implemented: test step found; missing: CI without tests; not-checked: no CI in repo |
| CC8.1-deploy-gate | No direct production deploys; releases go through the pipeline with approval | Deploy job trigger, `environment: production` with reviewers, `workflow_dispatch` permissions, deploy scripts outside CI | Pipeline snapshot; environment protection rules (`gh api .../environments`) | implemented: protected environment/approval; partial: pipeline-only, no approval; missing: deploy on push to unprotected production branch |
| CC8.1-traceability | Changes traceable to a ticket/work item | Ratio of recent commit subjects/PR titles with ticket references (JIRA keys, `#123`, `AB#123`, closing keywords; rules owned by `audit-git-history`) | git log export; PR list with linked issues | implemented: >= 80%; partial: 30-79%; missing: < 30%; not-checked: no git history (a shallow clone is sampled and noted) |

## CC9 Risk mitigation and vendor management

| Control id | Control | Technical check | Acceptable evidence artifact | Status rules |
|---|---|---|---|---|
| CC9.1-risk | Risk register and business risk mitigation (incl. insurance) | None | Risk register, risk assessment minutes | organisational |
| CC9.2-vendors | Vendor/subprocessor inventory with SOC 2 reports reviewed | Third-party SDKs/APIs from `audit-privacy-data-flow-mapper` inventory; grep docs for subprocessor list | Subprocessor list; vendor SOC 2 reports with review sign-off; DPAs | partial: vendors identified in code or listed in docs; organisational otherwise |

## A1 Availability

| Control id | Control | Technical check | Acceptable evidence artifact | Status rules |
|---|---|---|---|---|
| A1.1-monitoring | Health checks and uptime monitoring with alerting | Health endpoints, container probes, uptime monitor config, availability alert rules | Health check code; uptime monitor export; alert rules | implemented: health + alerting; partial: health endpoint only; missing: neither |
| A1.2-backups | Automated backups, encrypted, retained off-site | Backup scripts/cron, IaC (`backup_retention_period`, `aws_backup_plan`, `azurerm_backup_*`, LTR policies), encryption flags, retention/lifecycle | Backup script/IaC snapshot; backup job history | implemented: automation + encryption + retention; partial: some attributes not visible; not-checked: managed service, no IaC |
| A1.2-restore-test | Restore tested periodically and documented | Docs/logs for a dated restore test (date, dataset, outcome, RTO achieved) - restore instructions alone do not count | Restore-test log with date and result | implemented: dated test record; partial: instructions only; missing: nothing about restore |
| A1.2-dr-plan | DR plan with RTO/RPO and failover tested (A1.2/A1.3) | Docs for DR plan, RTO/RPO, multi-AZ/region IaC | DR plan, DR exercise report | partial: DR documented in repo; organisational otherwise |

## C1 Confidentiality

| Control id | Control | Technical check | Acceptable evidence artifact | Status rules |
|---|---|---|---|---|
| C1.1-classification | Confidential data identified and classified | `audit-privacy-data-flow-mapper` data inventory; classification attributes in code | Data inventory with classifications | implemented: inventory present; partial: markers only; missing: neither |
| C1.1-encrypt-rest | Confidential data encrypted at rest | Field encryption APIs, TDE/KMS/`storage_encrypted` in IaC | Config snapshot; cloud encryption settings export | partial: markers found (platform proof still needed); not-checked: none in repo |
| C1.1-policy | Data classification and handling policy | None | Policy document | organisational |
| C1.2-disposal | Confidential data disposed of per retention schedule | Purge/anonymise jobs, scheduled cleanup, lifecycle rules | Job code + schedule; deletion logs | partial: purge code found (schedule policy organisational); missing: none |

## PI1 Processing integrity

| Control id | Control | Technical check | Acceptable evidence artifact | Status rules |
|---|---|---|---|---|
| PI1.1-validation | Inputs validated before processing (PI1.1/PI1.2) | Validation attributes/libraries on request models; server-side, not only client | Validator code; sample rejected-input tests | implemented: widespread markers; partial: few; missing: none |
| PI1.3-integrity | Processing complete, accurate and idempotent (PI1.3/PI1.4) | Unique constraints, idempotency keys, concurrency tokens, reconciliation jobs, audit trail | Schema/migration snapshot; reconciliation reports | implemented: idempotency + audit trail; partial: some; missing: none |

## P1 Privacy

| Control id | Control | Technical check | Acceptable evidence artifact | Status rules |
|---|---|---|---|---|
| P1.1-notice-consent | Privacy notice and consent handling (P1-P8 entry point) | Read `audit/evidence/audit-gdpr-data-protection/gdpr-checks.json`; else grep notice/consent symbols | GDPR skill check results; consent records schema; privacy notice URL | Mirror the GDPR skill's consent status; partial: symbols only; not-checked: sibling not run |

Privacy depth (rights, retention, transfers, breach notification) belongs to
`audit-gdpr-data-protection`; this skill only records the P-series status and links it.

## How to use this map

1. Run `collect_evidence.py`, then `soc2_matrix.py`; the matrix rows arrive with a
   first-pass status computed from the rules above.
2. For every `implemented` row, open the cited artefact and confirm it; downgrade to
   `partial` when the evidence is weaker than the rule assumes (for example, a scan
   step that runs with `continue-on-error: true` does not block anything).
3. For every `missing` row, confirm the absence is proven (the file or snapshot shows
   it off), then write one SOC2 finding per root cause using the severity table.
4. For every `not-checked` row, name the export the user must provide.
5. Copy every `organisational` row into the organisational-gaps table with its owner.
