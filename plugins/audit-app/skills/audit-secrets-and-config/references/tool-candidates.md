# Secret-scanning tool candidates (with invocations)

This skill wraps whatever scanner is available in the environment. Detect one
(`which <tool>` / check CI config), run it, and fold its output into findings via
`audit-finding-writer`. If none is installed, the bundled `scripts/git_secret_scan.py`
is the stdlib fallback. Prefer a dedicated tool for real audits - they have
larger, maintained rule sets and lower false-positive rates.

## Git-history and filesystem scanners
- **gitleaks** - fast, Go, great default rules, history-aware.
  - Working tree: `gitleaks detect --source . --no-git`
  - Full history: `gitleaks detect --source . --log-opts="--all"`
  - Report: `gitleaks detect --source . -f json -r gitleaks.json`
  - CI/pre-commit: `gitleaks protect --staged`
- **trufflehog** - verifies many secrets against the live provider (confirmed vs candidate).
  - Repo + history: `trufflehog git file://. --json`
  - Only verified: `trufflehog git file://. --only-verified`
  - Filesystem: `trufflehog filesystem ./path --json`
- **detect-secrets** (Yelp) - baseline workflow, good for CI gating.
  - Baseline: `detect-secrets scan > .secrets.baseline`
  - Audit: `detect-secrets audit .secrets.baseline`
  - Pre-commit hook via `detect-secrets-hook`.
- **git-secrets** (AWS) - prevents committing AWS-style secrets.
  - `git secrets --scan-history`
- **ggshield** (GitGuardian) - `ggshield secret scan repo .` / `ggshield secret scan ci`.
- **semgrep** - has secret rules: `semgrep --config p/secrets`.

## Platform-native secret management (verify secrets are LOADED from these, not files)
- **.NET user-secrets** (dev only): `dotnet user-secrets set "Jwt:Key" "..."` / `list`.
- **Azure Key Vault**: `AddAzureKeyVault(...)`; `az keyvault secret list`.
- **AWS Secrets Manager**: `aws secretsmanager get-secret-value --secret-id <id>`.
- **Google Secret Manager**: `gcloud secrets versions access latest --secret=<id>`.
- **HashiCorp Vault**: `vault kv get secret/<path>`.
- **Kubernetes secrets / Docker secrets**: `valueFrom.secretKeyRef`, `/run/secrets/<name>`, `*_FILE` env conventions.

## Config / deploy hardening checkers
- **.NET**: analyzers; confirm `ASPNETCORE_ENVIRONMENT=Production`, HSTS/HTTPS on.
- **Django**: `python manage.py check --deploy`.
- **Node**: `helmet`, `npm audit`; ensure `NODE_ENV=production`.
- **Containers/IaC**: `trivy config .`, `checkov -d .`, `kube-linter`, `hadolint Dockerfile`.

## After confirming a committed secret
1. **Rotate** the secret immediately (assume it is compromised).
2. **Purge** it from history: `git filter-repo --path <file> --invert-paths` or BFG
   (`bfg --replace-text secrets.txt`), then force-push after coordinating.
3. Move the value to env / a secret manager and reference it from config.
4. List the offending commits (from `git_secret_scan.py` or the scanner) in the
   "commits to purge" section of the report.

## Choosing
- Need verified-live results -> trufflehog `--only-verified`.
- Need a CI gate with a baseline -> detect-secrets or gitleaks.
- Nothing installed / air-gapped -> `scripts/git_secret_scan.py`.
