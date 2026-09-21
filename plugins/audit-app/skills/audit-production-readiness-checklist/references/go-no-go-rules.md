# Go / No-Go decision rules

The verdict is decided by one rule shared by every audit skill, owned by
`audit-findings-rollup` (`verdict()`, contract in
`$AUDIT_CORE_ROOT/skills/audit-findings-rollup/references/audit-findings-rollup-contract.md`). The user decided this
rule. `scripts/aggregate_findings.py` prints it; never compute a different word by hand. Then
add one paragraph of judgement - the rule decides, the paragraph explains.

## Rule

| Open findings (after de-duplication by `root_cause_key`) | Recommendation |
|---|---|
| any **Critical or High**, from any skill (READY- included) | **NO-GO** |
| only **Medium or Low** | **CONDITIONAL GO** - list each condition with owner and date |
| nothing above Info | **GO** |

- **Open** excludes `confidence: false-positive` and findings covered by a valid risk
  acceptance (record format below).
- **Every skill's Highs block.** A High from a performance, design or business-logic skill
  counts the same as a security High. There is no prefix list.
- **Checklist items reach the verdict through findings.** A failed item becomes a READY-
  finding (SKILL.md step 4): hard-coded production secret Critical; no health checks, debug on
  in production, no rollback procedure High. An `unknown` item with no finding does not change
  the verdict; name it in the judgement paragraph and the conditions.

## Caveats instead of a prefix

Sibling skills that failed, were skipped, did not run, did not finish or ran with limited
access, unreadable findings or status files, and expired acceptances are **listed as caveats**
directly under the recommendation line. They never change the recommendation word, which is
never prefixed or qualified. A GO with caveats is not a sign-off for the areas the caveats name.

## Accepted-risk record (moves a finding off the blocker list)

What the rule reads is the JSON record in the file passed with `--accepted`:

```json
[
  {"id": "SEC-004", "accepted_by": "Sara Malik, Head of Engineering", "date": "2026-09-10",
   "reason": "reports API is IP-allow-listed at the load balancer (evidence: lb-rules.tf:41)",
   "expires": "2026-10-31",
   "compensating_control_verified_by": "<auditor>", "follow_up_ticket": "OPS-1234"}
]
```

- **Required, non-empty:** `id`, `accepted_by`, `date`, `reason`. A record missing one is
  invalid and the finding stays a blocker.
- **`expires`** (`YYYY-MM-DD`, optional): once it is before `--as-of`, the acceptance no longer
  applies and the finding is a blocker again. Always set it.
- **Other keys** (`compensating_control_verified_by`, `follow_up_ticket`) are kept verbatim.
  Fill them: the report shows them to the reader.
- **Matching is by exact finding id.** A merged finding is lifted only when every id merged
  into it is accepted.
- An acceptance can cover any severity; an accepted Medium is no longer an open condition.

The same record in the Markdown report:

```markdown
- **Finding:** SEC-004 - CORS allows any origin on the reports API
- **Accepted by:** <name, role>  **Date:** 2026-09-10  **Expires:** 2026-10-31
- **Reason:** reports API is IP-allow-listed at the load balancer (evidence: lb-rules.tf:41)
- **Compensating control verified by:** <auditor>  **Follow-up ticket:** OPS-1234
```

## Checks this skill enforces before writing or passing an acceptance record

The rule applies no modifiers, so these judgements happen before a record exists:

- **Regulated data** (payments, health, identity documents): do not write an acceptance for a
  High in `GDPR`, `PII`, `SEC` or `TENANT` unless the DPO or security owner is the acceptor.
- **Internal tools with no customer data:** a High in `HDR`, `XSS` or `CAUTH` may be accepted
  with an acceptance record naming the tool's owner; there is no automatic downgrade.

## Blocker table rules

- One row per open Critical/High, in severity order, then by skill.
- `Owner` is a person or team, never "TBD" in the final report (use "(unassigned)" and list it as a condition).
- `Status`: `open`, `fixed (commit)`, `accepted (see record)`.
- Sibling findings keep their own ids; do not renumber or copy them into READY-.

## Wording of the recommendation line

`# Recommendation: NO-GO` - followed by the caveats, then "because: <blocker 1>; <blocker 2>".
`# Recommendation: CONDITIONAL GO` - followed by the caveats, then the numbered conditions.
`# Recommendation: GO` - followed by the caveats, the date and the list of accepted unknowns.
