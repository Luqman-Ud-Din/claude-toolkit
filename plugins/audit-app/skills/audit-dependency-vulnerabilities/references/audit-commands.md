# Exact audit command per ecosystem

`scripts/dep_audit.py` runs these for you; use this file when you need to run
one by hand, read its raw output, or explain to the team what to add to CI.
Every command is read-only (no lockfile writes) as written; do not add `--fix`.

| Ecosystem | Detects | Command | Output | Needs |
|---|---|---|---|---|
| NuGet (.NET) | `*.csproj`, `*.fsproj`, `Directory.Packages.props` | `dotnet list <proj-or-sln> package --vulnerable --include-transitive --format json` | JSON: `projects[].frameworks[].topLevelPackages[]/transitivePackages[]` each with `id`, `resolvedVersion`, `vulnerabilities[{severity, advisoryurl}]` | SDK 7.0.200+ for `--format json`; prior `dotnet restore` (reads `obj/project.assets.json`) |
| Maven | `pom.xml` | `mvn org.owasp:dependency-check-maven:check -Dformat=JSON` | `target/dependency-check-report.json`: `dependencies[].vulnerabilities[{name, severity, cvssv3}]`, `packages[].id = pkg:maven/g/a@v` | Java, network for the NVD feed (first run 10+ min; pass `-DnvdApiKey=...` to avoid throttling) |
| Gradle | `build.gradle(.kts)` | `gradle dependencyCheckAnalyze` (plugin `org.owasp.dependencycheck`) with `dependencyCheck { formats = ['JSON'] }` | `build/reports/dependency-check-report.json` (same shape as Maven) | plugin applied in the build; same NVD download |
| npm | `package.json` + `package-lock.json` | `npm audit --json` | npm 7+: `vulnerabilities{name:{severity, isDirect, range, via[], fixAvailable{version, isSemVerMajor}}}`; npm 6: `advisories{}` | lockfile; registry access. `--omit=dev` to drop dev deps; `--audit-level=high` for CI gate |
| pnpm | `pnpm-lock.yaml` | `pnpm audit --json` | npm-6 style `advisories{id:{module_name, severity, patched_versions, findings[{version, paths}]}}` | lockfile |
| yarn classic | `yarn.lock` (v1) | `yarn audit --json` | NDJSON, one `{"type":"auditAdvisory","data":{"advisory":{...}}}` per advisory | lockfile |
| yarn berry | `.yarnrc.yml` | `yarn npm audit --json --all --recursive` | NDJSON, same advisory shape | yarn 2+ |
| pip | `requirements*.txt` | `pip-audit -r requirements.txt --format json` | `dependencies[{name, version, vulns[{id, fix_versions[], aliases[]}]}]`; no severity field (look up the CVE) | `pip install pip-audit`; resolves the file in a temp venv, so needs index access |
| pip (project) | `pyproject.toml`, `Pipfile` | `pip-audit --format json` inside the activated env, or `pipenv check --output json` | as above | environment installed |
| Container image | `Dockerfile` `FROM`, compose `image:` | `trivy image --format json --quiet <image>` | `Results[].Vulnerabilities[{VulnerabilityID, PkgName, InstalledVersion, FixedVersion, Severity}]` | image pullable; `trivy image --input <tar>` for offline |
| Container image (alt) | same | `grype <image> -o json -q` | `matches[{vulnerability{id, severity, fix{versions[]}}, artifact{name, version}}]` | image pullable |
| Whole repo (lockfiles) | any | `trivy fs --scanners vuln --format json <repo>` | same as image shape, per lockfile target | trivy; good cross-check for npm/pip/NuGet lockfiles |
| SBOM | any | `syft <dir-or-image> -o cyclonedx-json` then `grype sbom:sbom.json -o json` | as grype | syft + grype |

## Commands that are NOT read-only (never run inside the audit)

`npm audit fix`, `npm install`, `yarn upgrade`, `pnpm update`, `dotnet add package`,
`pip install -U`, `mvn versions:use-latest-releases`, `dependabot` pull requests.
Put them in the *Upgrade commands* section for the team to run.

## Reading severities across tools

| Tool | Values | Map to |
|---|---|---|
| dotnet | Low, Moderate, High, Critical | Moderate -> Medium |
| npm/pnpm/yarn | info, low, moderate, high, critical | moderate -> Medium |
| pip-audit | (none) | look up the CVE/GHSA and use its CVSS band; else `unknown` and rate by hand |
| dependency-check | LOW, MEDIUM, HIGH, CRITICAL (from CVSS v3, else v2) | as is |
| trivy/grype | UNKNOWN, LOW, MEDIUM, HIGH, CRITICAL (vendor-adjusted) | as is; note that OS-package severities are the distro's, not NVD's |

## Install hints (for the *Not checked* section)

- `pip-audit`: `pip install pip-audit` (or `pipx install pip-audit`)
- `trivy`: `winget install Aquasecurity.Trivy` / `brew install trivy` / `apt install trivy`
- `grype`: `brew install grype` / release binaries
- dependency-check CLI (no Maven needed): `dependency-check --scan <dir> --format JSON --out <dir>`
- NuGet built-in: SDK 8+ warns NU1901-NU1904 on restore when `<NuGetAudit>` is on (default since 8.0.100)

## What to put in CI

One of: `npm audit --audit-level=high`, `dotnet list package --vulnerable`
(fail on non-empty), `pip-audit`, `trivy fs --exit-code 1 --severity HIGH,CRITICAL .`,
or Dependabot / Renovate with security updates enabled. The absence of all of
these is itself a finding (Medium): vulnerabilities published after the audit
day are invisible until the next manual run.
