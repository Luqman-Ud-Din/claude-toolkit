# Outside code scope - needs organisational owner

Items code review cannot prove. Every run lists the ones that apply in the
report section "Outside code scope - needs organisational owner" with the
suggested owner role. They are not findings and carry no severity; they are
the hand-off list for the DPO / legal / ops.

| Item | Article | Suggested owner | Why it is not verifiable in code | What would make it code-verifiable |
|---|---|---|---|---|
| Records of processing activities (RoPA) reflecting the inventory | Art.30 | DPO | document | commit a `docs/ropa.md` generated from `data-inventory.json` |
| Lawful basis per purpose; special-category condition where applicable | Art.6, 9 | DPO / Legal | legal assessment | annotate purposes in the inventory (`purpose`, `lawful_basis`) |
| Consent text, version history, and proof the text shown matches the stored version | Art.7, 13 | Legal + Product | content | store `consent_version` = hash of the text in the repo |
| Privacy notices (Art.13/14 content) and their delivery at collection points | Art.13, 14 | Legal | content | link the notice version to the collection form |
| Data-processing agreements with each processor and their sub-processor lists | Art.28 | DPO / Legal | contracts | keep `docs/processors.md` with DPA date next to the vendor list |
| Transfer mechanism for non-EU/UK processors (SCCs, IDTA, DPF) and TIA | Art.44-49 | DPO / Legal | contracts, jurisdiction | record region per vendor in the inventory |
| Retention schedule per data category incl. logs, backups, exports | Art.5(1)(e) | DPO + Ops | policy | encode the schedule in the purge jobs and name the category in each job |
| Backup and DR: encryption, retention, re-deletion after restore | Art.17, 32 | Ops | backup system outside repo | script the post-restore re-deletion and commit it |
| Vendor-side retention and deletion (analytics, error trackers, mail providers) | Art.17, 28 | Engineering + DPO | vendor consoles | call vendor deletion APIs from the erasure job |
| Infrastructure encryption at rest (disk, TDE, KMS) and key rotation | Art.32 | Ops | cloud/DB configuration | IaC in the repo with `storage_encrypted`, KMS keys |
| DSAR intake process, identity verification, one-month SLA tracking | Art.12 | Support + DPO | process | a ticket type + the export/erasure endpoints |
| 72-hour breach notification runbook, roles, supervisory authority contacts | Art.33, 34 | Security lead | process | `docs/incident-response.md` + alert routing config |
| DPIA for high-risk processing; privacy review in the delivery process | Art.35, 25 | Product + DPO | process | PR template checkbox + `docs/dpia/` |
| DPO appointment / EU representative where required | Art.27, 37 | Leadership | organisational | - |
| Staff access reviews, least privilege, training, confidentiality | Art.32, 39 | HR / Security | organisational | access-review evidence exported by `audit-soc2-controls-evidence` |
| Children's data / age verification where the service targets minors | Art.8 | Product + Legal | product decision | age gate in the signup flow |
| Automated decision-making / profiling disclosures and opt-out | Art.22 | Product + Legal | product decision | flag in the inventory when a field feeds a model |

## How to present it

One table in the report, sorted by article. If the team already supplied a
document for an item (DPA list, retention policy), reference it and mark the
item "provided - not reviewed for legal adequacy".
