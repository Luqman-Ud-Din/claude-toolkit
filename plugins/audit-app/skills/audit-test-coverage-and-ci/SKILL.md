---
name: audit-test-coverage-and-ci
description: Reviews a repository's test and CI setup - unit tests on domain logic, integration tests against a real database (containers, not in-memory substitutes), end-to-end tests on critical user flows, coverage on auth/payment/data-mutation paths specifically rather than a global percentage, skipped/ignored/flaky tests with their reasons, test data hygiene, and CI pipeline gates (tests must pass, analyzers and security scans run, no direct pushes to main, reproducible builds, versioned or signed artifacts) - and produces a coverage map by critical path, a CI gate checklist, a skipped-test list and standard findings. Use it whenever the user asks about test coverage, testing strategy, test quality, missing tests, flaky or skipped tests, CI/CD pipeline review, GitHub Actions / Azure Pipelines / GitLab CI / Jenkins gates, build gates, branch protection, code quality process, or "are we safe to ship", even when they do not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit test coverage and CI

Answers one question: if a change broke authentication, payment, or a data
mutation, would this repository's tests and pipeline catch it before
production? A global coverage percentage does not answer that, so this skill
maps tests to the critical paths by name, lists every skipped test with its
reason, and checks whether the pipeline actually gates on the tests it has.

Read-only rule: never modify the audited code. Write only under `audit/`.
Running the existing test suite is optional and allowed (it does not change
the repo), but never add, un-skip, or edit tests.

## Inputs and prerequisites

- Repo root (defaults to `.`). Standalone runs read `audit/stack.json` if
  present, else run `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`
  (without `--write`, so a standalone run does not create `audit/stack.json`).
- Python 3 (stdlib only). Optional: the stack's toolchain to run the suite
  with coverage (`dotnet test --collect`, `npm test -- --coverage`, `pytest --cov`,
  `mvn verify`) and `gh`/`az`/`glab` CLIs to read branch protection.
- The list of critical paths if the user has one; otherwise derive it with
  `references/critical-paths.md` (auth, payment/money, data mutation, tenant
  isolation) and state the assumption.
- Sibling skills: `audit-dependency-vulnerabilities` (what the security scan
  should find), `audit-infra-and-deployment` (deploy stages, rollback),
  `audit-technical-debt` (test debt trends), `audit-business-logic` (what the
  domain tests should assert).
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack detection), `audit-code-scan` (grep pass, and the shared `repo_walk.py` walker the bundled scripts import) and `audit-finding-writer` (`$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`). A missing one stops the scripts with an error naming it.

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`; open
   `references/<stack>.md` for every detected stack (a repo with a .NET API
   and an Angular SPA needs both). Read `references/ci-gate-checklist.md` and
   `references/critical-paths.md` once.
2. **Automated pass.** Save under `audit/evidence/audit-test-coverage-and-ci/`:
   - `python scripts/test_inventory.py <repo> --out audit/evidence/audit-test-coverage-and-ci/tests.json --md audit/evidence/audit-test-coverage-and-ci/tests.md`
     finds test projects and files per stack, classifies unit / integration /
     e2e, real-DB vs in-memory, and stub / snapshot-only files; lists
     **skipped/ignored tests with name and reason** (`[Fact(Skip=)]`,
     `[Ignore]`, `@Disabled`, `it.skip`/`xit`/`test.skip`/`describe.skip`,
     `@pytest.mark.skip`, `@unittest.skip`, focused `.only`; falls back to the
     adjacent comment when the attribute carries no reason); maps
     service/controller/handler names to the test files that reference them;
     and prints a **coverage map per critical path** (covered / partial / none)
     with the untested critical units. It also reports coverage tooling and
     thresholds found.
   - `python scripts/ci_scan.py <repo> --out audit/evidence/audit-test-coverage-and-ci/ci.json --md audit/evidence/audit-test-coverage-and-ci/ci.md`
     parses GitHub Actions, Azure Pipelines, GitLab CI, Jenkinsfile, Bitbucket,
     CircleCI for test / analyzer / security-scan / coverage steps, PR triggers,
     steps that cannot fail (`continue-on-error`, `|| true`, `-DskipTests`),
     reproducible installs (`npm ci`, lockfiles, pinned actions), artifact
     versioning/signing, and branch-protection hints (CODEOWNERS, rulesets).
     Comment lines are ignored for gate detection but reported as
     `commented_out_gates` - a commented-out `dotnet test` is the evidence
     that the test gate was switched off, and `pr_files_without_test_step`
     names PR-triggered pipelines that never run tests.
   - `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-test-coverage-and-ci/hits.json`
     for test-hygiene smells: sleeps in tests, production connection strings
     in test config, in-memory database substitutes, giant timeouts, shared
     mutable fixtures.
   Every hit is a candidate. A "no test found" for a unit may be a naming
   mismatch; open the nearest test file before rating.
3. **Manual trace of the highest-risk flows.** For each critical path, in this
   order: (a) authentication (login, token refresh, password reset, role
   checks): find the test that asserts a *denied* case, not only the happy
   path; (b) money (payment, invoice, refund, pricing, tax): find tests with
   boundary values and rounding; (c) data mutation (create/update/delete of
   core entities, bulk imports, background jobs): find tests that run against
   a real database schema (containers or a disposable instance), and check
   tenant scoping is asserted where the app is multi-tenant; (d) the CI file
   that runs on pull requests: confirm the test step exists, is required, and
   cannot be skipped; then check branch protection out-of-band
   (`gh api repos/{o}/{r}/branches/main/protection`, Azure DevOps branch
   policies, GitLab protected branches) and record what you could not check.
   Optionally run the suite with coverage and attach the report path.
4. **Write findings** with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`. Prefix `TEST`. One finding
   per root cause ("PaymentService has no tests" and "AuthController has no
   tests" are two findings; "11 tests skipped since the DB upgrade" is one).
   Severity per the rubric read as production risk: untested money or auth
   path = High; CI does not run tests on PRs = High; tests run but cannot fail
   the build = High; integration tests against an in-memory substitute for a
   relational DB = Medium; skipped tests without reason = Medium; no
   security scan / analyzers = Medium; no coverage measurement = Low.
5. **Produce outputs**: `audit/findings/audit-test-coverage-and-ci.json`,
   `audit/reports/audit-test-coverage-and-ci.md` (template below: coverage
   map by critical path, CI gate checklist, skipped-test list, findings),
   evidence files, and `audit/status/audit-test-coverage-and-ci.json`
   (`{"skill","status":"completed|failed|skipped","reason","started_at","finished_at"}`).
6. **List what was not checked**: branch protection (no API access), suite
   not executed (no toolchain), flaky-test history (no CI logs), test data
   sources outside the repo, manual QA process, etc. Also list what the automated
   pass did not read: folders skipped by the shared walker (`repo_walk.SKIP_DIRS` in `audit-code-scan`: `.git`, `node_modules`, `bin`, `obj`, `dist`, `build`, `target`, `coverage`, `.angular`, `.next`, the `audit` workspace and similar) and files over 2 MB. `ci_scan.py` reads `build/` anyway (pipeline templates often live there);
   `test_inventory.py` also skips `vendor/` (third-party code).

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `TEST`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Location:** `path/to/file.ext:LINE` (symbol) - or `.` for repo-wide
- **Evidence:**

```lang
<the skipped attribute, the CI step list, or the inventory row>
```

- **Impact:** Plain language. Which class of regression reaches production undetected, and what it costs.
- **Remediation:** The concrete test or pipeline change in this stack, with a short example.
- **Reference:** CWE-1120/CWE-1127 (insufficient testing), ASVS-1.14.x / 14.1.x (build pipeline), framework docs


## Output template - `audit/reports/audit-test-coverage-and-ci.md`

````markdown
## audit-test-coverage-and-ci

**Target:** <repo> @ <commit> | **Stacks:** dotnet + angular | **Date:** <ISO>
**Suite executed:** yes (<command>, <n> passed / <n> failed / <n> skipped, line coverage <x>%) | no (<reason>)

### Coverage map by critical path
| Critical path | Units (services/controllers) | Unit tests | Integration (real DB) | E2E | Status |
|---|---|---|---|---|---|
| Authentication | AuthController, TokenService | 3 files | none | login.cy.ts | partial |
| Payment / money | PaymentService, InvoiceManager | none | none | none | none |
| Data mutation | OrderService, StockManager | 5 files | in-memory only | none | partial |
| Tenant isolation | CustomConnectionString, filters | none | none | none | none |
Status: covered (unit + integration or e2e asserting the risky case) / partial / none

### CI gate checklist
| Gate | Status | Evidence |
|---|---|---|
| Tests run on every PR | fail | `.github/workflows/build.yml`: no test step |
| Test failure blocks merge | unknown | branch protection not readable |
| Analyzers / lint run | ... | |
| Security scan (deps, secrets, SAST) | ... | |
| Coverage measured and thresholded | ... | |
| Reproducible install (lockfile, `npm ci`, pinned actions) | ... | |
| Artifacts versioned | ... | |
| Artifacts signed | ... | |
| No direct pushes to main (protection / CODEOWNERS) | ... | |
| Integration tests use a real database | ... | |

### Skipped / ignored / focused tests
| Test | Location | Kind | Reason given | Since |
|---|---|---|---|---|
| OrderServiceTests.Creates_order | `tests/.../OrderServiceTests.cs:31` | Fact(Skip) | "flaky since DB upgrade" | git blame date |

### Untested critical units
| Unit | Path | Category | Nearest test | Status |
|---|---|---|---|---|

### Findings
<finding blocks, highest severity first>

### Not checked
- <item> - <reason>
````

## Examples

**Input (test_inventory.py row):**
`PaymentService  src/Inventory.Api/Services/PaymentService.cs  category=payment  tests=none`

**Output:**
````markdown
### [High] TEST-001 - Payment service has no tests of any kind
- **Location:** `src/Inventory.Api/Services/PaymentService.cs:9` (PaymentService)
- **Confidence:** confirmed
- **Evidence:**

```text
test_inventory.py: 0 test files reference "PaymentService" (14 test files scanned)
PaymentService.Charge() computes amounts, applies discounts and calls the gateway
```

- **Impact:** A change to discount or rounding logic can overcharge or undercharge every customer and nothing in the pipeline would notice until finance reconciles.
- **Remediation:** Add `tests/Inventory.Tests/Services/PaymentServiceTests.cs` (xUnit) covering boundary amounts, rounding at 2 decimals, discount edge cases and a gateway failure; mock the gateway behind its interface. Then add the class to the CI coverage threshold.
- **Reference:** CWE-1120, ASVS-1.14.4
````

**Input (ci_scan.py row):** `.github/workflows/build.yml: steps=[checkout, setup-dotnet, restore, build] test_step=none pr_trigger=yes`

**Output:** `[High] TEST-002 - CI builds pull requests but never runs the test suite`,
Evidence shows the step list, Remediation adds
`- run: dotnet test --no-build --configuration Release --logger trx --collect:"XPlat Code Coverage"`
and marks the job as a required status check in branch protection.

## Bundled files

- `references/dotnet.md`, `java-spring.md`, `node-express.md`, `python-django.md`, `angular.md`, `react.md`, `vue.md` - test frameworks, skip syntax, real-DB integration tooling, coverage tooling, CI commands, false positives per stack.
- `references/ci-gate-checklist.md` - the gates, what counts as passing, and how to verify per CI system.
- `references/critical-paths.md` - how to derive critical paths and map units to them.
- `scripts/test_inventory.py` - test projects/files, classification, skipped tests with reasons, unit-to-test mapping, coverage tooling.
- `scripts/ci_scan.py` - CI file parser: steps, gates, reproducibility, artifacts, branch-protection hints.
- `scripts/patterns/*.json` - test-hygiene smells, run by `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`.
- Atomic scripts called: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`, `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` (and `repo_walk.py`, imported by `test_inventory.py` and `ci_scan.py`), `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`. To add a stack, start from `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `evals/` - prompts and a sample repo with an untested payment service, a skipped test, and a CI file with no test step.
