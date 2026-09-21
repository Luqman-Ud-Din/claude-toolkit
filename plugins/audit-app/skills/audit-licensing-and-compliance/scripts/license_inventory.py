#!/usr/bin/env python3
"""Inventory third-party dependencies with their licences, flag incompatible / unknown
ones for the chosen distribution model, and generate THIRD-PARTY-NOTICES.md.

Usage:
    python license_inventory.py <repo_root> [--model proprietary|saas|open-source]
                                [--policy scripts/license-policy.json]
                                [--nuget-cache ~/.nuget/packages] [--maven-cache ~/.m2/repository]
                                [--no-node-modules] [--out-dir audit/evidence/audit-licensing-and-compliance]
                                [--findings audit/findings/audit-licensing-and-compliance.json]
                                [--report audit/reports/audit-licensing-and-compliance.md]

Sources read (all read-only, nothing installed or downloaded):
  npm     every package.json outside node_modules (direct deps); package-lock.json v2/v3
          (resolved versions and, when present, the "license" field); node_modules/<pkg>/package.json
          license field and LICENSE* file (first line used as the copyright line).
  nuget   *.csproj PackageReference; packages.lock.json; <nuget-cache>/<id>/<version>/<id>.nuspec
          (<license type="expression">, <licenseUrl>). Missing cache entry -> unknown.
  maven   pom.xml <dependencies>; <maven-cache>/<group path>/<artifact>/<version>/<artifact>-<version>.pom
          <licenses><license><name>. Missing -> unknown (mvn license:add-third-party fills it).
  python  requirements*.txt, pyproject.toml [project].dependencies; any */site-packages/*.dist-info/METADATA
          under the repo (License: / Classifier: License ::). Missing -> unknown (pip-licenses fills it).
  images  Dockerfile FROM lines -> listed with licence unknown and the `docker inspect` label command.

Verdict per package = policy.verdicts[model][category]. Findings (LIC-nnn) are written for
incompatible, review and unknown packages (one finding per verdict group, packages listed in
evidence) and for missing attribution (no NOTICE / THIRD-PARTY* file in the repo). The notices
file is written under --out-dir, never into the repo root.
"""
import argparse
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

SKILL = "audit-licensing-and-compliance"
PREFIX = "LIC"
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
fw = _load_atomic("audit-finding-writer", "findings", "audit_finding_writer_findings")
SEVERITIES = fw.SEVERITIES


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def read(path, limit=400_000):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def walk(root, names=None, suffixes=None, max_depth=6):
    for path in repo_walk.iter_files(root, globs=("*",), max_depth=max_depth):
        low = os.path.basename(path).lower()
        if (names and low in names) or (suffixes and low.endswith(suffixes)):
            yield path


# ---------------------------------------------------------------- licence normalisation
class Policy:
    def __init__(self, doc):
        self.doc = doc
        self.aliases = {k.lower(): v for k, v in doc["aliases"].items()}
        self.cat_of = {}
        for cat, ids in doc["categories"].items():
            for i in ids:
                self.cat_of[i.lower()] = cat
        self.verdicts = doc["verdicts"]
        self.severity = doc["severity"]

    def normalise(self, raw):
        """Return (spdx-ish id, category). Handles 'MIT OR Apache-2.0' (most permissive wins)
        and 'X AND Y' (most restrictive wins)."""
        if raw is None:
            return None, "unknown"
        if isinstance(raw, dict):
            raw = raw.get("type") or raw.get("name") or raw.get("url")
        if isinstance(raw, list):
            raw = " AND ".join(self.normalise(x)[0] or "UNKNOWN" for x in raw)
        s = str(raw).strip().strip("()")
        if not s:
            return None, "unknown"
        if re.search(r"\bOR\b", s):
            parts = [self.normalise(p)[0] or "UNKNOWN" for p in re.split(r"\bOR\b", s)]
            best = min(parts, key=lambda p: self.rank(self.cat_of.get(p.lower(), "unknown")))
            return best, self.cat_of.get(best.lower(), "unknown")
        if re.search(r"\bAND\b", s):
            parts = [self.normalise(p)[0] or "UNKNOWN" for p in re.split(r"\bAND\b", s)]
            worst = max(parts, key=lambda p: self.rank(self.cat_of.get(p.lower(), "unknown")))
            return worst, self.cat_of.get(worst.lower(), "unknown")
        low = s.lower()
        if low in self.aliases:
            s = self.aliases[low]
        else:
            for k, v in sorted(self.aliases.items(), key=lambda kv: -len(kv[0])):
                if len(k) > 4 and k in low:
                    s = v
                    break
        canon = s
        for i in self.cat_of:
            if i == canon.lower() or i == canon.lower().replace("-only", "").replace("-or-later", "+").rstrip("+"):
                canon = [x for x in self.doc["categories"][self.cat_of[i]] if x.lower() == i][0]
                break
        cat = self.cat_of.get(canon.lower())
        if not cat:
            base = re.sub(r"-(only|or-later)$", "", canon)
            cat = self.cat_of.get(base.lower(), "unknown")
        return canon, cat

    @staticmethod
    def rank(cat):
        return ["permissive", "weak-copyleft", "strong-copyleft", "network-copyleft", "restricted", "unknown"].index(cat)

    def verdict(self, model, cat):
        return self.verdicts[model].get(cat, "unknown")


def first_copyright_line(text):
    for line in text.splitlines():
        if re.search(r"copyright|\(c\)|©", line, re.IGNORECASE):
            return line.strip()[:200]
    return None


# ---------------------------------------------------------------- collectors
def collect_npm(root, use_node_modules, rel):
    pkgs = {}
    for pj in walk(root, names={"package.json"}):
        try:
            doc = json.loads(read(pj))
        except ValueError:
            continue
        base = os.path.dirname(pj)
        lock = {}
        lp = os.path.join(base, "package-lock.json")
        if os.path.exists(lp):
            try:
                lock = json.loads(read(lp, 20_000_000)).get("packages", {})
            except ValueError:
                lock = {}
        for section in ("dependencies", "peerDependencies", "optionalDependencies"):
            for name, spec in (doc.get(section) or {}).items():
                key = f"npm:{name}"
                entry = pkgs.setdefault(key, {"ecosystem": "npm", "name": name, "version": None, "license": None,
                                              "source": rel(pj), "resolved_from": None, "copyright": None, "homepage": None,
                                              "scope": "runtime" if section == "dependencies" else section})
                entry["spec"] = spec
                lk = lock.get(f"node_modules/{name}")
                if lk:
                    entry["version"] = lk.get("version")
                    if lk.get("license") and not entry["license"]:
                        entry["license"], entry["resolved_from"] = lk["license"], "package-lock.json"
                if use_node_modules:
                    nm = os.path.join(base, "node_modules", *name.split("/"), "package.json")
                    if os.path.exists(nm):
                        try:
                            meta = json.loads(read(nm))
                        except ValueError:
                            meta = {}
                        entry["version"] = entry["version"] or meta.get("version")
                        lic = meta.get("license") or meta.get("licenses")
                        if lic:
                            entry["license"], entry["resolved_from"] = lic, "node_modules/package.json"
                        else:
                            entry["resolved_from"] = entry["resolved_from"] or "node_modules/package.json (no license field)"
                        entry["homepage"] = meta.get("homepage") or meta.get("repository", {}).get("url") if isinstance(meta.get("repository"), dict) else meta.get("homepage")
                        author = meta.get("author")
                        if isinstance(author, dict):
                            author = author.get("name")
                        for lf in glob.glob(os.path.join(os.path.dirname(nm), "LICEN[CS]E*")) + glob.glob(os.path.join(os.path.dirname(nm), "COPYING*")):
                            entry["copyright"] = first_copyright_line(read(lf, 20_000))
                            entry["license_file"] = rel(lf)
                            break
                        if not entry["copyright"] and author:
                            entry["copyright"] = f"Copyright (c) {author}"
                if not entry["resolved_from"]:
                    entry["resolved_from"] = "manifest only (no lockfile/node_modules)"
        for section in ("devDependencies",):
            for name in (doc.get(section) or {}):
                pkgs.setdefault(f"npm:{name}", {"ecosystem": "npm", "name": name, "version": None, "license": None,
                                                "source": rel(pj), "resolved_from": "devDependency (not shipped)",
                                                "copyright": None, "homepage": None, "scope": "dev"})
    return pkgs


def collect_nuget(root, cache, rel):
    pkgs = {}
    for proj in walk(root, suffixes=(".csproj", ".fsproj", ".props")):
        try:
            tree = ET.parse(proj)
        except ET.ParseError:
            continue
        for pr in tree.iter():
            if pr.tag.split("}")[-1] != "PackageReference":
                continue
            name = pr.get("Include") or pr.get("Update")
            if not name:
                continue
            ver = pr.get("Version") or (pr.find("Version").text if pr.find("Version") is not None else None)
            key = f"nuget:{name.lower()}"
            entry = pkgs.setdefault(key, {"ecosystem": "nuget", "name": name, "version": ver, "license": None,
                                          "source": rel(proj), "resolved_from": None, "copyright": None, "homepage": None, "scope": "runtime"})
            entry["version"] = entry["version"] or ver
        lock = os.path.join(os.path.dirname(proj), "packages.lock.json")
        if os.path.exists(lock):
            try:
                ld = load_json(lock)
                for fw in ld.get("dependencies", {}).values():
                    for name, meta in fw.items():
                        key = f"nuget:{name.lower()}"
                        if key in pkgs and meta.get("resolved"):
                            pkgs[key]["version"] = meta["resolved"]
            except ValueError:
                pass
    for key, entry in pkgs.items():
        if not cache or not entry["version"]:
            entry["resolved_from"] = "manifest only (no version or no nuget cache)"
            continue
        nuspec = os.path.join(cache, entry["name"].lower(), entry["version"].lower(), entry["name"].lower() + ".nuspec")
        if not os.path.exists(nuspec):
            entry["resolved_from"] = "not in nuget cache (" + (rel(nuspec) if nuspec.startswith(root) else nuspec).replace(os.sep, "/") + ")"
            continue
        try:
            t = ET.parse(nuspec)
        except ET.ParseError:
            continue
        ns = ""
        m = re.match(r"\{(.*)\}", t.getroot().tag)
        if m:
            ns = "{" + m.group(1) + "}"
        md = t.getroot().find(f"{ns}metadata")
        if md is None:
            continue
        lic = md.find(f"{ns}license")
        if lic is not None and lic.text:
            entry["license"] = lic.text.strip() if (lic.get("type") or "expression") == "expression" else f"SEE-LICENSE ({lic.text.strip()})"
        elif md.find(f"{ns}licenseUrl") is not None:
            entry["license"] = md.find(f"{ns}licenseUrl").text
        entry["resolved_from"] = "nuspec"
        for tag, field in (("copyright", "copyright"), ("projectUrl", "homepage"), ("authors", "authors")):
            el = md.find(f"{ns}{tag}")
            if el is not None and el.text:
                entry[field] = el.text.strip()
        if not entry["copyright"] and entry.get("authors"):
            entry["copyright"] = f"Copyright (c) {entry['authors']}"
    return pkgs


def collect_maven(root, cache, rel):
    pkgs = {}
    for pom in walk(root, names={"pom.xml"}):
        try:
            tree = ET.parse(pom)
        except ET.ParseError:
            continue
        ns = ""
        m = re.match(r"\{(.*)\}", tree.getroot().tag)
        if m:
            ns = "{" + m.group(1) + "}"
        props = {p.tag.replace(ns, ""): (p.text or "") for p in tree.getroot().findall(f"{ns}properties/*")}
        for dep in tree.getroot().iter(f"{ns}dependency"):
            g = dep.findtext(f"{ns}groupId") or ""
            a = dep.findtext(f"{ns}artifactId") or ""
            v = dep.findtext(f"{ns}version") or ""
            scope = dep.findtext(f"{ns}scope") or "compile"
            v = re.sub(r"\$\{([^}]+)\}", lambda mm: props.get(mm.group(1), mm.group(0)), v)
            key = f"maven:{g}:{a}"
            entry = pkgs.setdefault(key, {"ecosystem": "maven", "name": f"{g}:{a}", "version": v or None, "license": None,
                                          "source": rel(pom), "resolved_from": None, "copyright": None, "homepage": None,
                                          "scope": "runtime" if scope in ("compile", "runtime") else scope})
            if cache and v:
                p = os.path.join(cache, *g.split("."), a, v, f"{a}-{v}.pom")
                if os.path.exists(p):
                    try:
                        pt = ET.parse(p)
                        pns = ""
                        mm = re.match(r"\{(.*)\}", pt.getroot().tag)
                        if mm:
                            pns = "{" + mm.group(1) + "}"
                        names = [l.findtext(f"{pns}name") for l in pt.getroot().findall(f"{pns}licenses/{pns}license")]
                        names = [n for n in names if n]
                        if names:
                            entry["license"], entry["resolved_from"] = " AND ".join(names), "maven pom"
                        entry["homepage"] = pt.getroot().findtext(f"{pns}url")
                        org = pt.getroot().findtext(f"{pns}organization/{pns}name")
                        if org:
                            entry["copyright"] = f"Copyright (c) {org}"
                    except ET.ParseError:
                        pass
                if not entry["resolved_from"]:
                    entry["resolved_from"] = "not in maven cache (parent pom may hold the licence; run mvn license:add-third-party)"
            else:
                entry["resolved_from"] = "manifest only (managed version or no maven cache)"
    return pkgs


def collect_python(root, rel):
    pkgs = {}
    metas = {}
    for dirpath, dirnames, filenames in os.walk(root):
        if os.path.basename(dirpath) == "site-packages":
            for d in dirnames:
                if d.endswith(".dist-info"):
                    mp = os.path.join(dirpath, d, "METADATA")
                    txt = read(mp, 50_000)
                    name = re.search(r"^Name:\s*(.+)$", txt, re.M)
                    if name:
                        metas[name.group(1).strip().lower().replace("_", "-")] = (mp, txt)
            dirnames[:] = []
            continue
        # Deliberately descends into .venv/venv (shared skip list minus those two) to reach site-packages,
        # and stops at site-packages itself, which repo_walk.iter_files cannot do.
        dirnames[:] = [x for x in dirnames if x not in repo_walk.SKIP_DIRS - {".venv", "venv"}]
    for req in list(walk(root, suffixes=("requirements.txt",))) + [p for p in walk(root, names={"pyproject.toml"})]:
        txt = read(req)
        specs = []
        if req.lower().endswith("pyproject.toml"):
            m = re.search(r"dependencies\s*=\s*\[(.*?)\]", txt, re.S)
            if m:
                specs = re.findall(r"[\"']([^\"']+)[\"']", m.group(1))
        else:
            specs = [l.strip() for l in txt.splitlines() if l.strip() and not l.startswith(("#", "-"))]
        for spec in specs:
            m = re.match(r"([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*([=<>!~]+\s*[^;#\s]+)?", spec)
            if not m:
                continue
            name = m.group(1).lower().replace("_", "-")
            ver = (m.group(2) or "").lstrip("=<>!~ ").strip() or None
            key = f"pypi:{name}"
            entry = pkgs.setdefault(key, {"ecosystem": "pypi", "name": name, "version": ver, "license": None,
                                          "source": rel(req), "resolved_from": None, "copyright": None, "homepage": None, "scope": "runtime"})
            if name in metas:
                mp, mt = metas[name]
                lic = re.search(r"^License(?:-Expression)?:\s*(.+)$", mt, re.M)
                cls = re.findall(r"^Classifier:\s*License :: (?:OSI Approved :: )?(.+)$", mt, re.M)
                val = (lic.group(1).strip() if lic and lic.group(1).strip() not in ("UNKNOWN", "") else None) or (cls[0].strip() if cls else None)
                if val:
                    entry["license"], entry["resolved_from"] = val, "site-packages METADATA"
                entry["version"] = entry["version"] or (re.search(r"^Version:\s*(.+)$", mt, re.M) or [None, None])[1]
                hp = re.search(r"^Home-page:\s*(.+)$", mt, re.M)
                entry["homepage"] = hp.group(1).strip() if hp else None
                au = re.search(r"^Author:\s*(.+)$", mt, re.M)
                if au:
                    entry["copyright"] = f"Copyright (c) {au.group(1).strip()}"
            if not entry["resolved_from"]:
                entry["resolved_from"] = "manifest only (no site-packages found; run pip-licenses)"
    return pkgs


def collect_images(root, rel):
    pkgs = {}
    for df in list(walk(root, names={"dockerfile"})) + list(walk(root, suffixes=(".dockerfile",))):
        for line in read(df).splitlines():
            m = re.match(r"\s*FROM\s+(?:--platform=\S+\s+)?(\S+)", line, re.I)
            if m and m.group(1).lower() != "scratch":
                img = m.group(1)
                key = f"image:{img}"
                pkgs.setdefault(key, {"ecosystem": "container-image", "name": img.split(":")[0], "version": img.split(":")[1] if ":" in img else "latest",
                                      "license": None, "source": rel(df), "copyright": None, "homepage": None, "scope": "runtime",
                                      "resolved_from": f"not resolvable offline; run: docker inspect --format '{{{{json .Config.Labels}}}}' {img} and read org.opencontainers.image.licenses"})
    return pkgs


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--model", choices=["proprietary", "saas", "open-source"], default="proprietary")
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--policy", default=os.path.join(here, "license-policy.json"))
    ap.add_argument("--nuget-cache", default=os.path.expanduser("~/.nuget/packages"))
    ap.add_argument("--maven-cache", default=os.path.expanduser("~/.m2/repository"))
    ap.add_argument("--no-node-modules", action="store_true")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--findings", default=None)
    ap.add_argument("--report", default=None)
    a = ap.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    root = os.path.abspath(a.root)
    out_dir = a.out_dir or os.path.join(root, "audit", "evidence", SKILL)
    findings_path = a.findings or os.path.join(root, "audit", "findings", f"{SKILL}.json")
    report_path = a.report or os.path.join(root, "audit", "reports", f"{SKILL}.md")
    policy = Policy(load_json(a.policy))

    def rel(p):
        try:
            return os.path.relpath(p, root).replace(os.sep, "/")
        except ValueError:
            return p

    nuget_cache = a.nuget_cache if os.path.isdir(a.nuget_cache) else None
    maven_cache = a.maven_cache if os.path.isdir(a.maven_cache) else None
    pkgs = {}
    pkgs.update(collect_npm(root, not a.no_node_modules, rel))
    pkgs.update(collect_nuget(root, nuget_cache, rel))
    pkgs.update(collect_maven(root, maven_cache, rel))
    pkgs.update(collect_python(root, rel))
    pkgs.update(collect_images(root, rel))

    rows = []
    for key in sorted(pkgs):
        p = pkgs[key]
        lic_id, cat = policy.normalise(p.get("license"))
        verdict = policy.verdict(a.model, cat)
        if p.get("scope") == "dev":
            verdict = "ok"  # not shipped; still listed
            cat = cat if lic_id else "unknown"
        p.update({"license_raw": p.get("license"), "license": lic_id, "category": cat, "verdict": verdict})
        rows.append(p)

    # attribution file present?
    notice_files = []
    for path in repo_walk.iter_files(root, globs=("*",), max_depth=2):
        if re.match(r"(third[-_]?party|notices?|third[-_]?party[-_]?notices?|licen[cs]es?)(\.|$)", os.path.basename(path), re.I):
            notice_files.append(rel(path))

    # findings
    findings = []
    groups = {"incompatible": [], "review": [], "unknown": []}
    for p in rows:
        if p["verdict"] in groups:
            groups[p["verdict"]].append(p)
    n = 1
    texts = {
        "incompatible": ("Dependencies with licences incompatible with the {model} distribution model",
                         "Shipping or serving these packages under the current model breaches their licence: copyleft terms would oblige the product's own source to be published, or the licence forbids the use outright. Legal exposure and a forced rewrite late in the project.",
                         "For each package: replace with a permissively licensed alternative, buy a commercial licence, or isolate it behind a separate process/service if the licence permits (get legal sign-off). Record the decision next to the package in THIRD-PARTY-NOTICES.md."),
        "review": ("Dependencies whose licence needs a documented decision ({model} model)",
                   "Weak-copyleft or model-dependent licences are usually acceptable when the library is used unmodified, but the obligation (keep licence text, publish changes to the library itself, no static bundling for LGPL in some readings) must be checked and written down; an undocumented decision becomes a due-diligence finding at the next funding or acquisition review.",
                   "Confirm each package is used unmodified and consumed as a package; add a one-line decision per package to THIRD-PARTY-NOTICES.md; for LGPL in a compiled/bundled client ask legal."),
        "unknown": ("Dependencies with no licence metadata found locally",
                    "A package with no licence grants no rights; until the licence is known these packages must be treated as incompatible. Usually a metadata gap rather than a real problem, but it blocks the compliance sign-off.",
                    "Resolve each package on its registry page or its LICENSE file (see references/license-discovery-commands.md for the per-ecosystem command that fills the gap), then re-run this script. If a package truly has no licence, contact the author or replace it."),
    }
    for verdict in ("incompatible", "review", "unknown"):
        group = groups[verdict]
        if not group:
            continue
        title, impact, remediation = texts[verdict]
        findings.append({
            "id": f"{PREFIX}-{n:03d}", "title": title.format(model=a.model),
            "severity": policy.severity[verdict], "confidence": "confirmed" if verdict != "unknown" else "likely",
            "location": {"file": group[0]["source"], "symbol": f"{len(group)} package(s)"},
            "evidence": "\n".join(f"{p['ecosystem']} {p['name']}@{p['version'] or '?'} -> {p['license'] or 'UNKNOWN'} ({p['category']}; from {p['resolved_from']}; declared in {p['source']})" for p in group),
            "impact": impact, "remediation": remediation,
            "references": ["CWE-1104", "ASVS-14.2.1"] if verdict != "unknown" else ["CWE-1104"],
            "tags": ["license", verdict, a.model],
            "root_cause_key": f"license:{verdict}",
        })
        n += 1
    attribution_needed = [p for p in rows if p["verdict"] == "attribution"]
    if attribution_needed and not notice_files:
        findings.append({
            "id": f"{PREFIX}-{n:03d}", "title": "Attribution required by permissive licences is not provided",
            "severity": policy.severity["attribution-missing"], "confidence": "confirmed",
            "location": {"file": ".", "symbol": "repository root"},
            "evidence": f"No NOTICE / THIRD-PARTY-NOTICES / LICENSES file found in the repository; {len(attribution_needed)} packages (MIT/BSD/Apache-style) require their copyright notice and licence text to be reproduced with the distribution.",
            "impact": "MIT, BSD, Apache and similar licences are only granted if the notice is kept; omitting it is a breach even though the licences are otherwise permissive. Low effort, but a real obligation for shipped clients and mobile apps.",
            "remediation": f"Ship the generated {rel(os.path.join(out_dir, 'THIRD-PARTY-NOTICES.md'))} with the product (About page, package, container image); regenerate it in CI so it stays current.",
            "references": ["ASVS-14.2.1"], "tags": ["license", "attribution", a.model],
            "root_cause_key": "license:attribution-missing",
        })

    # write evidence: inventory.json, license-inventory.md, THIRD-PARTY-NOTICES.md
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "inventory.json"), "w", encoding="utf-8") as fh:
        json.dump({"model": a.model, "generated_at": started, "packages": rows, "notice_files": notice_files}, fh, indent=2)
    inv = ["| Ecosystem | Package | Version | Licence | Category | Verdict | Resolved from | Declared in |", "|---|---|---|---|---|---|---|---|"]
    for p in rows:
        inv.append(f"| {p['ecosystem']} | {p['name']} | {p['version'] or '?'} | {p['license'] or 'UNKNOWN'} | {p['category']} | {p['verdict']} | {str(p['resolved_from']).replace('|', '/')} | {p['source']} |")
    with open(os.path.join(out_dir, "license-inventory.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(inv) + "\n")
    notices = ["# Third-party notices", "",
               f"This product includes the following third-party components. Generated {started[:10]} by {SKILL}; "
               "review before shipping and keep with the distribution.", ""]
    for p in rows:
        if p.get("scope") == "dev":
            continue
        notices += [f"## {p['name']} {p['version'] or ''}".rstrip(),
                    f"- Licence: {p['license'] or 'UNKNOWN - resolve before release'}"
                    + (f" (see {p['license_file']})" if p.get("license_file") else ""),
                    f"- {p['copyright']}" if p.get("copyright") else "- Copyright: (not found in package metadata; copy from the package's LICENSE file)",
                    f"- Source: {p['homepage']}" if p.get("homepage") else f"- Source: {p['ecosystem']} registry",
                    ""]
    with open(os.path.join(out_dir, "THIRD-PARTY-NOTICES.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(notices))

    doc = {"skill": SKILL, "generated_at": started, "target": {"root": root, "commit": None}, "stack": {},
           "scope": {"checked": [f"{len(rows)} packages across " + ", ".join(sorted({p['ecosystem'] for p in rows})) + f" (model: {a.model})",
                     f"attribution files found: {', '.join(notice_files) or 'none'}"],
                     "not_checked": [
                         {"item": "transitive dependencies", "reason": "only direct manifest entries are inventoried offline; run the per-ecosystem tool in references/license-discovery-commands.md for the full tree"},
                         {"item": "container image licences", "reason": "need a Docker daemon (docker inspect labels); listed as unknown"},
                         {"item": "packages missing from local caches", "reason": "no network access; marked unknown"}]},
           "findings": findings, "summary": {},
           "extra": {"packages": len(rows), "by_verdict": {v: sum(1 for p in rows if p['verdict'] == v) for v in ("ok", "attribution", "review", "incompatible", "unknown")}}}
    summary = fw.summarize(doc)
    for err in fw.validate(doc):
        print(f"findings.json schema problem: {err}", file=sys.stderr)
    os.makedirs(os.path.dirname(findings_path), exist_ok=True)
    with open(findings_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)

    # report
    order = {k: i for i, k in enumerate(SEVERITIES)}
    R = [f"## {SKILL} findings", "", f"Model: **{a.model}**. Packages: {len(rows)}. "
         + ", ".join(f"{v}: {doc['extra']['by_verdict'][v]}" for v in doc["extra"]["by_verdict"]) + ".", "",
         "| " + " | ".join(SEVERITIES) + " |", "|" + "---|" * 5, "| " + " | ".join(str(summary[k]) for k in SEVERITIES) + " |", "",
         "### License inventory", ""] + inv + ["", "### Findings", ""]
    for f in sorted(findings, key=lambda x: order[x["severity"]]):
        R += [f"### [{f['severity']}] {f['id']} - {f['title']}",
              f"- **Location:** `{f['location']['file']}` ({f['location'].get('symbol', '')})",
              f"- **Confidence:** {f['confidence']}", "- **Evidence:**", "", "```", f["evidence"], "```", "",
              f"- **Impact:** {f['impact']}", f"- **Remediation:** {f['remediation']}",
              f"- **Reference:** {', '.join(f['references'])}", ""]
    if not findings:
        R.append("No incompatible, review-needed or unknown licences; attribution file present.")
    R += ["", f"### Generated files", "", f"- `{rel(os.path.join(out_dir, 'THIRD-PARTY-NOTICES.md'))}` (ship with the product)",
          f"- `{rel(os.path.join(out_dir, 'license-inventory.md'))}`, `{rel(os.path.join(out_dir, 'inventory.json'))}`", "",
          "### Not checked", ""] + [f"- {i['item']} - {i['reason']}" for i in doc["scope"]["not_checked"]] + [""]
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(R))
    os.makedirs(os.path.join(root, "audit", "status"), exist_ok=True)
    with open(os.path.join(root, "audit", "status", f"{SKILL}.json"), "w", encoding="utf-8") as fh:
        json.dump({"skill": SKILL, "status": "completed" if rows else "skipped", "reason": None if rows else "no manifests found",
                   "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
                   "scripts": [f"scripts/license_inventory.py --model {a.model}"]}, fh, indent=2)
    print(json.dumps({"packages": len(rows), "by_verdict": doc["extra"]["by_verdict"], "findings": [f["id"] + " " + f["severity"] for f in findings],
                      "notice_files": notice_files, "report": rel(report_path), "notices": rel(os.path.join(out_dir, "THIRD-PARTY-NOTICES.md"))}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
