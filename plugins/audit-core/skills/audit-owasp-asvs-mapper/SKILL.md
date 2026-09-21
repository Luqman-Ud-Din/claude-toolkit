---
name: audit-owasp-asvs-mapper
description: Maps every audit finding (from all audit/findings/*.json files) onto OWASP Top 10 2021 categories, OWASP ASVS 4.0 controls with their level, and CWE ids, writes those references back into each finding, and produces a coverage matrix showing which ASVS controls were verified, which failed, and which were never assessed. Use it whenever the user asks to map findings to OWASP, ASVS, CWE, or any security standard, asks "which OWASP categories did we cover", "what is our ASVS coverage", "what did the audit not check", wants industry-standard ids on a report, or as the step before audit-report-generator in a full audit - even when the user does not name the skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-core:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# OWASP / ASVS / CWE mapper

Every other audit skill describes defects in its own words. This skill translates
them into the vocabulary reviewers, auditors and customers expect - OWASP Top 10
2021, ASVS 4.0 controls (with level), CWE ids - and, just as importantly, shows
which parts of the standard the audit never looked at. A matrix that only lists
failures hides gaps; one that lists "Not assessed" keeps the report honest.

Read-only rule: this skill never edits the audited code. It writes only under
`audit/`: it updates `references` inside existing `audit/findings/*.json` (adds,
never removes), and creates its own report, findings and status files.

## Inputs and prerequisites

- `audit/findings/*.json` produced by other audit skills (format:
  `audit-finding-writer/references/findings-schema.md`). Zero files is allowed - the
  matrix then shows everything as Not assessed, which is itself the answer.
- `audit/status/*.json` if the orchestrator wrote them (used to decide "Verified").
- `audit/stack.json` if present, else `../audit-stack-detection/scripts/detect_stack.py` (stack only chooses
  which `references/<stack>.md` to read for default-satisfied controls).
- Python 3, stdlib only.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack),
  `audit-findings-rollup` (loads findings and status files), `audit-finding-writer` (`findings.py`).

## Workflow

1. **Resolve the stack.** Run `python ../audit-stack-detection/scripts/detect_stack.py <repo>` (returns
   `audit/stack.json` when present). Open only `references/<stack>.md` for the primary
   backend and frontend. Each file lists the ASVS controls that framework satisfies
   by default and what disables them, so you can tell "Verified" from "Not assessed"
   for sections with no findings.
   `../audit-stack-detection/references/stack-reference-template.md` is the outline for a new stack.
2. **Automated pass.** Run
   `python scripts/map_findings.py <repo>` (add `--dry-run` first to preview).
   It scores every finding against `scripts/mapping.json` (CWE match 3 points, tag
   match 2, keywords 1 each), adds `OWASP-A0n:2021`, `ASVS-x.y.z` and a canonical
   `CWE-nnn` to `references` where missing, records the rule under `extra.mapping`,
   and writes the matrix. Existing references always win; the script only fills gaps.
3. **Manual trace of the highest-risk mappings.** Open the per-finding table in the
   report and check, in this order: (a) every Critical/High finding - is the Top 10
   category and the ASVS control the one a reviewer would expect (see
   `references/mapping-table.md` for the deliberate choices, for example HSTS is A05
   while raw CWE-319 is A02); (b) every finding in "Unmapped" - is it truly
   non-security, or does the rule table need a tag/keyword; (c) every section marked
   Verified - did the covering skill actually check it (read its `scope.checked`), or
   should it be downgraded to Not assessed by adding an item to `scope.not_checked`.
   Fix disagreements by editing the finding's `tags` or `references` (never the
   mapping table for a one-off) and re-running the script.
4. **Write findings** for gaps in the audit itself, via
   `python ../audit-finding-writer/scripts/findings.py add audit/findings/audit-owasp-asvs-mapper.json --from f.json`
   with the `MAP` prefix. The script already emits `MAP-001` (sections not assessed)
   and `MAP-002` (unmapped findings) as Info; add a finding when a mis-mapping revealed
   a defect that no skill wrote up (rare, usually a `likely` finding pointing at the
   skill that should own it).
5. **Outputs** (all relative to the audited repo):
   - `audit/reports/audit-owasp-asvs-mapper.md` - Top 10 table, ASVS section matrix
     (control -> Verified / Failed / Not assessed -> linked finding ids), control-level
     table, per-finding mapping, unmapped list, not-assessed list.
   - Updated `audit/findings/<other-skill>.json` files (references added).
   - `audit/findings/audit-owasp-asvs-mapper.json` (MAP findings, summary, coverage counts in `extra`).
   - `audit/status/audit-owasp-asvs-mapper.json` (`completed` / `skipped` with reason).
   - `audit/evidence/audit-owasp-asvs-mapper/` - optional: a copy of `mapping.json` used, so the mapping is reproducible.
6. **Not checked.** State it in the report and in `scope.not_checked`: which ASVS
   levels were listed (default L1 plus anything a finding names; `--min-level 2|3` for
   more), that "Verified" means a covering skill completed and found nothing rather than
   every control being individually tested, that skills without a status file are
   assumed completed, and any findings file that failed to parse.

## Finding format

Only MAP-prefixed findings are written by this skill, and they describe gaps in the
audit, not in the product. Same block as every other skill
(`audit-finding-writer/references/findings-schema.md`):

```markdown
### [Info] MAP-001 - 41 ASVS 4.0 sections were not assessed by any audit skill
- **Location:** `audit/findings` (coverage matrix)
- **Confidence:** confirmed
- **Evidence:**

```text
V2.1 Password Security
V2.5 Credential Recovery
...
```

- **Impact:** The audit cannot claim ASVS coverage for these areas; a reader could mistake silence for a pass.
- **Remediation:** Run the owning skill for each section (skill_coverage in scripts/mapping.json) or record a manual check in that skill's scope.checked as "ASVS-2.1 verified: ...".
- **Reference:** ASVS-1.1.2
```

Fields in JSON: `id`, `title`, `severity`, `confidence`, `location`, `evidence`,
`impact`, `remediation`, `references`, `tags`, optional `root_cause_key`.

## Output template (`audit/reports/audit-owasp-asvs-mapper.md`)

```markdown
## audit-owasp-asvs-mapper findings

Generated <ts>. Findings files: N. Mapped findings: N. Unmapped: N. Findings files updated: N.

### OWASP Top 10 (2021) coverage
| Category | Status | Linked findings |
|---|---|---|
| A01:2021 Broken Access Control | Failed | AUTHZ-001 |
| A02:2021 Cryptographic Failures | Not assessed | - |
...

### ASVS 4.0 coverage matrix (by section)
| Section | Name | Status | Linked findings | Assessed by |
|---|---|---|---|---|
| V4.2 | Operation Level Access Control | Failed | AUTHZ-001 | audit-authz-and-access-control |
| V14.4 | HTTP Security Headers | Failed | HDR-001 | audit-security-headers-and-middleware |
| V2.1 | Password Security | Not assessed | - | - |
...

### ASVS controls (level <= 1, plus any control a finding names)
| Control | Level | Name | Status | Linked findings |
|---|---|---|---|---|
| ASVS-4.2.1 | L1 | Sensitive data and APIs protected against IDOR | Failed | AUTHZ-001 |
...

### Per-finding mapping
| Finding | Skill | Severity | OWASP Top 10 | ASVS | CWE | Rule | Matched by |
|---|---|---|---|---|---|---|---|
| AUTHZ-001 | audit-authz-and-access-control | High | OWASP-A01:2021 | ASVS-4.2.1, ASVS-4.1.3 | CWE-639 | idor | tag:idor |

### Unmapped findings
- FEBP-003 (audit-frontend-best-practices) - OnPush not used on list components

### ASVS sections not assessed
- V2.1 Password Security
...

### Not checked
- <levels listed, what Verified means, parse failures>
```

## Examples

**Input:** `audit/findings/audit-authz-and-access-control.json` holds
`AUTHZ-001 "Order lookup has no ownership check"`, tags `["idor"]`, references `[]`.

**Output:** references become `["OWASP-A01:2021", "ASVS-4.2.1", "ASVS-4.1.3", "CWE-639"]`,
`extra.mapping.rule = "idor"`; matrix row `V4.2 | Failed | AUTHZ-001`; control row
`ASVS-4.2.1 | L1 | Failed`.

**Input:** `HDR-001 "HSTS is not enabled in the production pipeline"`, tags `["hsts","headers"]`.

**Output:** `["OWASP-A05:2021", "ASVS-14.4.5", "CWE-319"]` - the `hsts` rule outscores the
generic `security-headers` rule (tag + keyword vs tag only), and A05 is chosen over the
raw CWE-319 category (A02) because a missing header is a misconfiguration.

## Bundled files

- `scripts/map_findings.py` - the mapper: scores rules, writes references back, builds the matrix, own findings and status.
- `scripts/mapping.json` - rules (CWE/tag/keyword -> Top 10, ASVS controls with level, canonical CWE), full ASVS section catalogue, control names, skill -> section coverage, Top 10 -> section map.
- Atomic scripts called: `../audit-findings-rollup/scripts/findings_rollup.py` (imported by
  `map_findings.py` to load findings and status files; underscore-prefixed files are ignored),
  `../audit-stack-detection/scripts/detect_stack.py` (stack detection, honours `audit/stack.json`),
  `../audit-finding-writer/scripts/findings.py` (init / add / validate / md / summary).
- `references/mapping-table.md` - human-readable mapping table and the reasoning behind non-obvious choices.
- `references/asvs-chapters.md` - every ASVS 4.0.3 chapter/section, which skill assesses it, how to record manual checks and N/A.
- `references/<stack>.md` - which ASVS controls that framework satisfies by default, what disables them, where evidence lives (dotnet, java-spring, node-express, python-django, angular, react, vue); add a stack from `../audit-stack-detection/references/stack-reference-template.md`.
- `evals/` - three fixture findings files (IDOR, XSS, missing HSTS) and the expected mappings.
