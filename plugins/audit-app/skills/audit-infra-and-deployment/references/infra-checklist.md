# Infra & deployment checklist (Docker, Compose, Kubernetes, Helm, Terraform, Bicep/ARM, CloudFormation)

This file is the topic checklist behind `scripts/lint_infra.py`. Each row gives
the check, why it matters, the benchmark or tool ids to cite in the finding's
Reference field, the `lint_infra.py` check id (automated) or "manual", and a
default severity. Adjust the severity with the rubric in
`audit-finding-writer/references/severity-rubric.md`.

CIS numbering: CIS Docker Benchmark section 4 (images and build files) has been
stable from v1.2 to v1.6. Section 5 (container runtime) shifts between versions,
so cite it as "CIS-Docker-5.x (<control title>)" and confirm the number against
the version the organisation uses. Kubernetes ids are from CIS Kubernetes Benchmark
v1.8/v1.9 section 5 (policies).

## 1. Container build files (Dockerfile / Containerfile)

| Check | Why | Reference ids | lint_infra | Default severity |
|---|---|---|---|---|
| Final stage runs as a non-root `USER` | A container escape or RCE starts as root, and root can write the filesystem | CIS-Docker-4.1; hadolint DL3002; CKV_DOCKER_3/CKV_DOCKER_8; trivy DS002; CWE-250 | DF-NONROOT | Medium (High if combined with privileged/hostPath) |
| Multi-stage build; runtime stage has no SDK/compiler/source | Smaller attack surface, no source or build caches shipped | CIS-Docker-4.3 | DF-MULTISTAGE | Low-Medium |
| Base images pinned: tag, preferably tag plus `@sha256:` digest | `latest` makes builds non-reproducible and lets an upstream change reach production unreviewed | CIS-Docker-4.2; hadolint DL3006/DL3007; CKV_DOCKER_7; trivy DS001 | DF-PINNED-BASE | Low (Medium for production images with no rebuild policy) |
| No secrets in `COPY`/`ADD`, `ENV`, `ARG`, or `RUN` | Layers and image config are readable by anyone who can pull the image, and deleting a file in a later layer does not remove it | CIS-Docker-4.10; CWE-798; CWE-538 | DF-NO-SECRETS | High (Critical if the image is in a public or shared registry) |
| Minimal runtime image (slim/alpine/distroless/chiseled; `--no-install-recommends`, `--no-cache`, `--no-cache-dir`) | Fewer packages means fewer CVEs and fewer tools for an attacker | CIS-Docker-4.3; hadolint DL3015/DL3009/DL3018/DL3042 | DF-MINIMAL | Low |
| `.dockerignore` excludes `.git`, `.env*`, `bin/obj/node_modules`, keys | `COPY . .` otherwise sends local secrets and history into the build context and often into the image | CWE-538 | DF-DOCKERIGNORE | Low (High when a secret demonstrably lands in the image) |
| `HEALTHCHECK` (only where no orchestrator probes exist) | Docker/Compose restarts only on process exit without it | CIS-Docker-4.6; CKV_DOCKER_2; trivy DS026 | DF-HEALTHCHECK | Low |
| `COPY` rather than `ADD` for local files; no `ADD http...` | `ADD` auto-extracts archives and fetches remote URLs unverified | CIS-Docker-4.9; hadolint DL3020 | manual / hadolint | Low |
| No `curl ... \| sh` without checksum verification | Supply-chain injection at build time | CIS-Docker-4.11 | grep `CURL-PIPE-SH` | Medium |
| Images scanned and rebuilt for patched bases | Pinned digests go stale; pinning needs a rebuild cadence (Renovate/Dependabot) | CIS-Docker-4.4 | manual (hand off to audit-dependency-vulnerabilities) | Medium |
| Content trust / image signing (cosign, Notation) | Proves the deployed image is the one CI built | CIS-Docker-4.5 | manual | Low-Medium |

## 2. docker-compose (when used for production or staging)

| Check | Reference ids | lint_infra | Default severity |
|---|---|---|---|
| `deploy.resources.limits` / `mem_limit` / `cpus` on every service | CIS-Docker-5.x (memory usage limited, CPU priority set); CWE-770 | CMP-LIMITS | Medium |
| `healthcheck` per service; `depends_on: condition: service_healthy` | CIS-Docker-4.6 / 5.x (container health checked at runtime) | CMP-HEALTHCHECK | Low |
| No literal secrets in `environment:`; use `secrets:` or `${VAR}` from an untracked env file | CWE-798 | CMP-SECRETS | High |
| No `privileged`, `network_mode: host`, `pid: host`, `cap_add: ALL`, docker.sock mounts, `user: root` | CIS-Docker-5.x (privileged containers, host network namespace, host devices, docker socket) | CMP-SECURITY | High |
| Image tags pinned | CIS-Docker-4.2 | CMP-IMAGE-PINNED | Low |
| `restart: unless-stopped` and named volumes with a backup job for stateful services | SOC2-A1.2 | manual | Medium |

A compose file that is only used for local development (`docker-compose.override.yml`, a `dev` profile) is out of scope. State it once in Not checked instead of scoring it.

## 3. Kubernetes manifests

| Check | Reference ids | lint_infra | Default severity |
|---|---|---|---|
| `resources.limits.memory` (and a CPU limit or deliberate no-limit policy) on every container | NSA/CISA Kubernetes Hardening Guide (resource policies); CKV_K8S_11/CKV_K8S_13; kube-score container-resources; CWE-770 | K8S-LIMITS | Medium |
| `resources.requests.cpu/memory` | CKV_K8S_10/CKV_K8S_12 | K8S-REQUESTS | Low-Medium |
| `livenessProbe` that does not depend on external services | CKV_K8S_8; kube-score pod-probes | K8S-LIVENESS | Medium |
| `readinessProbe` that reflects dependency health | CKV_K8S_9 | K8S-READINESS | Medium |
| `securityContext`: `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, not `privileged`, no `hostNetwork/hostPID/hostIPC` | CIS-K8s-5.2.2 (privileged), 5.2.3 (hostPID), 5.2.4 (hostIPC), 5.2.5 (hostNetwork), 5.2.6 (allowPrivilegeEscalation), 5.2.7 (root containers); CKV_K8S_16/20/23 | K8S-SECURITY-CONTEXT | Medium (High for privileged/host namespaces) |
| `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault` | CIS-K8s-5.2.8/5.2.9 (capabilities), 5.7.2 (seccomp), 5.7.3 (security context); CKV_K8S_22/28/37 | K8S-SECURITY-CONTEXT (recommended note) | Low |
| Secrets via `secretKeyRef`/`envFrom.secretRef`/CSI driver/External Secrets, never literal `env.value`; no committed `Secret` with data | CIS-K8s-5.4.1 (secrets as files over env), 5.4.2 (external secret storage); CKV_K8S_35; CWE-798 | K8S-SECRETS | High |
| Image pinned (no `:latest`, digest preferred), `imagePullPolicy` consistent | CKV_K8S_14/CKV_K8S_43; kube-score container-image-tag | K8S-IMAGE-PINNED | Low-Medium |
| `NetworkPolicy` (default deny plus explicit allows) in every namespace with workloads | CIS-K8s-5.3.2; CKV2_K8S_6 | K8S-NETWORK-POLICY | Medium |
| Ingress has `tls:` (or TLS verifiably terminated at the load balancer/CDN) and HTTP redirects | CWE-319 | K8S-INGRESS-TLS | High for authenticated apps |
| `revisionHistoryLimit` > 0; rollout strategy defined | Rollback readiness | K8S-ROLLBACK-HISTORY | Medium |
| PodDisruptionBudget, `replicas >= 2`, topology spread for stateless services | Availability (SOC2-A1.1) | manual | Low-Medium |
| Default service account not used; `automountServiceAccountToken: false` where not needed | CIS-K8s-5.1.5, 5.1.6 | manual (kube-linter) | Low-Medium |
| No workloads in `default` namespace | CIS-K8s-5.7.4 | manual | Low |
| `terminationGracePeriodSeconds` covers app graceful shutdown | Zero-downtime deploys | manual | Low |

## 4. Helm charts

- Render before linting: `helm template <release> <chart> -f values-prod.yaml > rendered.yaml`, then `python scripts/lint_infra.py <repo> --extra-manifest rendered.yaml`. Unrendered templates are not valid YAML.
- `values.yaml`: `resources: {}` and `securityContext: {}` defaults (HELM-RESOURCES, HELM-SECURITY-CONTEXT), `image.tag: latest` (HELM-IMAGE-PINNED), literal passwords (HELM-SECRETS).
- Templates contain probes (HELM-PROBES); `helm lint --strict`.
- Per-environment values files (`values-staging.yaml`, `values-prod.yaml`): diff them for environment parity. Only expected keys (replicas, hosts, sizes) should differ.
- Rollback: `helm history <release>`, `helm rollback <release> <revision>`. The `--history-max` default (10) must not be 0. Chart hooks (`pre-upgrade` migration Jobs) are not reversed by `helm rollback`.

## 5. Terraform (and OpenTofu)

| Check | Reference ids | lint_infra | Default severity |
|---|---|---|---|
| No literal `password`/`secret`/`token`/`access_key` attributes; use `sensitive` variables fed from a secret manager or `random_password` + secret store | CWE-798; CKV_SECRET_*; tfsec general-secrets | TF-SECRETS | High |
| Remote state with locking and encryption (`backend "s3"` + DynamoDB lock / `use_lockfile`, `azurerm`, `gcs`, Terraform Cloud) | State contains every secret in plain text | TF-REMOTE-STATE | Medium (High if `terraform.tfstate` is committed) |
| Managed DB automated backups (`backup_retention_period` > 0, `backup_retention_days`, `backup_configuration.enabled`) | CIS AWS Foundations section 2.3 (RDS); CKV_AWS_133; SOC2-A1.2 | TF-DB-BACKUP | High for production data |
| Storage encryption (`storage_encrypted = true`, KMS keys) | CKV_AWS_16; CWE-311 | TF-ENCRYPTION | Medium |
| No public DB (`publicly_accessible = true`) and no admin/DB ports open to `0.0.0.0/0` | CKV_AWS_17; CKV_AWS_24 (SSH), CKV_AWS_25 (RDP); CWE-284 | TF-PUBLIC-EXPOSURE | High |
| TLS minimums (`minimum_tls_version = "1.2"`, `https_only = true`, modern ELB `ssl_policy`) | CKV_AZURE_14/CKV_AZURE_15; CWE-326 | TF-TLS | Medium |
| Cross-region / cross-account backup copies, deletion protection, `prevent_destroy` on stateful resources | DR readiness | manual | Medium |
| Per-environment workspaces/tfvars share one module set | Environment parity | manual | Low |

## 6. Bicep / ARM

- `@secure()` on every password/secret/key param, with no literal defaults (BICEP-SECRETS). In ARM, use `securestring`/`secureObject` types (ARM-SECRETS).
- `httpsOnly: true`, `minTlsVersion: '1.2'`, `supportsHttpsTrafficOnly: true`, `minimumTlsVersion: 'TLS1_2'` (BICEP-TLS / ARM-TLS).
- Key Vault references in App Service settings (`@Microsoft.KeyVault(SecretUri=...)`) instead of literal connection strings.
- Backups: `Microsoft.Sql/servers/databases/backupShortTermRetentionPolicies`, `backupLongTermRetentionPolicies`, Recovery Services vault policies. Rollback: App Service deployment slots (`Microsoft.Web/sites/slots`) plus slot swap.
- Tools: `az bicep lint`, `checkov -d . --framework bicep arm`, PSRule for Azure (`Invoke-PSRule -Module PSRule.Rules.Azure`).

## 7. CloudFormation (cheap checks)

- `MasterUserPassword` via `{{resolve:secretsmanager:...}}` or `ManageMasterUserPassword: true`, never a literal (CFN-SECRETS).
- `BackupRetentionPeriod` not 0 (CFN-DB-BACKUP), `PubliclyAccessible` not true (CFN-PUBLIC-EXPOSURE), `StorageEncrypted: true` (CFN-ENCRYPTION).
- `DeletionPolicy: Snapshot` / `UpdateReplacePolicy: Snapshot` on databases; stack rollback triggers (`RollbackConfiguration` with CloudWatch alarms).
- Tools: `cfn-lint`, `checkov -d . --framework cloudformation`, `cfn_nag_scan --input-path`.

## 8. TLS termination

- Identify every hop: client, CDN/WAF, load balancer/ingress, service, database. Record where TLS terminates and whether traffic after that hop crosses an untrusted network (re-encrypt or mTLS for cross-zone/cross-cloud traffic).
- Minimum TLS 1.2, with TLS 1.3 preferred; no SSLv3/TLSv1/TLSv1.1 (TLS-PROTOCOLS for nginx, TF-TLS, BICEP-TLS). HTTP redirects to HTTPS at the first hop; HSTS is covered by audit-security-headers-and-middleware.
- Certificates are automated (cert-manager `Certificate`/`ClusterIssuer`, ACM, App Service managed certs, Let's Encrypt) with renewal alerting. Manually uploaded `.pfx` files expire silently.
- The application trusts forwarded headers only from the proxy (see the stack file: `UseForwardedHeaders`, `trust proxy`, `SECURE_PROXY_SSL_HEADER`, `server.forward-headers-strategy`).
- Database connections use TLS (`Encrypt=True;TrustServerCertificate=False`, `sslmode=verify-full`).

## 9. Backup automation and tested restore

Evidence that counts, strongest first:
1. A dated restore test record: a runbook entry, ticket, CI job log, or DR drill report naming the backup restored, the target, the duration and a data check. This supports "tested on <date>".
2. An automated restore verification job (a scheduled restore into a scratch database with a row-count or checksum check).
3. Backup automation configured in IaC or the platform (retention, schedule, cross-region copy) with no restore record. This is still "never tested".
4. A statement that "the provider backs it up". Treat it as unverified and "never tested".

Also check: file/blob storage and uploaded media are backed up, not just the database; backups are encrypted and in a separate account/subscription or immutable storage (ransomware); retention meets the stated RPO; access to backups is restricted and logged.

Readiness statement format (fixed): `Backup restore: tested on YYYY-MM-DD` or `Backup restore: never tested`, followed by the evidence (file:line, ticket id, or "no dated restore record found in the repository; owner confirmation requested").

## 10. Disaster-recovery plan

- A written plan exists (DR.md, runbook, wiki link recorded in the repo) with RTO and RPO per system, named owners, the contact tree, and the order of recovery (DNS, secrets, database, services, frontend).
- Infrastructure can be recreated from code in a second region or subscription. Secrets and state backends are recoverable too; a Key Vault or KMS key that exists only in the failed region blocks recovery.
- Last DR exercise date and outcome. Rehearsal is recorded like a restore test.
- Single points of failure are named (single-region database, single ingress controller, one person with production access).

## 11. Environment parity

- The same artefact (image digest, bundle) is promoted from staging to production, not rebuilt per environment.
- Environment config differs only in values, not in keys or features. Diff `appsettings.Staging.json` against `appsettings.Production.json`, `values-staging.yaml` against `values-prod.yaml`, and kustomize overlays, and flag keys present in one but not the other.
- Staging runs the same orchestrator, the same IaC modules, and the same TLS/ingress path as production. "Works in staging" on docker-compose says little about Kubernetes production.
- Data: staging does not use production data without masking (hand PII questions to audit-privacy-data-flow-mapper).
- `lint_infra.py` lists the environments it saw (`readiness.environments`), and the parity comparison is manual.

## 12. Rollback mechanism

| Mechanism | Evidence in repo | How it is exercised |
|---|---|---|
| Kubernetes rolling update | Deployment with `revisionHistoryLimit` > 0 | `kubectl rollout undo deploy/<name> [--to-revision=N]` |
| Helm | chart + release naming in pipeline | `helm rollback <release> <rev>` |
| Blue/green | two Deployments/Services, Argo Rollouts `blueGreen`, App Service slots, CodeDeploy `BlueGreen` | switch service selector / `az webapp deployment slot swap` back |
| Canary | Argo Rollouts `canary`, Flagger `Canary`, ingress weight annotations | abort the rollout (`kubectl argo rollouts abort`) |
| PaaS instant rollback | Vercel/Netlify/Amplify config | platform rollback command or UI |
| Documented manual steps | runbook section | only counts if rehearsed with a date |

Always check database migration compatibility. A rollback of the code is not a rollback if the schema moved forward with a destructive migration. Look for expand/contract migrations or tested down scripts.

Readiness statement format (fixed): `Rollback: tested on YYYY-MM-DD` or `Rollback: never tested`, plus the mechanism and evidence.
