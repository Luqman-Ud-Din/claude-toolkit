# Node / Express reference for audit-dependency-vulnerabilities

## Stack markers
`package.json` with `express`, `fastify`, `koa`, `@nestjs/core`, `hapi`; lockfile
decides the manager: `package-lock.json` (npm), `pnpm-lock.yaml`, `yarn.lock`
(v1 classic vs berry with `.yarnrc.yml`). Variants: monorepo workspaces
(`workspaces` in package.json, `pnpm-workspace.yaml`) - audit from the root so
hoisted versions are seen once.

## Where the relevant code lives
- Direct: `dependencies`, `devDependencies`, `optionalDependencies`; `overrides`
  (npm) / `resolutions` (yarn) / `pnpm.overrides` show existing transitive pins.
- Resolved graph: the lockfile; `npm ls <pkg>` prints the path.
- Install policy: `.npmrc` (`audit=false`, `ignore-scripts`, `registry=`), `engines`.
- CI: `npm ci` steps in workflows; `Dockerfile` `RUN npm ci --omit=dev`.

## Dangerous / interesting APIs and patterns
- Famous vulnerable versions: `lodash` < 4.17.21, `minimist` < 1.2.6, `axios` < 0.21.2
  (and 1.x < 1.6.0 for CSRF token leak, CVE-2023-45857), `jsonwebtoken` < 9,
  `express` < 4.19.2 (open redirect) and < 4.20.0, `node-fetch` < 2.6.7,
  `qs` < 6.5.3 / 6.11.0 (prototype pollution), `body-parser` < 1.20.3 (DoS),
  `multer` < 1.4.4-lts.1, `ws` < 8.17.1 (CVE-2024-37890), `path-to-regexp` < 0.1.12 (ReDoS),
  `semver` < 7.5.2, `tar` < 6.2.1, `moment` < 2.29.4, `mongoose` < 7.x prototype pollution,
  `sequelize` < 6.x SQL injection in `replacements`.
- Version specifiers `*`, `latest`, `>=1`, `git+https://`, `github:user/repo` without a
  commit; `file:` outside the repo.
- `.npmrc` with `audit=false`, `strict-ssl=false`, `registry=http://`.
- Install-time scripts: `npm ci` without `--ignore-scripts` on CI runners that hold secrets.
- Vendored `node_modules` committed to git (scanners skip them; nothing updates them).

## What "good" looks like
```json
{
  "dependencies": { "express": "^4.21.0", "lodash": "^4.17.21" },
  "overrides": { "semver": "^7.5.4" },
  "engines": { "node": ">=20" },
  "scripts": { "audit:ci": "npm audit --omit=dev --audit-level=high" }
}
```
CI: `npm ci --ignore-scripts` then `npm run audit:ci`; Dependabot or Renovate
with `security-updates` on; lockfile committed and `npm ci` (not `npm install`).

## Manual trace checklist
1. Critical/High direct deps in the request path: find the import and the call.
   Prototype pollution (`lodash.merge`, `qs`, `minimist`) matters when the input is
   a request body/query; ReDoS matters when the regex runs on user strings.
2. Transitive rows: `npm ls <pkg>` - if the parent has a newer release that
   moved past the range, remediation is the parent bump; else an `overrides` entry
   (say it is temporary).
3. `npm audit` result count vs `npm audit --omit=dev`: separate what ships.
4. Node runtime version in `engines`/Dockerfile: EOL Node lines (16, 18) carry
   unpatched OpenSSL/HTTP CVEs - one High finding.
5. Check that the lockfile is committed and CI uses `npm ci`; otherwise every
   deploy resolves a different graph and the audit result is stale on arrival.

## Stack-specific false positives
- `npm audit` reports advisories for dev tooling (`webpack-dev-server`, `karma`,
  `jest`) that never reach production: Low unless CI processes untrusted input.
- Advisories on packages only used at build time by the frontend bundler.
- `moderate` ReDoS in a package that only sees trusted config strings.
- Duplicate reports for the same package under several paths - one finding.
- "No fix available" + package unused: remediation is removal, not upgrade.

## Tooling
- `npm audit --json`, `npm audit --omit=dev --audit-level=high`
- `pnpm audit --json`, `yarn audit --json`, `yarn npm audit --all --recursive --json` (berry)
- `npm ls <pkg>` / `pnpm why <pkg>` / `yarn why <pkg>` for parents
- `npm outdated --long` for abandoned/major-behind packages
- `npx better-npm-audit`, `osv-scanner --lockfile package-lock.json`, `trivy fs .`
- `npm view <pkg> time --json` for last-release date; `deprecated` field in `npm view <pkg>`

## References
CWE-1395, CWE-1321 (prototype pollution), CWE-1333 (ReDoS), CWE-829 (untrusted
source), OWASP A06:2021, ASVS 14.2, GitHub Advisory Database (ecosystem=npm),
npm docs for `overrides` and `audit`.
