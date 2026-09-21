---
name: audit-frontend-best-practices
description: Audits a frontend codebase (Angular, React, Vue, Next, Nuxt, Vite) against current best practices for its framework - strict TypeScript, modern component model (standalone/hooks/composition), current control-flow and state patterns, OnPush/memo change detection, lazy-loaded routes, bundle budgets, production build settings (minification, tree shaking, no shipped source maps), lint config, and mixed legacy/modern patterns - and produces a per-category scorecard, standard findings and a bundle-size report. Use it whenever the user asks about frontend code quality, frontend modernization, frontend best practices, an Angular/React/Vue review, bundle size, bundle budgets, lazy loading, tree shaking, source maps in production, strict mode, frontend performance, or "is our frontend up to date", even when they do not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit frontend best practices

Checks a frontend codebase against the current best practices of its own
framework and reports a scorecard (pass / partial / fail per category with
counts), findings in the shared audit format, and a bundle-size report when the
production build can be run. This is not style policing: every category maps
to a production cost (slow first load, missed compile-time errors, leaked
source, unmaintainable mixed idioms), and the finding must say which.

Read-only rule: never modify the audited code. Write only under `audit/`.
If a build is run, direct its output under `audit/evidence/` (step 5) so the
repo tree stays untouched.

## Inputs and prerequisites

- Repo root (defaults to `.`). Standalone runs read `audit/stack.json` if
  present, else run `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` without
  `--write` (the stack.json contract: a standalone run must not create state the
  orchestrator would later trust).
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack), `audit-code-scan` (grep pass and the shared file walker the bundled scripts import), `audit-finding-writer` (findings.json).
- Python 3 (stdlib only) for the scripts. Node plus the project's package
  manager only for the optional bundle-size report.
- Sibling skills own adjacent topics; do not duplicate them:
  `audit-frontend-memory-leak` (teardown), `audit-frontend-xss-and-dom-safety`
  (sanitization), `audit-accessibility-and-i18n`, `audit-security-headers-and-middleware`
  (CSP, compression headers), `audit-performance-and-scalability` (runtime perf).

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`; read
   `primary_frontend` and open only `references/<stack>.md` (angular, react,
   vue). If the repo also has a backend, open that backend's reference file too:
   it lists the few frontend-serving checks the backend owns (static assets,
   compression, cache headers, SPA fallback) and defers everything else. If no
   frontend stack is detected, stop and write `audit/status/<skill>.json` with
   `status: skipped`, reason "no frontend manifest".
2. **Automated pass.** Run all three, saving output under
   `audit/evidence/audit-frontend-best-practices/`:
   - `python scripts/config_check.py <repo> --out audit/evidence/audit-frontend-best-practices/config.json`
     reads `tsconfig*.json` strict flags, `angular.json` / `vite.config.*` /
     `next.config.*` / `nuxt.config.*` for budgets, source maps, optimization,
     and lint config presence. It prints a preliminary scorecard.
   - `python scripts/route_scan.py <repo> --out audit/evidence/audit-frontend-best-practices/routes.json`
     lists every route and whether it is lazy (Angular `loadChildren`/`loadComponent`,
     React `React.lazy`/`lazy()`, Vue `() => import()`), per framework.
   - `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-frontend-best-practices/hits.json`
     finds legacy/modern mixing, `any` leakage, class components, Options-API
     residue, full-library imports.
   Every hit is a candidate. Only what you open and confirm becomes a finding.
3. **Manual trace of the highest-risk flows.** In this order, because these
   decide the user-visible cost: (a) the initial route and its eager imports -
   what ships in the first chunk; (b) the three heaviest feature areas
   (dashboard, lists, editors) - change detection strategy and state handling;
   (c) the production build configuration CI actually uses (`ng build --configuration`,
   `vite build --mode`, `next build`) - confirm source maps, minification and
   budgets in *that* configuration, not the default; (d) the shared/core module,
   because mixed idioms there propagate everywhere. Use the "Manual trace
   checklist" in the stack file.
4. **Write findings** with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` (`init`, then `add` per
   finding, `validate`, `md`). Prefix `FEBP`. One finding per root cause: "34
   components use `*ngIf` while 12 use `@if`" is one finding with counts, not
   34. Rate with the severity rubric read as production risk: source maps
   shipped = Medium (High if they reveal secrets or internal hosts); strict off
   = Medium; one eager admin route = Low; optimization off in prod = High.
5. **Bundle-size report (optional).** If `node_modules` exists and the build
   command is known, run
   `python scripts/bundle_report.py <repo> --run --out audit/evidence/audit-frontend-best-practices/bundle.json`;
   it builds into `audit/evidence/.../dist` (never into the repo's `dist/`),
   measures initial vs lazy chunks, gzip sizes, and compares them with the
   configured budgets. Without `--run` it measures an existing `dist/` if one is
   present. If neither is possible, record it under "Not checked".
6. **Produce outputs**: `audit/findings/audit-frontend-best-practices.json`,
   `audit/reports/audit-frontend-best-practices.md` (template below), evidence
   files, and `audit/status/audit-frontend-best-practices.json`
   (`{"skill","status":"completed|failed|skipped","reason","started_at","finished_at"}`).
7. **List what was not checked** and why: build not run, framework version not
   confirmed, generated code excluded, runtime performance (other skill), etc.
   Also list the automated pass's coverage limits from `audit-code-scan`: folders on the shared skip list (`node_modules`, `bin`, `obj`, `dist`, `build`, `.git`, `audit`, ... - see `$AUDIT_CORE_ROOT/skills/audit-code-scan/references/repo-walk-api.md`) and files over 2 MB are not read, and patterns match one line at a time. `config_check.py` and `route_scan.py` use the
   same walker, so config and route files under `dist`, `build`, `.angular`, `.next`,
   `.nuxt` or `.output` are not read. `bundle_report.py` deliberately reads the build
   output folders the walker skips (`dist`, `build`, `.next`, `.output`, via `include_dirs`)
   with no size cap; other skip-list folders nested inside the build output (for example
   `node_modules` or `coverage`) are not measured.

## Scorecard categories

| Category | Pass | Partial | Fail |
|---|---|---|---|
| Strict type checking | `strict: true` (+ `strictTemplates` for Angular) in the build tsconfig, no `@ts-ignore` sprawl | strict on but sub-flags disabled, or >10 `any` hot spots | `strict` absent or false |
| Component model | All components on the current model (standalone / function+hooks / `<script setup>`) | Mixed, migration documented | Legacy model dominant, no plan |
| Control flow & state | Current control flow (`@if/@for`, hooks, composition), one state approach | Two approaches coexist | Deprecated APIs (`UNSAFE_*`, `Vue.extend`, `ngModel` inside reactive forms) |
| Change detection | OnPush / memo / computed wherever lists render | Some hot lists default | No strategy anywhere, large lists |
| Lazy routes | Every feature route lazy | Some eager feature routes | Feature routes eager, single chunk |
| Bundle budgets | Budgets configured and enforced in CI | Configured, not enforced | None |
| Production build | Minify + tree shake + `sourceMap` off + hashed filenames | One setting off | Source maps shipped or optimization off |
| Lint config | ESLint / angular-eslint present, runnable, in CI | Present but not runnable or not in CI | Absent |
| Legacy/modern mixing | None | Isolated leftovers | Pervasive |

Put counts (files affected / total) in the cell so the reader can judge scale.
Full criteria per framework: `references/scorecard-rubric.md`.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `FEBP`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Reference:** CWE-nnn, ASVS-x.y.z, framework doc (use what applies; see references/<stack>.md)


## Output template - `audit/reports/audit-frontend-best-practices.md`

````markdown
## audit-frontend-best-practices

**Target:** <repo> @ <commit> | **Stack:** <framework + version> | **Date:** <ISO>

### Scorecard

| Category | Result | Count | Evidence |
|---|---|---|---|
| Strict type checking | pass/partial/fail | strict=false in tsconfig.json | config.json |
| Component model | ... | 12/40 components legacy | hits.json |
| Control flow & state | ... | | |
| Change detection | ... | | |
| Lazy routes | ... | 3/9 feature routes eager | routes.json |
| Bundle budgets | ... | | |
| Production build | ... | sourceMap=true in production | config.json |
| Lint config | ... | | |
| Legacy/modern mixing | ... | | |

**Totals:** pass N / partial N / fail N

### Bundle-size report
(built with: <command> | not run: <reason>)

| Chunk | Type | Raw | Gzip | Budget | Status |
|---|---|---|---|---|---|
| main.js | initial | 812 kB | 214 kB | 500 kB | over |

### Findings
| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| 0 | 1 | 3 | 2 | 1 |

<finding blocks, highest severity first>

### Not checked
- <item> - <reason>
````

## Examples

**Input (config_check.py line):**
`angular.json: projects.digital-inventory.architect.build.configurations.production.sourceMap = true`

**Output:**
````markdown
### [Medium] FEBP-002 - Source maps are shipped with the production build
- **Location:** `angular.json:88` (configurations.production.sourceMap)
- **Confidence:** confirmed
- **Evidence:**

```json
"production": { "sourceMap": true, "optimization": true }
```

- **Impact:** Anyone can download `main.*.js.map` and read the original TypeScript, including internal API paths, feature flags and comments; it also adds several MB to every deploy.
- **Remediation:** Set `"sourceMap": false` (or `{"scripts": false, "styles": false, "hidden": true}` when an error tracker needs maps uploaded out-of-band) in the `production` configuration and confirm CI runs `--configuration production`.
- **Reference:** CWE-540, ASVS-14.3.2
````

**Input (route_scan.py row):**
`src/app/app.routes.ts:14 path=reports component=ReportsComponent lazy=false`

**Output:** one `[Low] FEBP-004 - Reports feature is bundled into the initial chunk`
finding, remediation
`{ path: 'reports', loadChildren: () => import('./features/reports/reports.routes').then(m => m.routes) }`,
plus the measured initial-chunk delta from `bundle.json` if available.

## Bundled files

- `references/angular.md`, `react.md`, `vue.md` - per-framework checks, current-vs-legacy tables, config keys, false positives, tooling.
- `references/dotnet.md`, `java-spring.md`, `node-express.md`, `python-django.md` - what the backend owns when it serves the frontend (static assets, compression, cache headers, SPA fallback) and which sibling skill owns the rest.
- `references/scorecard-rubric.md` - pass/partial/fail criteria per category and framework.
- `scripts/config_check.py` - tsconfig strict flags, build config (budgets, source maps, optimization), lint presence; preliminary scorecard.
- `scripts/route_scan.py` - route inventory with lazy/eager per framework.
- `scripts/bundle_report.py` - measure `dist/` (or build into the evidence dir) and compare with budgets.
- `scripts/patterns/<stack>.json` (angular, react, vue, node-express, dotnet, java-spring, python-django) - legacy/modern mixing and bundle-hostile imports (format: `$AUDIT_CORE_ROOT/skills/audit-code-scan/references/pattern-file-format.md`).
- `evals/` - prompts and a sample repo with strict off, a non-lazy route and production source maps on.

To add a stack, follow `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.

Atomic scripts this skill calls (installed next to it, not bundled):

- `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` - stack detection (honours `audit/stack.json`).
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` - pattern-driven automated pass.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py` - shared walker imported by `config_check.py`, `route_scan.py` and `bundle_report.py`.
- `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` - init / add / validate / md for findings.json.
