# Report template (audit/audit-report.md)

`scripts/build_report.py` produces exactly this layout from the `audit-findings-rollup` view
(`../audit-findings-rollup/scripts/findings_rollup.py`). Edit the two together. The main
body is sections 1-7 and must stay under ~15 pages (about 6,500 words); everything
bulky belongs in the appendices. Placeholders are written in {braces}.

```markdown
# Pre-production audit report: {product}

Generated {date} UTC. Commit: {commit}. Stack: {backend} / {frontend}.

## 1. Executive summary

**Recommendation: {GO | CONDITIONAL GO | NO-GO}.** {one or two sentences a non-engineer
understands: how many blockers, what an attacker or ordinary user could do, any caveat
about areas that did not complete}

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| n | n | n | n | n |

Caveats (the verdict covers only what was assessed):

- {each rollup caveat: Failed / Not run / Skipped / Did not finish / Limited access / Unreadable files / Expired risk acceptances}

### Top three risks

1. **{finding title}** ({severity}, {id}). {impact sentence in plain language - who is
   affected, what they lose, how likely}
2. ...
3. ...

Audit areas run: n; completed: n; skipped: n; failed: n. Findings after de-duplication: n
(from n; n false positives excluded, see Appendix C).

## 2. Scope and methodology

{two-pass method paragraph; read-only statement}

| Audit area | Status | Checked | Not checked (reason) |
|---|---|---|---|
| {area} | completed / skipped - reason / failed - reason | {scope.checked joined} | {scope.not_checked item (reason)} |

## 3. Findings

### Critical (n)
#### [Critical] {ID} - {title}
- **Area:** {area}
- **Location:** `{file:line (symbol)}` (+n more, see Appendix A)
- **Confidence:** confirmed | likely - merged with {ids}
- **Evidence:**

```
{first N lines}
... (n more lines in Appendix A)
```

- **Impact:** {plain language}
- **Remediation:** {concrete fix}
- **Reference:** {CWE, ASVS, OWASP}

### High (n) ... ### Medium (n) ... ### Low (n) ... ### Info (n)

## 4. Pass/fail matrix by audit area

| Audit area | Run status | Critical | High | Medium | Low | Info | Result |
|---|---|---|---|---|---|---|---|
| {area} | completed | n | n | n | n | n | FAIL / WARN / PASS / NOT RUN / FAILED (skill error) |

## 5. OWASP Top 10 / ASVS coverage

{Top 10 table and ASVS section matrix embedded from audit/reports/audit-owasp-asvs-mapper.md,
headings demoted; or a sentence saying the mapper did not run}

## 6. Compliance status

### GDPR
{audit/reports/audit-gdpr-data-protection.md embedded, or "did not run; no statement can be made"}

### SOC 2
{audit/reports/audit-soc2-controls-evidence.md embedded, or the same sentence}

## 7. Remediation plan

### Must fix before launch (Critical and High)
| Priority | Id | Finding | Where | Fix summary |
|---|---|---|---|---|

### Risk accepted (not blocking while the acceptance is valid; only when a record applies)
| Id | Severity | Finding | Accepted by | Date | Expires | Reason |
|---|---|---|---|---|---|---|

### Ticket for post-launch (Medium and Low)
| Id | Severity | Finding | Suggested window |
|---|---|---|---|

### Record only (Info)
- {id} - {title}

---

## Appendix A. Full evidence
### {ID} - {title}
- Area / severity / confidence
- Location: (one line per merged location)
{full evidence in a fenced block}

## Appendix B. Scripts and tools used
- **{area}**: `{script invocations from status.scripts}`; evidence: `{audit/evidence/<skill>/... files}`

## Appendix C. Excluded false positives
| Id | Area | Title | Why excluded |

## Appendix D. ASVS control detail and per-finding mapping
{remainder of the mapper report}

## Appendix E. Source files
- `audit/findings/{skill}.json` (n findings, generated {ts})
- `audit/status/{skill}.json` ({status})
```

## Rules the generator applies

| Rule | Behaviour |
|---|---|
| Verdict | From `audit-findings-rollup`: NO-GO if any open Critical or High; CONDITIONAL GO if only Medium/Low are open; GO otherwise. Open excludes false positives and findings covered by a valid `--accepted` record. Failed, skipped, not-run and limited-access areas, unreadable files and expired acceptances are caveats and never change the verdict. See `go-no-go-rubric.md`. |
| Sorting | Severity, then confirmed before likely, then id. |
| De-duplication | By `audit-findings-rollup`: findings sharing `root_cause_key` collapse into the highest-severity member; merged ids and every location retained; references and tags unioned; false positives never merge. The body shows the primary's evidence, Appendix A every member's evidence with its location. Underscore-prefixed files in `audit/findings/` are ignored. |
| False positives | `confidence: false-positive` never counts; listed in Appendix C so the reader sees they were considered. |
| Top three risks | First three open findings after sorting; text is the finding's `impact` verbatim (already plain language per audit-finding-writer). |
| Evidence | Body shows `--evidence-lines` (default 4) lines; Appendix A has all of it. |
| Page budget | Body words / 450 is reported as `body_pages_estimate`; above 15 the script warns. Lower `--evidence-lines`, or move Low/Info findings to an appendix by hand. |
| Export | `--docx` / `--pdf` run pandoc when found on PATH (`pandoc audit/audit-report.md -o audit/audit-report.docx --toc --from gfm`; PDF adds `--pdf-engine=xelatex`). If not found, the command is printed and the Markdown remains the deliverable. |
