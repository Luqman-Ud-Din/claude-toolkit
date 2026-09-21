# Upgrade-path, de-duplication and abandonment rules

## Direct vs transitive

- **Direct**: named in the project's own manifest (`PackageReference`,
  `dependencies`/`devDependencies`, `<dependency>`, `requirements.txt` line).
  Fix = bump the version in that manifest.
- **Transitive**: pulled in by a direct dependency. Fix, in order of preference:
  1. Bump the direct parent to a release that itself depends on the fixed version
     (`npm ls <pkg>`, `dotnet nuget why <proj> <pkg>`, `mvn dependency:tree -Dincludes=g:a`,
     `pipdeptree -r -p <pkg>`).
  2. Pin the transitive explicitly: npm `overrides`, yarn `resolutions`,
     pnpm `pnpm.overrides`; .NET explicit `<PackageReference>` (nearest wins) or
     `Directory.Packages.props` with `<PackageVersion>`; Maven `<dependencyManagement>`;
     Gradle `resolutionStrategy.force`; pip constraints file `-c constraints.txt`.
  3. Replace the parent if it is abandoned.
  Name the parent in Remediation; an override without a parent bump is a
  temporary measure and should be tagged as such.

## "Breaking?" column

- `yes` when the first version component changes (npm/NuGet/Maven semver
  major; Python: first component, or second when the project uses 0.x/calver).
  npm's `fixAvailable.isSemVerMajor` is authoritative when present.
- `no` when only minor/patch changes.
- `?` when the scanner did not give a fixed-in version (dotnet, dependency-check):
  open the advisory URL and fill it in by hand before writing the finding.
- Always add the changelog/migration link for `yes` rows; a breaking upgrade with
  no migration note will not get scheduled.

## De-duplication

Key = `(ecosystem, package name, resolved version)`. Merge:
- advisories: union;
- severity: highest;
- direct flag: `true` if any source says direct;
- fixed-in: highest fixed version among sources (all advisories must be covered).
One finding per key. If the same package@version appears in several projects of
one repo (typical for .NET solutions), list every project path in Evidence and
set `root_cause_key` = `<ecosystem>:<name>@<version>`.

Do not merge different versions of the same package: they usually need
different upgrade commands and may have different advisory sets.

## Severity adjustments (apply after the advisory's CVSS band)

| Situation | Adjustment |
|---|---|
| Vulnerable API demonstrably not called (e.g. `lodash` present but only `_.chunk` used) | down one, say why, keep `confidence: confirmed` |
| Dev-only dependency (test runner, linter, build tool) with a runtime CVE | down to Medium or Low unless CI runs untrusted input through it |
| Package sits on the unauthenticated request path (parser, auth, TLS, image decoder) | keep or up one |
| Multi-tenant app and the advisory allows cross-request state (prototype pollution, static caches) | up one |
| Fix is a breaking major with no migration guide | no severity change; add "effort: high" tag |

## Abandoned packages

- Threshold: no release on the public registry for 2+ years (`--abandoned-years`).
- Signals that strengthen the finding: archived GitHub repo, `deprecated` flag in
  the npm registry document, open unfixed CVEs, maintainer notice in README.
- Signals that weaken it: package is intentionally frozen and tiny (e.g. a
  polyfill), or the project owns the package.
- Rating: Low by default; Medium if it handles untrusted input or crypto; High
  only if it also has an unfixed advisory (then it is really a vulnerability
  finding with "no fix available" in Remediation: replace the package).
- Registry queries: npm `https://registry.npmjs.org/<name>` (`time[latest]`),
  PyPI `https://pypi.org/pypi/<name>/json` (`releases`), NuGet
  `https://api.nuget.org/v3/registration5-semver1/<id>/index.json`
  (`catalogEntry.published`), Maven Central
  `https://search.maven.org/solrsearch/select?q=g:"<g>"+AND+a:"<a>"` (`timestamp`).
  Private feeds are not queried; those packages go to *Not checked*.

## Pinning hygiene findings (one finding per repo, Low unless CI is public)

- No lockfile committed (`package-lock.json`/`yarn.lock`/`pnpm-lock.yaml`,
  `packages.lock.json` optional for .NET, no `requirements.txt` pins).
- Floating versions: `*`, `latest`, `>=`, `1.*`, Maven `LATEST`/ranges, Gradle `+`.
- Git/URL/tarball sources without a commit hash.
- Registry over HTTP.
