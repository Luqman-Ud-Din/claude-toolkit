---
name: audit-infra-and-deployment
description: Reviews deployment artifacts and infrastructure-as-code - Dockerfiles (non-root user, multi-stage build, pinned base images, no baked-in secrets, minimal image, .dockerignore), docker-compose, Kubernetes, Helm, Terraform, Bicep/ARM and CloudFormation manifests (resource limits and requests, liveness/readiness probes, secrets from a manager, network policies, securityContext), TLS termination, backup automation with a tested restore, disaster-recovery plan, environment parity, and rollback mechanism (blue/green, canary, rehearsed manual steps) - producing findings, a container/manifest scorecard and a backup/rollback readiness statement (tested on date X or never tested). Use it whenever the user asks about containers, Docker, Kubernetes, Helm, orchestration, deployment, infrastructure, IaC, Terraform, hosting configuration, TLS termination, backups, restore tests, disaster recovery, RTO/RPO, rollback, blue/green or canary releases, or production infra readiness - even when they do not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit infra and deployment

Code that passes every application review can still fail in production because of
how it is packaged and run. Typical causes: an image running as root with a
connection string in a layer, a pod with no memory limit that takes down its node,
a backup nobody has ever restored, or a rollback that only exists as a sentence in
a wiki. This skill reviews the deployment artifacts and IaC in the repository.
It answers three questions: are the images and manifests safe, could we recover
the data, and could we undo a bad release?

**Read-only rule:** never modify the audited repository and never change real
infrastructure. Do not run `docker build/push`, `kubectl apply`, `helm upgrade`,
`terraform plan/apply` against a real backend, or restores. Read files, run the
bundled linter, and ask the owner for command output (see
`references/tool-candidates.md`) when evidence lives outside the repo. Write only
under `audit/`.

## Inputs and prerequisites

- The repository root. Container files, manifests, IaC, runbooks and docs are all inputs.
- `audit/stack.json` if the orchestrator wrote one; otherwise detect the stack.
- Optional on PATH: `hadolint`, `trivy`, `checkov`. `lint_infra.py` runs them when present and records them as not checked when absent. PyYAML improves YAML parsing to per-container precision; without it the linter uses a conservative regex scan and says so.
- Optional from the owner: backup/restore job history, the last DR drill report, `helm history` / slot swap logs. These are the only way to move the readiness statement to "tested on <date>" when the proof is not in the repo.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack detection), `audit-code-scan` (grep pass, and the shared `repo_walk.py` walker the bundled scripts import) and `audit-finding-writer` (`$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`), plus `audit-sensitive-data-catalog` (secret key names, secret values and placeholders in `lint_infra.py`). A missing one stops the scripts with an error naming it.

## Workflow

### 1. Resolve the stack
Run `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`. Open only the matching
`references/<stack>.md` for each deployable part (backend and frontend). The stack
file explains how that runtime is usually containerised and deployed, so you can
tell a real defect from an idiom. Examples: `USER $APP_UID` on .NET 8, layered
jars in Spring Boot, `npm ci --omit=dev` in Node, gunicorn instead of runserver in
Django, and nginx serving an Angular/React/Vue build. Keep
`references/infra-checklist.md` open for the benchmark ids and default severities.
If no stack matches, follow `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md` and use the checklist alone.

### 2. Automated pass
Evidence directory: `audit/evidence/audit-infra-and-deployment/`.

- **Scorecard linter** (the core of the automated pass):
  `python scripts/lint_infra.py <repo> --out audit/evidence/audit-infra-and-deployment/scorecard.json --md audit/evidence/audit-infra-and-deployment/scorecard.md --evidence-dir audit/evidence/audit-infra-and-deployment`
  It parses Dockerfiles line by line and compose/Kubernetes/Helm YAML, and runs
  cheap Terraform/Bicep/ARM/CloudFormation/nginx checks. It emits
  `file -> check -> pass/fail/n/a` rows, runs hadolint/trivy/checkov when
  installed, and drafts the readiness statement from repo evidence.
  For Helm, render first (`helm template ... > rendered.yaml`) and add
  `--extra-manifest rendered.yaml`; unrendered templates cannot be parsed.
- **Grep pass** for stack-specific deploy smells the linter does not model (dev
  servers in images, debug ports, migrations at startup, dev environment flags):
  `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/containers.json --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-infra-and-deployment/hits.json`
- **Extra tools**, only if installed: kube-score, kube-linter, tfsec, cfn-lint, gixy
  (invocations in `references/tool-candidates.md`). Save their output beside the
  scorecard.

Every `fail` row and grep hit is a candidate. It becomes a finding only after step 3.

### 3. Manual trace of the highest-risk flows
Work in this order; stop and record a gap when the evidence is outside the repo.

1. **Image to production, per service.** Which file builds the image (Dockerfile,
   `dotnet publish /t:PublishContainer`, buildpacks, Jib)? Which manifest, slot or
   platform runs it, and with which tag? A service that is deployed by hand, with
   no artifact in the repo, is itself a finding.
2. **Secrets path.** For every credential the app needs, trace where the running
   container gets it: secret manager, `secretKeyRef`, Key Vault reference,
   `/run/secrets`, or a literal in a Dockerfile, compose file, manifest, values
   file or tfvars. Anything copied into an image layer stays exposed even if a
   later layer deletes it.
3. **Runtime hardening.** User and securityContext, resource limits against the
   runtime's memory behaviour (JVM heap, .NET GC, Node heap), probes pointing at
   real health endpoints (liveness must not depend on the database), and
   NetworkPolicy coverage per namespace.
4. **Exposure and TLS termination.** List each hop (CDN/WAF, load balancer or
   ingress, service, database). Note where TLS terminates, the minimum version,
   certificate automation, HTTP-to-HTTPS redirect, whether the app trusts
   forwarded headers correctly, and whether DB connections are encrypted.
5. **Backups and restore.** Find what is backed up (databases *and*
   files/blobs/media), how (IaC setting, CronJob, provider feature), retention
   against the stated RPO, and where backups live (separate account, immutable).
   Then look for a dated restore test.
6. **Disaster recovery.** Is there a written plan with RTO/RPO, owners, recovery
   order and a second region/subscription path? Are secrets and state backends
   recoverable? When was the last exercise?
7. **Rollback.** Find the mechanism (rolling update history, `helm rollback`,
   blue/green, canary, slot swap, PaaS instant rollback, documented steps). Check
   whether database migrations allow running the previous build, and whether
   anything proves it was rehearsed.
8. **Environment parity.** Is the same artifact promoted, or rebuilt per
   environment? Diff the per-environment config files the linter lists
   (`readiness.environments`) and flag keys or features that exist in only one
   environment.

### 4. Write findings
`python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" init audit-infra-and-deployment`. For each confirmed
issue, write the finding block below to a temp JSON file and run
`python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" add audit/findings/audit-infra-and-deployment.json --from <finding.json>`.
Rate with `audit-finding-writer/references/severity-rubric.md`, starting from the
default severities in `references/infra-checklist.md`. Merge rows that share one
fix (for example, the same missing securityContext in five Deployments generated
from one Helm template) into one finding with all locations and a
`root_cause_key`. Put the CIS/tool id and the CWE in `references`. Redact secret
values in evidence.

### 5. Produce the outputs
1. **Findings.** `python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" md audit/findings/audit-infra-and-deployment.json --out audit/reports/audit-infra-and-deployment.md`, then wrap it in the template below.
2. **Container/manifest scorecard.** Copy the table from `scorecard.md` into the
   report. Correct any row the manual trace overturned and note why in Detail (for
   example "n/a - compose file is local-only"). Keep every row: pass rows show
   coverage.
3. **Backup and rollback readiness statement.** Use exactly one of these per line:
   `Backup restore: tested on YYYY-MM-DD` or `Backup restore: never tested`, and
   `Rollback: tested on YYYY-MM-DD` or `Rollback: never tested`. Follow each with
   the evidence it rests on (file:line, ticket, log excerpt saved under evidence).
   Rules:
   - The date must be when a restore or rollback was actually performed. The date a runbook was written does not count.
   - Automation without a restore record is "never tested". Say that automation exists.
   - If the owner claims a test but provides no evidence, write "never tested (owner reports a test on <date>; no evidence provided)".
   - Treat the linter's draft statement as a starting point, never the final answer.

### 6. Record what was NOT checked
Add each gap to `scope.not_checked` with a reason. Always consider:
- tools not installed (from the scorecard's tool table)
- regex fallback used instead of PyYAML
- unrendered Helm templates
- live cluster/cloud state and drift
- backup contents and restorability (they can only be proven by a restore)
- CI/CD gates (audit-test-coverage-and-ci)
- image CVEs (audit-dependency-vulnerabilities)
- HTTP security headers (audit-security-headers-and-middleware)
- folders the shared walker skips (`repo_walk.SKIP_DIRS` in `audit-code-scan`: `.git`, `node_modules`, `bin`, `obj`, `dist`, `build`, `target`, `.terraform` and similar), `.claude` and `vendor`, which `lint_infra.py` also skips on purpose, and files over 2 MB

Write `audit/status/audit-infra-and-deployment.json`:
`{"skill":"audit-infra-and-deployment","status":"completed|failed|skipped","reason":...,"started_at":...,"finished_at":...}`.
Use `skipped` with a reason when the repo has no deployment artifacts at all, but
still write one finding: "no deployment definition in repository".

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `INFRA`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Location:** `path/to/file:LINE` (object, e.g. Deployment/inventory-api)
- **Evidence:**

```lang
<the exact lines, or the lint_infra/tool row and its output>
```

- **Impact:** Plain language: what an attacker or an outage does to customers, data or uptime, with a one-line severity justification.
- **Remediation:** The concrete change in this stack's idiom (see references/<stack>.md), with a short snippet.
- **Reference:** CIS-Docker-4.x / CIS-K8s-5.x.x, tool id (DL3002, CKV_K8S_13), CWE-nnn, OWASP-A05:2021

This maps to `findings.json` fields `title`, `severity`, `confidence`, `location`,
`evidence`, `impact`, `remediation` and `references`, plus optional `tags`
(`container`, `k8s`, `iac`, `tls`, `backup`, `dr`, `rollback`, `parity`) and
`root_cause_key`.

## Output template (`audit/reports/audit-infra-and-deployment.md`)

```markdown
# Infrastructure & deployment audit

## Deployment inventory
| Service | Build artifact | Runs on | Image tag strategy | Manifest / config |
|---|---|---|---|---|
| Api | Api/Dockerfile | Kubernetes (deploy/k8s/api-deployment.yaml) | :latest | deploy/k8s/api-deployment.yaml |

## Container / manifest scorecard
YAML parser: PyYAML x.y | regex fallback. Tools: hadolint <ran|not installed>, trivy <...>, checkov <...>
| File | Object | Check | Result | Detail |
|---|---|---|---|---|
| `Api/Dockerfile:9` | - | DF-NONROOT | FAIL | last USER is 'root' |
| `Worker/Dockerfile:15` | - | DF-NONROOT | PASS | USER $APP_UID |
| `deploy/k8s/api-deployment.yaml:19` | Deployment/inventory-api | K8S-LIMITS | FAIL | no resources.limits.memory on: api |
| ... | | | | |

## TLS termination
| Hop | Terminates TLS? | Min version | Certificate source | Evidence |
|---|---|---|---|---|

## Backup & rollback readiness
- **Backup restore: never tested** - evidence: docs/deploy-runbook.md:12-13 ("backed up nightly by the hosting provider", "Restore procedure: TBD"); no dated restore record in the repository; owner asked for provider restore logs.
- **Rollback: never tested** - mechanism: rebuild previous commit and re-apply (docs/deploy-runbook.md:8-9, "has not been rehearsed yet"); `revisionHistoryLimit: 0` removes `kubectl rollout undo`.
- **DR plan:** none found (no RTO/RPO, owners or recovery order).
- **Environment parity:** <same artifact promoted? config key differences>

## Findings
(generated by $AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py md)

### Not checked
- <item> - <reason>
```

## Examples

**Input:** a scorecard row `Api/Dockerfile:5 DF-NO-SECRETS FAIL - COPY copies secret-like file 'secrets.json'; ENV ConnectionStrings__Default holds a literal secret`.
**Finding:** `[High] INFRA-001 - API image bakes secrets.json and a database connection string into its layers`.
- Location: `Api/Dockerfile:5`.
- Evidence: lines 5-6.
- Impact: anyone who can pull the image (CI, registry users, a leaked registry token) can read the production database password with `docker history`/layer extraction. Rated High, Critical if the registry is public.
- Remediation: remove both lines, add a `.dockerignore`, supply the value at runtime via a Kubernetes `secretKeyRef` mapped to `ConnectionStrings__Default`, rotate the password, and rebuild and re-push so the old image tags stop being served.
- Reference: CIS-Docker-4.10, CWE-798, CWE-538.

**Input:** `deploy/k8s/api-deployment.yaml` with no `resources` and no probes, plus `docs/deploy-runbook.md` saying the rollback "has not been rehearsed yet".
**Findings:**
- `[Medium] INFRA-004 - inventory-api pods have no resource limits or requests`. Impact: one memory leak can starve every pod on the node; the scheduler cannot place pods sensibly. Remediation: `resources: {requests: {cpu: 100m, memory: 256Mi}, limits: {memory: 512Mi}}`, sized from observed usage. Reference: CKV_K8S_11/13, CWE-770.
- `[Medium] INFRA-005 - no liveness or readiness probes`. Impact: traffic is routed to pods that are still starting or wedged, and rollouts report success for a broken release.
- The readiness statement gets `Rollback: never tested` with the runbook line as evidence.

## Bundled files

- `scripts/lint_infra.py`: stdlib scorecard linter (Dockerfile, compose, Kubernetes, Helm, Terraform, Bicep/ARM, CloudFormation, nginx). JSON and Markdown output, wraps hadolint/trivy/checkov, drafts the readiness statement. Secret names, values and placeholders come from `audit-sensitive-data-catalog`.
- `scripts/patterns/containers.json` (cross-stack) and `scripts/patterns/<stack>.json` (dotnet, java-spring, node-express, python-django, angular, react, vue): the grep pass, run by `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`.
- Atomic scripts called: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`, `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`, `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`. `lint_infra.py` imports `repo_walk.py` (audit-code-scan) and `catalog.py` (audit-sensitive-data-catalog).
- `references/<stack>.md`: how each runtime is containerised and deployed, its dangerous patterns and false positives (dotnet, java-spring, node-express, python-django, angular, react, vue). To add a stack, start from `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `references/infra-checklist.md`: Docker/Compose/Kubernetes/Helm/Terraform/Bicep/CloudFormation, TLS, backup, DR, parity and rollback checks with CIS and tool ids and default severities.
- `references/tool-candidates.md`: hadolint, trivy config, checkov, kube-score, kube-linter, tfsec and others, with invocations, plus commands to request backup/rollback evidence from owners.
- `evals/`: a sample .NET repo with a root Dockerfile that copies a secrets file, a Deployment without limits/probes, an unrehearsed runbook, and a clean multi-stage non-root Worker Dockerfile as the negative.
