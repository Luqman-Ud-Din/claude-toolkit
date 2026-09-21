#!/usr/bin/env python3
"""Collect SOC 2 evidence snapshots from a repository into an evidence folder
with an index.json.

Usage:
    python collect_evidence.py <repo_root> [--out audit/evidence/audit-soc2-controls-evidence]
                               [--no-gh] [--max-file-bytes 1000000]

What it collects (read-only against the repo; copies go under <out>/snapshots/):
  ci                 .github/workflows/*.yml, .gitlab-ci.yml, azure-pipelines*.yml, Jenkinsfile,
                     .circleci/config.yml, bitbucket-pipelines.yml, .buildkite/*, .drone.yml
  branch_protection  gh api repos/{owner}/{repo}/branches/{default}/protection (+ rulesets,
                     environments) when `gh` is installed, authenticated and the remote is GitHub;
                     otherwise .github/settings.yml (probot) / .github/rulesets/*.json if committed
  dependency_updates .github/dependabot.yml, renovate.json*, .renovaterc*
  code_ownership     CODEOWNERS, PULL_REQUEST_TEMPLATE*, CONTRIBUTING*, SECURITY.md
  backup_recovery    files whose name or content mentions backup/restore/snapshot/pg_dump/
                     mysqldump/velero/BackupPolicy/backup_retention/DR, plus docs mentioning
                     restore tests
  iac                *.tf, *.bicep, *.yaml under k8s/helm/deploy, docker-compose*, Dockerfile
  logging_monitoring logging config (Serilog sections, logback*.xml, log4j2*, LOGGING dicts,
                     winston/pino config), prometheus/alertmanager rules, datadog/newrelic config,
                     healthcheck/uptime config
  access_control     auth/security configuration files (Program.cs/Startup.cs, SecurityConfig*,
                     settings.py AUTH*, auth middleware), IdP config (oidc/saml/okta/auth0 files)
  secrets_management .env.example, .sops.yaml, sealed-secrets, key-vault/secrets-manager references
  policies_docs      docs/**/*(policy|incident|dr|disaster|runbook|onboarding|offboarding|access-review|restore)*.md
  git_metadata       commit, branch, remote, tag list, recent commit subjects, ticket references and the
                     shallow-clone flag, read through audit-git-history

index.json shape:
{
  "skill": "audit-soc2-controls-evidence", "collected_at": "...", "root": "...",
  "git": {"commit": "...", "branch": "...", "remote": "...", "provider": "github|gitlab|azure|other|none"},
  "items": [{"id": "ci-0001", "category": "ci", "source": ".github/workflows/ci.yml",
             "evidence_path": "snapshots/.github/workflows/ci.yml", "sha256": "...", "bytes": 123,
             "note": ""}],
  "not_collected": [{"item": "branch protection", "reason": "..."}],
  "stats": {"<category>": n}
}
Never modifies the audited repository.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
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
_GH_PATH = os.path.join(_SKILLS, "audit-git-history", "scripts", "githist.py")
if not os.path.exists(_GH_PATH):
    sys.exit("audit-git-history must be reachable from this skill (audit-core plugin or sibling layout; expected " + _GH_PATH + ")")
_spec = importlib.util.spec_from_file_location("audit_git_history_githist", _GH_PATH)
githist = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = githist
_spec.loader.exec_module(githist)

CATEGORY_RULES = [
    ("ci", re.compile(r"(?:^|/)\.github/workflows/[^/]+\.ya?ml$|(?:^|/)\.gitlab-ci\.ya?ml$|(?:^|/)azure-pipelines[^/]*\.ya?ml$|(?:^|/)Jenkinsfile$|(?:^|/)\.circleci/config\.ya?ml$|(?:^|/)bitbucket-pipelines\.ya?ml$|(?:^|/)\.buildkite/[^/]+\.ya?ml$|(?:^|/)\.drone\.ya?ml$|(?:^|/)\.travis\.ya?ml$|(?:^|/)cloudbuild\.ya?ml$|(?:^|/)(?:infra|deploy|scripts|ops)/[^/]*(?:deploy|release)[^/]*\.(?:sh|ps1)$", re.I)),
    ("branch_protection", re.compile(r"(?:^|/)\.github/settings\.ya?ml$|(?:^|/)\.github/rulesets/[^/]+\.json$|(?:^|/)\.github/branch-protection[^/]*$", re.I)),
    ("dependency_updates", re.compile(r"(?:^|/)\.github/dependabot\.ya?ml$|(?:^|/)renovate\.json5?$|(?:^|/)\.renovaterc(?:\.json)?$|(?:^|/)\.github/renovate\.json5?$", re.I)),
    ("code_ownership", re.compile(r"(?:^|/)CODEOWNERS$|(?:^|/)(?:\.github/)?(?:PULL_REQUEST_TEMPLATE|pull_request_template)[^/]*$|(?:^|/)CONTRIBUTING[^/]*$|(?:^|/)SECURITY\.md$", re.I)),
    ("backup_recovery", re.compile(r"(?:^|/)[^/]*(?:backup|restore|snapshot|pg_dump|mysqldump|velero|disaster|dr-plan|recovery)[^/]*\.(?:sh|ps1|py|ya?ml|json|tf|bicep|md|txt)$", re.I)),
    ("iac", re.compile(r"\.(?:tf|tfvars|bicep)$|(?:^|/)(?:k8s|kubernetes|helm|deploy|deployment|manifests|charts|terraform|infra|infrastructure)/.*\.(?:ya?ml|json)$|(?:^|/)docker-compose[^/]*\.ya?ml$|(?:^|/)compose\.ya?ml$|(?:^|/)Dockerfile[^/]*$|\.dockerfile$|(?:^|/)serverless\.ya?ml$|(?:^|/)template\.ya?ml$", re.I)),
    ("logging_monitoring", re.compile(r"(?:^|/)logback[^/]*\.xml$|(?:^|/)log4j2?[^/]*\.(?:xml|properties|ya?ml|json)$|(?:^|/)nlog\.config$|(?:^|/)[^/]*(?:prometheus|alertmanager|alert-rules|alerts|grafana|datadog|newrelic|uptime|healthcheck|monitor)[^/]*\.(?:ya?ml|json|toml)$|(?:^|/)serilog[^/]*\.json$", re.I)),
    ("access_control", re.compile(r"(?:^|/)(?:Program|Startup)\.cs$|(?:^|/)[^/]*SecurityConfig[^/]*\.(?:java|kt)$|(?:^|/)WebSecurity[^/]*\.(?:java|kt)$|(?:^|/)settings(?:/[^/]+)?\.py$|(?:^|/)(?:auth|authentication|authorization|security|passport|oidc|saml|okta|auth0|keycloak|rbac|permissions?|roles?)[^/]*\.(?:ts|js|py|cs|java|kt|ya?ml|json|xml)$|(?:^|/)middleware/auth[^/]*$|(?:^|/)ocelot[^/]*\.json$", re.I)),
    ("secrets_management", re.compile(r"(?:^|/)\.env\.(?:example|sample|template)$|(?:^|/)\.sops\.ya?ml$|(?:^|/)[^/]*sealed-?secret[^/]*\.ya?ml$|(?:^|/)[^/]*(?:keyvault|key-vault|secrets-?manager|vault)[^/]*\.(?:ya?ml|json|tf|bicep)$|(?:^|/)\.gitleaks\.toml$|(?:^|/)\.pre-commit-config\.ya?ml$", re.I)),
    ("policies_docs", re.compile(r"(?:^|/)docs?/.*(?:policy|policies|incident|disaster|dr\b|runbook|onboard|offboard|access-?review|restore|backup|retention|sdlc|change-?management|vendor|risk|bcp|continuity|security)[^/]*\.md$|(?:^|/)(?:SECURITY|INCIDENT|RUNBOOK|DR|DISASTER_RECOVERY|BACKUP)[^/]*\.md$", re.I)),
]
CONTENT_HINTS = {
    "backup_recovery": re.compile(r"\b(?:pg_dump|mysqldump|mongodump|sqlcmd .*BACKUP|BACKUP DATABASE|velero|aws_backup_plan|azurerm_backup|backup_retention_period|BackupPolicy|snapshot_identifier|restore[_ -]?test|point[_ -]in[_ -]time)\b", re.I),
    "logging_monitoring": re.compile(r"\"Serilog\"\s*:|\"WriteTo\"\s*:|LOGGING\s*=\s*\{|winston\.createLogger|pino\(|logging\.config|<appender|alerting:|alertmanager|scrape_configs|healthcheck:|HEALTHCHECK\b", re.I),
    "secrets_management": re.compile(r"\b(?:KeyVault|Key Vault|SecretsManager|secretsmanager|vault\.|VaultClient|AddAzureKeyVault|@azure/keyvault|boto3\.client\(['\"]secretsmanager|sops|SealedSecret|ExternalSecret)\b", re.I),
}
TEXT_EXT = {".yml", ".yaml", ".json", ".json5", ".md", ".txt", ".sh", ".ps1", ".py", ".cs", ".java", ".kt", ".ts", ".js",
            ".tf", ".tfvars", ".bicep", ".xml", ".properties", ".toml", ".config", ".ini", ".env", ""}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, cwd=None, timeout=60):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        return None, "", str(e)


def git_meta(root):
    meta = {"commit": None, "branch": None, "remote": None, "provider": "none", "tags": [], "recent_subjects": []}
    hist = githist.History(root)
    info = hist.info(tags_limit=20)
    meta["shallow"] = info["shallow"]
    meta["not_checked"] = info["not_checked"]
    if not info["head"]:
        return meta
    meta.update(commit=info["head"], branch=info["branch"], remote=info["remote"], provider=info["provider"],
                tags=info["tags"])
    meta["recent_subjects"] = ["%s %s" % (c["hash_full"][:7], c["subject"])
                               for c in hist.commits(last_n=50, merges=True, with_files=False)]
    tk = hist.tickets(last_n=50, merges=True, subject_only=True)
    meta["ticket_refs"] = {"commits": tk["summary"]["commits"], "with_ref": tk["summary"]["with_ref"],
                           "per_commit": [{"hash": c["hash"], "refs": [r["id"] for r in c["refs"]]} for c in tk["commits"]]}
    return meta


def github_slug(remote):
    mo = re.search(r"github\.com[:/]([^/]+)/([^/.]+)(?:\.git)?/?$", remote or "")
    return f"{mo.group(1)}/{mo.group(2)}" if mo else None


def collect_gh(meta, out_dir, items, not_collected):
    slug = github_slug(meta.get("remote"))
    if not slug:
        not_collected.append({"item": "branch protection (GitHub API)", "reason": "remote is not GitHub or no remote; using settings-as-code files if present"})
        return
    gh = shutil.which("gh") or shutil.which("gh.exe")
    if not gh:
        not_collected.append({"item": "branch protection (GitHub API)", "reason": "gh CLI not installed"})
        return
    rc, _, err = run([gh, "auth", "status"])
    if rc != 0:
        not_collected.append({"item": "branch protection (GitHub API)", "reason": "gh not authenticated: " + err.strip()[:120]})
        return
    rc, out, _ = run([gh, "api", f"repos/{slug}"])
    default = "main"
    if rc == 0:
        try:
            default = json.loads(out).get("default_branch", "main")
        except json.JSONDecodeError:
            pass
    calls = [
        ("branch_protection", f"repos/{slug}/branches/{default}/protection", f"gh/branch-protection-{default}.json"),
        ("branch_protection", f"repos/{slug}/rulesets", "gh/rulesets.json"),
        ("branch_protection", f"repos/{slug}/environments", "gh/environments.json"),
        ("dependency_updates", f"repos/{slug}/vulnerability-alerts", "gh/vulnerability-alerts.txt"),
        ("access_control", f"repos/{slug}/collaborators?per_page=100", "gh/collaborators.json"),
        ("code_ownership", f"repos/{slug}", "gh/repository.json"),
    ]
    for cat, endpoint, name in calls:
        rc, out, err = run([gh, "api", endpoint])
        dest = os.path.join(out_dir, "snapshots", name)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        body = out if rc == 0 else json.dumps({"endpoint": endpoint, "rc": rc, "error": err.strip()[:500]}, indent=2)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(body if body.strip() else "{}")
        note = "" if rc == 0 else f"API call failed (rc={rc}): {err.strip()[:120]} - 404 on /protection means the branch is NOT protected"
        items.append(mk_item(cat, f"gh api {endpoint}", os.path.relpath(dest, out_dir).replace(os.sep, "/"), dest, note))


def mk_item(cat, source, evidence_rel, dest, note=""):
    return {"category": cat, "source": source, "evidence_path": evidence_rel, "sha256": sha256(dest),
            "bytes": os.path.getsize(dest), "note": note}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--out", default=None, help="evidence folder (default <root>/audit/evidence/audit-soc2-controls-evidence)")
    ap.add_argument("--no-gh", action="store_true", help="skip gh api calls")
    ap.add_argument("--max-file-bytes", type=int, default=1_000_000)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    out_dir = os.path.abspath(a.out or os.path.join(root, "audit", "evidence", "audit-soc2-controls-evidence"))
    os.makedirs(os.path.join(out_dir, "snapshots"), exist_ok=True)

    items, not_collected = [], []
    meta = git_meta(root)
    if meta["commit"] is None:
        not_collected.append({"item": "git metadata", "reason": "not a git repository (or git not installed)"})
    for n in meta.get("not_checked", []):
        if n["item"] == "full git history":  # shallow clone: subjects and tags cover only the fetched commits
            not_collected.append({"item": n["item"], "reason": n["reason"]})
    gm = os.path.join(out_dir, "snapshots", "git-metadata.json")
    with open(gm, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    items.append(mk_item("git_metadata", "audit-git-history info/commits/tickets", "snapshots/git-metadata.json", gm))

    seen = set()
    for full in repo_walk.iter_files(root, globs=["*"], max_bytes=None):
        if os.path.abspath(full).startswith(out_dir + os.sep):
            continue
        fn = os.path.basename(full)
        rel = repo_walk.rel(root, full)
        ext = os.path.splitext(fn)[1].lower()
        cats = [c for c, rx in CATEGORY_RULES if rx.search(rel)]
        if not cats and ext in TEXT_EXT and os.path.getsize(full) <= a.max_file_bytes:
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                    head = fh.read(200_000)
            except OSError:
                head = ""
            cats = [c for c, rx in CONTENT_HINTS.items() if rx.search(head)]
        if not cats or rel in seen:
            continue
        seen.add(rel)
        if os.path.getsize(full) > a.max_file_bytes:
            not_collected.append({"item": rel, "reason": f"larger than {a.max_file_bytes} bytes"})
            continue
        dest = os.path.join(out_dir, "snapshots", rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(full, dest)
        for c in cats:
            items.append(mk_item(c, rel, "snapshots/" + rel, dest))

    if not a.no_gh:
        collect_gh(meta, out_dir, items, not_collected)
    else:
        not_collected.append({"item": "branch protection (GitHub API)", "reason": "--no-gh given"})
    if not any(i["category"] == "branch_protection" for i in items):
        not_collected.append({"item": "branch protection", "reason": "no API snapshot and no settings-as-code file (.github/settings.yml / rulesets)"})
    for cat, label in (("ci", "CI pipeline definitions"), ("dependency_updates", "Dependabot/Renovate configuration"),
                       ("backup_recovery", "backup/restore configuration"), ("logging_monitoring", "logging/monitoring configuration"),
                       ("policies_docs", "policy / runbook documents")):
        if not any(i["category"] == cat for i in items):
            not_collected.append({"item": label, "reason": "nothing matching in the repository (may live outside the repo)"})

    # Branch protection via the GitHub API is either checked (gh installed + authenticated + GitHub
    # remote) or explicitly "not-checked" - never silently treated as "off".
    gh_gap = [n for n in not_collected if n["item"] == "branch protection (GitHub API)"]
    bp_api = ({"status": "not-checked", "reason": gh_gap[0]["reason"]} if gh_gap
              else {"status": "checked", "reason": "exported with gh api (see snapshots/gh/)"})
    for n, it in enumerate(items, 1):
        it["id"] = f"{it['category']}-{n:04d}"
    index = {"skill": "audit-soc2-controls-evidence", "collected_at": datetime.now(timezone.utc).isoformat(), "root": root,
             "evidence_dir": out_dir, "git": meta, "branch_protection_api": bp_api, "items": items, "not_collected": not_collected,
             "stats": {c: sum(1 for i in items if i["category"] == c) for c in sorted({i["category"] for i in items})}}
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2)
    print(json.dumps({"evidence_dir": out_dir, "items": len(items), "stats": index["stats"], "branch_protection_api": bp_api,
                      "not_collected": [n["item"] for n in not_collected]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
