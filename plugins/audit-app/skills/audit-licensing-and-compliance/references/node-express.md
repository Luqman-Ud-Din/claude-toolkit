# Node / Express (NestJS, Fastify, Koa) reference for audit-licensing-and-compliance

Where licence information lives for npm dependencies on the server side, what resolves
offline, which packages carry surprising terms, and how notices are shipped for a Node
service (which, being SaaS, mostly has attribution duties rather than distribution duties).

## Stack markers
`package.json` (+ workspaces in monorepos), `package-lock.json` (v2/v3 include a `license`
field per package - the best offline source), `pnpm-lock.yaml` / `yarn.lock` (no licence
field), `node_modules/<pkg>/package.json`, `.npmrc` (private registries).

## Where the relevant code lives
- Direct deps: `dependencies` (shipped/run), `devDependencies` (build only - not shipped), `optionalDependencies`, `peerDependencies`.
- Resolved graph + licences: `package-lock.json` `packages` map (`"node_modules/x": {"version", "license"}`); pnpm/yarn: only via `pnpm licenses list` / `yarn licenses list`.
- Licence text: `node_modules/<pkg>/LICENSE*` / `LICENCE*` / `COPYING*`; copyright line is usually the first `Copyright (c)` line - the script copies it into the notices.
- Git/URL/file dependencies: `"pkg": "github:user/repo#sha"` or `"file:../local"` - no registry metadata.
- Bundled server code (`esbuild`/`ncc` single-file builds, Docker images) turn the SaaS backend into a distributed artefact if the image is handed to customers (on-prem) - then use `--model proprietary`.
- Shipping the notices: `THIRD-PARTY-NOTICES.md` in the repo root and copied into the image; an `/about` or `/licenses` endpoint for SaaS.

## Dangerous / interesting APIs and patterns
- Packages with copyleft/commercial terms often seen in Node backends: **sharp** (Apache, but bundles libvips LGPL - fine), **node-canvas** (MIT; system cairo LGPL), **puppeteer** (Apache; downloads Chromium BSD), **mongodb** driver (Apache) vs MongoDB server (SSPL), **redis** client (MIT) vs Redis 7.4+ server (RSALv2/SSPL), **ghostscript wrappers** (AGPL), **pdfkit** (MIT) vs **pdf-lib** (MIT) vs **jspdf** (MIT) vs **PDFTron/Apryse** (commercial), **highcharts** (commercial for non-personal use), **ag-grid-enterprise** (commercial), **bull** (MIT) vs **bullmq pro** (commercial), **ffmpeg-static** (GPL binary!), **@ffmpeg-installer** (GPL/LGPL build dependent), **mysql2** (MIT) - unlike the Java/.NET MySQL connectors.
- `"license": "UNLICENSED"` or `"SEE LICENSE IN LICENSE.txt"` - read the file.
- `"license": "(MIT OR GPL-3.0)"` dual licences - MIT wins.
- Missing `license` field (older or hobby packages) - unknown; check the repository.
- Git dependencies pinned to a fork: the fork inherits the upstream licence, but nobody has checked.
- Native modules built at install time (`node-gyp`) link against system libraries with their own licences.

## What "good" looks like
```jsonc
// package.json
"scripts": {
  "licenses:check": "license-checker --production --onlyAllow 'MIT;ISC;BSD-2-Clause;BSD-3-Clause;Apache-2.0;0BSD;CC0-1.0;Unlicense;BlueOak-1.0.0' --excludePrivatePackages",
  "licenses:notices": "license-checker --production --plainVertical > THIRD-PARTY-NOTICES.txt"
}
```
Run `licenses:check` in CI; commit the generated notices and copy them into the Docker image (`COPY THIRD-PARTY-NOTICES.txt /app/`).

## Manual trace checklist
1. Every `unknown` production package: open `node_modules/<pkg>/` for a LICENSE file, then the repository; record what you found.
2. Git/URL/file dependencies: identify upstream and licence; note the fork's commit.
3. Binary-downloading packages (`ffmpeg-static`, `puppeteer`, `sharp` prebuilds): the downloaded binary's licence governs (ffmpeg builds are often GPL).
4. If the backend is delivered as a Docker image or on-prem installer, re-run with `--model proprietary` - GPL server packages become blockers.
5. Where are notices exposed for a SaaS - `/licenses` endpoint, About page, docs site?

## Stack-specific false positives
- `devDependencies` (typescript, eslint, jest, webpack) - not shipped; `unknown` there is Info.
- `@types/*` packages - MIT.
- `private: true` workspace packages with no `license` field - your own code.
- GPL tooling run at build time only (some CLI generators) - not distributed.

## Tooling
- `npx license-checker --production --json` (also `--failOn`, `--onlyAllow`, `--customPath` for notices templates).
- `pnpm licenses list --prod`, `yarn licenses list --production`, `npx @cyclonedx/cyclonedx-npm` (SBOM).
- `npm view <pkg> license` for a single package.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py --patterns scripts/patterns/node-express.json` - vendored GPL headers, copyleft `license` fields in manifests/lockfiles, git/URL dependencies.

## References
npm docs "package.json license"; license-checker README; SPDX licence expressions;
ASVS 4.0.3 V14.2; CWE-1104.
