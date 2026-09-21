#!/usr/bin/env python3
"""Build the SOC 2 control-to-evidence matrix from the evidence folder and the
repository source.

Usage:
    python soc2_matrix.py <repo_root> [--evidence audit/evidence/audit-soc2-controls-evidence]
                          [--out control-matrix.json] [--md control-matrix.md]

Inputs:
  * <evidence>/index.json written by collect_evidence.py (run it first; if missing, the
    matrix still runs on the source but branch protection and API-only evidence are not-checked).
  * Optional sibling outputs under <repo>/audit/: the privacy inventory
    (evidence/audit-privacy-data-flow-mapper/data-inventory.json), dependency findings
    (findings/audit-dependency-vulnerabilities.json) and GDPR checks
    (evidence/audit-gdpr-data-protection/gdpr-checks.json).

Output: one row per control (ids in references/tsc-criteria-map.md):
  {"id", "criterion", "control", "status": implemented|partial|missing|organisational|not-checked,
   "evidence": [{"file", "line", "snippet", "note"}], "note", "owner"}
plus an organisational-gaps list. Read-only against the audited repo.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone

def _audit_core_skills_dir():
    """Resolve the explicit core installation, or the original sibling layout."""
    env = os.environ.get("AUDIT_CORE_ROOT")
    if env:
        skills = os.path.join(env, "skills")
        if os.path.isdir(os.path.join(skills, "audit-code-scan")):
            return skills
        sys.exit("AUDIT_CORE_ROOT does not contain audit-core skills: " + env)
    sibling = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if os.path.isdir(os.path.join(sibling, "audit-code-scan")):
        return sibling
    sys.exit("audit-core is unavailable. Enable audit-core and restart Claude Code, "
             "or set AUDIT_CORE_ROOT to its plugin directory when running manually.")

_SKILLS = _audit_core_skills_dir()
_WALK = os.path.join(_SKILLS, "audit-code-scan", "scripts", "repo_walk.py")
try:
    _spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", _WALK)
    repo_walk = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(repo_walk)
except (FileNotFoundError, AttributeError, ImportError):
    sys.exit("audit-code-scan must be reachable from this skill (audit-core plugin or sibling layout; expected " + _WALK + ")")
_SDC_PATH = os.path.join(_SKILLS, "audit-sensitive-data-catalog", "scripts", "catalog.py")
if not os.path.exists(_SDC_PATH):
    sys.exit("audit-sensitive-data-catalog must be reachable from this skill (audit-core plugin or sibling layout; expected " + _SDC_PATH + ")")
_spec = importlib.util.spec_from_file_location("sensitive_data_catalog", _SDC_PATH)
sdc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sdc)
_GH_PATH = os.path.join(_SKILLS, "audit-git-history", "scripts", "githist.py")
if not os.path.exists(_GH_PATH):
    sys.exit("audit-git-history must be reachable from this skill (audit-core plugin or sibling layout; expected " + _GH_PATH + ")")
_spec = importlib.util.spec_from_file_location("audit_git_history_githist", _GH_PATH)
githist = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = githist
_spec.loader.exec_module(githist)

SECRETISH = ("credential", "secret")
CODE_EXT = {".cs", ".java", ".kt", ".ts", ".tsx", ".js", ".jsx", ".vue", ".py", ".rb", ".go", ".php", ".sql",
            ".json", ".yml", ".yaml", ".xml", ".properties", ".toml", ".env", ".md", ".txt", ".sh", ".ps1",
            ".tf", ".bicep", ".cshtml", ".html", ".config", ""}
MAX_BYTES = 1_500_000

RX = {
    # access control
    "auth": re.compile(r"\b(?:UseAuthentication|AddAuthentication|AddJwtBearer|AddOpenIdConnect|AddMicrosoftIdentityWebApi|@EnableWebSecurity|SecurityFilterChain|oauth2Login|passport\.(?:use|authenticate)|express-jwt|jsonwebtoken|@nestjs/passport|AuthGuard|AUTHENTICATION_BACKENDS|rest_framework\.authentication|LoginRequiredMixin|@login_required|IsAuthenticated|JwtStrategy|next-auth|Auth0|Keycloak)\b", re.I),
    "sso": re.compile(r"\b(?:OpenIdConnect|oidc|OIDC|saml|SAML|Okta|okta|Auth0|auth0|Keycloak|keycloak|AzureAd|MicrosoftIdentity|EntraId|Entra|GoogleWorkspace|oauth2Login|passport-saml|passport-azure-ad|django-allauth|mozilla-django-oidc|social_django|next-auth)\b"),
    "mfa": re.compile(r"\b(?:mfa|MFA|2fa|TwoFactor|two[_\-]?factor|totp|TOTP|Authenticator|otp[_\-]?(?:verify|code|secret)|WebAuthn|webauthn|passkey|django_otp|pyotp|speakeasy|otplib|RequireMfa|amr)\b"),
    "rbac": re.compile(r"\[Authorize\s*\(\s*(?:Roles|Policy)\s*=|RequireRole|AddPolicy|@PreAuthorize|@Secured|hasRole|hasAuthority|@RolesAllowed|@Roles\(|RolesGuard|requireRole|checkRole|permission_required|DjangoModelPermissions|IsAdminUser|has_perm|CustomRoles\.|\bRoleGuard\b|casl|accesscontrol", re.I),
    "authorize_any": re.compile(r"\[Authorize\]|@PreAuthorize|IsAuthenticated|@login_required|AuthGuard|requireAuth|ensureAuthenticated|passport\.authenticate", re.I),
    "admin_action_log": re.compile(r"\b(?:AuditLog\w*|audit_log\w*|AuditTrail|@Audited|Envers|auditlog|simple_history|HistoricalRecords|IsTemporal|SYSTEM_VERSIONING|EntitySubscriber|AdminActionLog|admin_log|LogEntry|ActivityLog|activity_log|UserActivity)\b"),
    "deprovision": re.compile(r"\b(?:Deactivate\w*|deactivate\w*|Disable(?:User|Account)\w*|disable_user|LockoutEnd|is_active\s*=\s*False|IsActive\s*=\s*false|RevokeAllTokens|revokeTokens|offboard\w*|Offboard\w*|SuspendUser|suspend_user)\b"),
    # change management
    "ci_test": re.compile(r"\b(?:dotnet test|npm (?:run )?test|yarn test|pnpm test|pytest|mvn (?:-B )?(?:test|verify)|gradle(?:w)? (?:test|check)|go test|jest|vitest|karma|phpunit)\b", re.I),
    "ci_scan": re.compile(r"\b(?:npm audit|pnpm audit|yarn audit|dotnet list .*--vulnerable|pip-audit|safety check|trivy|grype|snyk|dependency-check|codeql|github/codeql-action|semgrep|sonar(?:qube|cloud)?|sonarsource|gitleaks|trufflehog|bandit|brakeman|zap|owasp|checkov|tfsec|kics|anchore|ossf/scorecard)\b", re.I),
    "ci_deploy": re.compile(r"\b(?:deploy|release|publish|kubectl apply|helm upgrade|az webapp|aws deploy|docker push|terraform apply|cdk deploy|serverless deploy|gcloud run deploy|dotnet publish)\b", re.I),
    "ci_env_protect": re.compile(r"environment\s*:\s*(?:\n\s*name\s*:\s*)?['\"]?(?:prod|production|live)|workflow_dispatch|required_reviewers|protection_rules", re.I),
    "ci_direct_prod": re.compile(r"if:\s*github\.ref\s*==\s*['\"]refs/heads/(?:main|master|production|release)['\"]|branches:\s*\[\s*(?:main|master|production)", re.I),
    "protection_off": re.compile(r"protection\s*:\s*(?:null|~|false)|required_pull_request_reviews\s*:\s*(?:null|~)|required_status_checks\s*:\s*(?:null|~)|enforce_admins\s*:\s*false|\"message\"\s*:\s*\"Branch not protected\"|Branch not protected", re.I),
    "protection_on": re.compile(r"required_approving_review_count\s*[:=]\s*[1-9]|\"required_pull_request_reviews\"\s*:\s*\{|required_status_checks\s*:\s*\{|\"required_status_checks\"\s*:\s*\{|\"enforce_admins\"\s*:\s*\{\s*\"enabled\"\s*:\s*true|enforce_admins\s*:\s*true|\"type\"\s*:\s*\"pull_request\"|require_code_owner_reviews\s*:\s*true", re.I),
    # logging / monitoring
    "log_central": re.compile(r"\b(?:Seq|Elasticsearch|Loki|Logstash|Splunk|Datadog|datadoghq|CloudWatch|ApplicationInsights|Sentry|Stackdriver|google\.cloud\.logging|MSSqlServer|winston\.transports\.(?:Http|File|Stream)|pino-(?:datadog|elasticsearch|loki)|SysLogHandler|HTTPHandler|WatchedFileHandler|RotatingFileHandler|logback|log4j2|fluentd|fluent-bit|filebeat|papertrail|logtail|betterstack|syslog|WriteTo\.(?:File|Seq|MSSqlServer|Elasticsearch|ApplicationInsights|Datadog|Splunk))\b", re.I),
    "log_console_only": re.compile(r"WriteTo\.Console\(\)|\"Name\"\s*:\s*\"Console\"|winston\.transports\.Console|StreamHandler\(\)|ConsoleAppender", re.I),
    "log_retention": re.compile(r"\b(?:retainedFileCountLimit|maxHistory|maxFiles|backupCount|retention_in_days|retention_days|retentionInDays|log_retention|RetentionPolicy|rollingInterval|RollingFile|TimedRotating)\b", re.I),
    "log_immutable": re.compile(r"\b(?:object_lock|ObjectLock|immutab\w*|WORM|append[_\-]?only|tamper|LogAnalyticsWorkspace|immutability_policy|compliance_mode)\b", re.I),
    "security_events": re.compile(r"\b(?:failed[_\-]?login\w*|login[_\-]?fail\w*|LoginFailed|InvalidCredentials|lockout|Lockout|axes|AuthenticationFailure\w*|user_login_failed|privilege[_\-]?change\w*|RoleChanged|role[_\-]?changed|PasswordChanged|SecurityEvent\w*|security[_\-]?event\w*)\b"),
    "alerting": re.compile(r"\b(?:PagerDuty|pagerduty|OpsGenie|opsgenie|AlertRule|alertmanager|Alertmanager|aws_cloudwatch_metric_alarm|azurerm_monitor_metric_alert|google_monitoring_alert_policy|datadog_monitor|Grafana alert|SendAlert|hooks\.slack\.com|slack[_\-]?webhook|alerts?\.ya?ml|notification_channel)\b"),
    "health": re.compile(r"/(?:healthz?|readyz|livez)\b|\b(?:MapHealthChecks|AddHealthChecks|HEALTHCHECK|actuator/health|livenessProbe|readinessProbe|uptime[_\-]?(?:robot|kuma|check)|StatusCake|pingdom|healthcheck)\b", re.I),
    # vulnerability mgmt
    "dependabot": re.compile(r"(?:^|/)\.github/dependabot\.ya?ml$|renovate\.json|\.renovaterc", re.I),
    # availability
    "backup": re.compile(r"\b(?:pg_dump|mysqldump|mongodump|BACKUP DATABASE|velero|aws_backup_plan|azurerm_backup|backup_retention_period|BackupPolicy|snapshot_identifier|rds_cluster.*backup|backup\.sh|backup\.ps1|Backup-Sql|AzureBackup|gsutil rsync.*backup|s3 (?:cp|sync).*backup)\b", re.I),
    "backup_encrypted": re.compile(r"(?:--sse|--encrypt)\b|\b(?:sse[_\-]?(?:kms|s3)|ServerSideEncryption|kms_key|storage_encrypted\s*=\s*true|gpg|age -r|encrypted\s*=\s*true)\b", re.I),
    "backup_retention": re.compile(r"\b(?:retention|-mtime\s*\+\d+|lifecycle|expire|keep\s+\d+\s+days|backup_retention_period|delete_after|DeleteAfter)\b", re.I),
    "restore_test": re.compile(r"\b(?:restore[_\-\s]?(?:test|drill|exercise|verification|verified|validated|rehearsal)|test[_\-\s]?restore|restore[_\-\s]?tested|DR[_\-\s]?(?:test|drill|exercise)|disaster[_\-\s]?recovery[_\-\s]?(?:test|drill)|game[_\-\s]?day|last restored|restored on|restore (?:was )?(?:performed|completed|verified) (?:on|at)|RTO|RPO)\b", re.I),
    "restore_instructions": re.compile(r"\b(?:restore|pg_restore|psql\s+\"?\$?\w*DATABASE|mysql\s+<|mongorestore|RESTORE DATABASE)\b", re.I),
    "dr_plan": re.compile(r"\b(?:disaster[_\-\s]?recovery|DR[_\-\s]?plan|business[_\-\s]?continuity|BCP|failover|multi[_\-]?(?:az|region)|RTO|RPO)\b", re.I),
    # confidentiality
    "encrypt_transit": re.compile(r"\b(?:UseHttpsRedirection|UseHsts|Encrypt=True|sslmode=require|SECURE_SSL_REDIRECT\s*=\s*True|helmet\s*\(|requiresSecure|server\.ssl\.enabled\s*=\s*true|tls:|ssl:\s*\{)\b", re.I),
    "encrypt_rest": re.compile(r"\b(?:IsEncrypted|EncryptedColumn|AttributeEncryptor|@Convert\s*\(\s*converter|pgcrypto|EncryptedField|fernet|AlwaysEncrypted|Always Encrypted|DataProtection|IDataProtector|KMS|KeyVault|Key Vault|aws:kms|sse-kms|storage_encrypted\s*=\s*true|TDE\b|Transparent Data Encryption)\b"),
    "secrets_ext": re.compile(r"\$\{\{\s*secrets\.|\$\{[A-Z_]+\}|\b(?:AddAzureKeyVault|KeyVault|Key Vault|SecretsManager|secretsmanager|VaultClient|vault\.|HashiCorp|sops|SealedSecret|ExternalSecret|\$\{\{\s*secrets\.|process\.env\.|os\.environ|Environment\.GetEnvironmentVariable|builder\.Configuration\[|AddUserSecrets|\$\{[A-Z_]+\})", re.I),
    "key_rotation": re.compile(r"\b(?:rotat\w+|KeyRotation|rotation_period|RotateKey|expire_after|key[_\-]?version)\b", re.I),
    "classification": re.compile(r"\b(?:data[_\-\s]?classification|DataClassification|\[Sensitive\]|\[PersonalData\]|Classification\s*=|confidential|restricted|internal[_\-\s]?only)\b", re.I),
    "retention_job": re.compile(r"\b(?:RecurringJob|@Scheduled|cron\.schedule|CronJob|@Cron|beat_schedule|celery)\b.*|\b(?:purge\w*|prune\w*|cleanup|older[_ ]?than|delete\w*old|anonymi[sz]e\w*)\b", re.I),
    # processing integrity
    "validation": re.compile(r"\b(?:\[Required\]|\[Range\(|\[StringLength|\[RegularExpression|ModelState\.IsValid|FluentValidation|AbstractValidator|@Valid\b|@NotNull|@Size\(|@Pattern\(|class-validator|@IsEmail|@IsNotEmpty|joi\.|zod\.|yup\.|express-validator|serializers\.\w+Field|is_valid\(\)|pydantic|BaseModel)\b"),
    "idempotency": re.compile(r"\b(?:Idempotency[_\-]?Key|idempotency[_\-]?key|IdempotentAttribute|dedup\w*|unique[_\-]?constraint|\[Index\([^)]*IsUnique\s*=\s*true|unique\s*=\s*True|@UniqueConstraint|UNIQUE\s*\()\b", re.I),
    "reconciliation": re.compile(r"\b(?:reconcil\w+|Reconcil\w+|checksum|integrity[_\-]?check|balance[_\-]?check|ledger[_\-]?(?:check|verify))\b"),
    # privacy
    "privacy_notice": re.compile(r"\b(?:privacy[_\-\s]?(?:policy|notice|statement)|PrivacyPolicy|/privacy\b|cookie[_\-\s]?(?:policy|banner|consent))\b", re.I),
    "consent": re.compile(r"\b\w*(?:consent|opt[_\-]?in|marketing[_\-]?(?:allowed|permission))\w*\b", re.I),
    # incident / vendor
    "incident_doc": re.compile(r"\b(?:incident[_\-\s]?(?:response|management|process|runbook|playbook)|on[_\-]?call|escalation|post[_\-]?mortem|postmortem|severity[_\-\s]?levels?|SEV[_\-]?[0-9])\b", re.I),
    "vendor_doc": re.compile(r"\b(?:sub[_\-]?processors?|vendor[_\-\s]?(?:list|management|review|risk)|third[_\-\s]?part(?:y|ies)[_\-\s]?(?:list|review)|SOC\s?2\s+report|DPA\b)\b", re.I),
    "pentest": re.compile(r"\b(?:pen[_\-\s]?test\w*|penetration[_\-\s]?test\w*|bug[_\-\s]?bounty|security[_\-\s]?assessment)\b", re.I),
    "patch_sla": re.compile(r"\b(?:patch[_\-\s]?(?:sla|window|policy|cadence)|remediat\w+\s+within|within\s+\d+\s+days|SLA)\b", re.I),
}


def read(path):
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return None


def ev(file, line, snippet, note=""):
    return {"file": file, "line": line, "snippet": snippet.strip()[:200], "note": note}


def scan(root, evidence_dir):
    hits = {k: [] for k in RX}
    hits["secrets_committed"] = []
    files = {}
    for full in repo_walk.iter_files(root, exts=CODE_EXT, names={"dockerfile", "jenkinsfile", "codeowners"}, max_bytes=None):
        text = read(full)
        if text is None:
            continue
        files[repo_walk.rel(root, full)] = text
    # also read API snapshots from the evidence folder (gh/*.json)
    gh_dir = os.path.join(evidence_dir, "snapshots", "gh") if evidence_dir else None
    if gh_dir and os.path.isdir(gh_dir):
        for fn in os.listdir(gh_dir):
            text = read(os.path.join(gh_dir, fn))
            if text is not None:
                files["<evidence>/gh/" + fn] = text
    for rel, text in files.items():
        for i, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            for key, rx in RX.items():
                if key == "dependabot":
                    continue
                if rx.search(line):
                    hits[key].append(ev(rel, i, line))
            # committed secrets: judged per value by audit-sensitive-data-catalog (placeholders excluded)
            if any(m["sensitive"] and m["category"] in SECRETISH and len(m["value"]) >= 12
                   for m in sdc.find_values(line)):
                hits["secrets_committed"].append(ev(rel, i, line))
        if RX["dependabot"].search(rel):
            hits["dependabot"].append(ev(rel, 0, rel))
    return hits, files


def is_ci(path):
    return bool(re.search(r"(?:^|/)\.github/workflows/|\.gitlab-ci|azure-pipelines|Jenkinsfile|\.circleci/|bitbucket-pipelines|\.buildkite/|\.drone\.yml", path, re.I))


def is_doc(path):
    return path.lower().endswith((".md", ".txt"))


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def evaluate(root, hits, files, index, siblings):
    rows = []
    org = []

    def add(cid, crit, control, status, evidence, note, owner=None):
        rows.append({"id": cid, "criterion": crit, "control": control, "status": status,
                     "evidence": evidence[:20], "note": note, "owner": owner})
        if status == "organisational" or owner:
            org.append({"item": control, "criterion": crit, "owner": owner or "Security lead", "note": note})

    ci = {k: [h for h in v if is_ci(h["file"])] for k, v in hits.items()}
    docs = {k: [h for h in v if is_doc(h["file"])] for k, v in hits.items()}
    not_collected = {n["item"] for n in (index or {}).get("not_collected", [])}
    bp_items = [i for i in (index or {}).get("items", []) if i["category"] == "branch_protection"]

    # ---- CC6 logical access
    if hits["auth"]:
        st = "partial"
        note = "authentication configured"
        if hits["sso"]:
            note += "; SSO/OIDC/SAML provider referenced"
        else:
            note += "; no SSO/IdP integration visible (local credentials?)"
        if hits["mfa"]:
            note += "; MFA symbols present"
            st = "implemented" if hits["sso"] or hits["mfa"] else st
        else:
            note += "; MFA not visible in code (may be enforced at the IdP - organisational evidence)"
        add("CC6.1-auth", "CC6.1", "Authentication with SSO and MFA for workforce/admin access", st, hits["auth"][:5] + hits["sso"][:5] + hits["mfa"][:5], note, None if hits["mfa"] else "Security lead (IdP MFA policy export)")
    else:
        add("CC6.1-auth", "CC6.1", "Authentication with SSO and MFA for workforce/admin access", "missing", [], "no authentication configuration found in code")
    if hits["rbac"]:
        add("CC6.1-rbac", "CC6.1/CC6.3", "Role-based authorization enforced on endpoints (least privilege)", "implemented" if len(hits["rbac"]) > 1 else "partial", hits["rbac"], f"{len(hits['rbac'])} role/policy check(s) found; confirm coverage of every admin endpoint")
    elif hits["authorize_any"]:
        add("CC6.1-rbac", "CC6.1/CC6.3", "Role-based authorization enforced on endpoints (least privilege)", "partial", hits["authorize_any"][:10], "authentication required but no role/policy distinctions found")
    else:
        add("CC6.1-rbac", "CC6.1/CC6.3", "Role-based authorization enforced on endpoints (least privilege)", "missing", [], "no authorization attributes/guards found")
    add("CC6.2-provisioning", "CC6.2", "User provisioning approved and documented; access reviews performed", "organisational", [], "approval workflow and periodic access reviews are process evidence (tickets, signed reviews)", "Security lead / IT")
    add("CC6.3-deprovisioning", "CC6.3", "Timely removal of access on role change / offboarding", "partial" if hits["deprovision"] else "organisational", hits["deprovision"][:10],
        "deactivation / token revocation code exists; the offboarding checklist and HR trigger are organisational" if hits["deprovision"] else "no deactivate/revoke path found in code; offboarding is organisational", "IT / HR")
    add("CC6.1-admin-log", "CC6.1/CC7.2", "Administrative and data-change actions are logged (audit trail)", "implemented" if hits["admin_action_log"] else "missing", hits["admin_action_log"][:10],
        "audit-trail mechanism found; confirm it covers admin actions" if hits["admin_action_log"] else "no audit log / history mechanism found")
    # CC6.6/6.7 transmission + secrets
    add("CC6.7-transit", "CC6.7", "Data encrypted in transit (HTTPS/HSTS/TLS to data stores)", "implemented" if hits["encrypt_transit"] else "not-checked", hits["encrypt_transit"][:10],
        "TLS enforcement markers found" if hits["encrypt_transit"] else "no TLS markers in code; may be at the load balancer (infra evidence needed)", None if hits["encrypt_transit"] else "Ops")
    committed = hits["secrets_committed"]
    if committed:
        add("CC6.1-secrets", "CC6.1/C1.1", "Secrets kept out of source control and managed centrally", "missing", committed[:10], "credential-looking literals found in the repo (hand to audit-secrets-and-config for confirmation)")
    elif hits["secrets_ext"]:
        add("CC6.1-secrets", "CC6.1/C1.1", "Secrets kept out of source control and managed centrally", "implemented", hits["secrets_ext"][:10], "secrets read from environment / vault / CI secrets; rotation policy is organisational")
    else:
        add("CC6.1-secrets", "CC6.1/C1.1", "Secrets kept out of source control and managed centrally", "not-checked", [], "no secret-source markers found")
    add("CC6.1-key-rotation", "CC6.1/C1.1", "Encryption keys and credentials rotated on a schedule", "partial" if hits["key_rotation"] else "organisational", hits["key_rotation"][:10],
        "rotation symbols found; schedule and last-rotation records are organisational" if hits["key_rotation"] else "no rotation logic in code; policy and records needed", "Security lead")
    # ---- CC7 system operations
    scan_hits = ci["ci_scan"]
    if scan_hits:
        add("CC7.1-scan", "CC7.1", "Vulnerability / dependency / SAST scanning in CI", "implemented", scan_hits, "scanner step(s) found in pipeline; confirm they block the merge")
    elif hits["dependabot"]:
        add("CC7.1-scan", "CC7.1", "Vulnerability / dependency / SAST scanning in CI", "partial", hits["dependabot"], "Dependabot/Renovate configured but no scanner step in the pipeline")
    else:
        add("CC7.1-scan", "CC7.1", "Vulnerability / dependency / SAST scanning in CI", "missing", [], "no npm audit / dotnet list --vulnerable / trivy / CodeQL / Dependabot found")
    dep = siblings.get("dep_findings")
    if dep:
        s = dep.get("summary", {})
        add("CC7.1-known-vulns", "CC7.1", "Known vulnerabilities remediated within the patch SLA", "partial" if (s.get("Critical", 0) + s.get("High", 0)) else "implemented",
            [ev("audit/findings/audit-dependency-vulnerabilities.json", 0, json.dumps(s))], f"dependency audit summary: {s}; SLA is organisational", "Engineering lead")
    else:
        add("CC7.1-known-vulns", "CC7.1", "Known vulnerabilities remediated within the patch SLA", "not-checked", [], "run audit-dependency-vulnerabilities first; patch SLA is organisational", "Engineering lead")
    add("CC7.1-pentest", "CC7.1", "Periodic penetration test with tracked remediation", "partial" if docs["pentest"] else "organisational", docs["pentest"][:5],
        "pen-test mentioned in docs; the report itself is organisational" if docs["pentest"] else "no pen-test record in the repo", "Security lead")
    central = [h for h in hits["log_central"] if not is_ci(h["file"])]
    console = hits["log_console_only"]
    if central:
        add("CC7.2-logging", "CC7.2", "Logs centralised, retained and protected from tampering", "implemented" if hits["log_retention"] else "partial", central[:10] + hits["log_retention"][:5] + hits["log_immutable"][:5],
            "central sink configured" + ("; retention configured" if hits["log_retention"] else "; retention not visible") + ("; immutability markers found" if hits["log_immutable"] else "; tamper-evidence (immutable storage) not visible - organisational"), None if hits["log_immutable"] else "Ops")
    elif console:
        add("CC7.2-logging", "CC7.2", "Logs centralised, retained and protected from tampering", "partial", console[:10], "console-only logging configured in the repo; shipping/retention must be proven at the platform level", "Ops")
    else:
        add("CC7.2-logging", "CC7.2", "Logs centralised, retained and protected from tampering", "not-checked", [], "no logging configuration found", "Ops")
    sev = hits["security_events"]
    al = hits["alerting"]
    add("CC7.2-alerting", "CC7.2/CC7.3", "Security events monitored with alerting", "implemented" if (sev and al) else ("partial" if (sev or al) else "missing"), sev[:10] + al[:10],
        f"security-event logging: {'yes' if sev else 'no'}; alerting: {'yes' if al else 'no'}")
    add("CC7.3-incident", "CC7.3/CC7.4/CC7.5", "Incident response process with roles, severity levels and post-mortems", "partial" if docs["incident_doc"] else "organisational", docs["incident_doc"][:5],
        "incident documentation present in repo; execution records are organisational" if docs["incident_doc"] else "no incident runbook in the repo", "Security lead")
    # ---- CC8 change management
    bp_off, bp_on = hits["protection_off"], hits["protection_on"]
    if bp_on and not bp_off:
        add("CC8.1-branch-protection", "CC8.1", "Pull-request review and status checks enforced on the production branch", "implemented", bp_on, "branch protection / rulesets require reviews and checks")
    elif bp_off:
        add("CC8.1-branch-protection", "CC8.1", "Pull-request review and status checks enforced on the production branch", "missing", bp_off + bp_on, "branch protection disabled or reviews/status checks not required")
    elif bp_items or "<evidence>/gh/branch-protection-main.json" in files:
        add("CC8.1-branch-protection", "CC8.1", "Pull-request review and status checks enforced on the production branch", "partial", [ev(i["evidence_path"], 0, i["source"], i.get("note", "")) for i in bp_items], "snapshot collected but no recognisable required-review settings; read it by hand")
    else:
        add("CC8.1-branch-protection", "CC8.1", "Pull-request review and status checks enforced on the production branch", "not-checked", [], "no branch-protection snapshot (gh unavailable) and no settings-as-code file", "Engineering lead (export from repo settings)")
    codeowners = [i for i in (index or {}).get("items", []) if i["category"] == "code_ownership" and i["source"].upper().endswith("CODEOWNERS")]
    add("CC8.1-codeowners", "CC8.1", "Code ownership / required reviewers defined", "implemented" if codeowners else "missing", [ev(i["evidence_path"], 0, i["source"]) for i in codeowners], "CODEOWNERS present" if codeowners else "no CODEOWNERS file")
    if ci["ci_test"]:
        add("CC8.1-ci-gate", "CC8.1", "CI gate: build and automated tests before merge/deploy", "implemented", ci["ci_test"], "test step(s) in pipeline; confirm they are required status checks")
    else:
        add("CC8.1-ci-gate", "CC8.1", "CI gate: build and automated tests before merge/deploy", "missing" if any(is_ci(f) for f in files) else "not-checked", [], "no test step found in CI" if any(is_ci(f) for f in files) else "no CI definition in the repo")
    deploy = ci["ci_deploy"]
    if deploy:
        prot = ci["ci_env_protect"]
        direct = ci["ci_direct_prod"]
        st = "implemented" if prot else "partial"
        note = "deploy job present; " + ("protected environment / manual approval referenced" if prot else "no protected environment or approval gate visible - relies on branch protection alone")
        if direct and not (bp_on and not bp_off):
            note += "; deploy triggers on push to the production branch, which is not protected"
            st = "missing" if bp_off else st
        add("CC8.1-deploy-gate", "CC8.1", "No direct production deploys: releases go through the pipeline with approval", st, deploy[:10] + prot[:5] + direct[:5], note)
    else:
        add("CC8.1-deploy-gate", "CC8.1", "No direct production deploys: releases go through the pipeline with approval", "not-checked", [], "no deploy step in the repo's CI; deployment path is outside the repo", "Ops")
    git_idx = (index or {}).get("git", {})
    subjects = git_idx.get("recent_subjects", []) or []
    tr = git_idx.get("ticket_refs")
    if subjects:
        if tr and tr.get("commits"):
            with_ref_n, total = tr["with_ref"], tr["commits"]
        else:  # an index written before ticket_refs existed: apply the same rules to the subjects
            with_ref_n = sum(1 for s in subjects if githist.ticket_refs(s.split(" ", 1)[-1]))
            total = len(subjects)
        ratio = with_ref_n / total
        note = f"{with_ref_n}/{total} recent commit subjects carry a ticket reference"
        if git_idx.get("shallow"):
            note += "; shallow clone: only the fetched commits were sampled"
        add("CC8.1-traceability", "CC8.1", "Changes traceable to a ticket / work item", "implemented" if ratio >= 0.8 else ("partial" if ratio >= 0.3 else "missing"),
            [ev("snapshots/git-metadata.json", 0, s) for s in subjects[:5]], note)
    else:
        add("CC8.1-traceability", "CC8.1", "Changes traceable to a ticket / work item", "not-checked", [], "git history not available")
    # ---- CC9 vendors
    inv = siblings.get("inventory")
    vendors = [t["name"] for t in (inv or {}).get("third_parties", [])]
    add("CC9.2-vendors", "CC9.2", "Vendor / subprocessor inventory with SOC 2 reports reviewed", "partial" if (vendors or docs["vendor_doc"]) else "organisational",
        ([ev("audit/evidence/audit-privacy-data-flow-mapper/data-inventory.json", 0, ", ".join(vendors))] if vendors else []) + docs["vendor_doc"][:5],
        ("processors found in code: " + ", ".join(vendors) + "; " if vendors else "") + "SOC 2 report review and contracts are organisational", "Security lead / Procurement")
    # ---- A1 availability
    bk = [h for h in hits["backup"] if not is_doc(h["file"])] or hits["backup"]
    if bk:
        enc = [h for h in hits["backup_encrypted"] if h["file"] in {b["file"] for b in bk}]
        ret = [h for h in hits["backup_retention"] if h["file"] in {b["file"] for b in bk}]
        add("A1.2-backups", "A1.2", "Automated backups, encrypted and retained off-site", "implemented" if (enc and ret) else "partial", bk[:5] + enc[:3] + ret[:3],
            "backup automation found" + ("; encryption flag present" if enc else "; encryption not visible") + ("; retention present" if ret else "; retention not visible"))
        if hits["restore_test"]:
            add("A1.2-restore-test", "A1.2", "Restore tested periodically and documented", "implemented", hits["restore_test"][:5], "restore test / drill record found; confirm it is dated and recent")
        elif hits["restore_instructions"]:
            add("A1.2-restore-test", "A1.2", "Restore tested periodically and documented", "partial", [h for h in hits["restore_instructions"] if is_doc(h["file"])][:5] or hits["restore_instructions"][:5],
                "restore instructions exist but no record of a performed restore test (date, outcome, RTO achieved)", "Ops")
        else:
            add("A1.2-restore-test", "A1.2", "Restore tested periodically and documented", "missing", [], "no restore procedure or test record", "Ops")
    else:
        add("A1.2-backups", "A1.2", "Automated backups, encrypted and retained off-site", "not-checked", [], "no backup configuration in the repo (managed service? export the console setting)", "Ops")
        add("A1.2-restore-test", "A1.2", "Restore tested periodically and documented", "organisational", [], "no restore test record in the repo", "Ops")
    add("A1.2-dr-plan", "A1.2/A1.3", "Disaster recovery plan with RTO/RPO and failover tested", "partial" if docs["dr_plan"] else "organisational", docs["dr_plan"][:5],
        "DR/RTO/RPO mentioned in docs; test records are organisational" if docs["dr_plan"] else "no DR plan in the repo", "Ops")
    add("A1.1-monitoring", "A1.1/A1.2", "Health checks and uptime monitoring with alerting", "implemented" if (hits["health"] and al) else ("partial" if hits["health"] else "missing"), hits["health"][:10],
        ("health endpoint(s) found" if hits["health"] else "no health endpoint") + ("; alerting configured" if al else "; external uptime monitoring/alerting not visible"))
    # ---- C1 confidentiality
    fields = (inv or {}).get("fields", [])
    if fields:
        classes = sorted({f.get("classification", "?") for f in fields})
        add("C1.1-classification", "C1.1", "Confidential data identified and classified", "implemented", [ev("audit/evidence/audit-privacy-data-flow-mapper/data-inventory.json", 0, ", ".join(classes))], f"inventory classifies {len(fields)} field(s): {', '.join(classes)}; the classification policy document is organisational", "DPO")
    elif hits["classification"]:
        add("C1.1-classification", "C1.1", "Confidential data identified and classified", "partial", hits["classification"][:5], "classification markers found; run audit-privacy-data-flow-mapper for the inventory", "DPO")
    else:
        add("C1.1-classification", "C1.1", "Confidential data identified and classified", "missing", [], "no data inventory or classification markers; run audit-privacy-data-flow-mapper", "DPO")
    add("C1.1-encrypt-rest", "C1.1/CC6.1", "Confidential data encrypted at rest (field-level or platform)", "partial" if hits["encrypt_rest"] else "not-checked", hits["encrypt_rest"][:10],
        "encryption/KMS markers found; disk/TDE is infra evidence" if hits["encrypt_rest"] else "no encryption-at-rest markers in code; platform evidence needed", "Ops")
    add("C1.2-disposal", "C1.2", "Confidential data disposed of per retention schedule", "partial" if hits["retention_job"] else "missing", hits["retention_job"][:10],
        "purge/retention code found; schedule policy is organisational" if hits["retention_job"] else "no purge/retention job found", "DPO / Ops")
    # ---- PI1 processing integrity
    add("PI1.1-validation", "PI1.1/PI1.2", "Inputs validated before processing", "implemented" if len(hits["validation"]) > 3 else ("partial" if hits["validation"] else "missing"), hits["validation"][:10], f"{len(hits['validation'])} validation marker(s)")
    add("PI1.3-integrity", "PI1.3/PI1.4", "Processing is complete, accurate and idempotent (unique constraints, reconciliation, audit trail)", "implemented" if (hits["idempotency"] and hits["admin_action_log"]) else ("partial" if (hits["idempotency"] or hits["reconciliation"] or hits["admin_action_log"]) else "missing"),
        hits["idempotency"][:5] + hits["reconciliation"][:5], f"idempotency/uniqueness: {'yes' if hits['idempotency'] else 'no'}; reconciliation: {'yes' if hits['reconciliation'] else 'no'}; audit trail: {'yes' if hits['admin_action_log'] else 'no'}")
    # ---- P1 privacy
    gd = siblings.get("gdpr")
    if gd:
        cmap = {c["id"]: c["status"] for c in gd.get("checks", [])}
        add("P1.1-notice-consent", "P1.1/P2.1/P3.1", "Privacy notice and consent handling", {"implemented": "implemented", "partial": "partial", "missing": "missing"}.get(cmap.get("consent-capture", "not-checked"), "not-checked"),
            [ev("audit/evidence/audit-gdpr-data-protection/gdpr-checks.json", 0, json.dumps({k: v for k, v in cmap.items() if k.startswith(("consent", "right-", "minimisation"))}))], "from audit-gdpr-data-protection")
    else:
        add("P1.1-notice-consent", "P1.1/P2.1/P3.1", "Privacy notice and consent handling", "partial" if (hits["privacy_notice"] or hits["consent"]) else "not-checked", hits["privacy_notice"][:5] + hits["consent"][:5],
            "notice/consent symbols found; run audit-gdpr-data-protection for the rights matrix" if (hits["privacy_notice"] or hits["consent"]) else "run audit-gdpr-data-protection", "DPO")
    # fixed organisational items
    for cid, crit, control, owner, note in [
        ("CC1-CC5-entity", "CC1-CC5", "Control environment, risk assessment, policies, training, board oversight", "Leadership / Compliance", "entity-level controls; not code"),
        ("CC6.2-access-review", "CC6.2/CC6.3", "Periodic (quarterly) user access reviews with sign-off", "Security lead", "review records"),
        ("CC7.1-patch-sla", "CC7.1", "Documented patch SLA by severity", "Engineering lead", "policy document"),
        ("CC9.1-risk", "CC9.1", "Risk register and business risk mitigation", "Leadership", "register"),
        ("C1.1-policy", "C1.1", "Data classification and handling policy", "DPO / Security lead", "policy document"),
    ]:
        add(cid, crit, control, "organisational", [], note, owner)
    return rows, org


def to_markdown(res):
    label = {"implemented": "Implemented", "partial": "Partial", "missing": "Missing", "organisational": "Organisational", "not-checked": "Not checked"}
    o = ["# SOC 2 control-to-evidence matrix", "", f"Root: `{res['root']}` - evidence: `{res['evidence_dir']}` - generated {res['generated_at']}", "",
         "| Criterion | Control | Evidence artifact | Status | Notes |", "|---|---|---|---|---|"]
    for r in res["rows"]:
        locs = []
        for e in r["evidence"]:
            loc = f"`{e['file']}:{e['line']}`" if e["line"] else f"`{e['file']}`"
            if loc not in locs:
                locs.append(loc)
        o.append(f"| {r['criterion']} | {r['control']} | {'; '.join(locs[:3]) or '-'} | {label[r['status']]} | {r['note']} |")
    o += ["", "## Summary", "", "| Status | Count |", "|---|---|"]
    for k, v in res["summary"].items():
        o.append(f"| {label[k]} | {v} |")
    o += ["", "## Organisational gaps (need a policy owner)", "", "| Item | Criterion | Suggested owner | Note |", "|---|---|---|---|"]
    for g in res["organisational"]:
        o.append(f"| {g['item']} | {g['criterion']} | {g['owner']} | {g['note']} |")
    o += ["", "## Evidence detail", ""]
    for r in res["rows"]:
        if not r["evidence"]:
            continue
        o.append(f"### {r['id']} ({r['status']})")
        for e in r["evidence"][:10]:
            o.append(f"- `{e['file']}:{e['line']}` {e['snippet'].replace('|', '/')}" + (f"  - {e['note']}" if e.get("note") else ""))
        o.append("")
    o += ["## Not checked", ""]
    for n in res["not_checked"]:
        o.append(f"- {n['item']} - {n['reason']}")
    return "\n".join(o) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--evidence", default=None)
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    evidence_dir = os.path.abspath(a.evidence or os.path.join(root, "audit", "evidence", "audit-soc2-controls-evidence"))
    index = load_json(os.path.join(evidence_dir, "index.json"))
    not_checked = [
        {"item": "IdP / SSO / MFA configuration", "reason": "lives in the identity provider console"},
        {"item": "cloud IAM, console settings, managed-service backups", "reason": "outside the repo unless IaC is committed"},
        {"item": "HR onboarding/offboarding records, access reviews, training", "reason": "organisational"},
        {"item": "vendor SOC 2 reports, pen-test reports, ticket linkage", "reason": "documents outside the repo"},
    ]
    if not index:
        not_checked.append({"item": "evidence index", "reason": "run collect_evidence.py first; branch protection and API evidence not available"})
    else:
        for n in index.get("not_collected", []):
            not_checked.append({"item": "evidence: " + n["item"], "reason": n["reason"]})
    siblings = {
        "inventory": load_json(os.path.join(root, "audit", "evidence", "audit-privacy-data-flow-mapper", "data-inventory.json")),
        "dep_findings": load_json(os.path.join(root, "audit", "findings", "audit-dependency-vulnerabilities.json")),
        "gdpr": load_json(os.path.join(root, "audit", "evidence", "audit-gdpr-data-protection", "gdpr-checks.json")),
    }
    hits, files = scan(root, evidence_dir)
    rows, org = evaluate(root, hits, files, index, siblings)
    res = {"skill": "audit-soc2-controls-evidence", "generated_at": datetime.now(timezone.utc).isoformat(), "root": root,
           "evidence_dir": evidence_dir, "index_loaded": bool(index), "rows": rows,
           "summary": {s: sum(1 for r in rows if r["status"] == s) for s in ("implemented", "partial", "missing", "organisational", "not-checked")},
           "organisational": org, "not_checked": not_checked}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(to_markdown(res))
    print(json.dumps({"index_loaded": bool(index), "summary": res["summary"], "controls": {r["id"]: r["status"] for r in rows}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
