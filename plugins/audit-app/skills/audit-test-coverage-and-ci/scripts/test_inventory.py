#!/usr/bin/env python3
"""Inventory a repository's tests and map them onto the production units that
matter, so the audit can answer "is the payment path tested?" instead of
quoting a global coverage percentage.

Usage:
    python test_inventory.py <repo_root> [--out tests.json] [--md tests.md]
                             [--critical-only] [--max-units 400]

What it reports:
  * test projects (manifests with test-framework markers) and test files, per
    stack, classified as unit | integration | e2e, real-db | in-memory | none,
    and quality ok | stub (only "should create"/toBeTruthy) | snapshot-only
  * skipped / ignored / focused tests with the test name and the reason string
    where one exists ([Fact(Skip=)], [Theory(Skip=)], [Ignore], [Explicit],
    Assert.Inconclusive, @Disabled, @Ignore, @Test(enabled=false), it.skip,
    test.skip, describe.skip, xit, xdescribe, .only, pending(),
    @pytest.mark.skip/skipif, @unittest.skip, self.skipTest); when no reason
    is given in the attribute, the adjacent comment is used
  * production units (controllers, services, managers, handlers, jobs, views,
    guards, interceptors, stores) with a critical-path category
    (auth | payment | tenant | data-mutation | other) and the test files that
    mention them by name -> untested critical units
  * a coverage map per category: covered (every unit tested and at least one
    integration/e2e test) | partial | none
  * coverage tooling and thresholds found in the repo

Every row is a *candidate*. A unit reported as untested may simply be tested
under a different name; open the nearest test file before writing a finding.
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

# Vendored third-party code is not this repository's tests; skipped on top of the shared walker defaults.
VENDOR_DIRS = ("vendor",)

CODE_EXT = {".cs", ".java", ".kt", ".js", ".jsx", ".ts", ".tsx", ".vue", ".py"}
MAX_BYTES = repo_walk.MAX_BYTES

# --- test file recognition -------------------------------------------------
TEST_FILE_RE = [
    re.compile(r"(^|/)tests?/", re.I),
    re.compile(r"(^|/)__tests__/"),
    re.compile(r"(^|/)spec/", re.I),
    re.compile(r"(^|/)e2e/", re.I),
    re.compile(r"(^|/)cypress/", re.I),
    re.compile(r"(^|/)[^/]*\.Tests?(\.[A-Za-z]+)*/"),
    re.compile(r"[._-](test|tests|spec|specs|cy|e2e)\.[a-z]+$", re.I),
    re.compile(r"(Test|Tests|Spec|Specs|IT)\.(cs|java|kt)$"),
    re.compile(r"(^|/)test_[^/]+\.py$"),
    re.compile(r"[^/]+_test\.py$"),
    re.compile(r"(^|/)tests\.py$"),
]

TEST_PROJECT_MARKERS = ["xunit", "nunit", "mstest.testframework", "microsoft.net.test.sdk",
                        "<istestproject>true</istestproject>", "junit", "spock", "testng",
                        "jest", "vitest", "mocha", "karma", "jasmine", "cypress", "playwright",
                        "pytest", "unittest"]

E2E_MARKERS = ["cypress", "playwright", "selenium", "webdriver", "protractor", "puppeteer",
               "specflow", "reqnroll", "cucumber", "detox"]
INTEGRATION_MARKERS = ["webapplicationfactory", "testcontainers", "@springboottest",
                       "@datajpatest", "testresttemplate", "mockmvc", "supertest",
                       "liveservertestcase", "respawn", "integrationtest", "request(app",
                       "apiclient(", "testclient("]
REAL_DB_MARKERS = ["testcontainers", "mssqlbuilder", "postgresqlbuilder", "mysqlbuilder",
                   "respawn", "pytest.mark.django_db", "@autoconfiguretestdatabase(replace = none",
                   "@autoconfiguretestdatabase(replace=none", "docker-compose"]
IN_MEMORY_MARKERS = ["useinmemorydatabase", "datasource=:memory:", "sqlite::memory:",
                     "h2:mem:", "mongodb-memory-server", "':memory:'", "\":memory:\"", "mock-knex"]

# --- skipped test detection ------------------------------------------------
# (label, regex, group-1 meaning: "reason" | "title" | None)
SKIP_PATTERNS = [
    ("Fact/Theory(Skip)", re.compile(r"\[\s*(?:Fact|Theory)\s*\([^\]]*Skip\s*=\s*\"([^\"]*)\""), "reason"),
    ("[Ignore]", re.compile(r"\[\s*(?:[\w,\s]*,\s*)?Ignore\s*(?:\(\s*\"([^\"]*)\"\s*\))?\s*[\],]"), "reason"),
    ("[Explicit]", re.compile(r"\[\s*Explicit\s*(?:\(\s*\"([^\"]*)\"\s*\))?\s*\]"), "reason"),
    ("Assert.Inconclusive", re.compile(r"Assert\.Inconclusive\s*\(\s*\"?([^\")]*)"), "reason"),
    ("@Disabled", re.compile(r"@Disabled\b(?!On|If)\s*(?:\(\s*\"([^\"]*)\"\s*\))?"), "reason"),
    ("@Ignore", re.compile(r"@Ignore\b\s*(?:\(\s*\"([^\"]*)\"\s*\))?"), "reason"),
    ("@Test(enabled=false)", re.compile(r"@Test\s*\([^)]*enabled\s*=\s*false"), None),
    ("it.skip/test.skip/describe.skip", re.compile(r"\b(?:it|test|describe|context|suite)\.skip\s*\(\s*[`'\"]([^`'\"]*)"), "title"),
    ("xit/xtest/xdescribe", re.compile(r"(?<![\w.])(?:xit|xdescribe|xtest|xcontext)\s*\(\s*[`'\"]([^`'\"]*)"), "title"),
    ("focused .only/fit/fdescribe", re.compile(r"(?:\b(?:it|test|describe|context)\.only|(?<![\w.])(?:fit|fdescribe))\s*\(\s*[`'\"]([^`'\"]*)"), "title"),
    ("it.todo/test.fixme", re.compile(r"\b(?:it|test)\.(?:todo|fixme)\s*\(\s*[`'\"]([^`'\"]*)"), "title"),
    ("pending()", re.compile(r"(?<![\w.])pending\s*\(\s*[`'\"]([^`'\"]*)"), "reason"),
    ("@pytest.mark.skip", re.compile(r"@pytest\.mark\.(?:skip|skipif)\b(?:\(\s*(?:reason\s*=\s*)?[\"']([^\"']*))?"), "reason"),
    ("@pytest.mark.xfail", re.compile(r"@pytest\.mark\.xfail\b"), None),
    ("@unittest.skip", re.compile(r"@(?:unittest\.)?skip(?:If|Unless)?\s*\(\s*(?:[^,\"')]*,\s*)?[\"']([^\"']*)"), "reason"),
    ("self.skipTest", re.compile(r"self\.skipTest\s*\(\s*[\"']([^\"']*)"), "reason"),
    ("this.skip()", re.compile(r"\bthis\.skip\s*\(\s*\)"), None),
]
DECL_RE = re.compile(r"(?:\bdef|\bfun|\bvoid|\bTask(?:<[^>]*>)?|\bfunction|\bIActionResult)\s+([A-Za-z_]\w*)\s*\(")
TEST_COUNT_RE = re.compile(r"\[\s*(?:Fact|Theory|Test|TestMethod|TestCase)\b|@Test\b|@ParameterizedTest\b|"
                           r"(?<![\w.])(?:it|test|fit|xit)\s*\(|\b(?:it|test)\.(?:skip|only)\s*\(|\bdef\s+test_")

# --- production unit recognition ------------------------------------------
UNIT_SUFFIX = (r"(?:Controller|Service|Manager|Handler|Repository|Job|Worker|Processor|UseCase|Gateway|"
               r"ViewSet|APIView|Guard|Interceptor|Store|Resolver|Consumer|Endpoints)")
UNIT_DECL = [
    re.compile(r"\bclass\s+([A-Z][A-Za-z0-9_]*" + UNIT_SUFFIX + r")\b"),
    re.compile(r"\bexport\s+const\s+([a-zA-Z][A-Za-z0-9_]*" + UNIT_SUFFIX + r")\s*[:=]"),
    re.compile(r"\bexport\s+(?:async\s+)?function\s+(use[A-Z]\w*(?:Auth|Payment|Checkout|Order|Cart)\w*)\s*\("),
]

CATEGORY_KEYWORDS = [
    ("auth", ["auth", "login", "logon", "logout", "token", "jwt", "password", "credential", "session",
              "identity", "permission", "role", "claim", "signin", "signup", "sso", "mfa", "otp", "account"]),
    ("payment", ["payment", "pay", "invoice", "billing", "charge", "refund", "checkout",
                 "price", "pricing", "discount", "tax", "vat", "money", "wallet", "ledger",
                 "subscription", "voucher", "transaction", "fbr", "zatca"]),
    ("tenant", ["tenant", "compan", "organisation", "organization", "workspace", "branch"]),
    ("data-mutation", ["create", "update", "delete", "import", "export", "bulk", "sync",
                       "order", "stock", "inventory", "product", "purchase", "sale",
                       "manufactur", "repository", "job", "worker", "migrat"]),
]
GENERIC_TOKENS = {"src", "app", "api", "services", "service", "controllers", "controller", "cs", "ts", "js",
                  "py", "java", "kt", "main", "lib", "core", "features", "managers", "manager"}

COVERAGE_MARKERS = {
    "coverlet": ["coverlet.collector", "coverlet.msbuild", "XPlat Code Coverage"],
    "reportgenerator": ["ReportGenerator", "reportgenerator"],
    "jacoco": ["jacoco"],
    "jest-coverage": ["collectCoverage", "coverageThreshold", "--coverage"],
    "karma-coverage": ["karma-coverage", "coverageReporter"],
    "vitest-coverage": ["@vitest/coverage"],
    "pytest-cov": ["pytest-cov", "--cov"],
    "coverage.py": ["[tool.coverage", ".coveragerc", "fail_under"],
    "sonar": ["sonar-project.properties", "SonarSource", "sonarqube", "sonarcloud"],
    "codecov": ["codecov"],
}
THRESHOLD_RE = re.compile(r"(fail_under|fail-below|coverageThreshold|Threshold\s*=|"
                          r"minimum[_-]?coverage|statements[\"']?\s*:\s*\d+|"
                          r"LINE.*COVEREDRATIO|threshold)\s*[:=]?\s*([0-9]{1,3})?", re.I)


def iter_files(root):
    # globs=("*",): manifests such as setup.cfg, .coveragerc and *.runsettings are matched by name.
    return repo_walk.iter_files(root, globs=("*",), extra_skip=VENDOR_DIRS)


def read(path):
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return None


def is_test_path(rel):
    return any(rx.search(rel) for rx in TEST_FILE_RE)


def classify_test(rel, text):
    low = (rel + "\n" + text).lower()
    kind = "unit"
    if any(m in low for m in E2E_MARKERS) or "/e2e/" in rel.lower():
        kind = "e2e"
    elif any(m in low for m in INTEGRATION_MARKERS) or "integration" in rel.lower():
        kind = "integration"
    db = "none"
    if any(m in low for m in IN_MEMORY_MARKERS):
        db = "in-memory"
    if any(m in low for m in REAL_DB_MARKERS):
        db = "real-db" if db == "none" else "mixed"
    assertions = re.findall(r"\bexpect\s*\([^)]*\)\s*\.\s*(\w+)|\bAssert\.\w+|\bassert\w*\b|\bShould\w*\(", text)
    named = [a for a in assertions if a]
    quality = "ok"
    if named and all(a in ("toBeTruthy", "toBeDefined") for a in named) and \
            len(TEST_COUNT_RE.findall(text)) <= 1 and not re.search(r"\bAssert\.|\bassert\b", text):
        quality = "stub"
    elif named and all(a in ("toMatchSnapshot", "toMatchInlineSnapshot") for a in named):
        quality = "snapshot-only"
    return kind, db, quality


def tokens(s):
    parts = re.split(r"[^A-Za-z0-9]+", s)
    out = []
    for p in parts:
        out += [t.lower() for t in re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+", p)]
    return [t for t in out if t and t not in GENERIC_TOKENS]


def categorize(name, rel):
    # the unit name wins; the path only breaks ties when the name says nothing
    for source in (tokens(name), tokens(rel)):
        for cat, words in CATEGORY_KEYWORDS:
            if any(t == w or t.startswith(w) for t in source for w in words):
                return cat
    return "other"


def decl_name(lines, n):
    for look in lines[n - 1:n + 6]:
        m = DECL_RE.search(look)
        if m:
            return m.group(1)
    return ""


def nearby_comment(lines, n):
    line = lines[n - 1]
    m = re.search(r"(?://|#)\s*(.+)$", line)
    if m and not re.search(r"['\"][^'\"]*(//|#)", line[:m.start() + 2]):
        return m.group(1).strip()
    for k in (n - 2, n - 3):
        if k >= 0:
            prev = lines[k].strip()
            if prev.startswith(("//", "#")):
                return prev.lstrip("/#").strip()
            if prev and not prev.startswith(("[", "@")):
                break
    return ""


def find_skips(rel, lines):
    out = []
    for n, line in enumerate(lines, 1):
        for label, rx, meaning in SKIP_PATTERNS:
            m = rx.search(line)
            if not m:
                continue
            captured = (m.group(1) or "").strip() if rx.groups else ""
            if meaning == "title":
                name, reason = captured, ""
            else:
                name, reason = decl_name(lines, n), captured
            if label.startswith("@pytest") or label.startswith("@unittest"):
                rm = re.search(r"reason\s*=\s*[\"']([^\"']*)", line)
                if rm:
                    reason = rm.group(1)
            if not reason:
                reason = nearby_comment(lines, n)
            out.append({"file": rel, "line": n, "kind": label, "test": name or "?",
                        "reason": reason or "(none given)", "snippet": line.strip()[:200]})
            break
    return out


def scan(root, max_units):
    test_files, prod_units, skipped = [], [], []
    coverage, test_project_files, test_texts = {}, [], {}

    for path in iter_files(root):
        rel = repo_walk.rel(root, path)
        ext = os.path.splitext(path)[1].lower()
        base = os.path.basename(path).lower()

        if ext in (".csproj", ".fsproj", ".vbproj") or base in ("pom.xml", "build.gradle", "build.gradle.kts",
                                                                "package.json", "pyproject.toml", "setup.cfg",
                                                                "tox.ini", "pytest.ini", "requirements-dev.txt",
                                                                "karma.conf.js", "jest.config.js", "jest.config.ts",
                                                                "vitest.config.ts", "playwright.config.ts",
                                                                "cypress.config.ts"):
            text = read(path) or ""
            low = text.lower()
            found = sorted({m for m in TEST_PROJECT_MARKERS if m in low})
            if found:
                test_project_files.append({"file": rel, "markers": found})
            for tool, markers in COVERAGE_MARKERS.items():
                if any(m.lower() in low for m in markers):
                    coverage.setdefault(tool, []).append(rel)

        if base in ("codecov.yml", "codecov.yaml", "sonar-project.properties", ".coveragerc") or base.endswith(".runsettings"):
            coverage.setdefault(base, []).append(rel)

        if ext not in CODE_EXT:
            continue
        text = read(path)
        if text is None:
            continue
        lines = text.splitlines()

        if is_test_path(rel):
            kind, db, quality = classify_test(rel, text)
            file_skips = find_skips(rel, lines)
            test_files.append({"file": rel, "kind": kind, "database": db, "quality": quality,
                               "tests": len(TEST_COUNT_RE.findall(text)), "skipped": len(file_skips)})
            skipped += file_skips
            test_texts[rel] = text
        else:
            names = set()
            for rx in UNIT_DECL:
                names.update(rx.findall(text))
            if not names:
                stem = os.path.splitext(os.path.basename(path))[0]
                if re.search(r"(Controller|Service|Manager|Handler|Repository|Job|Worker)$", stem):
                    names.add(stem)
            for name in names:
                line = next((i for i, ln in enumerate(lines, 1) if re.search(r"\b%s\b" % re.escape(name), ln)), 1)
                prod_units.append({"unit": name, "file": rel, "line": line, "category": categorize(name, rel)})

    kinds_by_file = {t["file"]: t for t in test_files}
    seen, units = set(), []
    for u in prod_units:
        key = (u["unit"], u["file"])
        if key in seen:
            continue
        seen.add(key)
        refs = [f for f, t in test_texts.items() if re.search(r"\b%s\b" % re.escape(u["unit"]), t)]
        u = dict(u)
        u["test_files"] = refs
        u["tested"] = bool(refs)
        u["kinds"] = sorted({kinds_by_file[f]["kind"] for f in refs})
        u["skipped_tests_in_referencing_files"] = sum(kinds_by_file[f]["skipped"] for f in refs)
        units.append(u)
    units.sort(key=lambda x: (x["tested"], x["category"] == "other", x["category"], x["unit"]))
    units = units[:max_units]

    thresholds = []
    for tool, files in coverage.items():
        for f in sorted(set(files)):
            for m in THRESHOLD_RE.finditer(read(os.path.join(root, f)) or ""):
                if m.group(2):
                    thresholds.append({"file": f, "tool": tool, "value": m.group(2)})
    return {
        "root": os.path.abspath(root),
        "test_projects": test_project_files,
        "test_files": sorted(test_files, key=lambda x: x["file"]),
        "skipped_tests": skipped,
        "units": units,
        "coverage_tooling": {k: sorted(set(v)) for k, v in coverage.items()},
        "coverage_thresholds": thresholds,
    }


def summarize(data, critical_only):
    cats = {}
    for u in data["units"]:
        if critical_only and u["category"] == "other":
            continue
        c = cats.setdefault(u["category"], {"units": [], "tested": [], "untested": [], "kinds": set(), "skipped": 0})
        c["units"].append(u["unit"])
        (c["tested"] if u["tested"] else c["untested"]).append(u["unit"])
        c["kinds"].update(u["kinds"])
        c["skipped"] += u["skipped_tests_in_referencing_files"]
    for c in cats.values():
        if not c["tested"]:
            c["status"] = "none"
        elif not c["untested"] and (c["kinds"] & {"integration", "e2e"}) and c["skipped"] == 0:
            c["status"] = "covered"
        else:
            c["status"] = "partial"
        c["kinds"] = sorted(c["kinds"])
    return {
        "test_projects": len(data["test_projects"]),
        "test_files": len(data["test_files"]),
        "tests_counted": sum(t["tests"] for t in data["test_files"]),
        "kinds": {k: sum(1 for t in data["test_files"] if t["kind"] == k) for k in ("unit", "integration", "e2e")},
        "real_db_tests": sum(1 for t in data["test_files"] if t["database"] in ("real-db", "mixed")),
        "in_memory_db_tests": sum(1 for t in data["test_files"] if t["database"] == "in-memory"),
        "stub_or_snapshot_only_files": [t["file"] for t in data["test_files"] if t["quality"] != "ok"],
        "skipped_tests": len(data["skipped_tests"]),
        "coverage_tooling": sorted(data["coverage_tooling"].keys()),
        "coverage_map": cats,
    }


def write_md(data, summary, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Test inventory\n\n## Coverage map by critical path\n\n")
        fh.write("| Critical path | Units | Units with tests | Test kinds | Skipped tests nearby | Status | Untested units |\n"
                 "|---|---|---|---|---|---|---|\n")
        for cat, c in sorted(summary["coverage_map"].items()):
            fh.write(f"| {cat} | {len(c['units'])} | {len(c['tested'])} | {', '.join(c['kinds']) or '-'} | "
                     f"{c['skipped']} | {c['status']} | {', '.join(c['untested'][:12]) or '-'} |\n")
        fh.write("\nStatus: covered = every unit referenced by a test, integration/e2e present, nothing skipped; "
                 "partial = some tests; none = no test references any unit.\n")
        fh.write("\n## Test projects\n\n")
        for p in data["test_projects"]:
            fh.write(f"- `{p['file']}` ({', '.join(p['markers'])})\n")
        if not data["test_projects"]:
            fh.write("- _none found_\n")
        fh.write("\n## Test files\n\n| File | Kind | Database | Quality | Tests | Skipped |\n|---|---|---|---|---|---|\n")
        for t in data["test_files"]:
            fh.write(f"| `{t['file']}` | {t['kind']} | {t['database']} | {t['quality']} | {t['tests']} | {t['skipped']} |\n")
        if not data["test_files"]:
            fh.write("| _none found_ | - | - | - | 0 | 0 |\n")
        fh.write("\n## Skipped / ignored / focused tests\n\n| Test | Location | Kind | Reason |\n|---|---|---|---|\n")
        for s in data["skipped_tests"]:
            fh.write(f"| {s['test']} | `{s['file']}:{s['line']}` | {s['kind']} | {s['reason'].replace('|', '/')} |\n")
        if not data["skipped_tests"]:
            fh.write("| _none_ | - | - | - |\n")
        fh.write("\n## Units and their tests\n\n| Unit | Path | Category | Test files |\n|---|---|---|---|\n")
        for u in data["units"]:
            fh.write(f"| {u['unit']} | `{u['file']}:{u['line']}` | {u['category']} | "
                     f"{', '.join('`%s`' % f for f in u['test_files']) or '**none**'} |\n")
        fh.write("\n## Coverage tooling\n\n" + (", ".join(summary["coverage_tooling"]) or "none found") + "\n")
        for t in data["coverage_thresholds"]:
            fh.write(f"- threshold {t['value']} in `{t['file']}` ({t['tool']})\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out")
    ap.add_argument("--md")
    ap.add_argument("--critical-only", action="store_true", help="omit category 'other' from the coverage map")
    ap.add_argument("--max-units", type=int, default=400)
    args = ap.parse_args()

    data = scan(args.root, args.max_units)
    summary = summarize(data, args.critical_only)
    data["summary"] = summary
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    if args.md:
        write_md(data, summary, args.md)
    brief = dict(summary)
    brief["coverage_map"] = {k: {"status": v["status"], "untested": v["untested"], "tested": v["tested"]}
                             for k, v in summary["coverage_map"].items()}
    brief["skipped"] = [f"{s['file']}:{s['line']} {s['kind']} {s['test']} - {s['reason']}" for s in data["skipped_tests"]]
    print(json.dumps(brief, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
