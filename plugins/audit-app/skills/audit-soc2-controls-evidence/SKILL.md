---
name: audit-soc2-controls-evidence
description: Checks the technical controls behind the SOC 2 Trust Services Criteria (Security CC6-CC9, Availability A1, Confidentiality C1, Processing Integrity PI1, Privacy P1) and collects evidence an auditor can accept - access control (SSO/MFA, least privilege, admin logs, offboarding), change management (PR review, branch protection, CI gates, no direct production deploys, ticket traceability), logging and monitoring (central, tamper-evident, retained, alerting), vulnerability management (CI scanning, patch SLA), availability (backups with tested restore, DR, uptime), confidentiality (classification, encryption, secrets, key rotation) and vendor management; exports evidence snapshots with an index and separates organisational gaps needing a policy owner. Use whenever the user asks about SOC 2, Trust Services Criteria, audit evidence, controls, control matrix, compliance readiness, "are we ready for a SOC 2 audit", type 1/type 2, or auditor requests - even when the user does not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: SOC 2 controls and evidence

Turns a repository into two things an auditor asks for: a control-to-evidence
matrix (criterion -> control -> evidence artifact -> status) and a folder of
exported evidence files with an index. It is explicit about the line between
what code and configuration can prove and what needs a policy owner - most
SOC 2 controls are organisational, and pretending otherwise fails the audit.

Read-only rule: never modify the audited code. Write only under `audit/`.
`gh api` calls are read-only GETs.

## Inputs and prerequisites

- Repo root (default `.`). Standalone runs read `audit/stack.json` if present,
  otherwise run `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>` (without `--write`).
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection`,
  `audit-code-scan` (grep pass and the shared file walker), `audit-git-history` (git
  metadata, recent subjects, ticket references, shallow-clone flag),
  `audit-sensitive-data-catalog` (committed-secret check) and `audit-finding-writer`
  (findings I/O).
- Optional but valuable: the GitHub CLI (`gh`) authenticated for the remote, so
  branch protection, required reviews and environment protection rules can be
  exported. Without it, the collector falls back to `.github/settings.yml`
  (probot) or repository rulesets committed as code, and otherwise records
  branch protection as *not collected*.
- Optional sibling outputs, used when present: the personal-data inventory
  (`audit/evidence/audit-privacy-data-flow-mapper/data-inventory.json`) for
  C1/P1 and vendor lists, `audit/findings/audit-dependency-vulnerabilities.json`
  for CC7.1, `audit/evidence/audit-gdpr-data-protection/gdpr-checks.json` for P1.
- Cloud consoles, IdP configuration, HR systems and vendor SOC 2 reports are
  outside the repo: they always land in the organisational gaps list unless a
  document in the repo evidences them.

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`; open only the
   matching `references/<stack>.md`. It lists where auth/RBAC/MFA, logging,
   audit trails, health checks, secrets and CI conventions live for that
   framework, and the hits that are usually fine.
2. **Automated pass.**
   - `python scripts/collect_evidence.py <repo> --out audit/evidence/audit-soc2-controls-evidence`
     snapshots CI pipeline definitions, branch protection (`gh api`, else
     settings-as-code), Dependabot/Renovate config, CODEOWNERS and PR templates,
     backup/restore scripts and IaC, logging/monitoring/alerting config, auth
     configuration, security/incident/DR docs and git metadata (commit, branch,
     tags, recent subjects, ticket references and the shallow flag, via
     `audit-git-history`) into
     `snapshots/` with `index.json` (sha256, size, category, source) and a
     `not_collected` list.
   - `python scripts/soc2_matrix.py <repo> --evidence audit/evidence/audit-soc2-controls-evidence --out audit/evidence/audit-soc2-controls-evidence/control-matrix.json --md audit/evidence/audit-soc2-controls-evidence/control-matrix.md`
     evaluates each control in `references/tsc-criteria-map.md` against the
     snapshots and the code, assigns `implemented | partial | missing |
     organisational | not-checked`, and writes the matrix plus the
     organisational gaps list.
   - `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-soc2-controls-evidence/hits.json`
     adds framework-specific candidates (RBAC attributes, MFA symbols, audit
     interceptors, health endpoints, secrets in config, console-only logging).
   Read `branch_protection_api` and `not_collected` in `index.json` first: when
   `gh` is not installed, not authenticated or the remote is not GitHub, the API
   query is recorded as `not-checked` with the reason. A control with no evidence
   for that reason is *not checked*, not *missing* - unless a committed
   settings-as-code file (or a saved 404 "Branch not protected") proves the gap.
3. **Manual trace of the highest-risk controls.** In priority order:
   - **Change management (CC8.1)**: can a change reach production without a
     reviewed PR and a green pipeline? Trace: branch protection -> required
     checks -> deploy job trigger -> who can run it -> is the deploy step
     reachable from a feature branch or manual dispatch.
   - **Logical access (CC6.1-6.3)**: how are users authenticated (SSO/OIDC,
     local passwords, MFA?), how are roles enforced (every controller?), how is
     an admin action logged, how is a leaver removed (endpoint/job)?
   - **Backups and restore (A1.2)**: backup exists -> is it encrypted, off-site,
     retained; is there a documented, dated restore test; is there a DR plan.
     "Restore instructions" are not a restore test.
   - **Vulnerability management (CC7.1)**: which scanner runs in CI, does it
     block, what is the patch SLA (organisational).
   - **Logging (CC7.2)**: where logs go, retention, tamper-evidence
     (append-only sink / immutable bucket), security events and alerts.
   Use the "Manual trace checklist" in the stack file.
4. **Write findings** with `python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py"` (prefix `SOC2`). One finding
   per control gap the code/config proves. Severity per
   `audit-finding-writer/references/severity-rubric.md`: no branch protection
   on the production branch is High; no security scan in CI is Medium; backups
   without a tested restore is Medium (High if the app is the system of
   record and no DR plan exists); console-only logging in production is Medium.
   Organisational items are not findings.
5. **Emit outputs** (relative to the audited repo):
   - `audit/findings/audit-soc2-controls-evidence.json`
   - `audit/reports/audit-soc2-controls-evidence.md` (template below)
   - `audit/evidence/audit-soc2-controls-evidence/` - `index.json`,
     `snapshots/**`, `control-matrix.json`, `control-matrix.md`, `hits.json`
   - `audit/status/audit-soc2-controls-evidence.json` -
     `{"skill": "...", "status": "completed|failed|skipped", "reason": "...", "started_at": "...", "finished_at": "..."}`
6. **Not checked.** Always include: IdP/SSO configuration, cloud IAM and
   console settings, HR onboarding/offboarding records, vendor SOC 2 reports,
   pen-test reports, ticketing system linkage, production runtime configuration
   not committed to the repo. Add every `not_collected` entry from `index.json`
   (including `full git history` for a shallow clone) and every `not-checked`
   control from the matrix.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `SOC2`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Location:** `path/to/config.yml:LINE` (or `.` for repo-wide)
- **Evidence:**

```yaml
<the branch-protection snapshot, the workflow steps, the backup script>
```

- **Impact:** Plain language. Which criterion fails, what an auditor will conclude, what the operational risk is.
- **Remediation:** The concrete setting or pipeline step, and the evidence artifact to keep afterwards.
- **Reference:** SOC2-CC8.1, SOC2-CC7.1, SOC2-A1.2, CWE-1104, ASVS-1.x


Same content goes to `findings.json`; put the criterion ids in `references`
(`SOC2-CCn.n`, `SOC2-A1.2`, ...), the control id from the matrix in `tags`, and
`root_cause_key` = `soc2:<control-id>`.

## Output template (`audit/reports/audit-soc2-controls-evidence.md`)

```markdown
## audit-soc2-controls-evidence

**Target:** <repo> @ <commit> - **Run:** <date> - **Stack:** dotnet
**Evidence folder:** `audit/evidence/audit-soc2-controls-evidence/` (N files, index.json)

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| n | n | n | n | n |

### Control-to-evidence matrix

| Criterion | Control | Evidence artifact | Status | Notes |
|---|---|---|---|---|
| CC8.1 | PR review enforced on production branch | `snapshots/.github/settings.yml` (protection: null) | Missing | branch protection disabled on main |
| CC8.1 | CI gate: build + tests before deploy | `snapshots/.github/workflows/ci.yml` | Implemented | deploy job needs build |
| CC7.1 | Vulnerability scanning in CI | - | Missing | no dependency/SAST/container scan step |
| A1.2 | Backups automated, encrypted, off-site | `snapshots/infra/backup.sh` | Implemented | nightly, SSE, 30/90-day retention |
| A1.2 | Restore tested and documented | `snapshots/docs/runbooks/backups.md` | Partial | restore instructions, no dated test record |
| CC6.1 | Authentication and role-based authorization | `snapshots/Api/Program.cs` | Partial | JWT + policy; MFA/SSO not visible |
| CC9.2 | Vendor management | - | Organisational | subprocessor list and SOC 2 reports |

### Findings
<finding blocks, most severe first>

### Organisational gaps (need a policy owner)

| Item | Criterion | Suggested owner | Evidence an auditor will expect |
|---|---|---|---|
| Access reviews (quarterly) | CC6.2/6.3 | Security lead | signed review records |
| Restore test cadence | A1.2 | Ops | dated restore-test log |

### Evidence index
<summary of index.json: category, path, sha256>

### Not checked
- <item> - <reason>
```

## Examples

**Input (snapshot):**
`.github/settings.yml` -> `branches: [{name: main, protection: null}]`

**Output:**
```markdown
### [High] SOC2-001 - Branch protection disabled on the production branch
- **Location:** `.github/settings.yml:9`
- **Confidence:** confirmed
- **Evidence:**

```yaml
- name: main
  protection: null        # develop: required_pull_request_reviews: null
```

- **Impact:** Any contributor can push directly to `main`, which the deploy job releases to production; there is no enforced review or status check, so the CC8.1 change-management control cannot be evidenced for the audit period.
- **Remediation:** Enable protection on `main` (and `develop`): `required_pull_request_reviews.required_approving_review_count: 1`, `required_status_checks.contexts: ["build"]`, `enforce_admins: true`, `restrictions` to the release team; export the setting with `gh api repos/{owner}/{repo}/branches/main/protection` into the evidence folder.
- **Reference:** SOC2-CC8.1, SOC2-CC6.1
```

**Input (workflow):** `ci.yml` with restore/build/test and no scan step.

**Output:** `[Medium] SOC2-002 - No vulnerability scanning in the CI pipeline`
with remediation adding `dotnet list package --vulnerable` (fail on output),
Dependabot config, and `trivy fs` for the image; reference `SOC2-CC7.1`.

## Bundled files

- `references/tsc-criteria-map.md` - criteria (CC6-CC9, A1, C1, PI1, P1) ->
  controls -> technical check -> evidence artifact -> status rules.
- `references/evidence-catalog.md` - what evidence auditors accept per control
  and how the collector names it.
- `references/organisational-gaps.md` - controls that always need a policy
  owner, with the evidence an auditor expects.
- `references/<stack>.md` - dotnet, java-spring, node-express, python-django,
  angular, react, vue; to add a stack, copy `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `scripts/collect_evidence.py` - evidence snapshots + `index.json`; git metadata and ticket
  references from `audit-git-history`, files walked with `audit-code-scan`'s `repo_walk`.
- `scripts/soc2_matrix.py` - control-to-evidence matrix and organisational gaps; ticket rules from
  `audit-git-history`, committed secrets judged per value by `audit-sensitive-data-catalog`.
- `scripts/patterns/<stack>.json` - framework-specific candidates, run with `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`.
- Atomic scripts called: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`,
  `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`, `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`;
  imported: `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py`, `$AUDIT_CORE_ROOT/skills/audit-git-history/scripts/githist.py`,
  `$AUDIT_CORE_ROOT/skills/audit-sensitive-data-catalog/scripts/catalog.py`.
- `evals/` - prompts and a fixture with branch protection off, CI without a
  security scan, and backups configured without a restore test.
