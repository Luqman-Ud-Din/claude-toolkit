#!/usr/bin/env python3
"""Stdlib-only infrastructure and deployment linter for audit-infra-and-deployment.

Walks a repository, lints container build files and orchestration / IaC
manifests, and emits a container/manifest scorecard (file -> check ->
pass/fail/n/a) as JSON and Markdown, plus a draft backup & rollback readiness
statement built from evidence found in the repo.

Usage:
    python lint_infra.py <repo_root> [--out scorecard.json] [--md scorecard.md]
                         [--evidence-dir audit/evidence/audit-infra-and-deployment]
                         [--extra-manifest rendered.yaml ...] [--no-tools] [--no-yaml]
                         [--timeout 300]

What it parses:
  * Dockerfile / Dockerfile.* / *.dockerfile / Containerfile - line by line
    (continuations, stages, ARG substitution). Checks: non-root user,
    multi-stage, pinned base images (digest preferred), no baked secrets,
    minimal final image, .dockerignore, HEALTHCHECK.
  * YAML - with PyYAML when installed (per `---` document, unknown tags such as
    CloudFormation !Ref tolerated); otherwise a conservative regex scan that is
    per-document rather than per-container, and the output says so.
    Kubernetes workloads/Ingress/Secret/NetworkPolicy, docker-compose services,
    Helm chart values.yaml + templates (templates are not rendered; pass
    `helm template` output via --extra-manifest to lint them properly).
  * Terraform (*.tf), Bicep (*.bicep), ARM (deploymentTemplate *.json),
    CloudFormation (yaml/json) - cheap regex checks: literal secrets, DB backup
    retention, encryption, public exposure, TLS minimums, remote state.
  * nginx *.conf - TLS protocols / termination.
  * Readiness evidence - backup automation, dated restore tests, DR plan,
    rollback mechanism and dated rehearsals, per-environment config files.

External tools: hadolint, trivy (config) and checkov are run when found on PATH
and their JSON output saved under --evidence-dir; when absent they are recorded
with status "not-installed" so the report lists them under "Not checked".

Every "fail" is a candidate for a finding, not a finding: open the file and
confirm before writing it up. Read-only: nothing in the audited repo is
modified; output goes only where --out/--md/--evidence-dir point.
"""
import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

try:
    import yaml  # optional
except ImportError:  # pragma: no cover
    yaml = None

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
sdc = _load_atomic("audit-sensitive-data-catalog", "catalog", "sensitive_data_catalog")

# Agent tooling and vendored third-party code are not this repo's deployment artifacts.
INFRA_EXTRA_SKIP = (".claude", "vendor")
SECRETISH = ("credential", "secret")
MAX_BYTES = 1_500_000
PASS, FAIL, NA = "pass", "fail", "n/a"

REFS = {
    "DF-NONROOT": "CIS-Docker-4.1; hadolint DL3002; CKV_DOCKER_8; CWE-250",
    "DF-MULTISTAGE": "Docker multi-stage build guidance; CIS-Docker-4.3",
    "DF-PINNED-BASE": "CIS-Docker-4.2; hadolint DL3006/DL3007; CKV_DOCKER_7",
    "DF-NO-SECRETS": "CIS-Docker-4.10; CWE-798; CWE-538",
    "DF-MINIMAL": "CIS-Docker-4.3; hadolint DL3015/DL3009/DL3042",
    "DF-DOCKERIGNORE": "CWE-538",
    "DF-HEALTHCHECK": "CIS-Docker-4.6; CKV_DOCKER_2",
    "K8S-LIMITS": "CKV_K8S_11/13; trivy KSV011/KSV018; CWE-770",
    "K8S-REQUESTS": "CKV_K8S_10/12; CWE-770",
    "K8S-LIVENESS": "CKV_K8S_8",
    "K8S-READINESS": "CKV_K8S_9",
    "K8S-SECURITY-CONTEXT": "CIS-K8s-5.2.2..5.2.7, 5.7.3; CKV_K8S_16/20/23; CWE-250",
    "K8S-SECRETS": "CIS-K8s-5.4.1/5.4.2; CKV_K8S_35; CWE-798",
    "K8S-IMAGE-PINNED": "CKV_K8S_14/43",
    "K8S-NETWORK-POLICY": "CIS-K8s-5.3.2",
    "K8S-INGRESS-TLS": "CWE-319",
    "K8S-ROLLBACK-HISTORY": "Deployment spec.revisionHistoryLimit",
    "CMP-LIMITS": "CIS-Docker-5.x memory/CPU limits; CWE-770",
    "CMP-HEALTHCHECK": "CIS-Docker-4.6",
    "CMP-SECRETS": "CWE-798",
    "CMP-SECURITY": "CIS-Docker-5.x privileged/host namespaces; CWE-250",
    "CMP-IMAGE-PINNED": "CIS-Docker-4.2",
    "HELM-RESOURCES": "CKV_K8S_10..13", "HELM-SECURITY-CONTEXT": "CIS-K8s-5.7.3",
    "HELM-PROBES": "CKV_K8S_8/9", "HELM-IMAGE-PINNED": "CKV_K8S_14", "HELM-SECRETS": "CWE-798",
    "TF-SECRETS": "CWE-798", "TF-DB-BACKUP": "CIS AWS/Azure DB backup controls; SOC2-A1.2",
    "TF-ENCRYPTION": "CWE-311", "TF-PUBLIC-EXPOSURE": "CWE-284", "TF-TLS": "CWE-326; CWE-319",
    "TF-REMOTE-STATE": "Terraform remote backend with locking",
    "BICEP-SECRETS": "CWE-798", "BICEP-TLS": "CWE-326", "ARM-SECRETS": "CWE-798", "ARM-TLS": "CWE-326",
    "CFN-SECRETS": "CWE-798", "CFN-DB-BACKUP": "SOC2-A1.2", "CFN-PUBLIC-EXPOSURE": "CWE-284",
    "CFN-ENCRYPTION": "CWE-311",
    "TLS-PROTOCOLS": "CWE-326", "TLS-TERMINATION": "CWE-319",
}

SECRET_FILE_RE = re.compile(r"(^|/)(\.env(\.[\w-]+)?|secrets?(\.[\w.-]+)?|credentials?(\.[\w.-]+)?|id_(rsa|dsa|ecdsa|ed25519)|"
                            r"\.npmrc|\.pypirc|\.netrc|[^/]*\.(pem|key|pfx|p12|jks|keystore)|appsettings\.(production|prod)\.json|"
                            r"service-account[^/]*\.json|kubeconfig)$", re.I)
EXAMPLE_RE = re.compile(r"(example|sample|template|dist|placeholder)", re.I)

NONROOT_IMAGE_RE = re.compile(r"(chiseled|distroless.*nonroot|:nonroot|nginx-unprivileged|^bitnami/|/bitnami/|cgr\.dev/chainguard)", re.I)
BUILD_CMD_RE = re.compile(r"\b(dotnet\s+(publish|build)|mvnw?\s|gradlew?\s|npm\s+run\s+build|ng\s+build|yarn\s+(run\s+)?build|"
                          r"pnpm\s+(run\s+)?build|go\s+build|cargo\s+build|vite\s+build)", re.I)


def row(rows, file, kind, check, result, detail="", line=None, obj=""):
    rows.append({"file": file, "line": line, "object": obj, "kind": kind, "check": check,
                 "result": result, "detail": detail, "reference": REFS.get(check, "")})


def read_text(path):
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return None


def _secret_name(name):
    r = sdc.classify_name(str(name))
    return r["sensitive"] and r["category"] in SECRETISH


def _real_value(value):
    ph = sdc.is_placeholder(value)
    return ph is None or ph["kind"] == "default-credential"


def is_secret_literal(name, value):
    value = "" if value is None else str(value).strip().strip('"').strip("'")
    for m in sdc.find_values(value):
        if m["kind"] != "assignment" and m["category"] in SECRETISH and m["exposure"] != "public" and _real_value(value):
            return True
    return bool(name) and _secret_name(name) and _real_value(value) and len(value) >= 4


# --------------------------------------------------------------------------- discovery

def discover(root):
    out = {"dockerfile": [], "yaml": [], "tf": [], "bicep": [], "json": [], "nginx": [], "dockerignore": [],
           "text": [], "charts": []}
    # globs=("*",): Dockerfile.*, Containerfile, .conf, .cron and similar are matched by name below.
    for p in repo_walk.iter_files(root, globs=("*",), extra_skip=INFRA_EXTRA_SKIP):
        dirpath, fn = os.path.split(p)
        if fn == "Chart.yaml":
            out["charts"].append(dirpath)
        low = fn.lower()
        if low == "dockerfile" or low.startswith("dockerfile.") or low.endswith(".dockerfile") or low == "containerfile":
            out["dockerfile"].append(p)
        elif low.endswith((".yml", ".yaml")):
            out["yaml"].append(p)
        elif low.endswith(".tf"):
            out["tf"].append(p)
        elif low.endswith(".bicep"):
            out["bicep"].append(p)
        elif low.endswith(".json"):
            out["json"].append(p)
        elif low.endswith(".conf") or low.startswith("nginx"):
            out["nginx"].append(p)
        elif low == ".dockerignore" or low.endswith(".dockerignore"):
            out["dockerignore"].append(p)
        if low.endswith((".md", ".txt", ".adoc", ".rst", ".yml", ".yaml", ".sh", ".ps1", ".tf", ".bicep", ".json",
                         ".sql", ".cron", ".toml", ".ini")) or low in ("makefile", "crontab"):
            out["text"].append(p)
    return out


# --------------------------------------------------------------------------- Dockerfile

def parse_dockerfile(text):
    instrs, buf, start, escape = [], "", None, "\\"
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        stripped = line.strip()
        if not buf and (not stripped or stripped.startswith("#")):
            m = re.match(r"#\s*escape\s*=\s*(\S)", stripped)
            if m and not instrs:
                escape = m.group(1)
            continue
        if buf and stripped.startswith("#"):
            continue
        if start is None:
            start = n
        if line.endswith(escape):
            buf += line[:-1] + " "
            continue
        buf += line
        parts = buf.strip().split(None, 1)
        instrs.append((start, parts[0].upper(), parts[1] if len(parts) > 1 else ""))
        buf, start = "", None
    if buf.strip():
        parts = buf.strip().split(None, 1)
        instrs.append((start, parts[0].upper(), parts[1] if len(parts) > 1 else ""))
    return instrs


def split_stages(instrs):
    global_args, stages = {}, []
    for ln, ins, args in instrs:
        if ins == "FROM":
            toks = [t for t in args.split() if not t.startswith("--")]
            image = toks[0] if toks else ""
            alias = toks[2] if len(toks) >= 3 and toks[1].upper() == "AS" else ""
            stages.append({"line": ln, "image": image, "alias": alias, "instrs": []})
        elif not stages:
            if ins == "ARG":
                k, _, v = args.partition("=")
                global_args[k.strip()] = v.strip().strip('"')
        else:
            stages[-1]["instrs"].append((ln, ins, args))
    return global_args, stages


def subst(img, args):
    def rep(m):
        name = m.group(1) or m.group(2)
        return args.get(name, m.group(0)) or m.group(0)
    return re.sub(r"\$\{(\w+)(?::-[^}]*)?\}|\$(\w+)", rep, img)


def split_image(img):
    digest = ""
    if "@" in img:
        img, digest = img.split("@", 1)
    last = img.rsplit("/", 1)[-1]
    if ":" in last:
        name, tag = img.rsplit(":", 1)
    else:
        name, tag = img, ""
    return name.lower(), tag.lower(), digest


def is_heavy(img):
    name, tag, _ = split_image(img)
    base = name.rsplit("/", 1)[-1]
    light_tag = any(x in tag for x in ("slim", "alpine", "distroless", "chiseled", "minimal", "micro"))
    if "/sdk" in name or base == "sdk" or base in ("maven", "gradle", "golang", "rust"):
        return True
    if "jdk" in tag or base.endswith("jdk"):
        return True
    if base in ("node", "python", "ruby", "php", "ubuntu", "debian", "centos", "fedora", "amazonlinux", "buildpack-deps"):
        return not light_tag
    return False


def df_resolve_final(stages, idx, args, seen=None):
    """Follow FROM <alias> chains to the real base image and collect USER lines."""
    seen = seen or set()
    st = stages[idx]
    img = subst(st["image"], args)
    users = [(ln, a) for ln, i, a in st["instrs"] if i == "USER"]
    for j, other in enumerate(stages[:idx]):
        if other["alias"] and other["alias"].lower() == img.lower() and j not in seen:
            seen.add(j)
            base_img, base_users = df_resolve_final(stages, j, args, seen)
            return base_img, base_users + users
    return img, users


def check_dockerfile(rel, text, abs_path, root, has_orchestrator, rows):
    instrs = parse_dockerfile(text)
    args, stages = split_stages(instrs)
    if not stages:
        row(rows, rel, "dockerfile", "DF-PINNED-BASE", NA, "no FROM instruction found")
        return
    aliases = {s["alias"].lower() for s in stages if s["alias"]}
    final_idx = len(stages) - 1
    final_img, users = df_resolve_final(stages, final_idx, args)
    final = stages[final_idx]

    # Non-root user
    if users:
        ln, u = users[-1]
        uname = u.strip().split(":")[0].strip('"')
        if uname.lower() in ("root", "0"):
            row(rows, rel, "dockerfile", "DF-NONROOT", FAIL, f"last USER is '{u.strip()}' - container runs as root", ln)
        else:
            row(rows, rel, "dockerfile", "DF-NONROOT", PASS, f"USER {u.strip()}", ln)
    elif NONROOT_IMAGE_RE.search(final_img):
        row(rows, rel, "dockerfile", "DF-NONROOT", PASS, f"no USER, but base image {final_img} defaults to a non-root user", final["line"])
    else:
        row(rows, rel, "dockerfile", "DF-NONROOT", FAIL, "no USER instruction in the final stage - image default user (root) is used", final["line"])

    # Multi-stage
    build_runs = [(ln, a) for s in stages for ln, i, a in s["instrs"] if i == "RUN" and BUILD_CMD_RE.search(a)]
    if len(stages) >= 2:
        row(rows, rel, "dockerfile", "DF-MULTISTAGE", PASS, f"{len(stages)} stages; final stage FROM {final['image']}", final["line"])
    elif build_runs or is_heavy(final_img):
        ln = build_runs[0][0] if build_runs else final["line"]
        row(rows, rel, "dockerfile", "DF-MULTISTAGE", FAIL, "single stage that builds the app - SDK/toolchain and sources ship in the runtime image", ln)
    else:
        row(rows, rel, "dockerfile", "DF-MULTISTAGE", NA, "single stage with no build step (copies prebuilt output)", final["line"])

    # Pinned base images
    problems, notes = [], []
    for s in stages:
        img = subst(s["image"], args)
        if img.lower() in aliases or img.lower() == "scratch":
            continue
        name, tag, digest = split_image(img)
        if "$" in img:
            notes.append(f"{img} unresolved ARG")
        elif digest:
            notes.append(f"{img.split('@')[0]} pinned by digest")
        elif not tag or tag == "latest":
            problems.append((s["line"], f"{img} has no tag or uses :latest"))
        else:
            notes.append(f"{img} tag only (digest preferred)")
    if problems:
        row(rows, rel, "dockerfile", "DF-PINNED-BASE", FAIL, "; ".join(p for _, p in problems), problems[0][0])
    else:
        row(rows, rel, "dockerfile", "DF-PINNED-BASE", PASS, "; ".join(notes) or "only stage aliases / scratch", stages[0]["line"])

    # Secrets baked in
    secret_hits = []
    for s in stages:
        for ln, ins, a in s["instrs"]:
            if ins in ("COPY", "ADD"):
                body = a.strip()
                if "--from=" in body:
                    continue
                if body.startswith("["):
                    try:
                        toks = json.loads(body)
                    except ValueError:
                        toks = body.strip("[]").replace('"', "").split(",")
                else:
                    toks = [t for t in body.split() if not t.startswith("--")]
                for src in toks[:-1]:
                    src_n = src.strip().replace("\\", "/")
                    if SECRET_FILE_RE.search(src_n) and not EXAMPLE_RE.search(src_n):
                        secret_hits.append((ln, f"{ins} copies secret-like file '{src_n}' into the image"))
            elif ins == "ENV":
                pairs = re.findall(r"(\w+)=(\"[^\"]*\"|'[^']*'|\S+)", a)
                if not pairs:
                    k, _, v = a.strip().partition(" ")
                    pairs = [(k, v)]
                for k, v in pairs:
                    if is_secret_literal(k, v):
                        secret_hits.append((ln, f"ENV {k} holds a literal secret (visible in image config/history)"))
            elif ins == "ARG":
                k = a.strip().partition("=")[0]
                if _secret_name(k):
                    secret_hits.append((ln, f"ARG {k} - build args persist in image history; use RUN --mount=type=secret"))
            elif ins == "RUN":
                if re.search(r"://[^/\s:@$]+:[^/\s@$]+@", a) or re.search(r"(_authToken=|--password[= ]|PASSWORD=)[^\s$]", a):
                    secret_hits.append((ln, "RUN line carries an inline credential"))
    if secret_hits:
        row(rows, rel, "dockerfile", "DF-NO-SECRETS", FAIL, "; ".join(h for _, h in secret_hits), secret_hits[0][0])
    else:
        row(rows, rel, "dockerfile", "DF-NO-SECRETS", PASS, "no secret-like COPY/ADD sources, ENV/ARG values or inline credentials")

    # Minimal final image
    minimal_issues = []
    if is_heavy(final_img):
        minimal_issues.append(f"final base {final_img} is a full SDK/OS image")
    for ln, ins, a in final["instrs"]:
        if ins != "RUN":
            continue
        if re.search(r"apt-get\s+(-\S+\s+)*install", a) and "--no-install-recommends" not in a:
            minimal_issues.append(f"line {ln}: apt-get install without --no-install-recommends")
        if re.search(r"\bapk\s+add\b", a) and "--no-cache" not in a:
            minimal_issues.append(f"line {ln}: apk add without --no-cache")
        if re.search(r"\bpip3?\s+install\b", a) and "--no-cache-dir" not in a:
            minimal_issues.append(f"line {ln}: pip install without --no-cache-dir")
    if minimal_issues:
        row(rows, rel, "dockerfile", "DF-MINIMAL", FAIL, "; ".join(minimal_issues), final["line"])
    else:
        row(rows, rel, "dockerfile", "DF-MINIMAL", PASS, f"final base {final_img}", final["line"])

    # .dockerignore
    d = os.path.dirname(abs_path)
    candidates = [abs_path + ".dockerignore", os.path.join(d, ".dockerignore")]
    cur = d
    while os.path.abspath(cur) != os.path.abspath(root) and len(cur) > len(root):
        cur = os.path.dirname(cur)
        candidates.append(os.path.join(cur, ".dockerignore"))
    found = next((c for c in candidates if os.path.isfile(c)), None)
    if found:
        content = read_text(found) or ""
        missing = [k for k, pat in (("git", r"\.git"), ("env files", r"\.env"), ("build output", r"bin|obj|node_modules|dist|target"))
                   if not re.search(pat, content)]
        where = os.path.relpath(found, root).replace(os.sep, "/")
        row(rows, rel, "dockerfile", "DF-DOCKERIGNORE", PASS,
            f"{where}" + (f" (does not exclude: {', '.join(missing)})" if missing else ""))
    else:
        copies_all = any(i in ("COPY", "ADD") and re.search(r"(^|\s)\.\s+\S", a) for s in stages for _, i, a in s["instrs"])
        row(rows, rel, "dockerfile", "DF-DOCKERIGNORE", FAIL,
            "no .dockerignore beside the Dockerfile or in a parent up to the repo root"
            + ("; 'COPY . .' sends .git, bin/obj and any local secrets into the build context" if copies_all else ""))

    # HEALTHCHECK
    hc = [(ln, a) for ln, i, a in final["instrs"] if i == "HEALTHCHECK"]
    if hc and not hc[-1][1].strip().upper().startswith("NONE"):
        row(rows, rel, "dockerfile", "DF-HEALTHCHECK", PASS, "HEALTHCHECK defined", hc[-1][0])
    elif has_orchestrator:
        row(rows, rel, "dockerfile", "DF-HEALTHCHECK", NA, "no HEALTHCHECK; orchestrator manifests exist - probes are checked there")
    else:
        row(rows, rel, "dockerfile", "DF-HEALTHCHECK", FAIL, "no HEALTHCHECK and no orchestrator probes found in the repo")


# --------------------------------------------------------------------------- YAML helpers

if yaml is not None:
    class _Loader(yaml.SafeLoader):
        pass

    def _any_tag(loader, suffix, node):
        if isinstance(node, yaml.ScalarNode):
            return loader.construct_scalar(node)
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node)
        return loader.construct_mapping(node)

    _Loader.add_multi_constructor("!", _any_tag)


def yaml_chunks(text):
    chunks, cur, start = [], [], 1
    for n, line in enumerate(text.splitlines(), 1):
        if re.match(r"^---(\s|$)", line):
            if any(l.strip() for l in cur):
                chunks.append((start, "\n".join(cur)))
            cur, start = [], n + 1
        else:
            cur.append(line)
    if any(l.strip() for l in cur):
        chunks.append((start, "\n".join(cur)))
    return chunks


def line_of(chunk, start, pattern):
    for i, l in enumerate(chunk.splitlines()):
        if re.search(pattern, l):
            return start + i
    return start


WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "Job", "CronJob", "Pod", "DeploymentConfig", "Rollout"}


def pod_spec(doc):
    kind, spec = doc.get("kind"), doc.get("spec") or {}
    if kind == "Pod":
        return spec
    if kind == "CronJob":
        return ((((spec.get("jobTemplate") or {}).get("spec") or {}).get("template") or {}).get("spec")) or {}
    return ((spec.get("template") or {}).get("spec")) or {}


def image_pin_issue(image):
    if not image or "$" in image or "{{" in image:
        return None, "templated image"
    name, tag, digest = split_image(image)
    if digest:
        return None, f"{image.split('@')[0]} pinned by digest"
    if not tag or tag == "latest":
        return f"{image} has no tag or uses :latest", None
    return None, f"{image} tag only (digest preferred)"


def check_k8s_doc(rel, doc, chunk, start, rows, ctx):
    kind = doc.get("kind")
    meta = doc.get("metadata") or {}
    name = meta.get("name", "?")
    ns = meta.get("namespace", "default")
    obj = f"{kind}/{name}"
    ln = line_of(chunk, start, r"^kind:")
    if kind == "List":
        for item in doc.get("items") or []:
            if isinstance(item, dict):
                check_k8s_doc(rel, item, chunk, start, rows, ctx)
        return
    if kind in ("NetworkPolicy", "CiliumNetworkPolicy", "CiliumClusterwideNetworkPolicy"):
        ctx["netpol_ns"].add(ns if kind != "CiliumClusterwideNetworkPolicy" else "*")
        ctx["netpol_files"].add(rel)
        return
    if kind == "Secret":
        if doc.get("data") or doc.get("stringData"):
            row(rows, rel, "k8s", "K8S-SECRETS", FAIL, "Secret manifest committed with data/stringData values (base64 is not encryption)", ln, obj)
        return
    if kind in ("SealedSecret", "ExternalSecret", "SecretProviderClass"):
        row(rows, rel, "k8s", "K8S-SECRETS", PASS, f"{kind} - secret sourced from a manager/encrypted store", ln, obj)
        return
    if kind == "Ingress":
        spec = doc.get("spec") or {}
        if spec.get("tls"):
            row(rows, rel, "k8s", "K8S-INGRESS-TLS", PASS, "spec.tls configured", ln, obj)
        else:
            row(rows, rel, "k8s", "K8S-INGRESS-TLS", FAIL, "Ingress has no spec.tls - traffic served over plain HTTP unless TLS is terminated upstream", ln, obj)
        return
    if kind not in WORKLOAD_KINDS:
        return
    ctx["workload_ns"].add(ns)
    ps = pod_spec(doc)
    containers = [c for c in (ps.get("containers") or []) if isinstance(c, dict)]
    inits = [c for c in (ps.get("initContainers") or []) if isinstance(c, dict)]
    allc = containers + inits
    cl = line_of(chunk, start, r"^\s*containers:")

    no_limits = [c.get("name", "?") for c in allc if not ((c.get("resources") or {}).get("limits") or {}).get("memory")]
    no_cpu_lim = [c.get("name", "?") for c in allc if not ((c.get("resources") or {}).get("limits") or {}).get("cpu")]
    row(rows, rel, "k8s", "K8S-LIMITS", FAIL if no_limits else PASS,
        (f"no resources.limits.memory on: {', '.join(no_limits)}" if no_limits else "memory limits set")
        + (f"; no cpu limit on: {', '.join(no_cpu_lim)}" if no_cpu_lim else ""), cl, obj)
    no_req = [c.get("name", "?") for c in allc
              if not all(((c.get("resources") or {}).get("requests") or {}).get(k) for k in ("cpu", "memory"))]
    row(rows, rel, "k8s", "K8S-REQUESTS", FAIL if no_req else PASS,
        f"missing requests.cpu/memory on: {', '.join(no_req)}" if no_req else "cpu and memory requests set", cl, obj)

    batch = kind in ("Job", "CronJob") or (kind == "Pod" and ps.get("restartPolicy") in ("Never", "OnFailure"))
    for check, key in (("K8S-LIVENESS", "livenessProbe"), ("K8S-READINESS", "readinessProbe")):
        if batch:
            row(rows, rel, "k8s", check, NA, f"{kind} runs to completion; {key} not expected", cl, obj)
            continue
        missing = [c.get("name", "?") for c in containers if not c.get(key)]
        row(rows, rel, "k8s", check, FAIL if missing else PASS,
            f"no {key} on: {', '.join(missing)}" if missing else f"{key} on every container", cl, obj)

    psc = ps.get("securityContext") or {}
    sc_issues, sc_notes = [], []
    for flag in ("hostNetwork", "hostPID", "hostIPC"):
        if ps.get(flag) is True:
            sc_issues.append(f"{flag}: true")
    for c in allc:
        csc = c.get("securityContext") or {}
        cname = c.get("name", "?")
        non_root = csc.get("runAsNonRoot", psc.get("runAsNonRoot"))
        uid = csc.get("runAsUser", psc.get("runAsUser"))
        if not (non_root is True or (isinstance(uid, int) and uid > 0)):
            sc_issues.append(f"{cname}: runAsNonRoot not true")
        if csc.get("allowPrivilegeEscalation") is not False:
            sc_issues.append(f"{cname}: allowPrivilegeEscalation not false")
        if csc.get("privileged") is True:
            sc_issues.append(f"{cname}: privileged: true")
        if csc.get("readOnlyRootFilesystem") is not True:
            sc_notes.append(f"{cname}: readOnlyRootFilesystem not set")
        drops = [str(x).upper() for x in ((csc.get("capabilities") or {}).get("drop") or [])]
        if "ALL" not in drops:
            sc_notes.append(f"{cname}: capabilities.drop ALL not set")
    detail = "; ".join(sc_issues) if sc_issues else "runAsNonRoot, allowPrivilegeEscalation=false, no privileged/host namespaces"
    if sc_notes:
        detail += " | recommended: " + "; ".join(sc_notes)
    row(rows, rel, "k8s", "K8S-SECURITY-CONTEXT", FAIL if sc_issues else PASS, detail, cl, obj)

    lit, managed = [], []
    for c in allc:
        for e in c.get("env") or []:
            if not isinstance(e, dict):
                continue
            if "valueFrom" in e:
                if (e.get("valueFrom") or {}).get("secretKeyRef"):
                    managed.append(e.get("name"))
            elif is_secret_literal(e.get("name"), e.get("value")):
                lit.append(f"{c.get('name', '?')}.env.{e.get('name')}")
        for ef in c.get("envFrom") or []:
            if isinstance(ef, dict) and ef.get("secretRef"):
                managed.append("envFrom secretRef")
    if lit:
        row(rows, rel, "k8s", "K8S-SECRETS", FAIL, f"literal secret values in env: {', '.join(lit)}",
            line_of(chunk, start, re.escape(lit[0].split(".env.")[-1])), obj)
    else:
        row(rows, rel, "k8s", "K8S-SECRETS", PASS,
            ("secrets via secretKeyRef/envFrom: " + ", ".join(str(m) for m in managed)) if managed else "no literal secret-like env values", cl, obj)

    pin_issues, pin_notes = [], []
    for c in allc:
        issue, note = image_pin_issue(str(c.get("image", "")))
        (pin_issues.append(issue) if issue else pin_notes.append(note))
    row(rows, rel, "k8s", "K8S-IMAGE-PINNED", FAIL if pin_issues else PASS, "; ".join(pin_issues or pin_notes),
        line_of(chunk, start, r"^\s*image:"), obj)

    if kind in ("Deployment", "StatefulSet", "DaemonSet"):
        spec = doc.get("spec") or {}
        rhl = spec.get("revisionHistoryLimit")
        strategy = (spec.get("strategy") or spec.get("updateStrategy") or {}).get("type", "RollingUpdate (default)")
        if rhl == 0:
            row(rows, rel, "k8s", "K8S-ROLLBACK-HISTORY", FAIL, "revisionHistoryLimit: 0 - `kubectl rollout undo` has nothing to roll back to",
                line_of(chunk, start, r"revisionHistoryLimit"), obj)
        else:
            row(rows, rel, "k8s", "K8S-ROLLBACK-HISTORY", PASS, f"revisionHistoryLimit {rhl if rhl is not None else '10 (default)'}; strategy {strategy}", ln, obj)
        ctx["rollback_signals"].append(f"{rel}: {obj} strategy {strategy}")
    if kind == "Rollout":
        strat = (doc.get("spec") or {}).get("strategy") or {}
        ctx["rollback_signals"].append(f"{rel}: Argo Rollout {name} strategy {', '.join(strat.keys()) or '?'}")


def k8s_regex(rel, chunk, start, rows, ctx):
    """Conservative fallback when PyYAML is missing or the document does not parse."""
    km = re.search(r"^kind:\s*['\"]?(\w+)", chunk, re.M)
    if not km:
        return
    kind = km.group(1)
    nm = re.search(r"^\s{2}name:\s*['\"]?([\w.-]+)", chunk, re.M)
    obj = f"{kind}/{nm.group(1) if nm else '?'} (regex)"
    ln = line_of(chunk, start, r"^kind:")
    has = lambda p: re.search(p, chunk, re.M)
    tag = "regex fallback, per document not per container: "
    if kind in ("NetworkPolicy", "CiliumNetworkPolicy"):
        ctx["netpol_ns"].add("*")
        ctx["netpol_files"].add(rel)
        return
    if kind == "Ingress":
        row(rows, rel, "k8s", "K8S-INGRESS-TLS", PASS if has(r"^\s{2}tls:") else FAIL, tag + ("tls: present" if has(r"^\s{2}tls:") else "no tls:"), ln, obj)
        return
    if kind == "Secret":
        if has(r"^(data|stringData):"):
            row(rows, rel, "k8s", "K8S-SECRETS", FAIL, tag + "Secret manifest committed with values", ln, obj)
        return
    if kind not in WORKLOAD_KINDS:
        return
    ctx["workload_ns"].add("*")
    row(rows, rel, "k8s", "K8S-LIMITS", PASS if has(r"\blimits\s*:") and has(r"\bmemory\s*:") else FAIL, tag + "limits/memory keys", ln, obj)
    row(rows, rel, "k8s", "K8S-REQUESTS", PASS if has(r"\brequests\s*:") else FAIL, tag + "requests key", ln, obj)
    batch = kind in ("Job", "CronJob")
    for check, key in (("K8S-LIVENESS", "livenessProbe"), ("K8S-READINESS", "readinessProbe")):
        row(rows, rel, "k8s", check, NA if batch else (PASS if has(rf"\b{key}\s*:") else FAIL), tag + key, ln, obj)
    ok = has(r"runAsNonRoot:\s*true") and has(r"allowPrivilegeEscalation:\s*false") and not has(r"privileged:\s*true") \
        and not has(r"host(Network|PID|IPC):\s*true")
    row(rows, rel, "k8s", "K8S-SECURITY-CONTEXT", PASS if ok else FAIL, tag + "runAsNonRoot/allowPrivilegeEscalation/privileged/host*", ln, obj)
    lits = [m.group(1) for m in re.finditer(r"-\s*name:\s*['\"]?([\w.-]+)['\"]?\s*\n\s*value:\s*(.+)", chunk)
            if is_secret_literal(m.group(1), m.group(2))]
    row(rows, rel, "k8s", "K8S-SECRETS", FAIL if lits else PASS, tag + (f"literal env values: {', '.join(lits)}" if lits else "no literal secret env"), ln, obj)
    imgs = re.findall(r"^\s*-?\s*image:\s*['\"]?(\S+?)['\"]?\s*$", chunk, re.M)
    bad = [i for i in imgs if image_pin_issue(i)[0]]
    row(rows, rel, "k8s", "K8S-IMAGE-PINNED", FAIL if bad else PASS, tag + ("; ".join(bad) if bad else ", ".join(imgs)), ln, obj)
    if kind == "Deployment" and has(r"revisionHistoryLimit:\s*0\b"):
        row(rows, rel, "k8s", "K8S-ROLLBACK-HISTORY", FAIL, tag + "revisionHistoryLimit: 0", ln, obj)


COMPOSE_NAME_RE = re.compile(r"^(docker-)?compose([.-][\w.-]+)?\.ya?ml$", re.I)


def check_compose(rel, doc, text, rows):
    services = doc.get("services") or {}
    for sname, svc in services.items():
        if not isinstance(svc, dict):
            continue
        obj = f"service/{sname}"
        ln = line_of(text, 1, rf"^\s{{2}}['\"]?{re.escape(str(sname))}['\"]?:")
        lim = ((svc.get("deploy") or {}).get("resources") or {}).get("limits") or {}
        has_lim = bool(lim) or svc.get("mem_limit") or svc.get("cpus")
        row(rows, rel, "compose", "CMP-LIMITS", PASS if has_lim else FAIL,
            "resource limits set" if has_lim else "no deploy.resources.limits / mem_limit / cpus", ln, obj)
        hc = svc.get("healthcheck")
        if hc and not (isinstance(hc, dict) and hc.get("disable")):
            row(rows, rel, "compose", "CMP-HEALTHCHECK", PASS, "healthcheck defined", ln, obj)
        else:
            row(rows, rel, "compose", "CMP-HEALTHCHECK", FAIL, "no healthcheck (or disabled)", ln, obj)
        env = svc.get("environment") or {}
        pairs = env.items() if isinstance(env, dict) else [(str(e).partition("=")[0], str(e).partition("=")[2]) for e in env]
        lits = [k for k, v in pairs if is_secret_literal(k, v)]
        row(rows, rel, "compose", "CMP-SECRETS", FAIL if lits else PASS,
            f"literal secret values in environment: {', '.join(lits)}" if lits else
            ("uses compose secrets:" if svc.get("secrets") else "no literal secret-like environment values"), ln, obj)
        bad = []
        if svc.get("privileged") is True:
            bad.append("privileged: true")
        for k in ("network_mode", "pid", "ipc"):
            if str(svc.get(k, "")).lower() == "host":
                bad.append(f"{k}: host")
        if any(str(c).upper() in ("ALL", "SYS_ADMIN") for c in svc.get("cap_add") or []):
            bad.append("cap_add ALL/SYS_ADMIN")
        user = str(svc.get("user", "")).split(":")[0]
        if user in ("root", "0"):
            bad.append("user: root")
        if any(str(v).startswith(("/var/run/docker.sock", "/:")) for v in svc.get("volumes") or []):
            bad.append("mounts docker.sock or host root")
        row(rows, rel, "compose", "CMP-SECURITY", FAIL if bad else PASS,
            "; ".join(bad) if bad else ("user " + user if user else "no privileged/host settings; user comes from the image USER"), ln, obj)
        if svc.get("image"):
            issue, note = image_pin_issue(str(svc["image"]))
            row(rows, rel, "compose", "CMP-IMAGE-PINNED", FAIL if issue else PASS, issue or note, ln, obj)
        else:
            row(rows, rel, "compose", "CMP-IMAGE-PINNED", NA, "built from source (see the Dockerfile rows)", ln, obj)


def compose_regex(rel, text, rows):
    tag = "regex fallback, whole file: "
    has = lambda p: re.search(p, text, re.M)
    row(rows, rel, "compose", "CMP-LIMITS", PASS if has(r"^\s+(limits:|mem_limit:|cpus:)") else FAIL, tag + "limits keys", None, "(all services)")
    row(rows, rel, "compose", "CMP-HEALTHCHECK", PASS if has(r"^\s+healthcheck:") else FAIL, tag + "healthcheck key", None, "(all services)")
    lits = [m.group(1) for m in re.finditer(r"^[ \t]+-?[ \t]*['\"]?([\w.]+)['\"]?[ \t]*[=:][ \t]*['\"]?([^\s'\"$][^\s'\"]*)", text, re.M)
            if _secret_name(m.group(1)) and is_secret_literal(m.group(1), m.group(2))]
    row(rows, rel, "compose", "CMP-SECRETS", FAIL if lits else PASS, tag + (", ".join(lits) or "no literal secrets"), None, "(all services)")
    row(rows, rel, "compose", "CMP-SECURITY", FAIL if has(r"privileged:\s*true|network_mode:\s*['\"]?host") else PASS, tag + "privileged/host", None, "(all services)")


def walk_values(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_values(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_values(v, f"{path}[{i}]")
    else:
        yield path, obj


def find_keys(obj, key):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
            yield from find_keys(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from find_keys(v, key)


def check_helm(chart_dir, root, rows, use_yaml, notes):
    rel_chart = os.path.relpath(chart_dir, root).replace(os.sep, "/")
    values_path = os.path.join(chart_dir, "values.yaml")
    vtext = read_text(values_path) or ""
    vrel = f"{rel_chart}/values.yaml"
    tdir = os.path.join(chart_dir, "templates")
    ttext = ""
    for tp in repo_walk.iter_files(tdir, globs=("*",)):
        ttext += (read_text(tp) or "") + "\n"
    values = None
    if use_yaml and vtext:
        try:
            values = yaml.load(vtext, Loader=_Loader) or {}
        except yaml.YAMLError:
            notes.append(f"{vrel}: did not parse; regex fallback used")
    obj = f"chart/{os.path.basename(chart_dir)}"
    if values is not None:
        res = [v for v in find_keys(values, "resources")]
        ok = any(isinstance(r, dict) and r.get("limits") for r in res)
        row(rows, vrel, "helm", "HELM-RESOURCES", PASS if ok else FAIL,
            "resources.limits set in values" if ok else "resources empty/absent in values.yaml (chart default ships without limits)", None, obj)
        scs = [v for k in ("securityContext", "podSecurityContext", "containerSecurityContext") for v in find_keys(values, k)]
        ok = any(isinstance(s, dict) and s for s in scs)
        row(rows, vrel, "helm", "HELM-SECURITY-CONTEXT", PASS if ok else FAIL,
            "non-empty securityContext in values" if ok else "securityContext/podSecurityContext empty or absent", None, obj)
        tags = [str(v) for img in find_keys(values, "image") if isinstance(img, dict) for v in [img.get("tag", "")]]
        bad = [t for t in tags if t.lower() == "latest"]
        row(rows, vrel, "helm", "HELM-IMAGE-PINNED", FAIL if bad else PASS,
            "image.tag: latest" if bad else "image.tag pinned or defaults to Chart appVersion", None, obj)
        lits = [p for p, v in walk_values(values) if isinstance(v, str) and is_secret_literal(p.rsplit(".", 1)[-1], v)]
        row(rows, vrel, "helm", "HELM-SECRETS", FAIL if lits else PASS,
            f"literal secret values: {', '.join(lits)}" if lits else "no literal secret-like values", None, obj)
    else:
        row(rows, vrel, "helm", "HELM-RESOURCES", FAIL if re.search(r"^\s*resources:\s*\{\}", vtext, re.M) or "limits:" not in vtext else PASS,
            "regex fallback: resources {} / limits", None, obj)
    probes = "livenessProbe" in ttext and "readinessProbe" in ttext
    row(rows, f"{rel_chart}/templates", "helm", "HELM-PROBES", PASS if probes else FAIL,
        "livenessProbe and readinessProbe in templates" if probes else "templates lack livenessProbe and/or readinessProbe", None, obj)


# --------------------------------------------------------------------------- Terraform / Bicep / ARM / CFN / nginx

def tf_blocks(text, header_re):
    for m in re.finditer(header_re, text, re.M):
        i = text.find("{", m.start())
        depth, j = 0, i
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        yield m, text[i:j + 1], text.count("\n", 0, m.start()) + 1


def check_terraform(files, root, rows):
    state_ok, state_detail = False, "no backend block found in any .tf file - state is local and unlocked"
    for path in files:
        text = read_text(path)
        if text is None:
            continue
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        bm = re.search(r'backend\s+"(\w+)"', text)
        if bm:
            if bm.group(1) == "local":
                state_detail = f"{rel}: backend \"local\""
            else:
                state_ok, state_detail = True, f"{rel}: backend \"{bm.group(1)}\""
        if re.search(r"^\s*cloud\s*\{", text, re.M):
            state_ok, state_detail = True, f"{rel}: Terraform Cloud block"
        lits = []
        for n, line in enumerate(text.splitlines(), 1):
            m = re.match(r'^\s*(\w+)\s*=\s*"([^"]*)"', line)
            if m and "${" not in m.group(2) and _secret_name(m.group(1)) and _real_value(m.group(2)) and len(m.group(2)) >= 4:
                lits.append((n, m.group(1)))
        row(rows, rel, "terraform", "TF-SECRETS", FAIL if lits else PASS,
            f"literal values: {', '.join(k for _, k in lits)}" if lits else "no literal secret attributes", lits[0][0] if lits else None)
        for m, body, ln in tf_blocks(text, r'^\s*resource\s+"(\w+)"\s+"([\w-]+)"'):
            rtype, obj = m.group(1), f"{m.group(1)}.{m.group(2)}"
            if rtype in ("aws_db_instance", "aws_rds_cluster", "aws_docdb_cluster", "aws_neptune_cluster"):
                br = re.search(r"backup_retention_period\s*=\s*(\d+)", body)
                if br and br.group(1) == "0":
                    row(rows, rel, "terraform", "TF-DB-BACKUP", FAIL, "backup_retention_period = 0 (automated backups disabled)", ln, obj)
                elif br:
                    row(rows, rel, "terraform", "TF-DB-BACKUP", PASS, f"backup_retention_period = {br.group(1)} days", ln, obj)
                else:
                    row(rows, rel, "terraform", "TF-DB-BACKUP", NA, "backup_retention_period not set; provider/API default applies - set it explicitly", ln, obj)
                enc = re.search(r"storage_encrypted\s*=\s*(\w+)", body)
                row(rows, rel, "terraform", "TF-ENCRYPTION", PASS if enc and enc.group(1) == "true" else FAIL,
                    "storage_encrypted = true" if enc and enc.group(1) == "true" else "storage_encrypted false or unset (defaults to false)", ln, obj)
                pub = re.search(r"publicly_accessible\s*=\s*true", body)
                row(rows, rel, "terraform", "TF-PUBLIC-EXPOSURE", FAIL if pub else PASS,
                    "publicly_accessible = true" if pub else "not publicly accessible", ln, obj)
            elif rtype in ("azurerm_postgresql_flexible_server", "azurerm_mysql_flexible_server", "azurerm_postgresql_server", "azurerm_mysql_server"):
                br = re.search(r"backup_retention_days\s*=\s*(\d+)", body)
                row(rows, rel, "terraform", "TF-DB-BACKUP", PASS if br else NA,
                    f"backup_retention_days = {br.group(1)}" if br else "backup_retention_days not set (service default 7 days)", ln, obj)
            elif rtype in ("azurerm_mssql_database", "azurerm_sql_database"):
                ok = re.search(r"(short_term_retention_policy|long_term_retention_policy)\s*\{", body)
                row(rows, rel, "terraform", "TF-DB-BACKUP", PASS if ok else NA,
                    "retention policy block present" if ok else "no retention policy block (service default PITR retention)", ln, obj)
            elif rtype == "google_sql_database_instance":
                en = re.search(r"backup_configuration\s*\{[^}]*enabled\s*=\s*(\w+)", body, re.S)
                row(rows, rel, "terraform", "TF-DB-BACKUP", PASS if en and en.group(1) == "true" else FAIL,
                    "backup_configuration.enabled = true" if en and en.group(1) == "true" else "backups not enabled", ln, obj)
            elif rtype in ("aws_security_group", "aws_security_group_rule", "azurerm_network_security_rule", "azurerm_network_security_group"):
                bad = []
                for im, ib, _ in tf_blocks(body, r"^\s*ingress\s*") if rtype == "aws_security_group" else [(None, body, ln)]:
                    if re.search(r'0\.0\.0\.0/0|"\*"|"Internet"', ib):
                        fp = re.search(r"from_port\s*=\s*(\d+)", ib)
                        tp = re.search(r"to_port\s*=\s*(\d+)", ib)
                        dp = re.search(r'destination_port_range\s*=\s*"([\d*-]+)"', ib)
                        ports = {22, 3389, 1433, 3306, 5432, 6379, 27017, 9200}
                        if fp and tp:
                            lo, hi = int(fp.group(1)), int(tp.group(1))
                            bad += [str(p) for p in ports if lo <= p <= hi]
                        elif dp:
                            r = dp.group(1)
                            bad += [r] if r == "*" or any(str(p) == r for p in ports) else []
                row(rows, rel, "terraform", "TF-PUBLIC-EXPOSURE", FAIL if bad else PASS,
                    f"admin/database ports open to the internet: {', '.join(sorted(set(bad)))}" if bad else "no admin/DB ports open to 0.0.0.0/0", ln, obj)
        tls_bad = []
        for n, line in enumerate(text.splitlines(), 1):
            if re.search(r'(minimum_tls_version|min_tls_version|ssl_minimal_tls_version_enforced)\s*=\s*"(1\.0|1\.1|TLS1_0|TLS1_1|TLS1_0_0|TLSEnforcementDisabled)"', line) \
                    or re.search(r"(https_only|enable_https_traffic_only|https_traffic_only_enabled)\s*=\s*false", line) \
                    or re.search(r'ssl_policy\s*=\s*"ELBSecurityPolicy-(2015-05|2016-08|TLS-1-0|TLS-1-1)', line):
                tls_bad.append((n, line.strip()))
        if tls_bad or re.search(r"tls|https|ssl_policy", text, re.I):
            row(rows, rel, "terraform", "TF-TLS", FAIL if tls_bad else PASS,
                "; ".join(t for _, t in tls_bad) if tls_bad else "no weak TLS/HTTPS settings", tls_bad[0][0] if tls_bad else None)
    if files:
        row(rows, "(repo)", "terraform", "TF-REMOTE-STATE", PASS if state_ok else FAIL, state_detail)


def check_bicep(files, root, rows):
    for path in files:
        text = read_text(path) or ""
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        lines = text.splitlines()
        lits = []
        for i, line in enumerate(lines):
            m = re.match(r"^\s*param\s+(\w+)\s+string(\s*=\s*'([^']*)')?", line)
            if m and _secret_name(m.group(1)):
                prev = next((l for l in reversed(lines[:i]) if l.strip()), "")
                if "@secure()" not in prev:
                    lits.append((i + 1, f"{m.group(1)} lacks @secure()"))
                elif m.group(3) and _real_value(m.group(3)):
                    lits.append((i + 1, f"{m.group(1)} has a literal default"))
        row(rows, rel, "bicep", "BICEP-SECRETS", FAIL if lits else PASS, "; ".join(t for _, t in lits) or "secret params use @secure() without defaults",
            lits[0][0] if lits else None)
        bad = [(i + 1, l.strip()) for i, l in enumerate(lines)
               if re.search(r"(httpsOnly|supportsHttpsTrafficOnly)\s*:\s*false|(minTlsVersion|minimumTlsVersion)\s*:\s*'(1\.0|1\.1|TLS1_0|TLS1_1)'", l)]
        row(rows, rel, "bicep", "BICEP-TLS", FAIL if bad else PASS, "; ".join(t for _, t in bad) or "no weak TLS/HTTPS settings", bad[0][0] if bad else None)


def check_arm_or_cfn_json(path, root, rows, ctx):
    text = read_text(path) or ""
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    if "deploymentTemplate.json" in text[:400]:
        try:
            doc = json.loads(text)
        except ValueError:
            return
        params = doc.get("parameters") or {}
        bad = [k for k, v in params.items() if isinstance(v, dict) and _secret_name(k) and str(v.get("type", "")).lower() == "string"]
        row(rows, rel, "arm", "ARM-SECRETS", FAIL if bad else PASS,
            f"secret parameters typed string (use securestring): {', '.join(bad)}" if bad else "secret parameters use securestring")
        weak = re.findall(r'"(httpsOnly|supportsHttpsTrafficOnly)"\s*:\s*false|"(minTlsVersion|minimumTlsVersion)"\s*:\s*"(1\.0|1\.1|TLS1_0|TLS1_1)"', text)
        row(rows, rel, "arm", "ARM-TLS", FAIL if weak else PASS, "weak TLS/HTTPS setting present" if weak else "no weak TLS/HTTPS settings")
    elif re.search(r'"AWSTemplateFormatVersion"|"Type"\s*:\s*"AWS::', text):
        check_cfn_text(rel, text, rows)


def check_cfn_text(rel, text, rows):
    k = lambda key: rf"['\"]?{key}['\"]?\s*:\s*['\"]?"
    def first(p):
        for n, l in enumerate(text.splitlines(), 1):
            if re.search(p, l):
                return n, l.strip()
        return None
    sec = first(k(r"(MasterUserPassword|DBPassword|Password|SecretString)") + r"(?!\{\{resolve|!Ref|!Sub|!GetAtt|\{|Ref\b)[^\s'\"{!]{4,}")
    row(rows, rel, "cloudformation", "CFN-SECRETS", FAIL if sec else PASS, sec[1] if sec else "passwords via Ref/resolve/Secrets Manager", sec[0] if sec else None)
    if re.search(r"AWS::RDS::DB(Instance|Cluster)", text):
        b = first(k("BackupRetentionPeriod") + r"0\b")
        row(rows, rel, "cloudformation", "CFN-DB-BACKUP", FAIL if b else PASS, b[1] if b else "BackupRetentionPeriod not 0", b[0] if b else None)
        p = first(k("PubliclyAccessible") + r"true")
        row(rows, rel, "cloudformation", "CFN-PUBLIC-EXPOSURE", FAIL if p else PASS, p[1] if p else "not publicly accessible", p[0] if p else None)
        e = first(k("StorageEncrypted") + r"true")
        row(rows, rel, "cloudformation", "CFN-ENCRYPTION", PASS if e else FAIL, e[1] if e else "StorageEncrypted not true", e[0] if e else None)


def check_nginx(files, root, rows):
    for path in files:
        text = read_text(path) or ""
        if not re.search(r"server\s*\{", text):
            continue
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        protos = re.search(r"ssl_protocols\s+([^;]+);", text)
        has_ssl = re.search(r"ssl_certificate\s", text) or re.search(r"listen\s+[^;]*\bssl\b", text)
        if protos:
            weak = [p for p in protos.group(1).split() if p in ("SSLv2", "SSLv3", "TLSv1", "TLSv1.1")]
            row(rows, rel, "nginx", "TLS-PROTOCOLS", FAIL if weak else PASS, f"ssl_protocols {protos.group(1).strip()}",
                text.count("\n", 0, protos.start()) + 1)
        elif has_ssl:
            row(rows, rel, "nginx", "TLS-PROTOCOLS", PASS, "ssl_protocols not set - nginx defaults (TLSv1.2/1.3 on current versions; verify version)")
        redirect = re.search(r"return\s+30[18]\s+https://", text)
        if has_ssl:
            row(rows, rel, "nginx", "TLS-TERMINATION", PASS, "TLS terminated in this nginx" + ("; HTTP redirects to HTTPS" if redirect else ""))
        else:
            row(rows, rel, "nginx", "TLS-TERMINATION", NA, "plain HTTP listener; confirm TLS is terminated upstream (ingress/load balancer/CDN)")


# --------------------------------------------------------------------------- readiness evidence

DATE_RE = re.compile(r"\b(20\d{2})[-/](\d{2})[-/](\d{2})\b|\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(20\d{2})\b", re.I)
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
NEG_RE = re.compile(r"\b(not (yet )?(been )?(tested|rehearsed|verified|exercised)|never|untested|unrehearsed|tbd|todo)\b", re.I)
TESTED_RE = re.compile(r"\b(tested|rehearsed|drill|exercised|verified|performed|practi[cs]ed|test run|dry[- ]run|game ?day)\b", re.I)
BACKUP_RE = re.compile(r"\b(back(ed)?[ -]?ups?|pg_dump|pg_basebackup|mysqldump|mongodump|BACKUP DATABASE|sqlpackage|velero|restic|borg|"
                       r"aws_backup_plan|azurerm_backup_policy|recovery_services|backup_retention|BackupRetentionPeriod|snapshot schedule)\b", re.I)
RESTORE_RE = re.compile(r"\b(restor(e|ed|ing)|point[- ]in[- ]time recovery|PITR)\b", re.I)
ROLLBACK_RE = re.compile(r"(roll[- ]?back|rollout undo|helm rollback|blue[-/ ]?green|canary|kind:\s*Rollout|slot swap|deployment slot|"
                         r"CodeDeployDefault|flagger|previous (image|tag|release))", re.I)
DR_RE = re.compile(r"\b(disaster recovery|RTO|RPO|failover|business continuity|DR plan|DR drill)\b")
ENV_FILE_RES = [re.compile(p, re.I) for p in (
    r"appsettings\.(\w+)\.json$", r"environment\.(\w+)\.ts$", r"values[-.](\w+)\.ya?ml$", r"overlays/(\w+)/",
    r"(\w+)\.tfvars(\.json)?$", r"\.env\.(\w+)$", r"(?:docker-)?compose\.(\w+)\.ya?ml$", r"application-(\w+)\.(yml|yaml|properties)$",
    r"settings/(\w+)\.py$", r"environments/(\w+)/")]


def norm_date(m):
    if m.group(1):
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return f"{m.group(6)}-{MONTHS[m.group(5)[:3].lower()]:02d}-{int(m.group(4)):02d}"


def readiness_scan(text_files, root, ctx):
    ev = {"backup_automation": [], "restore_tests": [], "restore_negative": [], "rollback_mechanism": list(ctx["rollback_signals"]),
          "rollback_tests": [], "rollback_negative": [], "dr_plan": [], "environments": {}}
    for path in text_files:
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        low = rel.lower()
        for rx in ENV_FILE_RES:
            m = rx.search(rel)
            if m and m.group(1).lower() not in ("example", "sample", "template", "json"):
                ev["environments"].setdefault(m.group(1).lower(), []).append(rel)
        if re.search(r"(disaster|dr[-_]?plan|business[-_]continuity|\bbcp\b)", low):
            ev["dr_plan"].append(f"{rel} (file name)")
        text = read_text(path)
        if not text:
            continue
        lines = text.splitlines()
        prose = low.endswith((".md", ".adoc", ".rst", ".txt"))
        section = None  # topic of the current Markdown heading, so "not rehearsed yet" under "## Rollback" counts
        for n, line in enumerate(lines, 1):
            if len(line) > 400:
                continue
            loc = f"{rel}:{n}: {line.strip()[:160]}"
            is_restore, is_rollback, is_dr = RESTORE_RE.search(line), ROLLBACK_RE.search(line), DR_RE.search(line)
            if prose and re.match(r"^\s{0,3}#{1,6}\s", line):
                section = ("rollback" if is_rollback else
                           "restore" if (is_restore or is_dr or BACKUP_RE.search(line)) else None)
                continue
            if BACKUP_RE.search(line):
                ev["backup_automation"].append(loc)
            if is_dr:
                ev["dr_plan"].append(loc)
            if is_rollback:
                ev["rollback_mechanism"].append(loc)
            topic = "restore" if (is_restore or is_dr) else "rollback" if is_rollback else (section if prose else None)
            if topic is None:
                continue
            if NEG_RE.search(line):
                ev[f"{topic}_negative"].append(loc)
                continue
            if not TESTED_RE.search(line):
                continue
            dm = DATE_RE.search(line) or DATE_RE.search("\n".join(lines[max(0, n - 3):n + 2]))
            if dm:
                ev[f"{topic}_tests"].append({"date": norm_date(dm), "evidence": loc})
    for k in ("backup_automation", "rollback_mechanism", "dr_plan"):
        ev[k] = ev[k][:40]

    def statement(tests, negative, mechanism, what):
        if tests:
            latest = max(tests, key=lambda t: t["date"])
            return f"tested on {latest['date']}", [latest["evidence"]] + [t["evidence"] for t in tests if t is not latest][:4]
        basis = negative[:5] + [f"mechanism described: {m}" for m in mechanism[:3]]
        basis.append(f"no dated {what} test/rehearsal record found in the repository")
        return "never tested", basis

    rs, rb = statement(ev["restore_tests"], ev["restore_negative"], ev["backup_automation"], "restore")
    ks, kb = statement(ev["rollback_tests"], ev["rollback_negative"], ev["rollback_mechanism"], "rollback")
    ev["statement"] = {
        "backup_restore": {"status": rs, "evidence": rb, "automation_found": bool(ev["backup_automation"])},
        "rollback": {"status": ks, "evidence": kb, "mechanism_found": bool(ev["rollback_mechanism"])},
        "caveat": "Draft from repository evidence only. Confirm with the owner and the hosting console; a restore test kept outside the repo still counts if dated evidence is produced.",
    }
    return ev


# --------------------------------------------------------------------------- external tools

def run_tool(name, argv, cwd, timeout, evidence_dir, outname):
    exe = shutil.which(argv[0])
    rec = {"name": name, "command": " ".join(argv), "status": "not-installed", "issues": None, "output": None}
    if not exe:
        rec["note"] = f"{argv[0]} not on PATH - recorded as not checked"
        return rec
    try:
        p = subprocess.run([exe] + argv[1:], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        rec["status"] = "timeout"
        return rec
    except OSError as exc:
        rec.update(status="error", note=str(exc))
        return rec
    rec["status"], rec["exit_code"] = "ran", p.returncode
    out = p.stdout or ""
    if evidence_dir:
        os.makedirs(evidence_dir, exist_ok=True)
        target = os.path.join(evidence_dir, outname)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(out)
        rec["output"] = target
    try:
        data = json.loads(out) if out.strip() else None
        if isinstance(data, list) and name == "hadolint":
            rec["issues"] = len(data)
        elif isinstance(data, dict) and "Results" in data:
            rec["issues"] = sum(len(r.get("Misconfigurations") or []) for r in data.get("Results") or [])
        elif name == "checkov":
            items = data if isinstance(data, list) else [data]
            rec["issues"] = sum(len(((i or {}).get("results") or {}).get("failed_checks") or []) for i in items)
    except ValueError:
        rec["note"] = "output was not JSON; see saved output"
    return rec


# --------------------------------------------------------------------------- main

def to_markdown(res):
    s = res["summary"]
    out = ["# Infra & deployment scorecard", "",
           f"Root: `{res['root']}`  ", f"YAML parser: {res['yaml_parser']}  ",
           f"Result: {s['pass']} pass, {s['fail']} fail, {s['n/a']} n/a across {s['files']} files", ""]
    for n in res["notes"]:
        out.append(f"> {n}")
    out += ["", "## Container / manifest scorecard", "", "| File | Object | Check | Result | Detail |", "|---|---|---|---|---|"]
    for r in res["scorecard"]:
        loc = f"{r['file']}:{r['line']}" if r.get("line") else r["file"]
        res_txt = {"pass": "PASS", "fail": "**FAIL**", "n/a": "n/a"}[r["result"]]
        detail = str(r["detail"]).replace("|", "\\|")
        out.append(f"| `{loc}` | {r['object'] or '-'} | {r['check']} | {res_txt} | {detail} |")
    out += ["", "## External tools", "", "| Tool | Status | Issues | Command | Output |", "|---|---|---|---|---|"]
    for t in res["tools"]:
        out.append(f"| {t['name']} | {t['status']} | {t['issues'] if t['issues'] is not None else '-'} | `{t['command']}` | {t.get('output') or t.get('note', '-')} |")
    st = res["readiness"]["statement"]
    out += ["", "## Backup & rollback readiness (draft - confirm manually)", "",
            f"- **Backup restore:** {st['backup_restore']['status']} (backup automation evidence found: {'yes' if st['backup_restore']['automation_found'] else 'no'})"]
    out += [f"  - {e}" for e in st["backup_restore"]["evidence"]]
    out.append(f"- **Rollback:** {st['rollback']['status']} (rollback mechanism evidence found: {'yes' if st['rollback']['mechanism_found'] else 'no'})")
    out += [f"  - {e}" for e in st["rollback"]["evidence"]]
    rd = res["readiness"]
    out.append(f"- **DR plan evidence:** {len(rd['dr_plan'])} line(s)" + ("" if rd["dr_plan"] else " - none found"))
    out += [f"  - {e}" for e in rd["dr_plan"][:5]]
    out.append("- **Environments seen:** " + (", ".join(f"{k} ({len(v)} files)" for k, v in sorted(rd["environments"].items())) or "none"))
    out += ["", f"_{st['caveat']}_", "", "## Not checked", ""]
    out += [f"- {n['item']} - {n['reason']}" for n in res["not_checked"]]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out", help="write scorecard JSON here")
    ap.add_argument("--md", help="write scorecard Markdown here")
    ap.add_argument("--evidence-dir", help="directory for raw external-tool output")
    ap.add_argument("--extra-manifest", action="append", default=[], help="extra YAML (e.g. helm template output) to lint")
    ap.add_argument("--no-tools", action="store_true", help="do not run hadolint/trivy/checkov")
    ap.add_argument("--no-yaml", action="store_true", help="force the regex fallback even if PyYAML is installed")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    use_yaml = yaml is not None and not args.no_yaml
    notes, rows = [], []
    if not use_yaml:
        notes.append("PyYAML not available (or --no-yaml): YAML manifests were checked with a conservative regex scan, "
                     "per document rather than per container. A PASS can hide one container that lacks the setting; "
                     "install PyYAML (pip install pyyaml) and re-run for per-container results.")
    found = discover(root)
    chart_dirs = [os.path.abspath(c) for c in found["charts"]]
    ctx = {"netpol_ns": set(), "netpol_files": set(), "workload_ns": set(), "rollback_signals": []}

    yaml_files = found["yaml"] + [os.path.abspath(p) for p in args.extra_manifest]
    k8s_like = False
    for path in yaml_files:
        if any(os.path.abspath(path).startswith(os.path.join(c, "templates")) for c in chart_dirs):
            continue
        if os.path.basename(path) in ("Chart.yaml", "values.yaml") and any(os.path.dirname(os.path.abspath(path)) == c for c in chart_dirs):
            continue
        text = read_text(path)
        if not text:
            continue
        rel = os.path.relpath(path, root).replace(os.sep, "/") if os.path.abspath(path).startswith(root) else path.replace(os.sep, "/")
        if re.search(r"^AWSTemplateFormatVersion|^\s+Type:\s*['\"]?AWS::", text, re.M):
            check_cfn_text(rel, text, rows)
            continue
        is_compose_name = bool(COMPOSE_NAME_RE.match(os.path.basename(path)))
        if use_yaml:
            parsed_compose = False
            for start, chunk in yaml_chunks(text):
                try:
                    doc = yaml.load(chunk, Loader=_Loader)
                except yaml.YAMLError:
                    if re.search(r"^apiVersion:", chunk, re.M) and re.search(r"^kind:", chunk, re.M):
                        notes.append(f"{rel}:{start}: YAML did not parse (templated?); regex fallback used for this document")
                        k8s_like = True
                        k8s_regex(rel, chunk, start, rows, ctx)
                    continue
                if not isinstance(doc, dict):
                    continue
                if doc.get("apiVersion") and doc.get("kind"):
                    k8s_like = True
                    check_k8s_doc(rel, doc, chunk, start, rows, ctx)
                elif isinstance(doc.get("services"), dict) and not parsed_compose and (
                        is_compose_name or any(isinstance(v, dict) and ("image" in v or "build" in v) for v in doc["services"].values())):
                    parsed_compose = True
                    check_compose(rel, doc, text, rows)
        else:
            if is_compose_name:
                compose_regex(rel, text, rows)
                continue
            for start, chunk in yaml_chunks(text):
                if re.search(r"^apiVersion:", chunk, re.M) and re.search(r"^kind:", chunk, re.M):
                    k8s_like = True
                    k8s_regex(rel, chunk, start, rows, ctx)

    has_orch = k8s_like or bool(chart_dirs) or any(r["kind"] == "compose" for r in rows)
    for path in found["dockerfile"]:
        text = read_text(path)
        if text is not None:
            check_dockerfile(os.path.relpath(path, root).replace(os.sep, "/"), text, path, root, has_orch, rows)
    for c in chart_dirs:
        check_helm(c, root, rows, use_yaml, notes)
    check_terraform(found["tf"], root, rows)
    check_bicep(found["bicep"], root, rows)
    for path in found["json"]:
        check_arm_or_cfn_json(path, root, rows, ctx)
    check_nginx(found["nginx"], root, rows)

    if ctx["workload_ns"]:
        if "*" in ctx["netpol_ns"]:
            uncovered = set()
        else:
            uncovered = {ns for ns in ctx["workload_ns"] if ns not in ctx["netpol_ns"]} if "*" not in ctx["workload_ns"] else (set() if ctx["netpol_ns"] else {"*"})
        row(rows, "(repo)", "k8s", "K8S-NETWORK-POLICY", FAIL if uncovered else PASS,
            (f"no NetworkPolicy for namespace(s): {', '.join(sorted(uncovered))} - all pod-to-pod traffic allowed" if uncovered
             else f"NetworkPolicy found in {', '.join(sorted(ctx['netpol_files']))}"))

    tools = []
    if args.no_tools:
        tools = [{"name": n, "command": c, "status": "skipped", "issues": None, "output": None, "note": "--no-tools"}
                 for n, c in (("hadolint", "hadolint"), ("trivy", "trivy config"), ("checkov", "checkov -d"))]
    else:
        if found["dockerfile"]:
            if shutil.which("hadolint"):
                for i, df in enumerate(found["dockerfile"]):
                    tools.append(run_tool("hadolint", ["hadolint", "--no-fail", "--format", "json", df], root, args.timeout,
                                          args.evidence_dir, f"hadolint-{i}.json"))
            else:
                tools.append(run_tool("hadolint", ["hadolint", "--format", "json", "<Dockerfile>"], root, args.timeout, None, ""))
        else:
            tools.append({"name": "hadolint", "command": "hadolint", "status": "skipped", "issues": None, "output": None, "note": "no Dockerfiles"})
        tools.append(run_tool("trivy", ["trivy", "config", "--format", "json", "--quiet", root], root, args.timeout, args.evidence_dir, "trivy-config.json"))
        tools.append(run_tool("checkov", ["checkov", "-d", root, "-o", "json", "--quiet", "--compact"], root, args.timeout, args.evidence_dir, "checkov.json"))

    readiness = readiness_scan(found["text"], root, ctx)
    not_checked = [{"item": f"{t['name']} scan", "reason": t.get("note", t["status"])} for t in tools if t["status"] != "ran"]
    if not use_yaml:
        not_checked.append({"item": "per-container YAML checks", "reason": "PyYAML unavailable; regex fallback is per document"})
    if chart_dirs and not args.extra_manifest:
        not_checked.append({"item": "rendered Helm templates", "reason": "templates not rendered; run `helm template` and pass the output with --extra-manifest"})
    not_checked += [
        {"item": "live cluster / cloud state", "reason": "only files in the repository were read; drift from the deployed state is not detected"},
        {"item": "whether backups actually restore", "reason": "a restore can only be proven by running one; the readiness statement reflects recorded evidence"},
        {"item": "image CVEs", "reason": "owned by audit-dependency-vulnerabilities (trivy image / grype)"},
        {"item": "CI/CD pipeline gates", "reason": "owned by audit-test-coverage-and-ci"},
    ]

    files = {r["file"] for r in rows}
    summary = {"pass": sum(r["result"] == PASS for r in rows), "fail": sum(r["result"] == FAIL for r in rows),
               "n/a": sum(r["result"] == NA for r in rows), "files": len(files)}
    res = {"root": root, "generated_at": datetime.now(timezone.utc).isoformat(),
           "yaml_parser": f"PyYAML {yaml.__version__}" if use_yaml else "regex-fallback",
           "notes": notes, "summary": summary, "scorecard": rows, "tools": tools, "readiness": readiness,
           "not_checked": not_checked}
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
    if args.md:
        os.makedirs(os.path.dirname(os.path.abspath(args.md)) or ".", exist_ok=True)
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write(to_markdown(res))
    print(json.dumps({"summary": summary, "yaml_parser": res["yaml_parser"],
                      "fails": [f"{r['file']}{':' + str(r['line']) if r['line'] else ''} {r['check']}" for r in rows if r["result"] == FAIL],
                      "readiness": {k: v["status"] for k, v in readiness["statement"].items() if isinstance(v, dict)},
                      "tools": {t["name"]: t["status"] for t in tools}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
