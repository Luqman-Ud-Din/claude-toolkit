---
name: audit-dependency-vulnerabilities
description: Runs the vulnerability audit for every package ecosystem in a repo (dotnet list package --vulnerable, npm/pnpm/yarn audit, pip-audit, OWASP dependency-check for Maven/Gradle, trivy/grype for container images), de-duplicates the results into one table (name, current, fixed-in, severity, direct/transitive, breaking?), works out the upgrade path and exact upgrade commands, and flags abandoned packages with no release in 2+ years. Use whenever the user asks about vulnerable dependencies, CVEs, advisories, outdated or abandoned packages, package or dependency audit, supply-chain risk, SBOM, npm audit, NuGet or Maven vulnerabilities, "are our packages safe", or as part of any security, pre-production, or readiness audit - even when the user does not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: dependency vulnerabilities

Finds known-vulnerable and abandoned third-party packages across every ecosystem
in the audited repo and turns the raw scanner output into one de-duplicated table,
standard findings, and copy-paste upgrade commands. Most breaches that start in
code start in someone else's code, so this skill runs early in every audit.

Read-only rule: never modify the audited code, manifests, or lockfiles. Never run
`npm install`, `dotnet restore` with changes, or any command that rewrites a
lockfile. Write only under `audit/`.

## Inputs and prerequisites

- Repo root (default `.`). Standalone runs read `audit/stack.json` if present,
  otherwise `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` computes it (run
  without `--write`, so a standalone run leaves no `audit/stack.json` behind).
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack), `audit-code-scan` (grep pass and the shared file walker `dep_audit.py` imports), `audit-finding-writer` (findings.json).
- Scanner CLIs are optional. `scripts/dep_audit.py` detects which are installed
  and records the rest as *not checked*; it never fails the run because a tool is
  missing. Exact commands and install hints: `references/audit-commands.md`.
- Network is optional. Registry metadata (npm, PyPI, NuGet, Maven Central) is
  used for the abandoned-package check; pass `--no-network` in air-gapped runs
  and that column becomes `not-checked`.
- Restored dependencies help: `dotnet list package --vulnerable` needs a prior
  restore (`obj/project.assets.json`); `npm audit` needs a lockfile. Do not
  create either yourself - report the gap.

## Workflow

1. **Resolve the stack.** Run `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`. Open only
   the matching `references/<stack>.md` files (one per detected backend and
   frontend). They hold the manifest locations, the audit command, output quirks,
   upgrade idioms, and the false positives specific to that ecosystem. If nothing
   matches, follow `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md` and say so in `scope.not_checked`.
2. **Automated pass.**
   - `python scripts/dep_audit.py <repo> --out audit/evidence/audit-dependency-vulnerabilities/dep-audit.json --md audit/evidence/audit-dependency-vulnerabilities/dep-audit.md`
     detects manifests, runs every applicable scanner, normalises everything into
     one row shape, de-duplicates (same ecosystem + package + version), computes
     direct/transitive and breaking-jump, queries registries for last-release
     dates, and prints the upgrade commands. Read `tools` and `not_checked` in the
     JSON before trusting the table: an ecosystem with no scanner installed has
     zero rows *because it was not scanned*, not because it is clean.
   - `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-dependency-vulnerabilities/hits.json`
     is the manifest-level fallback: it matches version strings of widely known
     vulnerable releases and unsafe version specifiers (`*`, `latest`, git URLs,
     unpinned Python requirements). It works with no tools and no network, and it
     is the only signal when the scanner could not run. Every grep hit is a
     candidate: confirm the version is actually resolved (lockfile / assets file)
     before rating it.
   - Container images: when a `Dockerfile` or compose file exists, `dep_audit.py`
     runs `trivy` (or `grype`) against the base images it finds in `FROM` /
     `image:` lines. Images that cannot be pulled are listed as not checked.
3. **Manual trace of the highest-risk items.** In priority order:
   - Critical/High rows that are *direct* dependencies of an internet-facing
     service (gateway, auth, upload/parsing code paths). Open the code that uses
     the package and decide whether the vulnerable API is reachable with
     attacker-controlled input; write that in Impact.
   - Transitive rows whose fix requires a major bump of the direct parent: name
     the parent and the override mechanism (`overrides`/`resolutions`,
     `Directory.Packages.props`, `<dependencyManagement>`, constraints file).
   - Abandoned packages that sit in the request path (auth, crypto, parsing).
   - Pinning hygiene: missing lockfile, floating versions, git/tarball sources.
   - Whether any scanner runs in CI at all (grep pipelines for `npm audit`,
     `dotnet list package --vulnerable`, `trivy`, `dependabot.yml`, `renovate.json`).
   Use the "Manual trace checklist" in the stack file.
4. **Write findings** with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` (init, then `add --from` per
   finding, then `validate`). One finding per root cause: group all advisories
   for one package@version into one finding; group "N packages with no
   scanner in CI" into one; group all abandoned packages into one Low unless one
   of them is in a security-sensitive path. Severity comes from the advisory
   (CVSS band) adjusted by reachability as in
   `audit-finding-writer/references/severity-rubric.md` -
   a High CVE in a dev-only test helper is Medium at most; say why.
5. **Emit outputs** (all relative to the audited repo):
   - `audit/findings/audit-dependency-vulnerabilities.json`
   - `audit/reports/audit-dependency-vulnerabilities.md` (template below)
   - `audit/evidence/audit-dependency-vulnerabilities/` - raw scanner JSON,
     `dep-audit.json`, `dep-audit.md`, `hits.json`
   - `audit/status/audit-dependency-vulnerabilities.json` -
     `{"skill": "...", "status": "completed|failed|skipped", "reason": "...", "started_at": "...", "finished_at": "..."}`
6. **Not checked.** Copy every entry from `dep_audit.json.not_checked` into
   `scope.not_checked` and add anything you skipped by hand: ecosystems with no
   scanner installed, images that could not be pulled, registries unreachable,
   private feeds you had no credentials for, reachability you did not trace.
   Also list the automated pass's coverage limits from `audit-code-scan`: folders on the shared skip list (`node_modules`, `bin`, `obj`, `dist`, `build`, `.git`, `audit`, ... - see `$AUDIT_CORE_ROOT/skills/audit-code-scan/references/repo-walk-api.md`) and files over 2 MB are not read, and patterns match one line at a time. `dep_audit.py` discovers manifests with the
   same walker: manifests under `node_modules`, `bin`, `obj`, `dist`, `build`, `target`
   or `.gradle` and manifests over 2 MB are not audited. `packages/` IS read, so
   JavaScript workspace packages are audited; a legacy NuGet `packages/` restore folder
   is read too, and any manifest found inside it is vendored content, not a project.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `DEP`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Location:** `path/to/manifest:LINE` (package@version)
- **Evidence:**

```text
<scanner row, advisory id and URL, or the manifest line>
```

- **Impact:** Plain language. What the CVE lets an attacker do here, whether the vulnerable API is reachable, who is affected.
- **Remediation:** The exact upgrade command, the target version, and whether it is a breaking jump; the override mechanism for transitive cases.
- **Reference:** CVE-yyyy-nnnn, GHSA-xxxx, CWE-1395 (dependency on vulnerable component), OWASP-A06:2021


Same content goes to `findings.json` (`title`, `severity`, `confidence`,
`location`, `evidence`, `impact`, `remediation`, `references`); put advisory ids
in `references`, the package name in `tags`, and `root_cause_key` =
`<ecosystem>:<package>@<version>` so the report generator can merge duplicates
across skills.

## Output template (`audit/reports/audit-dependency-vulnerabilities.md`)

```markdown
## audit-dependency-vulnerabilities

**Target:** <repo> @ <commit> - **Run:** <date> - **Ecosystems:** dotnet, npm, pip, images

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| n | n | n | n | n |

### Scanners run

| Ecosystem | Manifests | Tool | Status |
|---|---|---|---|
| dotnet | 12 csproj | dotnet list package --vulnerable | ran |
| npm | package.json (root) | npm audit --json | ran |
| maven | pom.xml | dependency-check | not installed - not checked |
| images | Dockerfile (2 images) | trivy | ran |

### Vulnerable packages

| Package | Ecosystem | Current | Fixed in | Severity | Direct/Transitive | Breaking? | Advisories |
|---|---|---|---|---|---|---|---|
| lodash | npm | 4.17.15 | 4.17.21 | High | direct | no | CVE-2020-8203, CVE-2021-23337 |

### Abandoned packages (no release in 2+ years)

| Package | Ecosystem | Last release | Used by |
|---|---|---|---|

### Upgrade commands

```bash
npm install lodash@4.17.21
dotnet add Account.MicroAPI/Account.MicroAPI.csproj package Newtonsoft.Json --version 13.0.3
```

### Findings
<finding blocks, most severe first>

### Not checked
- <ecosystem/image/registry> - <reason>
```

## Examples

**Input (dep-audit row):**
`npm | lodash | 4.17.15 | fixed 4.17.21 | high | direct | GHSA-p6mc-m468-83gw`

**Output:**
```markdown
### [High] DEP-001 - lodash 4.17.15 has prototype-pollution advisories
- **Location:** `package.json:14` (lodash@4.17.15)
- **Confidence:** confirmed
- **Evidence:**

```text
npm audit: lodash <4.17.21 - Prototype Pollution (GHSA-p6mc-m468-83gw, CVE-2020-8203), ReDoS in toNumber (CVE-2021-23337); direct dependency
```

- **Impact:** `_.merge` / `_.set` are called on request bodies in `src/orders/orders.service.ts`, so a crafted JSON body can add properties to `Object.prototype` and change behaviour for every request in the process. Rated High: authenticated input, process-wide effect.
- **Remediation:** `npm install lodash@4.17.21` (same major, no breaking change); re-run `npm audit` to confirm no other path pulls the old version.
- **Reference:** CVE-2020-8203, CVE-2021-23337, CWE-1321, OWASP-A06:2021
```

**Input (dep-audit `not_checked`):**
`{"item": "maven (pom.xml)", "reason": "dependency-check not installed and no target/dependency-check-report.json"}`

**Output:** no finding; an entry under *Not checked*, plus one Info finding
`DEP-00N - No dependency scanner runs in CI` if the pipeline grep found none.

## Bundled files

- `references/audit-commands.md` - exact scanner command per ecosystem, output
  shape, install hints, and the trivy/grype image commands.
- `references/upgrade-path-rules.md` - direct vs transitive, breaking-jump
  rules, override mechanisms, abandoned-package thresholds.
- `references/<stack>.md` - dotnet, java-spring, node-express, python-django,
  angular, react, vue. To add a stack, follow
  `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `scripts/dep_audit.py` - detects manifests (with `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py`),
  runs scanners, normalises, de-duplicates, checks registry dates, prints upgrade commands.
- `scripts/patterns/<stack>.json` - manifest-level patterns for widely known
  vulnerable versions and unsafe specifiers (format:
  `$AUDIT_CORE_ROOT/skills/audit-code-scan/references/pattern-file-format.md`).

Atomic scripts this skill calls (installed next to it, not bundled):

- `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` - stack detection (honours `audit/stack.json`).
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` - runs the manifest-level patterns.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py` - shared walker imported by `dep_audit.py`.
- `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` - init / add / validate / md for findings.json.
- `evals/` - prompts and a fixture repo with one known-vulnerable package per
  ecosystem plus safe versions that must not be flagged.
