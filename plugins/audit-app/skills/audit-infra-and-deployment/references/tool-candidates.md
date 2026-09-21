# Infra linting tool candidates (with invocations)

`scripts/lint_infra.py` is the stdlib baseline. It already runs **hadolint**,
**trivy config** and **checkov** when they are on PATH, and records each one as
"not-installed" otherwise. The rest of this list are optional tools to run by
hand when available. Save raw output under
`audit/evidence/audit-infra-and-deployment/` and turn confirmed items into
findings. Tool ids (DL3002, CKV_K8S_13, KSV012) go in the Reference field next
to the CIS id from `infra-checklist.md`.

Check availability first: `hadolint --version`, `trivy --version`, `checkov --version`,
`kube-score version`, `kube-linter version`, `tfsec --version`. On Windows use
`where <tool>`.

## Dockerfile

### hadolint
- Lints Dockerfile instructions and shells out to ShellCheck for `RUN` lines.
- `hadolint Dockerfile`
- JSON, never fail the shell: `hadolint --no-fail --format json Dockerfile > hadolint.json`
- Without installing: `docker run --rm -i hadolint/hadolint < Dockerfile`
- Useful rules: DL3002 (last USER root), DL3006/DL3007 (untagged/latest), DL3008/DL3018 (pin apt/apk), DL3009 (apt lists), DL3015 (no-install-recommends), DL3020 (ADD vs COPY), DL3025 (JSON CMD), DL3042 (pip cache), DL4006 (pipefail).
- Config: `.hadolint.yaml` (`ignored:`, `trustedRegistries:`). Review any `ignored` entries as part of the audit.

### trivy config (Dockerfile, Kubernetes, Helm, Terraform, CloudFormation, ARM)
- `trivy config .`
- JSON: `trivy config --format json --quiet . > trivy-config.json`
- Only high/critical: `trivy config --severity HIGH,CRITICAL .`
- Helm values: `trivy config --helm-values values-prod.yaml ./chart`
- Ids: `DS002` (root user), `DS001` (latest tag), `DS026` (no HEALTHCHECK), `KSV001` (privilege escalation), `KSV011`/`KSV018` (CPU/memory limits), `KSV012` (runAsNonRoot), `KSV014` (read-only root fs). Terraform checks use `AVD-AWS-*`/`AVD-AZU-*` ids. trivy now contains the former tfsec engine.
- Image contents (CVEs) are out of scope here: `trivy image` belongs to audit-dependency-vulnerabilities.

### docker scout / dive (optional)
- `docker scout quickview <image>`, `docker scout recommendations <image>` for base image upgrade advice.
- `dive <image>` to inspect layers for leftover secrets or build caches (`CI=true dive <image>` for a pass/fail efficiency check).
- `docker history --no-trunc <image>` shows `ENV`/`ARG` values baked into layers.

## Multi-framework policy scanner

### checkov
- `checkov -d .`
- JSON: `checkov -d . -o json --quiet --compact > checkov.json`
- Scope: `checkov -d . --framework dockerfile kubernetes helm terraform bicep arm cloudformation`
- Single file: `checkov -f deploy/k8s/api-deployment.yaml`
- Terraform plan (resolves variables): `terraform plan -out tf.plan && terraform show -json tf.plan > tf.json && checkov -f tf.json`
- Ids: `CKV_DOCKER_2/3/7/8`, `CKV_K8S_8..16/20/22/23/28/35/37/40/43`, `CKV2_K8S_6` (NetworkPolicy), `CKV_AWS_16/17/133`, `CKV_AZURE_14/15`, `CKV_SECRET_*`.
- Inline skips (`#checkov:skip=CKV_K8S_13:reason`) are part of the evidence. Read the reasons.

## Kubernetes-specific

### kube-score
- `kube-score score deploy/k8s/*.yaml`
- Helm: `helm template app ./chart -f values-prod.yaml | kube-score score -`
- CI output: `kube-score score --output-format ci deploy/k8s/*.yaml`
- Checks container resources, probes (including identical liveness/readiness), image tag and pull policy, NetworkPolicy targeting, PodDisruptionBudget, security context, and HPA vs replicas.

### kube-linter
- `kube-linter lint deploy/k8s/`
- Helm chart directory: `kube-linter lint ./chart`
- JSON: `kube-linter lint --format json deploy/k8s/ > kube-linter.json`
- All checks: `kube-linter checks list`; enable extra ones with `--add-all-built-in`.
- Notable checks: `run-as-non-root`, `no-read-only-root-fs`, `unset-cpu-requirements`, `unset-memory-requirements`, `no-liveness-probe`, `no-readiness-probe`, `latest-tag`, `env-var-secret`, `privilege-escalation-container`, `default-service-account`.

### Also useful
- `kubeconform -strict -summary deploy/k8s/` - schema validation against the target Kubernetes version.
- `polaris audit --audit-path deploy/k8s/ --format pretty`.
- `helm lint --strict ./chart -f values-prod.yaml`.
- Live cluster (only if the user grants access, and read-only): `kubectl get networkpolicy -A`, `kubectl rollout history deploy/<name> -n <ns>`, `kubectl get deploy -A -o jsonpath='{..resources}'`.

## Terraform

### tfsec (now maintained as part of trivy)
- `tfsec .`
- JSON: `tfsec . --format json > tfsec.json`
- Per environment: `tfsec . --tfvars-file envs/prod.tfvars`
- Equivalent in trivy: `trivy config --tf-vars envs/prod.tfvars .`

### Also useful
- `terraform validate` and `terraform fmt -check -recursive`.
- `tflint --recursive` (provider-specific rules, e.g. invalid instance types).
- `terraform state list` is **not** read-only-safe on a shared backend if it triggers a lock or migration. Only run it if the user explicitly allows it.

## Bicep / ARM / CloudFormation
- `az bicep build --file main.bicep` (also runs the Bicep linter; config in `bicepconfig.json`).
- PSRule for Azure: `Invoke-PSRule -InputPath . -Module PSRule.Rules.Azure -Format File`.
- `cfn-lint templates/**/*.yaml`; `cfn_nag_scan --input-path templates/`.

## nginx / TLS
- `gixy /path/to/nginx.conf` - nginx misconfiguration (host header, alias traversal, add_header inheritance).
- Live endpoint (only with permission): `testssl.sh https://host` or `nmap --script ssl-enum-ciphers -p 443 host`. `sslyze host` is a Python alternative.

## Backup, restore and rollback evidence (manual commands to request from the owner)
- Azure SQL: `az sql db ltr-policy show`, `az sql db show --query earliestRestoreDate`, activity log entries for past restores.
- AWS RDS: `aws rds describe-db-instances --query "DBInstances[].BackupRetentionPeriod"`, `aws backup list-restore-jobs`.
- Kubernetes/Velero: `velero schedule get`, `velero restore get` (past restores with dates).
- Helm: `helm history <release>` shows past rollbacks as `Rollback to N` entries with timestamps.
- App Service: `az webapp deployment slot list`, activity log `swap` operations.

A command output that shows a completed restore or rollback with a date is valid
evidence for "tested on <date>". Save it under `audit/evidence/audit-infra-and-deployment/`.
