---
name: audit-report-generator
description: Assembles every audit/findings/*.json (plus status files, the OWASP/ASVS coverage matrix and GDPR/SOC 2 sections when present) into the final audit/audit-report.md - executive summary with a GO / CONDITIONAL GO / NO-GO recommendation and the top three risks in plain language, scope and methodology, findings sorted Critical to Info and de-duplicated by root cause, a pass/fail matrix by audit area, OWASP/ASVS coverage, compliance status, a prioritised remediation plan (must fix before launch vs post-launch tickets) and evidence appendices; exports .docx/.pdf via pandoc on request. Use it whenever the user asks to generate, compile, build, assemble, produce or export the audit report, security report, review summary, final deliverable, pre-production sign-off, "the report for the client", or asks whether the app is ready to launch based on the audits - and as the last step of a full audit run, even when the skill is not named.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-core:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit report generator

Every audit skill writes its own findings.json and Markdown section. This skill turns
that pile into one document a product owner can read in twenty minutes and an
engineer can work from: a go/no-go verdict, three risks in plain words, the full
findings list, and a remediation plan that separates launch blockers from backlog.
The body stays under ~15 pages by pushing evidence and detail to appendices.

Read-only rule: this skill never edits the audited code and never edits other skills'
findings files. It writes `audit/audit-report.md` (plus `.docx`/`.pdf` on request)
and its own `audit/status/audit-report-generator.json`.

## Inputs and prerequisites

- `audit/findings/*.json` (any number; format in
  `audit-finding-writer/references/findings-schema.md`). With zero files the report is
  still produced, says so, and the status is `skipped`.
- `audit/status/*.json` - run status per skill (`completed | failed | skipped`, reason,
  optional `scripts` list used for Appendix B).
- `audit/reports/audit-owasp-asvs-mapper.md` - coverage matrix (optional; run
  `audit-owasp-asvs-mapper` first when possible).
- `audit/reports/audit-gdpr-data-protection.md`, `audit/reports/audit-soc2-controls-evidence.md` (optional).
- `audit/evidence/<skill>/*` - listed in Appendix B when present.
- `audit/stack.json` if present, else `../audit-stack-detection/scripts/detect_stack.py` (only to
  name the stack on the title line and pick `references/<stack>.md`).
- Optional risk-acceptance file (`--accepted`): a JSON list of `{"id", "accepted_by", "date",
  "reason"}` plus optional `"expires"`, the format audit-production-readiness-checklist keeps.
- Python 3 stdlib. `pandoc` on PATH only for `.docx`/`.pdf`.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-findings-rollup` (gathering, de-duplication,
  counts, verdict and caveats), `audit-stack-detection` (stack), `audit-finding-writer` (`findings.py`).

## Workflow

1. **Resolve the stack.** `python ../audit-stack-detection/scripts/detect_stack.py <repo>` (returns
   `audit/stack.json` when present). Open only `references/<stack>.md` for the primary
   backend and frontend: it says what the scope table must enumerate for that stack,
   how to phrase that stack's typical blockers for executives, how to group remediation
   tickets, and which hits are false positives that must not become launch blockers.
2. **Automated pass.** Run
   `python scripts/build_report.py <repo> --product "<name>"` (add `--docx` / `--pdf`
   when asked; add `--evidence-lines 2` if the page estimate exceeds 15; add
   `--accepted <file> --as-of <date>` when risk acceptances exist). The script takes the
   rolled-up view from `audit-findings-rollup` (`findings_rollup.rollup()`): findings
   de-duplicated by `root_cause_key` (highest-severity member survives, merged ids and all
   locations kept), sorted Critical -> Info, the verdict and its caveats
   (`references/go-no-go-rubric.md`). It then embeds the mapper and compliance sections, builds
   the remediation plan and appendices, and prints the verdict, counts, merged count and
   a page estimate.
3. **Manual trace of the highest-risk content.** Read the generated report top-down as
   the client would: (a) is the verdict defensible - open every Critical/High and check
   severity against `audit-finding-writer/references/severity-rubric.md`; (b) are the
   top three risks readable by a non-engineer (no CWE ids, no framework names) - if not,
   fix the finding's `impact` in its own findings.json (via audit-finding-writer) and
   regenerate, never hand-edit the report; (c) does the scope table name every shipping
   project and every skipped security area; (d) are merged findings really one root
   cause; (e) is any skipped/failed area a security area that should be called out in
   the summary sentence. Regenerate after every correction so report and findings agree.
4. **Write findings** only for defects in the audit itself (prefix `RPT`), for example a
   findings file that failed to parse or a skill whose status says completed but wrote no
   findings and no scope. Use `python ../audit-finding-writer/scripts/findings.py add audit/findings/audit-report-generator.json --from f.json`.
   Most runs have none.
5. **Outputs** (relative to the audited repo):
   - `audit/audit-report.md` - the deliverable (structure in `references/report-template.md`).
   - `audit/audit-report.docx` / `.pdf` when requested and pandoc is installed; otherwise
     the script prints the exact pandoc command and the Markdown stays the deliverable.
   - `audit/status/audit-report-generator.json` with `exports` recorded.
   - `audit/findings/audit-report-generator.json` and `audit/reports/audit-report-generator.md` only if step 4 produced findings.
6. **Not checked.** The report's scope table already carries every skill's
   `not_checked`. Add to the summary by hand: audit areas that never ran (no findings and
   no status file), whether the mapper/GDPR/SOC 2 sections are absent, that de-duplication
   relies on skills setting `root_cause_key` (unset keys are not merged), and that
   `.docx`/`.pdf` were not produced when pandoc was missing.

## Finding format

RPT findings (rare) use the shared block from
`audit-finding-writer/references/findings-schema.md`:

```markdown
### [Low] RPT-001 - audit-injection-vulnerabilities reports completed but wrote no scope
- **Location:** `audit/findings/audit-injection-vulnerabilities.json` (scope)
- **Confidence:** confirmed
- **Evidence:**

```json
"scope": {"checked": [], "not_checked": []}
```

- **Impact:** The report cannot say what the injection review covered, so a reader may assume full coverage that was not verified.
- **Remediation:** Re-run the skill or fill scope.checked / scope.not_checked by hand from the skill's evidence folder, then regenerate the report.
- **Reference:** ASVS-1.1.2
```

JSON fields: `id`, `title`, `severity`, `confidence`, `location`, `evidence`, `impact`,
`remediation`, `references`, `tags`, optional `root_cause_key`.

## Output template (`audit/audit-report.md`)

Full skeleton with every table: `references/report-template.md`. Section order is fixed:

```markdown
# Pre-production audit report: {product}
Generated ... Commit ... Stack ...

## 1. Executive summary
**Recommendation: NO-GO.** {plain-language why}
| Critical | High | Medium | Low | Info |
Caveats (the verdict covers only what was assessed): - {failed / skipped / not run / limited access areas}
### Top three risks
1. **{title}** ({severity}, {id}). {impact}
## 2. Scope and methodology
| Audit area | Status | Checked | Not checked (reason) |
## 3. Findings            (### Critical (n) ... #### [Critical] ID - title ... ### Info (n))
## 4. Pass/fail matrix by audit area
| Audit area | Run status | Critical | High | Medium | Low | Info | Result |
## 5. OWASP Top 10 / ASVS coverage      (embedded from the mapper, or "did not run")
## 6. Compliance status                 (### GDPR, ### SOC 2 - embedded or "did not run")
## 7. Remediation plan
### Must fix before launch (Critical and High)   | Priority | Id | Finding | Where | Fix summary |
### Risk accepted (only when --accepted covers a finding) | Id | Severity | Finding | Accepted by | Date | Expires | Reason |
### Ticket for post-launch (Medium and Low)      | Id | Severity | Finding | Suggested window |
### Record only (Info)
---
## Appendix A. Full evidence
## Appendix B. Scripts and tools used
## Appendix C. Excluded false positives
## Appendix D. ASVS control detail and per-finding mapping
## Appendix E. Source files
```

## Examples

**Input:** three findings files - authz (Critical `AUTHZ-001` unauthenticated admin
endpoint; High `AUTHZ-002` and `AUTHZ-003` sharing `root_cause_key
base-repository:missing-tenant-filter`), headers (Medium HSTS, Low nosniff), frontend
best practices (Info source maps, one `false-positive`).

**Output:** `**Recommendation: NO-GO.** 1 Critical and 1 High findings are open ...`;
top three risks = AUTHZ-001, AUTHZ-002 (merged with AUTHZ-003, both locations in Appendix
A), HDR-001; "Must fix before launch" table lists AUTHZ-001 and AUTHZ-002; HDR-001 and
HDR-002 under post-launch; FEBP-001 under record only; FEBP-002 in Appendix C; matrix rows
`authz ... FAIL`, `security headers ... WARN`, `frontend best practices ... PASS`.

**Input:** the same repo after the two authz fixes, findings re-rated, `--docx` requested
on a machine without pandoc.

**Output:** `**Recommendation: CONDITIONAL GO.**`, blockers table says "None", status
file `exports.docx` holds the pandoc command to run, and the reply tells the user pandoc
was not found.

## Bundled files

- `scripts/build_report.py` - reads the rollup, writes the report, appendices, status; optional pandoc export.
- Atomic scripts called: `../audit-findings-rollup/scripts/findings_rollup.py` (imported: loading,
  de-duplication, verdict, caveats, risk acceptances), `../audit-stack-detection/scripts/detect_stack.py`
  (stack detection, honours `audit/stack.json`), `../audit-finding-writer/scripts/findings.py`
  (init / add / validate / md / summary for the rare RPT finding).
- `references/report-template.md` - the exact skeleton and the rules the generator applies.
- `references/go-no-go-rubric.md` - verdict rule, reviewer checks, remediation buckets.
- `references/<stack>.md` - per-stack scope enumeration, executive wording for typical blockers, ticket grouping, false positives (dotnet, java-spring, node-express, python-django, angular, react, vue); add a stack from `../audit-stack-detection/references/stack-reference-template.md`.
- `evals/` - three fixture findings files with mixed severities, status files, a mapper report and the expected verdicts.
