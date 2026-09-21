#!/usr/bin/env python3
"""Parse a repository's CI/CD definitions and report which build gates exist,
which are advisory, and which are missing, without needing CI API access.

Usage:
    python ci_scan.py <repo_root> [--out ci.json] [--md ci.md]

Understands (by file location / name, no YAML library needed - stdlib only):
    .github/workflows/*.yml|yaml     GitHub Actions
    azure-pipelines*.yml, .azure*/   Azure Pipelines
    .gitlab-ci.yml (+ includes)      GitLab CI
    Jenkinsfile*                     Jenkins declarative/scripted
    bitbucket-pipelines.yml          Bitbucket
    .circleci/config.yml             CircleCI
    .drone.yml, .travis.yml, appveyor.yml, cloudbuild.yaml, buildspec.yml

Per file it reports: triggers (push / pull_request / merge_request / tag),
the command-ish lines it runs, and for each gate (test, lint/analyzer,
security scan, coverage, reproducible install, artifact versioning, artifact
signing, deploy) whether it is present, and whether it is *advisory* - a step
that cannot fail the build (continue-on-error, || true, -DskipTests,
allow_failure, ignoreLastExitCode, `set +e`, catchError).

It also collects branch-protection *hints* that live in the repo (CODEOWNERS,
.github/rulesets, GitLab approval config, Azure branch policy exports). Real
branch protection lives in the forge, not the repo: verify out-of-band with
`gh api repos/{owner}/{repo}/branches/main/protection` and record what you
could not check.

Read-only: nothing in the audited repo is modified.
"""
import argparse
import json
import os
import re
import sys

import importlib.util

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


def _load_atomic(skill, module, alias):
    """Load an atomic skill's script by path under a unique module name."""
    path = os.path.join(_SKILLS, skill, "scripts", module + ".py")
    if not os.path.exists(path):
        sys.exit(f"{skill} must be reachable from this skill (audit-core plugin or sibling layout; expected {path})")
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


repo_walk = _load_atomic("audit-code-scan", "repo_walk", "audit_code_scan_repo_walk")

MAX_BYTES = 1_000_000
# build/ is read on purpose: pipeline templates often live there (build/azure-pipelines.yml).
CI_INCLUDE_DIRS = ("build",)

CI_MATCHERS = [
    ("github-actions", re.compile(r"^\.github/workflows/[^/]+\.(yml|yaml)$", re.I)),
    ("github-actions", re.compile(r"^\.github/actions/.*/action\.(yml|yaml)$", re.I)),
    ("azure-pipelines", re.compile(r"(^|/)azure-pipelines[^/]*\.(yml|yaml)$", re.I)),
    ("azure-pipelines", re.compile(r"(^|/)\.azuredevops/.*\.(yml|yaml)$", re.I)),
    ("gitlab-ci", re.compile(r"(^|/)\.gitlab-ci[^/]*\.(yml|yaml)$", re.I)),
    ("gitlab-ci", re.compile(r"(^|/)\.gitlab/ci/.*\.(yml|yaml)$", re.I)),
    ("jenkins", re.compile(r"(^|/)Jenkinsfile[^/]*$")),
    ("bitbucket", re.compile(r"(^|/)bitbucket-pipelines\.(yml|yaml)$", re.I)),
    ("circleci", re.compile(r"(^|/)\.circleci/config\.(yml|yaml)$", re.I)),
    ("drone", re.compile(r"(^|/)\.drone\.(yml|yaml)$", re.I)),
    ("travis", re.compile(r"(^|/)\.travis\.(yml|yaml)$", re.I)),
    ("appveyor", re.compile(r"(^|/)appveyor\.(yml|yaml)$", re.I)),
    ("cloudbuild", re.compile(r"(^|/)cloudbuild\.(yml|yaml)$", re.I)),
    ("codebuild", re.compile(r"(^|/)buildspec\.(yml|yaml)$", re.I)),
    ("teamcity", re.compile(r"(^|/)\.teamcity/.*\.kts$", re.I)),
]

GATES = {
    "test": [
        r"\bdotnet\s+test\b", r"^\s*command:\s*['\"]?test\b", r"VSTest@\d",
        r"\bmvn\b[^\n]*\b(test|verify)\b", r"\bgradlew?\b[^\n]*\b(test|check)\b",
        r"\bnpm\s+(run\s+)?test\b", r"\byarn\s+(run\s+)?test\b", r"\bpnpm\s+(run\s+)?test\b",
        r"\bnpx\s+(jest|vitest|cypress|playwright)\b", r"\bjest\b", r"\bvitest\b",
        r"\bng\s+test\b", r"\bkarma\s+start\b", r"\bpytest\b", r"\bpython\s+-m\s+pytest\b",
        r"manage\.py\s+test\b", r"\btox\b", r"\bgo\s+test\b", r"\bcargo\s+test\b",
        r"PublishTestResults@", r"\bplaywright\s+test\b", r"\bnpm\s+run\s+e2e\b",
    ],
    "lint-analyzer": [
        r"\beslint\b", r"\bnpm\s+run\s+lint\b", r"\bng\s+lint\b", r"\bstylelint\b",
        r"\bdotnet\s+format\b", r"-warnaserror", r"TreatWarningsAsErrors",
        r"\bcheckstyle\b", r"\bspotbugs\b", r"\bpmd\b", r"\bspotless\b",
        r"\bruff\b", r"\bflake8\b", r"\bpylint\b", r"\bblack\s+--check\b", r"\bmypy\b",
        r"\btsc\s+--noEmit\b", r"\bgolangci-lint\b", r"\bclippy\b",
    ],
    "security-scan": [
        r"\bnpm\s+audit\b", r"\byarn\s+audit\b", r"\bpnpm\s+audit\b",
        r"dotnet\s+list\s+package\s+--vulnerable", r"\bpip-audit\b", r"\bsafety\s+check\b",
        r"dependency-check", r"\bsnyk\b", r"\btrivy\b", r"\bgrype\b", r"\bsyft\b",
        r"github/codeql", r"\bcodeql\b", r"\bsemgrep\b", r"\bbandit\b",
        r"gitleaks", r"trufflehog", r"dependency-review-action", r"\bsonar", r"\bowasp\b",
        r"anchore", r"\bcheckov\b", r"\btfsec\b", r"\bhadolint\b", r"\bkubesec\b",
    ],
    "coverage": [
        r"--collect:?\s*\"?XPlat Code Coverage", r"\bcoverlet\b", r"\breportgenerator\b",
        r"--coverage\b", r"collectCoverage", r"\bjacoco\b", r"--cov\b", r"\bcodecov\b",
        r"coveralls", r"PublishCodeCoverageResults@", r"--code-coverage\b",
        r"fail[_-]under", r"coverageThreshold",
    ],
    "reproducible-install": [
        r"\bnpm\s+ci\b", r"\byarn\s+install\s+--frozen-lockfile\b",
        r"\bpnpm\s+install\s+--frozen-lockfile\b", r"--locked-mode", r"\bpip\s+install\s+-r\b",
        r"pip-sync", r"poetry\s+install\b", r"--require-hashes", r"RestoreLockedMode",
    ],
    "artifact-version": [
        r"-p:Version=", r"\bGitVersion\b", r"\bMinVer\b", r"Nerdbank\.GitVersioning",
        r"npm\s+version\b", r"\bsemantic-release\b", r"\$\{\{\s*github\.sha\s*\}\}",
        r"\$\(Build\.BuildNumber\)", r"CI_COMMIT_(SHA|TAG)", r"docker\s+build[^\n]*:\$",
        r"\btag:\s*\$\{", r"--tag\s+\S+:\S",
    ],
    "artifact-sign": [
        r"\bcosign\b", r"\bsigntool\b", r"dotnet\s+nuget\s+sign", r"\bgpg\s+--detach-sig",
        r"sigstore", r"attest-build-provenance", r"\bnotation\s+sign\b", r"apksigner",
    ],
    "deploy": [
        r"\bkubectl\s+apply\b", r"\bhelm\s+(upgrade|install)\b", r"\bterraform\s+apply\b",
        r"azure/webapps-deploy", r"aws\s+ecs\s+update-service", r"\bdocker\s+push\b",
        r"AzureRmWebAppDeployment@", r"\bserverless\s+deploy\b", r"\bfly\s+deploy\b",
    ],
}

ADVISORY = [
    (r"continue-on-error\s*:\s*true", "continue-on-error: true"),
    (r"continueOnError\s*:\s*true", "continueOnError: true"),
    (r"allow_failure\s*:\s*true", "allow_failure: true"),
    (r"\|\|\s*true\b", "|| true"),
    (r"\|\|\s*exit\s+0\b", "|| exit 0"),
    (r"-DskipTests|-Dmaven\.test\.skip", "maven tests skipped"),
    (r"--no-tests|-p:SkipTests=true", "tests skipped by property"),
    (r"ignoreLASTExitCode\s*:\s*true", "ignoreLastExitCode: true"),
    (r"catchError\s*\(", "Jenkins catchError"),
    (r"set\s+\+e\b", "set +e"),
    (r"failOnStderr\s*:\s*false", "failOnStderr: false"),
    (r"if:\s*always\(\)", "step runs with if: always()"),
]

TRIGGERS = [
    ("pull_request", r"\bpull_request(_target)?\b|^\s*pr\s*:|changeRequest\s*\(|pull-requests\s*:"),
    ("merge_request", r"merge_request_event|\bmerge_requests?\b"),
    ("push", r"^\s*push\s*:|\btrigger\s*:|branches:"),
    ("tag", r"\btags\s*:|refs/tags"),
    ("schedule", r"\bschedule\s*:|\bcron\b"),
    ("manual", r"workflow_dispatch|\bwhen:\s*manual\b|parameters\s*\{"),
]

CMD_RE = re.compile(r"^\s*(?:-\s*)?(?:run|script|sh|bat|powershell|pwsh|cmd|task|bash)\s*[:=]\s*(.+)$", re.I)
JENKINS_CMD_RE = re.compile(r"^\s*(?:sh|bat|powershell|pwsh)\s*\(?\s*(?:script\s*:\s*)?['\"]{1,3}(.+?)['\"]{0,3}\)?\s*$")
USES_RE = re.compile(r"^\s*-?\s*uses\s*:\s*(\S+)", re.I)


def is_comment(line):
    s = line.strip()
    return s.startswith("#") or s.startswith("//") or s.startswith("*")


def iter_ci_files(root):
    # globs=("*",): Jenkinsfile.*, .kts and other CI names are matched by path, not by extension.
    for full in repo_walk.iter_files(root, globs=("*",), include_dirs=CI_INCLUDE_DIRS):
        rel = repo_walk.rel(root, full)
        for system, rx in CI_MATCHERS:
            if rx.search(rel):
                yield system, rel, full
                break


def read(path):
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return ""
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def analyse_file(system, rel, text):
    lines = text.splitlines()
    steps = []
    for n, line in enumerate(lines, 1):
        if is_comment(line):
            continue
        m = CMD_RE.match(line) or (JENKINS_CMD_RE.match(line) if system == "jenkins" else None)
        if m:
            steps.append({"line": n, "text": m.group(1).strip()[:200]})
            continue
        m = USES_RE.match(line)
        if m:
            steps.append({"line": n, "text": "uses: " + m.group(1)})
    gates = {}
    commented_out = []
    for gate, pats in GATES.items():
        hits = []
        for pat in pats:
            rx = re.compile(pat, re.I | re.M)
            for n, line in enumerate(lines, 1):
                if not rx.search(line):
                    continue
                if is_comment(line):
                    # a gate that exists only as a commented-out line is evidence it was switched off
                    commented_out.append({"gate": gate, "line": n, "snippet": line.strip()[:200]})
                    continue
                hits.append({"line": n, "snippet": line.strip()[:200], "pattern": pat})
                break
        gates[gate] = {"present": bool(hits), "hits": hits[:8]}
    advisory = []
    for pat, label in ADVISORY:
        rx = re.compile(pat, re.I)
        for n, line in enumerate(lines, 1):
            if rx.search(line) and not is_comment(line):
                advisory.append({"line": n, "issue": label, "snippet": line.strip()[:200]})
    live_text = "\n".join("" if is_comment(l) else l for l in lines)
    triggers = [name for name, pat in TRIGGERS
                if re.search(pat, live_text, re.I | re.M)]
    # a test gate that shares a file with an advisory marker is *possibly* advisory
    if gates["test"]["present"] and advisory:
        gates["test"]["advisory_suspect"] = True
    pinned = None
    if system == "github-actions":
        uses = re.findall(r"uses\s*:\s*(\S+)", text)
        if uses:
            pinned = {
                "total": len(uses),
                "sha_pinned": sum(1 for u in uses if re.search(r"@[0-9a-f]{40}$", u)),
                "floating": [u for u in uses if re.search(r"@(main|master|latest)$", u)],
            }
    seen_co = set()
    commented_out = [c for c in commented_out if not ((c["gate"], c["line"]) in seen_co or seen_co.add((c["gate"], c["line"])))]
    return {"system": system, "file": rel, "triggers": triggers, "steps": steps,
            "gates": gates, "advisory": advisory, "commented_out_gates": commented_out,
            "action_pinning": pinned}


def protection_hints(root):
    hints = []
    for cand in ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS",
                 ".github/pull_request_template.md", ".github/settings.yml",
                 ".gitlab/CODEOWNERS", ".github/branch-protection.yml"]:
        p = os.path.join(root, cand.replace("/", os.sep))
        if os.path.exists(p):
            hints.append({"file": cand, "hint": "present"})
    rulesets = os.path.join(root, ".github", "rulesets")
    if os.path.isdir(rulesets):
        for fn in os.listdir(rulesets):
            hints.append({"file": f".github/rulesets/{fn}", "hint": "ruleset definition in repo"})
    for cand in [".husky", ".pre-commit-config.yaml", ".git/hooks"]:
        if os.path.exists(os.path.join(root, cand)):
            hints.append({"file": cand, "hint": "local hooks only - not a server-side gate"})
    return hints


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out")
    ap.add_argument("--md")
    args = ap.parse_args()

    files = []
    for system, rel, full in iter_ci_files(args.root):
        files.append(analyse_file(system, rel, read(full)))

    rollup = {}
    for gate in GATES:
        present = [f["file"] for f in files if f["gates"][gate]["present"]]
        rollup[gate] = {"present_in": present,
                        "status": "present" if present else "missing"}
    pr_files = [f["file"] for f in files
                if any(t in f["triggers"] for t in ("pull_request", "merge_request"))]
    tests_on_pr = [f["file"] for f in files
                   if f["gates"]["test"]["present"]
                   and any(t in f["triggers"] for t in ("pull_request", "merge_request", "push"))]
    result = {
        "root": os.path.abspath(args.root),
        "ci_files": files,
        "summary": {
            "ci_systems": sorted({f["system"] for f in files}),
            "ci_file_count": len(files),
            "gates": rollup,
            "pr_triggered_files": pr_files,
            "test_on_pr_or_push": tests_on_pr,
            "pr_files_without_test_step": [f["file"] for f in files if f["file"] in pr_files
                                           and not f["gates"]["test"]["present"]],
            "advisory_steps": sum(len(f["advisory"]) for f in files),
            "commented_out_gates": [f"{f['file']}:{c['line']} {c['gate']}: {c['snippet']}"
                                    for f in files for c in f["commented_out_gates"]],
        },
        "branch_protection_hints": protection_hints(args.root),
        "not_checked": [
            "actual branch protection / required status checks (forge API, not in repo)",
            "self-hosted runner hardening",
            "CI secrets and variable scoping (stored in the forge)",
            "historical flaky-test rate (needs CI run history)",
        ],
    }
    if not files:
        result["summary"]["gates"] = {g: {"present_in": [], "status": "no-ci-files"} for g in GATES}

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if args.md:
        os.makedirs(os.path.dirname(os.path.abspath(args.md)) or ".", exist_ok=True)
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("# CI gate scan\n\n## Gate rollup\n\n| Gate | Status | Files |\n|---|---|---|\n")
            for gate, r in result["summary"]["gates"].items():
                fh.write(f"| {gate} | {r['status']} | {', '.join('`%s`' % p for p in r['present_in']) or '-'} |\n")
            fh.write("\n## CI files\n\n| File | System | Triggers | Test step | Advisory markers | Steps |\n"
                     "|---|---|---|---|---|---|\n")
            for f in files:
                fh.write(f"| `{f['file']}` | {f['system']} | {', '.join(f['triggers']) or '-'} | "
                         f"{'yes' if f['gates']['test']['present'] else 'NO'} | "
                         f"{len(f['advisory'])} | {len(f['steps'])} |\n")
            if not files:
                fh.write("| _no CI definition found_ | - | - | NO | - | - |\n")
            fh.write("\n## Advisory (cannot fail the build) steps\n\n")
            for f in files:
                for a in f["advisory"]:
                    fh.write(f"- `{f['file']}:{a['line']}` - {a['issue']}: `{a['snippet']}`\n")
            fh.write("\n## Gates present only as commented-out lines\n\n")
            for f in files:
                for c in f["commented_out_gates"]:
                    fh.write(f"- `{f['file']}:{c['line']}` - {c['gate']}: `{c['snippet']}`\n")
            fh.write("\n## Branch-protection hints in repo\n\n")
            for h in result["branch_protection_hints"]:
                fh.write(f"- `{h['file']}` - {h['hint']}\n")
            fh.write("\n## Not checked\n\n")
            for n in result["not_checked"]:
                fh.write(f"- {n}\n")
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
