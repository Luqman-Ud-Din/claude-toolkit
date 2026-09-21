# CI gate checklist

Every row of the report's "CI gate checklist" table comes from this file. A gate
is **pass** only when it exists *and* can block a merge; a step that runs but
cannot fail the build is **advisory** and rated as if missing. Use **unknown**
when the evidence lives in the forge (branch protection, required checks) and
you could not read it - never guess pass.

`scripts/ci_scan.py` fills the in-repo half of each row. The out-of-band column
says how to confirm the rest.

## The gates

| # | Gate | Pass means | Advisory / fail signals | Out-of-band verification |
|---|---|---|---|---|
| 1 | Tests run on every PR | A job triggered by `pull_request` / MR / PR build validation runs the stack's test command | No PR trigger; test step only on `main` push or nightly; test job behind `if: false` or manual | GitHub: Actions tab of a recent PR. Azure: branch policy "Build validation". GitLab: MR pipeline list |
| 2 | Test failure blocks merge | The test job is a *required* status check on the default branch | `continue-on-error: true`, `|| true`, `allow_failure: true`, `-DskipTests`, `--passWithNoTests`, `catchError`, `failOnStderr: false` | `gh api repos/{o}/{r}/branches/main/protection --jq .required_status_checks`; `az repos policy list --branch main`; GitLab "Pipelines must succeed" setting |
| 3 | Analyzers / lint run | Lint or compiler analyzers with warnings-as-errors on the PR build | `npm run lint` absent or broken; `dotnet build` without `-warnaserror` and no `TreatWarningsAsErrors`; lint job advisory | Run the lint command locally and confirm it exits non-zero on a planted issue |
| 4 | Security scan | Dependency scan (`npm audit`, `dotnet list package --vulnerable`, `pip-audit`, dependency-check, Dependabot/Renovate), secret scan (gitleaks, GitHub push protection), SAST (CodeQL, Semgrep, Sonar) - at least deps + secrets | Scans only on schedule with nobody reading results; `--audit-level=critical` hiding High; scan uploaded but not failing | GitHub "Code security" settings (Dependabot alerts, secret scanning, push protection); Azure Advanced Security; GitLab Security dashboard |
| 5 | Coverage measured and thresholded | Coverage collected in CI with a failing threshold, ideally per critical project/folder | Coverage collected but no threshold; threshold global only (80% overall while payment is at 0%) | Open the coverage report artifact of the last main build |
| 6 | Reproducible install | Lockfile committed and honoured (`npm ci`, `--frozen-lockfile`, `dotnet restore --locked-mode`, `pip install --require-hashes`, Maven enforcer), SDK pinned (`global.json`, `.nvmrc`, `engines`), actions pinned to a tag or SHA | `npm install` in CI; no lockfile; `uses: foo@main`; `Version="*"`; `FROM node:latest` in the build image | Rebuild the same commit twice and compare artifact hashes (optional) |
| 7 | Artifacts versioned | Every published artifact/image carries a unique version tied to the commit (semver + SHA, build number) | `:latest` only; `1.0.0` hard-coded forever; artifacts overwritten in place | Registry listing shows distinct tags per build |
| 8 | Artifacts signed / provenance | Images signed (cosign/notation), packages signed, or build provenance attested (SLSA, `actions/attest-build-provenance`) | No signing step; signing key stored as plain CI variable | `cosign verify` against the registry; check signature policy in the cluster |
| 9 | No direct pushes to main | Branch protection or ruleset requires PR + at least one approval, dismisses stale approvals, blocks force-push, applies to admins; CODEOWNERS on critical paths | Only CODEOWNERS file (no enforcement); protection exists but admins bypass; local hooks (husky, pre-commit) mistaken for a gate | `gh api repos/{o}/{r}/rulesets`; Azure "Require a minimum number of reviewers"; GitLab protected branches "Allowed to push: No one" |
| 10 | Integration tests use a real database | Integration job starts the real engine (Testcontainers, CI `services:` container, disposable cloud DB) and runs migrations/schema | `UseInMemoryDatabase`, H2, SQLite for a SQL Server/Postgres app; integration tests excluded by filter in CI | Read the job's `services:` block and test fixture setup |
| 11 | E2E on critical flows | Browser/API e2e suite for login, checkout/payment, core create/update runs on PR or pre-deploy | e2e only runs manually or locally; e2e job advisory | Last pipeline run shows e2e job and its result |
| 12 | Deploy gated on the above | Deploy job `needs:` / `dependsOn:` the test job; production deploy requires approval / environment protection | Deploy on push to main in parallel with tests; `workflow_dispatch` deploy with no checks | GitHub Environments protection rules; Azure environment approvals and checks |

## Status vocabulary

- **pass** - present and blocking, evidence cited.
- **advisory** - present but cannot fail the build or is not required. Rate like fail.
- **fail** - absent.
- **unknown** - lives outside the repo and could not be read; add to "Not checked".
- **n/a** - genuinely not applicable (for example no artifacts are published); say why.

## Severity guidance for gate failures

| Gate failure | Default severity | Raise to | Lower to |
|---|---|---|---|
| 1 or 2 (tests not run / cannot fail) | High | Critical if the repo deploys straight to production from the same pipeline | Medium if there is effectively nothing to run (then the missing tests are the finding) |
| 9 (direct pushes to main possible) | High | - | Medium for a single-maintainer repo with documented compensating review |
| 4 (no security scan) | Medium | High for an internet-facing app handling payments or PII | Low when Dependabot/secret scanning is confirmed on at org level |
| 10 (in-memory DB substitute) | Medium | High when the app relies on raw SQL, stored procedures or tenant query filters | Low when separate real-DB tests exist for the same paths |
| 3, 5, 6 | Low-Medium | Medium when combined with no tests on critical paths | Info |
| 7, 8 | Low | Medium for regulated or customer-installed software | Info for internal tools |
| 11, 12 | Medium | High when deploy runs without depending on tests | Low |

## Per CI system - where to look

- **GitHub Actions**: `on:` (look for `pull_request`), `jobs.<id>.needs`, `continue-on-error`,
  `if:`, `uses:` pinning, `permissions:` (write-all is a separate supply-chain finding),
  `environment:` on deploy jobs.
- **Azure Pipelines**: `trigger:` and `pr:` (note: PR validation for Azure Repos is set by
  branch policy, not `pr:`), `DotNetCoreCLI@2 command: test`, `continueOnError`,
  `condition: succeededOrFailed()`, `dependsOn`, `environment:` approvals, templates under
  `extends:`.
- **GitLab CI**: `rules:` / `only: merge_requests`, `allow_failure`, `needs:`, `include:`
  (scan templates like `Security/SAST.gitlab-ci.yml`), `when: manual`, `coverage:` regex.
- **Jenkins**: `stages`, `when { changeRequest() }`, `catchError`, `returnStatus: true`
  (swallows exit codes), `junit` step with `allowEmptyResults: true`, `sh 'mvn -DskipTests'`.
- **Bitbucket / CircleCI / others**: `pull-requests:` pipelines, `requires:` workflows,
  `when: always`, `ignore_errors`.
