#!/usr/bin/env python3
"""Run the dependency-vulnerability audit for every package ecosystem found in a
repository, normalise the results into one table, and print upgrade commands.

Usage:
    python dep_audit.py <repo_root> [--out dep-audit.json] [--md dep-audit.md]
                        [--no-network] [--no-tools] [--run-dependency-check]
                        [--timeout 600] [--abandoned-years 2]

What it does (read-only against the audited repo; writes only --out/--md):
  1. Detects manifests: *.csproj/*.fsproj/*.sln (dotnet), pom.xml/build.gradle(.kts)
     (maven/gradle), package.json + lockfile (npm/pnpm/yarn), requirements*.txt /
     pyproject.toml / Pipfile (pip), Dockerfile / docker-compose (images).
  2. Runs whichever scanner is installed:
       dotnet list <proj> package --vulnerable --include-transitive --format json
       npm audit --json | pnpm audit --json | yarn audit --json
       pip-audit -r <file> --format json   (pyproject: pip-audit --format json in dir)
       mvn org.owasp:dependency-check-maven:check -Dformat=JSON   (only with --run-dependency-check;
          otherwise an existing target/dependency-check-report.json or build/reports/... is parsed)
       trivy image --format json <image>  (or grype <image> -o json)
     Missing tools, failed commands and unpullable images are reported under
     "not_checked" - never as "clean".
  3. Fallback knowledge base: a small built-in list of very widely known advisories
     is matched against manifest versions so the table is never empty just because
     no scanner is installed. Rows from it carry source="builtin-kb" and MUST be
     confirmed against a real scanner or advisory before being reported as confirmed.
  4. Normalises every result to:
       {ecosystem, name, current, fixed_in, severity, direct, breaking, advisories,
        manifest, source}
     de-duplicates on (ecosystem, name, current), and flags "breaking" when the
     first version component of fixed_in differs from current.
  5. Abandoned check: queries registry metadata (npm, PyPI, NuGet, Maven Central)
     for the last release date of every direct dependency; packages with no
     release in --abandoned-years are listed. With --no-network or when the
     registry is unreachable the package is marked not-checked, not abandoned.
  6. Emits the upgrade command per row.

Exit code is always 0 unless the arguments are wrong, so that an orchestrator can
keep going; look at "tools" and "not_checked" in the JSON for what actually ran.
"""
import argparse
import datetime as dt
import glob
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import urllib.error

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
_REPO_WALK = os.path.join(_SKILLS, "audit-code-scan", "scripts", "repo_walk.py")
if not os.path.exists(_REPO_WALK):
    sys.exit("audit-code-scan must be reachable from this skill (audit-core plugin or sibling layout; expected " + _REPO_WALK + ")")
_rw_spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", _REPO_WALK)
repo_walk = importlib.util.module_from_spec(_rw_spec)
_rw_spec.loader.exec_module(repo_walk)

SEV_ORDER = {"critical": 0, "high": 1, "moderate": 2, "medium": 2, "low": 3, "info": 4, "unknown": 5}

# ---------------------------------------------------------------------------
# Built-in fallback knowledge base. Deliberately short and limited to advisories
# that are famous enough to be safe to hard-code. Range = [min_vuln, fixed).
# ---------------------------------------------------------------------------
BUILTIN_KB = [
    {"eco": "npm", "name": "lodash", "vuln_below": "4.17.21", "severity": "high",
     "advisories": ["CVE-2020-8203", "CVE-2021-23337", "GHSA-p6mc-m468-83gw"]},
    {"eco": "npm", "name": "minimist", "vuln_below": "1.2.6", "severity": "critical",
     "advisories": ["CVE-2021-44906"]},
    {"eco": "npm", "name": "axios", "vuln_below": "0.21.2", "severity": "high",
     "advisories": ["CVE-2021-3749"]},
    {"eco": "npm", "name": "jsonwebtoken", "vuln_below": "9.0.0", "severity": "high",
     "advisories": ["CVE-2022-23529", "CVE-2022-23540"]},
    {"eco": "npm", "name": "express", "vuln_below": "4.19.2", "severity": "medium",
     "advisories": ["CVE-2024-29041"]},
    {"eco": "npm", "name": "node-fetch", "vuln_below": "2.6.7", "severity": "high",
     "advisories": ["CVE-2022-0235"]},
    {"eco": "nuget", "name": "Newtonsoft.Json", "vuln_below": "13.0.1", "severity": "high",
     "advisories": ["CVE-2024-21907", "GHSA-5crp-9r3c-p9vr"]},
    {"eco": "nuget", "name": "System.Text.Json", "vuln_below": "8.0.4", "severity": "high",
     "advisories": ["CVE-2024-30105", "CVE-2024-43485"]},
    {"eco": "nuget", "name": "SharpZipLib", "vuln_below": "1.3.3", "severity": "high",
     "advisories": ["CVE-2021-32840"]},
    {"eco": "nuget", "name": "BouncyCastle.Cryptography", "vuln_below": "2.2.1", "severity": "medium",
     "advisories": ["CVE-2023-33201"]},
    {"eco": "maven", "name": "org.apache.logging.log4j:log4j-core", "vuln_below": "2.17.1", "severity": "critical",
     "advisories": ["CVE-2021-44228", "CVE-2021-45046", "CVE-2021-45105", "CVE-2021-44832"]},
    {"eco": "maven", "name": "org.springframework:spring-beans", "vuln_below": "5.3.18", "severity": "critical",
     "advisories": ["CVE-2022-22965"]},
    {"eco": "maven", "name": "com.fasterxml.jackson.core:jackson-databind", "vuln_below": "2.13.4.2", "severity": "high",
     "advisories": ["CVE-2022-42003", "CVE-2022-42004"]},
    {"eco": "maven", "name": "org.apache.commons:commons-text", "vuln_below": "1.10.0", "severity": "critical",
     "advisories": ["CVE-2022-42889"]},
    {"eco": "maven", "name": "org.yaml:snakeyaml", "vuln_below": "2.0", "severity": "high",
     "advisories": ["CVE-2022-1471"]},
    {"eco": "pypi", "name": "django", "vuln_below": "3.2.25", "severity": "high",
     "advisories": ["CVE-2023-41164", "CVE-2024-24680", "CVE-2024-27351"],
     "series": "3.2"},
    {"eco": "pypi", "name": "django", "vuln_below": "4.2.11", "severity": "high",
     "advisories": ["CVE-2024-24680", "CVE-2024-27351"], "series": "4.2"},
    {"eco": "pypi", "name": "requests", "vuln_below": "2.32.0", "severity": "medium",
     "advisories": ["CVE-2024-35195"]},
    {"eco": "pypi", "name": "pyyaml", "vuln_below": "5.4", "severity": "critical",
     "advisories": ["CVE-2020-14343"]},
    {"eco": "pypi", "name": "pillow", "vuln_below": "10.3.0", "severity": "high",
     "advisories": ["CVE-2024-28219"]},
    {"eco": "pypi", "name": "cryptography", "vuln_below": "42.0.0", "severity": "medium",
     "advisories": ["CVE-2023-49083", "CVE-2024-26130"]},
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def vtuple(v):
    """Turn '4.17.15', '2.14.1-rc1', '^1.2' into a comparable tuple of ints."""
    nums = re.findall(r"\d+", str(v or "0"))
    return tuple(int(n) for n in nums[:4]) or (0,)


def clean_version(spec):
    m = re.search(r"\d+(?:\.\d+){0,3}", str(spec or ""))
    return m.group(0) if m else None


def is_breaking(current, fixed):
    if not current or not fixed:
        return None
    return vtuple(current)[0] != vtuple(fixed)[0]


def run(cmd, cwd=None, timeout=600):
    """Run a command; return (rc, stdout, stderr) or (None, '', reason)."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           shell=False)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return None, "", f"{cmd[0]} not found"
    except subprocess.TimeoutExpired:
        return None, "", f"timed out after {timeout}s"
    except OSError as e:
        return None, "", str(e)


def which(name):
    return shutil.which(name) or shutil.which(name + ".cmd") or shutil.which(name + ".exe")


def walk(root):
    # Shared skip list and size cap from audit-code-scan. Every file name (Pipfile,
    # build.gradle.kts, *.fsproj included) is offered to the manifest matchers below.
    for path in repo_walk.iter_files(root, globs=["*"]):
        yield os.path.dirname(path), os.path.basename(path)


def read(path, limit=2_000_000):
    return repo_walk.read_text(path, limit)


def rel(root, path):
    return repo_walk.rel(root, path)


def fetch_json(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "audit-dependency-vulnerabilities/1.0",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


# ---------------------------------------------------------------------------
# manifest discovery
# ---------------------------------------------------------------------------
def discover(root):
    m = {"dotnet": [], "maven": [], "gradle": [], "node": [], "pip": [], "images": []}
    for dirpath, fn in walk(root):
        full = os.path.join(dirpath, fn)
        low = fn.lower()
        if low.endswith((".csproj", ".fsproj")):
            m["dotnet"].append(full)
        elif low == "pom.xml":
            m["maven"].append(full)
        elif low in ("build.gradle", "build.gradle.kts"):
            m["gradle"].append(full)
        elif low == "package.json":
            m["node"].append(full)
        elif low in ("requirements.txt", "pyproject.toml", "pipfile") or \
                (low.startswith("requirements") and low.endswith(".txt")):
            m["pip"].append(full)
        elif low == "dockerfile" or low.endswith(".dockerfile") or \
                low in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            m["images"].append(full)
    return m


def images_from(files):
    imgs = []
    for f in files:
        text = read(f)
        for line in text.splitlines():
            s = line.strip()
            mo = re.match(r"FROM\s+(?:--platform=\S+\s+)?([^\s]+)", s, re.I)
            if mo and mo.group(1).lower() != "scratch" and "$" not in mo.group(1):
                imgs.append((mo.group(1).split(" ")[0], f))
            mo = re.match(r"image:\s*['\"]?([^'\"\s]+)", s, re.I)
            if mo and "$" not in mo.group(1):
                imgs.append((mo.group(1), f))
    # de-dupe, keep first manifest
    seen, out = set(), []
    for img, f in imgs:
        if img not in seen:
            seen.add(img)
            out.append((img, f))
    return out


# ---------------------------------------------------------------------------
# manifest parsing (direct dependencies) - used by KB fallback + abandoned check
# ---------------------------------------------------------------------------
def direct_deps(root, manifests):
    """Return list of (eco, name, version_spec, manifest_rel, line)."""
    deps = []
    for f in manifests["dotnet"]:
        for n, line in enumerate(read(f).splitlines(), 1):
            mo = re.search(r'<PackageReference\s+[^>]*Include="([^"]+)"[^>]*Version="([^"]+)"', line)
            if not mo:
                mo2 = re.search(r'<PackageReference\s+[^>]*Include="([^"]+)"', line)
                mo3 = re.search(r'Version="([^"]+)"', line)
                if mo2 and mo3:
                    deps.append(("nuget", mo2.group(1), mo3.group(1), rel(root, f), n))
                continue
            deps.append(("nuget", mo.group(1), mo.group(2), rel(root, f), n))
    # Directory.Packages.props (central package management)
    for dirpath, fn in walk(root):
        if fn.lower() == "directory.packages.props":
            f = os.path.join(dirpath, fn)
            for n, line in enumerate(read(f).splitlines(), 1):
                mo = re.search(r'<PackageVersion\s+Include="([^"]+)"\s+Version="([^"]+)"', line)
                if mo:
                    deps.append(("nuget", mo.group(1), mo.group(2), rel(root, f), n))
    for f in manifests["maven"]:
        text = read(f)
        props = dict(re.findall(r"<([\w.\-]+)>\s*([^<\s]+)\s*</\1>", text))
        lines = text.splitlines()
        # dependency blocks: groupId/artifactId/version may be on separate lines
        for mo in re.finditer(r"<dependency>(.*?)</dependency>", text, re.S):
            block = mo.group(1)
            g = re.search(r"<groupId>\s*([^<]+?)\s*</groupId>", block)
            a = re.search(r"<artifactId>\s*([^<]+?)\s*</artifactId>", block)
            v = re.search(r"<version>\s*([^<]+?)\s*</version>", block)
            if not (g and a):
                continue
            ver = v.group(1) if v else ""
            pm = re.match(r"\$\{([^}]+)\}", ver)
            if pm:
                ver = props.get(pm.group(1), ver)
            line_no = text[:mo.start()].count("\n") + 1
            deps.append(("maven", f"{g.group(1)}:{a.group(1)}", ver, rel(root, f), line_no))
        del lines
    for f in manifests["gradle"]:
        for n, line in enumerate(read(f).splitlines(), 1):
            mo = re.search(r"""(?:implementation|api|compile|runtimeOnly|compileOnly)\s*\(?\s*['"]([\w.\-]+):([\w.\-]+):([^'"]+)['"]""", line)
            if mo:
                deps.append(("maven", f"{mo.group(1)}:{mo.group(2)}", mo.group(3), rel(root, f), n))
    for f in manifests["node"]:
        try:
            pkg = json.loads(read(f))
        except json.JSONDecodeError:
            continue
        lines = read(f).splitlines()
        for section in ("dependencies", "devDependencies", "optionalDependencies"):
            for name, spec in (pkg.get(section) or {}).items():
                line_no = next((i for i, l in enumerate(lines, 1) if f'"{name}"' in l), None)
                deps.append(("npm", name, str(spec), rel(root, f), line_no))
    for f in manifests["pip"]:
        low = os.path.basename(f).lower()
        for n, line in enumerate(read(f).splitlines(), 1):
            s = line.strip()
            if low.endswith(".txt"):
                if not s or s.startswith(("#", "-")):
                    continue
                mo = re.match(r"([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*([=<>!~]=?\s*[^;#\s]+)?", s)
                if mo:
                    deps.append(("pypi", mo.group(1), (mo.group(2) or "").replace(" ", ""), rel(root, f), n))
            else:
                mo = re.match(r"""\s*['"]?([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*([=<>!~]=?\s*[\d.*]+)?['"]?\s*[,\]]?\s*$""", s)
                if mo and ("=" in s or ">" in s or "~" in s) and not s.startswith(("[", "#")):
                    deps.append(("pypi", mo.group(1), (mo.group(2) or "").replace(" ", ""), rel(root, f), n))
    return deps


# ---------------------------------------------------------------------------
# scanners
# ---------------------------------------------------------------------------
def scan_dotnet(root, projects, timeout, tools, not_checked, raw):
    rows = []
    exe = which("dotnet")
    if not exe:
        tools["dotnet"] = "not installed"
        for p in projects:
            not_checked.append({"item": f"dotnet ({rel(root, p)})", "reason": "dotnet CLI not installed"})
        return rows
    tools["dotnet"] = "ran"
    for proj in projects:
        assets = os.path.join(os.path.dirname(proj), "obj", "project.assets.json")
        if not os.path.exists(assets):
            not_checked.append({"item": f"dotnet ({rel(root, proj)})",
                                "reason": "project not restored (obj/project.assets.json missing); run dotnet restore in a scratch copy"})
            continue
        rc, out, err = run([exe, "list", proj, "package", "--vulnerable", "--include-transitive", "--format", "json"],
                           timeout=timeout)
        raw.setdefault("dotnet", []).append({"project": rel(root, proj), "rc": rc, "stdout": out[-20000:], "stderr": err[-2000:]})
        if rc is None or not out.strip():
            not_checked.append({"item": f"dotnet ({rel(root, proj)})", "reason": f"command failed: {err.strip()[:200]}"})
            continue
        try:
            doc = json.loads(out[out.index("{"):])
        except (ValueError, json.JSONDecodeError):
            not_checked.append({"item": f"dotnet ({rel(root, proj)})", "reason": "could not parse --format json output (needs SDK 7.0.200+)"})
            continue
        for p in doc.get("projects", []):
            for fw in p.get("frameworks", []) or []:
                for kind, direct in (("topLevelPackages", True), ("transitivePackages", False)):
                    for pkg in fw.get(kind, []) or []:
                        vulns = pkg.get("vulnerabilities") or []
                        if not vulns:
                            continue
                        sev = max((v.get("severity", "unknown").lower() for v in vulns), key=lambda s: -SEV_ORDER.get(s, 5))
                        rows.append({"ecosystem": "nuget", "name": pkg.get("id"),
                                     "current": pkg.get("resolvedVersion"), "fixed_in": None,
                                     "severity": sev, "direct": direct,
                                     "advisories": [v.get("advisoryurl") for v in vulns if v.get("advisoryurl")],
                                     "manifest": rel(root, proj), "source": "dotnet list package"})
    return rows


def scan_node(root, pkg_files, timeout, tools, not_checked, raw):
    rows = []
    for pf in pkg_files:
        d = os.path.dirname(pf)
        if "node_modules" in pf.replace(os.sep, "/").split("/"):
            continue
        if os.path.exists(os.path.join(d, "pnpm-lock.yaml")):
            mgr, cmd = "pnpm", ["pnpm", "audit", "--json"]
        elif os.path.exists(os.path.join(d, "yarn.lock")):
            mgr, cmd = "yarn", ["yarn", "audit", "--json"]
        elif os.path.exists(os.path.join(d, "package-lock.json")) or os.path.exists(os.path.join(d, "npm-shrinkwrap.json")):
            mgr, cmd = "npm", ["npm", "audit", "--json"]
        else:
            not_checked.append({"item": f"npm ({rel(root, pf)})",
                                "reason": "no lockfile (package-lock.json / yarn.lock / pnpm-lock.yaml); npm audit needs one and the skill must not create it"})
            continue
        exe = which(mgr)
        if not exe:
            tools[mgr] = "not installed"
            not_checked.append({"item": f"{mgr} ({rel(root, pf)})", "reason": f"{mgr} not installed"})
            continue
        tools[mgr] = "ran"
        cmd[0] = exe
        rc, out, err = run(cmd, cwd=d, timeout=timeout)
        raw.setdefault(mgr, []).append({"manifest": rel(root, pf), "rc": rc, "stdout": out[-40000:], "stderr": err[-2000:]})
        if rc is None or not out.strip():
            not_checked.append({"item": f"{mgr} ({rel(root, pf)})", "reason": f"audit command produced no output: {err.strip()[:200]}"})
            continue
        rows += parse_node_audit(mgr, out, rel(root, pf))
    return rows


def parse_node_audit(mgr, out, manifest):
    rows = []
    if mgr == "yarn":
        for line in out.splitlines():
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "auditAdvisory":
                adv = obj["data"]["advisory"]
                for f in adv.get("findings", []) or [{}]:
                    paths = f.get("paths") or []
                    rows.append({"ecosystem": "npm", "name": adv.get("module_name"),
                                 "current": f.get("version"), "fixed_in": clean_version(adv.get("patched_versions")),
                                 "severity": adv.get("severity", "unknown"),
                                 "direct": any(p == adv.get("module_name") for p in paths) if paths else None,
                                 "advisories": [a for a in [adv.get("cves") and adv["cves"][0], adv.get("url")] if a],
                                 "manifest": manifest, "source": "yarn audit"})
        return rows
    try:
        doc = json.loads(out[out.index("{"):])
    except (ValueError, json.JSONDecodeError):
        return rows
    if "vulnerabilities" in doc and isinstance(doc["vulnerabilities"], dict):  # npm >= 7
        for name, v in doc["vulnerabilities"].items():
            fix = v.get("fixAvailable")
            fixed_in = fix.get("version") if isinstance(fix, dict) else None
            advs = []
            for via in v.get("via", []):
                if isinstance(via, dict):
                    advs.append(via.get("url") or via.get("title"))
            rows.append({"ecosystem": "npm", "name": name, "current": v.get("range"),
                         "fixed_in": fixed_in, "severity": v.get("severity", "unknown"),
                         "direct": bool(v.get("isDirect")),
                         "breaking_hint": fix.get("isSemVerMajor") if isinstance(fix, dict) else None,
                         "advisories": [a for a in advs if a], "manifest": manifest, "source": f"{mgr} audit"})
    elif "advisories" in doc:  # npm 6 / pnpm
        for _, adv in doc["advisories"].items():
            for f in adv.get("findings", []) or [{}]:
                paths = f.get("paths") or []
                rows.append({"ecosystem": "npm", "name": adv.get("module_name"),
                             "current": f.get("version"), "fixed_in": clean_version(adv.get("patched_versions")),
                             "severity": adv.get("severity", "unknown"),
                             "direct": any(p == adv.get("module_name") for p in paths) if paths else None,
                             "advisories": [a for a in [adv.get("url")] if a] + list(adv.get("cves") or []),
                             "manifest": manifest, "source": f"{mgr} audit"})
    return rows


def scan_pip(root, files, timeout, tools, not_checked, raw):
    rows = []
    exe = which("pip-audit")
    if not exe:
        tools["pip-audit"] = "not installed"
        for f in files:
            not_checked.append({"item": f"pip ({rel(root, f)})", "reason": "pip-audit not installed (pip install pip-audit)"})
        return rows
    tools["pip-audit"] = "ran"
    for f in files:
        low = os.path.basename(f).lower()
        if low.endswith(".txt"):
            cmd = [exe, "-r", f, "--format", "json", "--progress-spinner", "off"]
        else:
            cmd = [exe, "--format", "json", "--progress-spinner", "off"]
        rc, out, err = run(cmd, cwd=os.path.dirname(f), timeout=timeout)
        raw.setdefault("pip-audit", []).append({"manifest": rel(root, f), "rc": rc, "stdout": out[-40000:], "stderr": err[-2000:]})
        if rc is None or not out.strip():
            not_checked.append({"item": f"pip ({rel(root, f)})", "reason": f"pip-audit failed: {err.strip()[:200]}"})
            continue
        try:
            doc = json.loads(out[out.index("{"):])
        except (ValueError, json.JSONDecodeError):
            not_checked.append({"item": f"pip ({rel(root, f)})", "reason": "could not parse pip-audit JSON"})
            continue
        for dep in doc.get("dependencies", []):
            vulns = dep.get("vulns") or []
            if not vulns:
                continue
            fixes = sorted({fv for v in vulns for fv in (v.get("fix_versions") or [])}, key=vtuple)
            rows.append({"ecosystem": "pypi", "name": dep.get("name"), "current": dep.get("version"),
                         "fixed_in": fixes[-1] if fixes else None, "severity": "unknown",
                         "direct": None,
                         "advisories": [v.get("id") for v in vulns] + [a for v in vulns for a in (v.get("aliases") or [])],
                         "manifest": rel(root, f), "source": "pip-audit"})
    return rows


def scan_maven(root, poms, gradles, timeout, tools, not_checked, raw, run_dc):
    rows = []
    for f in poms + gradles:
        d = os.path.dirname(f)
        is_pom = f.lower().endswith("pom.xml")
        report = None
        candidates = [os.path.join(d, "target", "dependency-check-report.json"),
                      os.path.join(d, "build", "reports", "dependency-check-report.json")]
        if run_dc:
            tool = "mvn" if is_pom else "gradle"
            exe = which(tool) or (which("gradlew") if not is_pom else None)
            if not exe:
                tools[tool] = "not installed"
                not_checked.append({"item": f"{tool} ({rel(root, f)})", "reason": f"{tool} not installed"})
                continue
            if is_pom:
                cmd = [exe, "-q", "org.owasp:dependency-check-maven:check", "-Dformat=JSON", "-DfailBuildOnCVSS=11"]
            else:
                cmd = [exe, "dependencyCheckAnalyze", "--info"]
            rc, out, err = run(cmd, cwd=d, timeout=max(timeout, 1800))
            raw.setdefault("dependency-check", []).append({"manifest": rel(root, f), "rc": rc, "stdout": out[-5000:], "stderr": err[-2000:]})
            tools[tool] = "ran"
        for c in candidates:
            if os.path.exists(c):
                report = c
                break
        if not report:
            tools.setdefault("dependency-check", "not run")
            not_checked.append({"item": f"maven/gradle ({rel(root, f)})",
                                "reason": "no dependency-check report found; re-run with --run-dependency-check (downloads the NVD feed, slow) "
                                          "or run 'mvn org.owasp:dependency-check-maven:check -Dformat=JSON' / 'gradle dependencyCheckAnalyze' and re-run this script"})
            continue
        try:
            doc = json.loads(read(report, 50_000_000))
        except json.JSONDecodeError:
            not_checked.append({"item": f"maven/gradle ({rel(root, f)})", "reason": f"could not parse {rel(root, report)}"})
            continue
        for dep in doc.get("dependencies", []):
            vulns = dep.get("vulnerabilities") or []
            if not vulns:
                continue
            name, ver = None, None
            for p in dep.get("packages", []) or []:
                mo = re.match(r"pkg:maven/([^/]+)/([^@]+)@([^?]+)", p.get("id", ""))
                if mo:
                    name, ver = f"{mo.group(1)}:{mo.group(2)}", mo.group(3)
                    break
            if not name:
                name = dep.get("fileName")
            sev = max((v.get("severity", "unknown").lower() for v in vulns), key=lambda s: -SEV_ORDER.get(s, 5))
            direct = not bool(dep.get("isVirtual")) and any(
                not ip.get("transitive", True) for ip in dep.get("includedBy", []) or [{}])
            rows.append({"ecosystem": "maven", "name": name, "current": ver, "fixed_in": None,
                         "severity": sev, "direct": direct if dep.get("includedBy") else None,
                         "advisories": [v.get("name") for v in vulns],
                         "manifest": rel(root, f), "source": "dependency-check"})
    return rows


def scan_images(root, image_files, timeout, tools, not_checked, raw):
    rows = []
    images = images_from(image_files)
    if not images:
        return rows
    trivy, grype = which("trivy"), which("grype")
    if not trivy and not grype:
        tools["trivy/grype"] = "not installed"
        for img, f in images:
            not_checked.append({"item": f"image {img} ({rel(root, f)})", "reason": "neither trivy nor grype installed"})
        return rows
    for img, f in images:
        if trivy:
            tools["trivy"] = "ran"
            rc, out, err = run([trivy, "image", "--format", "json", "--quiet", img], timeout=timeout)
            raw.setdefault("trivy", []).append({"image": img, "rc": rc, "stdout": out[-40000:], "stderr": err[-2000:]})
            if rc is None or rc != 0 or not out.strip():
                not_checked.append({"item": f"image {img}", "reason": f"trivy failed (pull/auth?): {err.strip()[:200]}"})
                continue
            try:
                doc = json.loads(out[out.index("{"):])
            except (ValueError, json.JSONDecodeError):
                not_checked.append({"item": f"image {img}", "reason": "could not parse trivy JSON"})
                continue
            for res in doc.get("Results", []) or []:
                for v in res.get("Vulnerabilities", []) or []:
                    rows.append({"ecosystem": f"image:{img}", "name": v.get("PkgName"),
                                 "current": v.get("InstalledVersion"), "fixed_in": v.get("FixedVersion") or None,
                                 "severity": (v.get("Severity") or "unknown").lower(), "direct": None,
                                 "advisories": [v.get("VulnerabilityID")], "manifest": rel(root, f), "source": "trivy"})
        else:
            tools["grype"] = "ran"
            rc, out, err = run([grype, img, "-o", "json", "-q"], timeout=timeout)
            raw.setdefault("grype", []).append({"image": img, "rc": rc, "stdout": out[-40000:], "stderr": err[-2000:]})
            if rc is None or rc != 0 or not out.strip():
                not_checked.append({"item": f"image {img}", "reason": f"grype failed: {err.strip()[:200]}"})
                continue
            try:
                doc = json.loads(out[out.index("{"):])
            except (ValueError, json.JSONDecodeError):
                not_checked.append({"item": f"image {img}", "reason": "could not parse grype JSON"})
                continue
            for m in doc.get("matches", []) or []:
                vul, art = m.get("vulnerability", {}), m.get("artifact", {})
                fixes = (vul.get("fix") or {}).get("versions") or []
                rows.append({"ecosystem": f"image:{img}", "name": art.get("name"), "current": art.get("version"),
                             "fixed_in": fixes[0] if fixes else None,
                             "severity": (vul.get("severity") or "unknown").lower(), "direct": None,
                             "advisories": [vul.get("id")], "manifest": rel(root, f), "source": "grype"})
    return rows


def kb_scan(deps):
    rows = []
    for eco, name, spec, manifest, line in deps:
        ver = clean_version(spec)
        if not ver:
            continue
        for kb in BUILTIN_KB:
            if kb["eco"] != eco or kb["name"].lower() != name.lower():
                continue
            if kb.get("series") and not ver.startswith(kb["series"] + "."):
                continue
            if vtuple(ver) < vtuple(kb["vuln_below"]):
                rows.append({"ecosystem": eco, "name": name, "current": ver, "fixed_in": kb["vuln_below"],
                             "severity": kb["severity"], "direct": True, "advisories": list(kb["advisories"]),
                             "manifest": manifest, "line": line, "source": "builtin-kb"})
    return rows


# ---------------------------------------------------------------------------
# normalise / dedupe / upgrade commands
# ---------------------------------------------------------------------------
def dedupe(rows):
    merged = {}
    for r in rows:
        key = (r["ecosystem"], (r.get("name") or "").lower(), clean_version(r.get("current")) or str(r.get("current")))
        cur = merged.get(key)
        if not cur:
            r = dict(r)
            r["advisories"] = sorted({a for a in r.get("advisories", []) if a})
            r["sources"] = [r.pop("source", "?")]
            merged[key] = r
            continue
        cur["advisories"] = sorted(set(cur["advisories"]) | {a for a in r.get("advisories", []) if a})
        if SEV_ORDER.get(r.get("severity", "unknown"), 5) < SEV_ORDER.get(cur.get("severity", "unknown"), 5):
            cur["severity"] = r["severity"]
        if not cur.get("fixed_in") and r.get("fixed_in"):
            cur["fixed_in"] = r["fixed_in"]
        if cur.get("direct") is None and r.get("direct") is not None:
            cur["direct"] = r["direct"]
        if r.get("line") and not cur.get("line"):
            cur["line"] = r["line"]
        src = r.get("source", "?")
        if src not in cur["sources"]:
            cur["sources"].append(src)
    out = []
    for r in merged.values():
        r["severity"] = {"moderate": "medium"}.get(r.get("severity", "unknown"), r.get("severity", "unknown"))
        cv = clean_version(r.get("current"))
        r["breaking"] = r.get("breaking_hint") if r.get("breaking_hint") is not None else is_breaking(cv, r.get("fixed_in"))
        r.pop("breaking_hint", None)
        r["upgrade_command"] = upgrade_command(r)
        out.append(r)
    out.sort(key=lambda r: (SEV_ORDER.get(r["severity"], 5), r["ecosystem"], r["name"] or ""))
    return out


def upgrade_command(r):
    eco, name, fixed, manifest = r["ecosystem"], r.get("name"), r.get("fixed_in"), r.get("manifest", "")
    target = fixed or "<latest patched version - see advisory>"
    if eco == "npm":
        mgr = "npm install" if "pnpm" not in " ".join(r.get("sources", [])) else "pnpm add"
        if "yarn" in " ".join(r.get("sources", [])):
            mgr = "yarn add"
        if r.get("direct") is False:
            return (f"# transitive: bump the parent, or pin via package.json \"overrides\" (npm) / \"resolutions\" (yarn) / pnpm.overrides: "
                    f"\"{name}\": \"{target}\"")
        return f"{mgr} {name}@{target}"
    if eco == "nuget":
        if r.get("direct") is False:
            return f"# transitive: add an explicit <PackageReference Include=\"{name}\" Version=\"{target}\" /> (or PackageVersion in Directory.Packages.props) to force the fixed version"
        return f"dotnet add {manifest} package {name} --version {target}"
    if eco == "pypi":
        return f"pip install '{name}>={target}'  # then update {manifest}"
    if eco == "maven":
        if manifest.endswith("pom.xml"):
            return f"# set <version>{target}</version> for {name} in {manifest} (use <dependencyManagement> for transitive); then mvn versions:use-latest-releases -Dincludes={name}"
        return f"# set '{name}:{target}' in {manifest} (or a resolutionStrategy.force for transitive)"
    if eco.startswith("image:"):
        return f"# rebuild on a newer base image / apply OS patches in the Dockerfile ({manifest}); fixed in {target}"
    return f"# upgrade {name} to {target}"


# ---------------------------------------------------------------------------
# abandoned-package check via registry metadata
# ---------------------------------------------------------------------------
def last_release_date(eco, name):
    """Return ISO date string or raise."""
    if eco == "npm":
        doc = fetch_json(f"https://registry.npmjs.org/{name}")
        t = doc.get("time", {})
        latest = doc.get("dist-tags", {}).get("latest")
        return (t.get(latest) or t.get("modified") or "")[:10]
    if eco == "pypi":
        doc = fetch_json(f"https://pypi.org/pypi/{name}/json")
        dates = [f["upload_time"] for files in doc.get("releases", {}).values() for f in files if f.get("upload_time")]
        return max(dates)[:10] if dates else ""
    if eco == "nuget":
        doc = fetch_json(f"https://api.nuget.org/v3/registration5-semver1/{name.lower()}/index.json")
        pages = doc.get("items", [])
        if not pages:
            return ""
        last = pages[-1]
        items = last.get("items")
        if not items:
            last = fetch_json(last["@id"])
            items = last.get("items", [])
        pub = [i.get("catalogEntry", {}).get("published", "") for i in items]
        pub = [p for p in pub if p and not p.startswith("1900")]
        return max(pub)[:10] if pub else ""
    if eco == "maven":
        g, a = name.split(":", 1)
        doc = fetch_json(f"https://search.maven.org/solrsearch/select?q=g:%22{g}%22+AND+a:%22{a}%22&rows=1&wt=json")
        docs = doc.get("response", {}).get("docs", [])
        if not docs:
            return ""
        ts = docs[0].get("timestamp")
        return dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc).strftime("%Y-%m-%d") if ts else ""
    raise ValueError("unsupported ecosystem")


def abandoned_check(deps, years, no_network, not_checked):
    results = []
    if no_network:
        not_checked.append({"item": "abandoned-package check", "reason": "--no-network given; registry metadata not queried"})
        return results
    cutoff = dt.date.today() - dt.timedelta(days=365 * years)
    seen = set()
    unreachable = 0
    for eco, name, spec, manifest, line in deps:
        key = (eco, name.lower())
        if key in seen:
            continue
        seen.add(key)
        try:
            date = last_release_date(eco, name)
        except Exception as e:  # network, 404, parse
            unreachable += 1
            results.append({"ecosystem": eco, "name": name, "last_release": None, "status": "not-checked",
                            "reason": str(e)[:120], "manifest": manifest})
            continue
        if not date:
            results.append({"ecosystem": eco, "name": name, "last_release": None, "status": "not-checked",
                            "reason": "no release date in registry metadata", "manifest": manifest})
            continue
        try:
            d = dt.date.fromisoformat(date)
        except ValueError:
            results.append({"ecosystem": eco, "name": name, "last_release": date, "status": "not-checked",
                            "reason": "unparseable date", "manifest": manifest})
            continue
        results.append({"ecosystem": eco, "name": name, "last_release": date,
                        "status": "abandoned" if d < cutoff else "active", "manifest": manifest, "line": line})
    if unreachable:
        not_checked.append({"item": f"abandoned-package check ({unreachable} packages)",
                            "reason": "registry unreachable or package not found (private feed?)"})
    return results


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------
def to_markdown(result):
    o = ["# Dependency audit", "", f"Root: `{result['root']}`  ", f"Run: {result['run_at']}", "", "## Scanners", "",
         "| Tool | Status |", "|---|---|"]
    for t, s in sorted(result["tools"].items()):
        o.append(f"| {t} | {s} |")
    o += ["", "## Vulnerable packages", "",
          "| Package | Ecosystem | Current | Fixed in | Severity | Direct/Transitive | Breaking? | Advisories | Source |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in result["vulnerable"]:
        d = {True: "direct", False: "transitive", None: "?"}[r.get("direct")]
        b = {True: "yes", False: "no", None: "?"}[r.get("breaking")]
        loc = r["manifest"] + (f":{r['line']}" if r.get("line") else "")
        o.append(f"| {r['name']} | {r['ecosystem']} | {r.get('current') or '?'} | {r.get('fixed_in') or 'see advisory'} | "
                 f"{r['severity']} | {d} | {b} | {', '.join(r['advisories'][:4])} | {', '.join(r['sources'])} (`{loc}`) |")
    if not result["vulnerable"]:
        o.append("| (none reported by the scanners that ran) | | | | | | | | |")
    o += ["", "## Abandoned packages (no release in %d+ years)" % result["abandoned_years"], "",
          "| Package | Ecosystem | Last release | Manifest |", "|---|---|---|---|"]
    ab = [a for a in result["abandoned"] if a["status"] == "abandoned"]
    for a in ab:
        o.append(f"| {a['name']} | {a['ecosystem']} | {a['last_release']} | `{a['manifest']}` |")
    if not ab:
        o.append("| (none) | | | |")
    nc_ab = [a for a in result["abandoned"] if a["status"] == "not-checked"]
    if nc_ab:
        o.append(f"\n{len(nc_ab)} package(s) not checked (registry unreachable / not found): " +
                 ", ".join(a["name"] for a in nc_ab[:20]))
    o += ["", "## Upgrade commands", "", "```bash"]
    seen = set()
    for r in result["vulnerable"]:
        if r["upgrade_command"] not in seen:
            seen.add(r["upgrade_command"])
            o.append(r["upgrade_command"])
    o += ["```", "", "## Not checked", ""]
    for n in result["not_checked"]:
        o.append(f"- {n['item']} - {n['reason']}")
    if not result["not_checked"]:
        o.append("- (nothing)")
    return "\n".join(o) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--out", help="write the normalised JSON here")
    ap.add_argument("--md", help="write the Markdown table here")
    ap.add_argument("--no-network", action="store_true", help="skip registry metadata (abandoned check)")
    ap.add_argument("--no-tools", action="store_true", help="do not run any scanner; manifest KB fallback only")
    ap.add_argument("--run-dependency-check", action="store_true",
                    help="actually run OWASP dependency-check for Maven/Gradle (slow: downloads NVD)")
    ap.add_argument("--timeout", type=int, default=600, help="per-command timeout in seconds")
    ap.add_argument("--abandoned-years", type=int, default=2)
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    manifests = discover(root)
    tools, not_checked, raw, rows = {}, [], {}, []
    deps = direct_deps(root, manifests)

    if not a.no_tools:
        rows += scan_dotnet(root, manifests["dotnet"], a.timeout, tools, not_checked, raw)
        rows += scan_node(root, manifests["node"], a.timeout, tools, not_checked, raw)
        rows += scan_pip(root, manifests["pip"], a.timeout, tools, not_checked, raw)
        rows += scan_maven(root, manifests["maven"], manifests["gradle"], a.timeout, tools, not_checked, raw,
                           a.run_dependency_check)
        rows += scan_images(root, manifests["images"], a.timeout, tools, not_checked, raw)
    else:
        not_checked.append({"item": "all scanners", "reason": "--no-tools given"})
    kb_rows = kb_scan(deps)
    tools["builtin-kb"] = f"matched {len(kb_rows)} manifest version(s) - confirm against a real scanner"
    rows += kb_rows

    vulnerable = dedupe(rows)
    abandoned = abandoned_check(deps, a.abandoned_years, a.no_network, not_checked)

    result = {
        "root": root,
        "run_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "manifests": {k: [rel(root, p) for p in v] for k, v in manifests.items()},
        "images": [i for i, _ in images_from(manifests["images"])],
        "direct_dependency_count": len(deps),
        "tools": tools,
        "vulnerable": vulnerable,
        "abandoned_years": a.abandoned_years,
        "abandoned": abandoned,
        "upgrade_commands": sorted({r["upgrade_command"] for r in vulnerable}),
        "not_checked": not_checked,
        "raw": raw,
    }
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(to_markdown(result))
    summary = {"vulnerable": len(vulnerable),
               "by_severity": {s: sum(1 for r in vulnerable if r["severity"] == s) for s in ("critical", "high", "medium", "low", "unknown")},
               "abandoned": sum(1 for x in abandoned if x["status"] == "abandoned"),
               "tools": tools, "not_checked": len(not_checked)}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
