# Evidence catalog

What an auditor will accept per control family, and how
`scripts/collect_evidence.py` names and stores it. Evidence lives under
`audit/evidence/audit-soc2-controls-evidence/` in the audited repo.

## Folder layout

```
audit/evidence/audit-soc2-controls-evidence/
  index.json                      # manifest, one entry per artefact
  snapshots/
    git-metadata.json             # commit, branch, remote, tags, recent subjects, ticket_refs, shallow (audit-git-history)
    .github/workflows/ci.yml      # copies keep their repo-relative path
    .github/CODEOWNERS
    .github/settings.yml
    infra/backup.sh
    gh/branch-protection-main.json  # only when gh was installed and authenticated
    gh/rulesets.json
    gh/environments.json
  control-matrix.json / control-matrix.md   # from soc2_matrix.py
  hits.json                                 # from $AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py
```

## index.json shape

```json
{
  "skill": "audit-soc2-controls-evidence",
  "collected_at": "2026-09-11T10:00:00+00:00",
  "root": "D:/repo",
  "git": {"commit": "abc123", "branch": "main", "remote": "https://github.com/acme/api", "provider": "github"},
  "branch_protection_api": {"status": "checked | not-checked", "reason": "gh CLI not installed"},
  "items": [
    {"id": "ci-0002", "category": "ci", "source": ".github/workflows/ci.yml",
     "evidence_path": "snapshots/.github/workflows/ci.yml", "sha256": "...", "bytes": 644, "note": ""}
  ],
  "not_collected": [{"item": "Dependabot/Renovate configuration", "reason": "nothing matching in the repository"}],
  "stats": {"ci": 1, "backup_recovery": 2}
}
```

`sha256` lets the auditor confirm the copy was not edited after collection; record
the commit so the snapshot is tied to a point in history.

## Categories

| Category | What is copied | Controls it evidences |
|---|---|---|
| ci | Workflow/pipeline files (GitHub Actions, GitLab, Azure Pipelines, Jenkinsfile, CircleCI, Bitbucket, Buildkite, Drone) and deploy scripts | CC8.1-ci-gate, CC8.1-deploy-gate, CC7.1-scan |
| branch_protection | `gh api` protection/rulesets/environments JSON; `.github/settings.yml`; committed rulesets | CC8.1-branch-protection, CC8.1-deploy-gate |
| dependency_updates | `.github/dependabot.yml`, `renovate.json*`, `.renovaterc*`; `gh api .../vulnerability-alerts` | CC7.1-scan |
| code_ownership | `CODEOWNERS`, PR templates, `CONTRIBUTING`, `SECURITY.md`; repository settings JSON | CC8.1-codeowners |
| backup_recovery | Backup/restore scripts, backup IaC, docs mentioning restore tests | A1.2-backups, A1.2-restore-test, A1.2-dr-plan |
| iac | Terraform, Bicep, Kubernetes/Helm manifests, compose files, Dockerfiles | A1.2, C1.1-encrypt-rest, CC6.7-transit, CC7.2 |
| logging_monitoring | Logger config, Prometheus/Alertmanager rules, Grafana/Datadog/uptime config | CC7.2-logging, CC7.2-alerting, A1.1-monitoring |
| access_control | Auth bootstrap files, security config, IdP config, gateway routes; collaborators JSON | CC6.1-auth, CC6.1-rbac, CC6.2-access-review |
| secrets_management | `.env.example`, `.sops.yaml`, sealed/external secrets, vault config, gitleaks and pre-commit config | CC6.1-secrets, CC6.1-key-rotation |
| policies_docs | Security, incident, DR, runbook, onboarding/offboarding, access review, vendor docs | CC7.3-incident, A1.2-dr-plan, CC9.2-vendors |
| git_metadata | Commit, branch, remote, tags, last 50 commit subjects | CC8.1-traceability |

## GitHub API calls (read-only GETs)

Made only when `gh` is installed, `gh auth status` succeeds, and the remote is GitHub:

- `repos/{slug}` - default branch, visibility, merge settings.
- `repos/{slug}/branches/{default}/protection` - required reviews, status checks,
  admin enforcement. A **404 "Branch not protected"** body is saved and is itself
  the evidence of the gap (status `missing`, not `not-checked`).
- `repos/{slug}/rulesets` - repository rulesets that may replace classic protection.
- `repos/{slug}/environments` - required reviewers / wait timers on `production`.
- `repos/{slug}/vulnerability-alerts` - Dependabot alerts enabled (204) or not (404).
- `repos/{slug}/collaborators?per_page=100` - seeds the access review; needs admin scope.

Otherwise `branch_protection_api.status` is `not-checked` with the reason, and the
control is `not-checked` unless a settings-as-code file exists. Ask the user to run
`gh api repos/<owner>/<repo>/branches/main/protection > protection.json` and drop the
file in `snapshots/gh/`.

## Point-in-time vs period-of-time evidence

- **Type 1** (design at a date): config snapshots prove the control is designed -
  pipeline files, protection JSON, backup scripts, alert rules, auth config.
- **Type 2** (operating over 3-12 months): the auditor samples operation across the
  period. Snapshots are not enough; point the user at what to export:
  merged PRs with approvals (`gh pr list --state merged --json number,reviews,mergedAt`),
  pipeline run history for deploys, restore-test logs, access-review sign-offs,
  alert/incident tickets, vulnerability tickets closed within SLA.
- Mark Type 2 needs in the report's organisational-gaps list with the owner.

## Never copy into evidence

- Secrets: `.env`, `appsettings.*.json` with live credentials, private keys,
  kubeconfig, `terraform.tfstate` (contains secrets), `*.pfx`/`*.pem`.
- Production data, database dumps, backup files, log exports with personal data.
- Anything outside the repo root. If a needed file contains a secret, record it in
  `not_collected` with the reason and reference it by path and line instead.
