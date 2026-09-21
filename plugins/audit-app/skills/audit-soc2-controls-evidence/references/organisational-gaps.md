# Organisational gaps - controls code review cannot prove

Most SOC 2 controls are processes. A repository can show a control is *designed*
into the system; it cannot show a policy was approved, a review was signed or a
training was completed. These items never become findings. They go into the
report's "Organisational gaps (need a policy owner)" table so the gap is visible
and assigned, without pretending the code audit proved or disproved it.

## How to phrase them

- In the report: a separate table after the findings - Item | Criterion |
  Suggested owner | Evidence an auditor will expect. No severity column.
- In conversation: "This is outside code scope - it needs a policy owner. Code
  review cannot confirm it either way; the auditor will ask <owner> for <artifact>."
- If the repo contains a document that evidences the item (a dated restore-test log,
  an incident runbook), move the control to `partial`/`implemented` in the matrix and
  cite the file - but still list the recurring record (for example, the next test) if
  a Type 2 period needs it.
- Never write "missing" for these: absence from the repo is not absence from the company.

## Catalogue

| Item | Criterion | Suggested owner | Evidence an auditor will expect |
|---|---|---|---|
| Information security policy set (incl. acceptable use) approved and published | CC1.1, CC2.2, CC5.3 | Security lead / Leadership | Approved policies with version, date, and employee acknowledgements |
| Board / management oversight of security | CC1.2, CC2.2 | Leadership | Meeting minutes, security reports to management |
| Risk assessment and risk register | CC3.1-CC3.4, CC9.1 | Leadership / Compliance | Annual risk assessment, register with owners and treatments |
| Security awareness training | CC1.4, CC2.2 | HR / Security lead | Training completion records per employee, annual |
| Background checks for new hires | CC1.4 | HR | Background check completion records (sampled) |
| Onboarding/offboarding checklist tied to HR events | CC6.2, CC6.3 | IT / HR | Tickets showing access granted on approval and revoked within SLA of termination |
| Periodic user access reviews | CC6.2, CC6.3 | Security lead | Quarterly review records with reviewer sign-off and remediation |
| MFA enforced at the identity provider | CC6.1 | IT / Security lead | IdP policy export (Conditional Access, Okta sign-on policy) and MFA enrollment report |
| Patch / vulnerability remediation SLA | CC7.1 | Engineering lead | Vulnerability management policy with SLAs by severity; tickets closed within SLA |
| Penetration test and remediation tracking | CC4.1, CC7.1 | Security lead | Annual pen-test report from a third party and remediation tracker |
| Incident response plan and exercises | CC7.3-CC7.5 | Security lead | IR plan, on-call rota, tabletop exercise record, post-mortems |
| Business continuity / DR plan and test | A1.2, A1.3, CC9.1 | Ops | BCP/DR plan with RTO/RPO, annual DR test report |
| Restore test log | A1.2 | Ops | Dated restore tests (dataset, duration, outcome, RTO achieved), at least annually |
| Vendor inventory with SOC 2 reports and DPAs | CC9.2 | Security lead / Procurement | Subprocessor list, vendor SOC 2 reports reviewed with bridge letters, signed DPAs |
| Change advisory and emergency change procedure | CC8.1 | Engineering lead | Change management policy; emergency change tickets with retrospective approval |
| Data classification and handling policy | C1.1 | DPO / Security lead | Classification policy with levels and handling rules |
| Data retention and disposal schedule | C1.2, P4.2 | DPO | Retention schedule; disposal/deletion records |
| Encryption key and credential rotation records | CC6.1, C1.1 | Security lead / Ops | KMS/Key Vault rotation history; rotation procedure |
| Monitoring of controls (internal audit / control self-assessment) | CC4.1, CC4.2 | Compliance | Control testing results and deficiency tracking |
| Customer commitments and system description | CC2.3 | Leadership / Legal | Terms, SLAs, system description for the SOC 2 report |

## Matrix control ids that are always organisational

`CC1-CC5-entity`, `CC6.2-provisioning`, `CC6.2-access-review`, `CC7.1-patch-sla`,
`CC9.1-risk`, `C1.1-policy`. These appear with status `organisational` in every run;
others (`CC6.3-deprovisioning`, `CC7.1-pentest`, `CC7.3-incident`, `CC9.2-vendors`,
`A1.2-dr-plan`, `CC6.1-key-rotation`) become organisational when the repo holds no
code or document for them.

## Type 2 reminder

For a Type 2 report, every item above needs records spread across the audit period,
not a single document. When the user is preparing for Type 2, add a line per item:
"sample needed across <period>".
