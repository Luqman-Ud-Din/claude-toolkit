---
name: audit-licensing-and-compliance
description: Inventories every third-party dependency (NuGet, Maven/Gradle, npm/pnpm/yarn, pip, container base images, bundled fonts/icons/vendored code) with its licence, flags licences incompatible with the project's distribution model (GPL/AGPL/SSPL in proprietary or SaaS software, non-commercial or source-available terms), lists packages with no or unknown licence, checks that required attribution exists, and generates THIRD-PARTY-NOTICES.md. Use it whenever the user asks about open-source licences, licence compliance, GPL, AGPL, LGPL, copyleft, attribution, third-party notices, NOTICE files, SBOM licence review, "can we ship this dependency", OSS legal review or due diligence of dependencies - even when the user does not name the skill, and as part of any pre-production or full audit run.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Licensing and compliance audit

A product can be secure and still un-shippable because one PDF library is AGPL or
because a hundred MIT packages never got their copyright lines reproduced. This skill
builds the licence inventory from what is in the repository and local package caches,
judges each package against the chosen distribution model, and produces the notices
file the product is supposed to ship. It is engineering triage: every "incompatible" or
"review" result is a decision for whoever owns legal risk, recorded next to the package.

Read-only rule: the audited code and its manifests are never modified. Everything is
written under `audit/`; the generated notices file lives in
`audit/evidence/audit-licensing-and-compliance/THIRD-PARTY-NOTICES.md` for the team to
copy into the product.

## Inputs and prerequisites

- The repository (manifests: `package.json` + lockfile, `*.csproj` / `Directory.Packages.props`,
  `pom.xml` / `build.gradle`, `requirements*.txt` / `pyproject.toml`, `Dockerfile`).
- Optional local caches that let licences resolve offline: `node_modules/`, `~/.nuget/packages`,
  `~/.m2/repository`, a virtualenv with `site-packages`. Without them packages are `unknown`,
  which is reported honestly rather than guessed.
- The **distribution model**: `proprietary` (code or bundles shipped to customers - always
  true for a frontend bundle or mobile app), `saas` (backend only runs on your servers),
  `open-source`. Ask if unclear; default to `proprietary` (strictest).
- `audit/stack.json` if present, else `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`. Python 3 stdlib only.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack detection), `audit-code-scan` (grep pass, and the shared `repo_walk.py` walker the bundled scripts import) and `audit-finding-writer` (`$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`). A missing one stops the scripts with an error naming it.

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`. Open only
   `references/<stack>.md` for each detected stack (backend and frontend): it names where
   licence metadata lives for that ecosystem, the well-known packages with surprising terms
   (iText, MySQL connectors, CKEditor, Highcharts, ffmpeg-static ...), the false positives,
   and how the notices file is normally shipped. Frontend bundles are always distributed;
   run the frontend with `--model proprietary` even when the backend is SaaS.
2. **Automated pass.**
   - `python scripts/license_inventory.py <repo> --model <model>` (add `--nuget-cache` /
     `--maven-cache` if caches are elsewhere). Writes the inventory, LIC findings, report,
     status and `THIRD-PARTY-NOTICES.md`. Verdicts come from `scripts/license-policy.json`
     (`references/license-compatibility-matrix.md` explains them).
   - `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-licensing-and-compliance/hits.json --md .../hits.md`
     for what manifests cannot show: vendored files with GPL/AGPL headers or SPDX tags,
     copyleft licence fields in manifests, git/URL dependencies, DLL/system-scope jars,
     bundled fonts/icon sets, CDN scripts, base images. Every hit is a candidate.
   - For a multi-repo product (separate backend and frontend repos) run both against each
     root and merge the findings with distinct ids.
3. **Manual trace of the highest-risk items**, in this order: (a) every `incompatible`
   package - confirm it is really shipped/served (not dev-only, not behind a feature flag),
   note the version (many packages changed licence between majors) and whether a commercial
   licence key is already configured; (b) every vendored copyleft file from the grep pass -
   find its origin; (c) every `unknown` runtime package - open its LICENSE file or registry
   page (`references/license-discovery-commands.md`) and record what you found; (d) `review`
   packages - is the library used unmodified and consumed as a package (fine) or patched /
   statically bundled into a client (needs legal); (e) attribution - where would a customer
   find the notices (About page, `/licenses`, `3rdpartylicenses.txt`, image `/licenses`)?
   Update the findings file with what you confirmed (confidence `confirmed`, decisions in
   remediation) and regenerate the Markdown with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py md`.
4. **Write findings** with prefix `LIC` via `python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" add
   audit/findings/audit-licensing-and-compliance.json --from f.json`. The script already
   emits one finding per verdict group (incompatible = High, review = Medium, unknown =
   Medium/likely, attribution missing = Medium). Add separate findings for vendored copyleft
   code (High when in a shipped bundle) and for commercial packages used without a licence
   key. Severity moves up one when the incompatible package is in a mobile/desktop
   artefact already in stores, down one when a purchased licence is shown.
5. **Outputs** (relative to the audited repo):
   - `audit/findings/audit-licensing-and-compliance.json`, `audit/reports/audit-licensing-and-compliance.md` (inventory table + findings).
   - `audit/evidence/audit-licensing-and-compliance/THIRD-PARTY-NOTICES.md` (ship it),
     `license-inventory.md`, `inventory.json`, `hits.json`/`hits.md`, any tool output (`license-checker`, `pip-licenses`, `dotnet-project-licenses`, SBOM).
   - `audit/status/audit-licensing-and-compliance.json`.
6. **Not checked.** Always state: transitive dependencies are only covered when a
   lockfile/`node_modules`/tool output was available; packages absent from local caches
   are `unknown`, not cleared; container image contents were not inspected without a
   Docker daemon; commercial licence *terms* (seat counts, revenue caps) were not read;
   this is not legal advice. Also state what was not read: folders skipped by the shared walker
   (`repo_walk.SKIP_DIRS` in `audit-code-scan`; `node_modules/<pkg>/package.json` is still read for licences),
   manifests more than six folders deep, notice files more than two folders deep, and files over 2 MB.
   `.venv`/`venv` are read on purpose to find `site-packages` metadata.

## Finding format

Shared block from `audit-finding-writer/references/findings-schema.md`, prefix `LIC`:

```markdown
### [High] LIC-001 - Dependencies with licences incompatible with the proprietary distribution model
- **Location:** `web/package.json` (1 package)
- **Confidence:** confirmed
- **Evidence:**

```text
npm pdf-render-agpl@2.1.0 -> AGPL-3.0 (network-copyleft; from node_modules/package.json; declared in web/package.json)
```

- **Impact:** Shipping the Angular bundle with this package obliges the company to publish the product's own source under AGPL; refusing is a licence breach the vendor actively enforces.
- **Remediation:** Replace with pdf-lib (MIT) or buy the vendor's commercial licence before the release branch is cut; record the decision in THIRD-PARTY-NOTICES.md.
- **Reference:** CWE-1104, ASVS-14.2.1
```

JSON fields: `id`, `title`, `severity`, `confidence`, `location`, `evidence`, `impact`,
`remediation`, `references`, `tags` (`license`, verdict, model), `root_cause_key`
(`license:<verdict>` so the report groups them).

## Output template (`audit/reports/audit-licensing-and-compliance.md`)

```markdown
## audit-licensing-and-compliance findings

Model: **proprietary**. Packages: N. ok: n, attribution: n, review: n, incompatible: n, unknown: n.

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| 0 | 1 | 3 | 0 | 0 |

### License inventory
| Ecosystem | Package | Version | Licence | Category | Verdict | Resolved from | Declared in |
|---|---|---|---|---|---|---|---|
| npm | pdf-render-agpl | 2.1.0 | AGPL-3.0 | network-copyleft | incompatible | node_modules/package.json | web/package.json |
| npm | tiny-widget | 0.3.1 | UNKNOWN | unknown | unknown | node_modules/package.json (no license field) | web/package.json |
| nuget | Newtonsoft.Json | 13.0.3 | MIT | permissive | attribution | nuspec | Api/Api.csproj |
...

### Findings
### [High] LIC-001 - ...          (standard blocks, Critical -> Info)

### Generated files
- `audit/evidence/audit-licensing-and-compliance/THIRD-PARTY-NOTICES.md` (ship with the product)
- `audit/evidence/audit-licensing-and-compliance/license-inventory.md`, `inventory.json`

### Not checked
- transitive dependencies - ...
- container image licences - ...
- packages missing from local caches - ...
```

## Examples

**Input:** `web/package.json` depends on `pdf-render-agpl` (node_modules says
`"license": "AGPL-3.0-only"`), `tiny-widget` (no `license` field), `express` (MIT),
`chart-bindings` (LGPL-3.0); model `proprietary`; no NOTICE file in the repo.

**Output:** `LIC-001` High incompatible (pdf-render-agpl), `LIC-002` Medium review
(chart-bindings, LGPL in a bundle - decide), `LIC-003` Medium/likely unknown
(tiny-widget plus anything not in caches), `LIC-004` Medium attribution missing
(express and other permissive packages), and `THIRD-PARTY-NOTICES.md` listing every
runtime package with licence and copyright line. `express` and `lodash` are not findings.

**Input:** `src/vendor/legacy-date-parser.js` with `SPDX-License-Identifier: GPL-3.0-or-later`
found by the grep pass; `src/main.ts` with `SPDX-License-Identifier: MIT` (own code).

**Output:** one High finding for the vendored GPL file (bundle is distributed); the MIT
tag is not flagged.

## Bundled files

- `scripts/license_inventory.py` - manifest/lockfile/cache reader, verdicts, LIC findings, inventory, notices file, report, status.
- `scripts/license-policy.json` - alias table, licence categories, verdict matrix per model, severities.
- `scripts/patterns/<stack>.json` - vendored copyleft headers, copyleft manifest fields, git/URL deps, DLL/system jars, fonts/icons, CDN scripts, base images; run by `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`.
- Atomic scripts called: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`, `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`, `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`. `license_inventory.py` imports `repo_walk.py` (audit-code-scan) and `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` (summary counts and schema validation).
- `references/license-compatibility-matrix.md` - categories x distribution models, why each cell is what it is, attribution duties, how to record decisions.
- `references/license-discovery-commands.md` - per-ecosystem commands that resolve what the offline pass cannot (dotnet-project-licenses, mvn license:add-third-party, license-checker/pnpm licenses, pip-licenses, docker inspect labels, SBOM tools).
- `references/<stack>.md` - where metadata lives, packages with surprising terms, false positives, how notices ship (dotnet, java-spring, node-express, python-django, angular, react, vue); add one from `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `evals/` - fixture repo with an AGPL package, a package with no licence field, an LGPL package, MIT packages (must not be flagged), a vendored GPL file, a NuGet cache stub and a Dockerfile.
