# Go / no-go rubric

The script computes the verdict mechanically; the reviewer confirms it with judgement.
Change the verdict only by changing the findings (severity, confidence, `scope`), never by
editing the report text, so the report and the findings files stay consistent.

## Mechanical rule (decided by `audit-findings-rollup`, printed by `build_report.py`)

The rule is owned by `../audit-findings-rollup` (`verdict()`; contract in
`../audit-findings-rollup/references/audit-findings-rollup-contract.md`). This skill never
computes its own verdict, so the report, the readiness checklist and the orchestrator's
console summary always agree.

| Open findings (after de-duplication; not false-positive; not covered by a valid acceptance) | Verdict | Plain-language meaning for the executive summary |
|---|---|---|
| Any Critical or High | **NO-GO** | "Do not launch until the listed blockers are fixed and re-verified. Each can be exploited by an ordinary user or an outsider and leads to data exposure, data loss or takeover." |
| Only Medium / Low | **CONDITIONAL GO** | "Launch is acceptable if every Medium has an owner and a date within 30 days, and Lows are scheduled." |
| Only Info, or none | **GO** | "No defects above informational were found in the areas audited." |

A risk acceptance (`--accepted`) lifts a finding only when the record has `id`, `accepted_by`,
`date` and `reason`, and no `expires` before `--as-of`. A merged finding is lifted only when
every merged id is accepted. Accepted findings are listed under "Risk accepted" in section 7.

Caveats listed automatically after the recommendation line (they never change the word):

- Failed, skipped, not-run, unfinished and limited-access skills, by skill id.
- Unreadable findings or status files, and expired acceptances that were not applied.
- A skipped security area is also visible in the scope table; if it is a security area
  (authz, injection, secrets, headers, tenant isolation, dependencies) say so in the
  summary by hand: "Not audited: secrets and config - treat as unknown risk."

## Reviewer checks before signing the verdict

1. **Severity sanity.** Open each Critical/High and re-read the Impact against
   `audit-finding-writer/references/severity-rubric.md`. A High that needs an admin
   account *and* a race is a Medium; a Medium on a multi-tenant boundary is a High.
2. **Confidence.** A `likely` Critical still blocks launch, but the summary should say
   "to be confirmed by <test>" so the team knows the fastest path to unblock.
3. **Compensating controls.** If a WAF rule, network isolation or feature flag neutralises
   a blocker in production and the evidence is in `audit/evidence/`, either lower the finding's
   severity in its findings.json (with the control named in Impact) or record a dated risk
   acceptance and pass it with `--accepted`, then regenerate.
4. **Coverage.** A GO with half the security areas skipped is not a GO; write
   "GO for the areas assessed; the following areas were not audited: ...".
5. **Top three risks.** They must be readable by a product owner: no CWE ids, no
   framework names, one sentence each. The script copies `impact`; if an impact is
   jargon-heavy, fix it in the finding (audit-finding-writer), not in the report.

## Remediation buckets

| Bucket | Contents | Owner and window |
|---|---|---|
| Must fix before launch | open Critical + High (after de-duplication) | Engineering lead; before the release branch is cut; each needs a re-test note |
| Risk accepted | Critical/High (or any severity) covered by a valid acceptance record | The acceptor named in the record; re-review before `expires` |
| Ticket for post-launch | open Medium (30 days), Low (next quarter) | Product backlog with the finding id in the ticket title |
| Record only | Info | Appendix / engineering wiki; no ticket unless the team wants one |

A merged finding (shared `root_cause_key`) is one ticket with all locations listed - the
fix is one change; do not split it back into per-file tickets.
