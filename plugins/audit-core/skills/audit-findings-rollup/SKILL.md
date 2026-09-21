---
name: audit-findings-rollup
description: Rolls every audit/findings/*.json and audit/status/*.json up into one view - findings de-duplicated by root_cause_key across skills, severity counts without false positives, the Critical/High list, risk-accepted findings, skills not run, failed, skipped or run with limited access, and the GO / CONDITIONAL GO / NO-GO verdict with its reason and caveats - written to audit/evidence/audit-findings-rollup/. Also merges duplicate findings inside one findings file. Use it whenever the user asks for the go/no-go or launch verdict, overall audit status, how many Critical or High findings are open, severity totals, which audits failed or were skipped, whether a risk acceptance still applies, or to de-duplicate findings by root cause - even when they do not name this skill. Also used by audit-application, audit-report-generator, audit-production-readiness-checklist, audit-owasp-asvs-mapper, audit-technical-debt and audit-finding-writer.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-core:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit findings rollup

One job: read what the audit skills already recorded and produce one rolled-up view
of it, with the verdict decided by one fixed rule. Six scripts used to do this
separately and disagreed on the verdict, on de-duplication and on what "not run" means.
Each consumer now reads the same answer from here.

This skill knows nothing about any audit topic. Whether something is a finding, what
severity it has and whether it is a false positive are decided by the skill that wrote
it. This skill only counts, merges and applies the verdict rule.

Read-only rule: the audited code and every findings and status file are never modified.
The rollup is written only to `audit/evidence/audit-findings-rollup/`, and the script
refuses any output path inside `audit/findings/`. A rollup file there would be read back
as a skill's findings by every consumer that globs that folder. The one exception is
`dedupe --write`, which rewrites the single findings file its caller names. That is
audit-finding-writer's documented clean-up of its own file, and it never creates a file.

## Inputs and prerequisites

- An audit workspace: `audit/findings/<skill>.json` in the shared format
  (`../audit-finding-writer/references/findings-schema.md`) and `audit/status/<skill>.json`.
  Either folder may be missing or empty.
- Optional risk-acceptance file, passed with `--accepted`. It is a JSON list of
  `{"id", "accepted_by", "date", "reason"}`, plus an optional `"expires"` date. The
  required fields are defined in audit-production-readiness-checklist's
  `references/go-no-go-rules.md`. There is no default location, so the caller passes the path.
- Optional expected-skill list (`--expected`), used to report skills that never ran.
  Without it, `audit/plan.json` from audit-application is used when present.
- Python 3, standard library only. Neither the stack (`audit/stack.json`) nor the
  repository walker is needed, because only two fixed `audit/` folders are read.

## Workflow

1. **Run the rollup** from this skill's directory, or with the path from a consumer:

   ```bash
   python scripts/findings_rollup.py rollup <repo> \
     [--accepted <path/to/accepted.json>] [--as-of 2026-09-11] [--expected skill-a,skill-b]
   ```

   It writes `audit/evidence/audit-findings-rollup/rollup.json` and `rollup.md` and prints
   a short summary. Pass `--as-of` whenever the result must be reproducible, because
   expiry is checked against that date (default: today, UTC).
2. **Need one fact only?** Use `verdict [--text]` or `counts`. Both print and write
   nothing. From Python, import the module and call the functions in
   `references/audit-findings-rollup-contract.md`.
3. **De-duplicate one findings file** (audit-finding-writer's step):

   ```bash
   python scripts/findings_rollup.py dedupe audit/findings/<skill>.json          # preview
   python scripts/findings_rollup.py dedupe audit/findings/<skill>.json --write  # apply
   ```

4. **Read the caveats before quoting the verdict.** A NO-GO is still a NO-GO when an
   area failed. A GO is only as good as the areas that ran, so always repeat the caveats
   next to the verdict word.
5. **Check the not-applied acceptances.** Expired, invalid or unmatched records are
   listed. Tell the user which findings are blockers only because an acceptance lapsed
   or lacks a field, since that is usually quicker to fix than the code.

### The verdict rule

This rule was decided by the user. `verdict()` is the only code that applies it.

| Open findings | Verdict |
|---|---|
| any Critical or High | **NO-GO** |
| only Medium or Low | **CONDITIONAL GO** |
| nothing above Info | **GO** |

- **Open** excludes `confidence: false-positive` and findings covered by a valid risk
  acceptance. Findings are counted after de-duplication.
- **Valid acceptance.** It has all four fields `id`, `accepted_by`, `date` and `reason`,
  and either no `expires` or an `expires` on or after the as-of date. A covered finding
  leaves the blocker list but is still listed under risk-accepted findings. A merged
  finding is covered only when every id merged into it is covered, because accepting
  one symptom does not accept the others.
- **Every skill's Highs block.** A High from a performance or design skill counts the
  same as a security High, whatever its id prefix.
- **Caveats, never a different word.** Failed, skipped, not-run, unfinished and
  limited-access skills, unreadable files and expired acceptances each add a caveat
  naming them. The verdict word never gets a prefix.

### De-duplication rule

- Findings that share a non-empty `root_cause_key` merge, within one file or across
  skills. False positives never merge. Findings without a key stay unique.
- The merged finding is a copy of the highest-severity member (ties: files in name
  order, then findings in file order). It keeps every id (`extra.merged_ids`), every
  location (`extra.locations`), the union of references and tags, and every member's
  evidence. The primary's own evidence is kept in `extra.primary_evidence`.

## Output contract

The full schema, field meanings, Python API and stability promise are in
`references/audit-findings-rollup-contract.md`. Consumers code against that file. In short:

```json
{
  "tool": "audit-findings-rollup", "schema_version": 1, "as_of": "2026-09-11",
  "summary": {"raw": {}, "deduplicated": {}, "open": {}, "merged": 1, "false_positives": 1,
              "cross_skill_groups": 1, "risk_accepted": 1},
  "verdict": {"verdict": "NO-GO", "reason": "...", "caveats": ["Failed: audit-secrets-and-config. ..."],
              "open": {}, "accepted": {}, "blockers": [{"id": "PERF-001", "severity": "High"}]},
  "critical_high": [], "risk_accepted": [], "acceptances": {"valid": [], "expired": [], "invalid": [], "unmatched": []},
  "skills": {"failed": [], "skipped": [], "limited_access": [], "not_run": [], "by_skill": []},
  "groups": [], "findings": [], "false_positives": [], "parse_errors": [], "ignored_files": []
}
```

`rollup.md` opens with `**Recommendation: <VERDICT>.** <reason>`, the same line format
audit-report-generator writes, so existing parsers keep working. Below it come the caveats,
a counts table, the Critical/High table with each row's acceptance state, the risk-accepted
table, the skills table, merged root causes and excluded false positives.

## Limits

- **Only recorded facts.** A skill that ran but wrote no findings file and no status file
  is invisible unless it is in the expected list, where it shows as not run.
- **A missing status file is not assumed to mean completed.** A skill with findings but
  no status file is listed under `no_status_file` with status `null`. Some old consumers
  treated it as completed.
- **Underscore-prefixed files in `audit/findings/` are ignored**, so a scratch or derived
  file placed there is never counted as an audit area. They are listed under `ignored_files`.
- **Unknown severities count as Info** and are never blockers. Fix the findings file
  instead (`findings.py validate`).
- **Acceptance matching is by exact finding id.** Renumbered findings lose their
  acceptance, which then shows as unmatched.
- **Some checks are not reproduced here.** Readiness checklist probes, regulated-data
  upgrades and internal-tool downgrades from audit-production-readiness-checklist's
  `references/go-no-go-rules.md` need judgement. They
  stay in the consumer, which emits failed checklist items as READY- findings so the rule
  sees them.

## Bundled files

- `scripts/findings_rollup.py`: the module and CLI (`rollup`, `verdict`, `counts`, `dedupe`).
- `references/audit-findings-rollup-contract.md`: rollup.json schema, merged-finding
  fields, Python API, stability promise.
- `evals/`: a three-skill workspace with a Critical, a blocking performance High, valid,
  expired and invalid acceptances, a cross-skill root cause, a false positive, a failed,
  a skipped and a limited-access skill, plus a single-file de-duplication fixture.
