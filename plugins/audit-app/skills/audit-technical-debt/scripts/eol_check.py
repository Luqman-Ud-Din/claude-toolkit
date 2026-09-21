#!/usr/bin/env python3
"""End-of-life check for runtimes, frameworks and packages declared in a repo,
against the bundled table references/eol-dates.json.

Usage:
    python eol_check.py <repo_root> [--table ../references/eol-dates.json] [--as-of YYYY-MM-DD]
                        [--warn-days 180] [--stale-table-days 180] [--out eol.json] [--md eol.md]

Declarations read (read-only):
  .NET     <TargetFramework(s)> in *.csproj/*.fsproj/*.vbproj/Directory.Build.props,
           global.json sdk.version, <PackageReference>/<PackageVersion> names+versions
  Node     package.json engines.node, .nvmrc/.node-version, dependencies + devDependencies
           (@angular/core, angular (AngularJS), vue, react, nuxt, express, and any package
           listed in the table)
  Python   python_requires (setup.py/setup.cfg), requires-python (pyproject.toml),
           .python-version, runtime.txt, Pipfile python_version; Django and listed
           packages in requirements*.txt / pyproject / Pipfile
  Java     <java.version>, maven.compiler.release/source, <release>, Gradle
           sourceCompatibility / JavaVersion.VERSION_x / JavaLanguageVersion.of(x),
           spring-boot-starter-parent / org.springframework.boot plugin version, log4j 1.x
  Images   Dockerfile FROM node:x, python:x, mcr.microsoft.com/dotnet/*:x, eclipse-temurin/openjdk:x
Status per declaration: eol (EOL date before as-of), eol-soon (within --warn-days),
supported, unknown (cycle not in the table - check https://endoflife.date). A version
range with only a lower bound (">=16") is marked floor=true: the project allows but
may not require the EOL version.

THE TABLE AGES. references/eol-dates.json carries an "as_of" date; the output repeats it
and sets stale_table=true when it is older than --stale-table-days relative to the run
date. Refresh it from endoflife.date and vendor lifecycle pages at least quarterly.
"""
import argparse
import glob
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
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

EXTRA_SKIP = ("vendor",)  # vendored third-party code, on top of repo_walk.SKIP_DIRS


def parse_day(s):
    return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc) if s else None


def read(p):
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def line_of(text, needle_re):
    for n, line in enumerate(text.splitlines(), 1):
        if re.search(needle_re, line):
            return n, line.strip()
    return None, None


def nums(v):
    return [int(x) for x in re.findall(r"\d+", str(v))]


def cycle_for(product, version):
    key = product.get("cycle_key", "major")
    n = nums(version)
    if key == "any":
        return "*"
    if key == "tfm":
        return str(version).strip().lower()
    if not n:
        return None
    if key == "major.minor":
        return "%d.%d" % (n[0], n[1] if len(n) > 1 else 0)
    return str(n[0])


def walk(root):
    # Manifest names vary (.nvmrc, Pipfile, *.fsproj, build.gradle.kts), so every file is offered.
    for full in repo_walk.iter_files(root, globs=["*"], extra_skip=EXTRA_SKIP):
        yield full, os.path.basename(full)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--table", default=os.path.join(HERE, "..", "references", "eol-dates.json"))
    ap.add_argument("--as-of")
    ap.add_argument("--warn-days", type=int, default=180)
    ap.add_argument("--stale-table-days", type=int, default=180)
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args()
    with open(a.table, "r", encoding="utf-8") as fh:
        table = json.load(fh)
    products = table["products"]
    lower = {k.lower(): k for k in products}
    as_of = parse_day(a.as_of) if a.as_of else datetime.now(timezone.utc)
    root = os.path.abspath(a.root)
    decls = []  # (product_id, version, file, line, evidence, floor)

    def add(pid, version, full, line_re, floor=False):
        text = read(full)
        n, ev = line_of(text, line_re)
        decls.append((pid, str(version), os.path.relpath(full, root).replace(os.sep, "/"), n, ev, floor))

    def pkg(name, version, full, floor=False):
        pid = lower.get(name.lower())
        if pid is None:
            for k, p in products.items():
                if p.get("prefix") and name.lower().startswith(k.lower()):
                    pid = k
                    break
        if pid:
            add(pid, version, full, re.escape(name), floor)

    for full, fn in walk(root):
        low = fn.lower()
        ext = os.path.splitext(low)[1]
        text = None
        if ext in (".csproj", ".fsproj", ".vbproj") or low in ("directory.build.props", "directory.packages.props"):
            text = read(full)
            for m in re.finditer(r"<TargetFrameworks?>([^<]+)</TargetFrameworks?>", text):
                for tfm in m.group(1).split(";"):
                    tfm = tfm.strip().lower()
                    if not tfm or tfm.startswith("$("):
                        continue
                    if re.match(r"^net4\d+", tfm):
                        add("dotnet-framework", tfm, full, re.escape(tfm))
                    elif tfm.startswith(("net", "netcoreapp")) and not tfm.startswith("netstandard"):
                        add("dotnet", re.sub(r"-.*$", "", tfm), full, re.escape(tfm))
            for m in re.finditer(r"<Package(?:Reference|Version)\s+Include=\"([^\"]+)\"\s+Version=\"([^\"]+)\"", text):
                pkg(m.group(1), m.group(2), full)
        elif low == "global.json":
            m = re.search(r'"version"\s*:\s*"(\d+)\.(\d+)', read(full))
            if m:
                add("dotnet", "net%s.0" % m.group(1) if int(m.group(1)) >= 5 else "netcoreapp%s.%s" % (m.group(1), m.group(2)),
                    full, r'"version"')
        elif low == "package.json" and "node_modules" not in full:
            try:
                doc = json.loads(read(full))
            except ValueError:
                continue
            eng = (doc.get("engines") or {}).get("node")
            if eng:
                add("nodejs", eng, full, r'"node"\s*:', floor=bool(re.match(r"^\s*>", eng)))
            deps = dict(doc.get("devDependencies") or {}, **(doc.get("dependencies") or {}))
            for name, ver in deps.items():
                if not re.search(r"\d", str(ver)):
                    continue
                mapped = {"@angular/core": "angular", "angular": "angularjs", "vue": "vue", "react": "react",
                          "nuxt": "nuxt", "express": "express"}.get(name)
                if mapped:
                    add(mapped, ver, full, '"%s"' % re.escape(name))
                else:
                    pkg(name, ver, full)
        elif low in (".nvmrc", ".node-version"):
            add("nodejs", read(full).strip(), full, r"\d")
        elif low in (".python-version", "runtime.txt"):
            add("python", read(full).strip().replace("python-", ""), full, r"\d")
        elif low in ("setup.py", "setup.cfg", "pyproject.toml", "pipfile") or (low.startswith("requirements") and ext == ".txt"):
            text = read(full)
            m = re.search(r"(?:python_requires|requires-python|python_version)\s*=\s*['\"]?([^'\"\n]+)", text)
            if m:
                add("python", m.group(1), full, r"python_requires|requires-python|python_version",
                    floor=bool(re.match(r"^\s*>", m.group(1))))
            for m in re.finditer(r"(?im)^\s*['\"]?(django|[\w.-]+)\s*(?:\[[^\]]*\])?\s*(==|~=|>=|<=|=)\s*['\"]?([\d.]+)", text):
                name = m.group(1)
                if name.lower() == "django":
                    add("django", m.group(3), full, r"(?i)^\s*['\"]?django\b", floor=m.group(2) == ">=")
                elif name.lower() not in ("python", "python_requires", "requires-python", "python_version"):
                    pkg(name, m.group(3), full)
        elif low == "pom.xml":
            text = read(full)
            m = re.search(r"<(?:java\.version|maven\.compiler\.release|maven\.compiler\.source|release)>\s*(?:1\.)?(\d+)", text)
            if m:
                add("java", m.group(1), full, r"java\.version|maven\.compiler|<release>")
            m = re.search(r"<parent>[\s\S]*?spring-boot-starter-parent[\s\S]*?<version>([\d.]+)", text)
            if m:
                add("spring-boot", m.group(1), full, r"spring-boot-starter-parent")
            m = re.search(r"<groupId>log4j</groupId>\s*<artifactId>log4j</artifactId>\s*<version>([\d.]+)", text)
            if m:
                add("log4j", m.group(1), full, r"<groupId>log4j</groupId>")
        elif low in ("build.gradle", "build.gradle.kts"):
            text = read(full)
            m = re.search(r"(?:sourceCompatibility\s*=\s*['\"]?(?:JavaVersion\.VERSION_)?(?:1[._])?|JavaLanguageVersion\.of\()(\d+)", text)
            if m:
                add("java", m.group(1), full, r"sourceCompatibility|JavaLanguageVersion")
            m = re.search(r"org\.springframework\.boot['\"]?\)?\s*version\s*['\"]([\d.]+)", text)
            if m:
                add("spring-boot", m.group(1), full, r"org\.springframework\.boot")
        elif low == "dockerfile" or low.startswith("dockerfile.") or low.endswith(".dockerfile"):
            text = read(full)
            for m in re.finditer(r"(?im)^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)", text):
                img = m.group(1).lower()
                tag = img.split(":", 1)[1] if ":" in img else ""
                if not re.match(r"\d", tag):
                    continue
                if re.search(r"(^|/)node$", img.split(":")[0]):
                    add("nodejs", tag, full, re.escape(m.group(1)))
                elif re.search(r"(^|/)python$", img.split(":")[0]):
                    add("python", tag, full, re.escape(m.group(1)))
                elif "mcr.microsoft.com/dotnet/" in img:
                    v = nums(tag)
                    if v:
                        add("dotnet", "net%d.0" % v[0] if v[0] >= 5 else "netcoreapp%d.%d" % (v[0], v[1] if len(v) > 1 else 0),
                            full, re.escape(m.group(1)))
                elif re.search(r"(eclipse-temurin|openjdk|amazoncorretto|maven)", img):
                    v = nums(tag)
                    if v:
                        add("java", str(v[0]), full, re.escape(m.group(1)))

    items = []
    seen = set()
    for pid, version, rel, line, ev, floor in decls:
        p = products[pid]
        cyc = cycle_for(p, version)
        key = (pid, cyc, rel)
        if key in seen:
            continue
        seen.add(key)
        cycles = p.get("cycles", {})
        eol_s = cycles.get(cyc) if cyc in cycles else (cycles.get("*") if "*" in cycles else None)
        known = cyc in cycles or "*" in cycles
        eol = parse_day(eol_s) if eol_s else None
        if not known:
            status = "unknown"
        elif eol is None:
            status = "supported"
        elif eol < as_of:
            status = "eol"
        elif (eol - as_of).days <= a.warn_days:
            status = "eol-soon"
        else:
            status = "supported"
        items.append({"product": pid, "label": p.get("label", pid), "kind": p.get("kind", "package"),
                      "declared": version, "cycle": cyc, "eol": eol_s, "status": status, "floor": floor,
                      "days_past_eol": (as_of - eol).days if eol and eol < as_of else None,
                      "days_to_eol": (eol - as_of).days if eol and eol >= as_of else None,
                      "security_sensitive": bool(p.get("security_sensitive")), "successor": p.get("successor"),
                      "source": p.get("source"), "file": rel, "line": line, "evidence": ev})
    order = {"eol": 0, "eol-soon": 1, "unknown": 2, "supported": 3}
    items.sort(key=lambda i: (order[i["status"]], -(i["days_past_eol"] or 0)))
    table_as_of = parse_day(table.get("as_of"))
    run_date = datetime.now(timezone.utc)
    table_age = (run_date - table_as_of).days if table_as_of else None
    result = {"root": root, "as_of": as_of.strftime("%Y-%m-%d"), "table_as_of": table.get("as_of"),
              "table_age_days": table_age, "stale_table": bool(table_age is not None and table_age > a.stale_table_days),
              "table_note": table.get("refresh"),
              "summary": {s: sum(1 for i in items if i["status"] == s) for s in order},
              "items": items}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("EOL table as of %s%s\n\n" % (table.get("as_of"), " (STALE - refresh before trusting)" if result["stale_table"] else ""))
            fh.write("| Product | Declared | Cycle | EOL | Status | Location | Successor |\n|---|---|---|---|---|---|---|\n")
            for i in items:
                fh.write("| %s | %s | %s | %s | %s%s | `%s:%s` | %s |\n" % (i["label"], i["declared"], i["cycle"], i["eol"] or "-",
                                                                         i["status"], " (floor)" if i["floor"] else "",
                                                                         i["file"], i["line"], i["successor"] or ""))
    print(json.dumps({"table_as_of": table.get("as_of"), "stale_table": result["stale_table"], "summary": result["summary"],
                      "eol": ["%s %s (%s) at %s:%s" % (i["label"], i["declared"], i["eol"], i["file"], i["line"])
                              for i in items if i["status"] in ("eol", "eol-soon")]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
