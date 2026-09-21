# Scorecard rubric for audit-frontend-best-practices

Each category gets exactly one of `pass`, `partial`, `fail`, or `n/a` (with a
reason). Always attach a count in the form `affected/total` so the reader can
judge scale. `config_check.py` and `route_scan.py` emit preliminary results;
the manual pass may override them and must say why in the Evidence column.

## How to decide

| Category | Pass | Partial | Fail |
|---|---|---|---|
| Strict type checking | Effective `strict: true` in the build tsconfig chain; Angular also `strictTemplates: true`; Vue also `vue-tsc` in scripts; `@ts-ignore`/`@ts-nocheck` count <= 5 and `: any` hot spots <= 10 | `strict` true but two or more sub-flags disabled (`strictNullChecks`, `noImplicitAny`, `strictTemplates`), or any-count above threshold | `strict` false/absent, or `tsconfig.app.json` overrides it to false, or JS-only project claiming TypeScript |
| Component model | 100% current model (Angular standalone; React function components; Vue `<script setup>` or Composition) except documented exceptions (React error boundaries) | Mixed; migration schematic/codemod run partly or a migration plan exists in the repo | Legacy majority and no plan; Vue 2 or CRA (unmaintained platform) |
| Control flow & state | Current control flow everywhere the framework has one (`@if/@for`, hooks, composition); a single state approach for each kind of state (server state, UI state) | Old and new control flow coexist; two libraries for the same state kind | Deprecated APIs present (`UNSAFE_*`, `componentWill*`, `Vue.extend`, `ReactDOM.render`, `ngModel` in reactive forms) |
| Change detection | OnPush (Angular) / `memo`+stable keys (React) / `computed` + stable `:key` (Vue) on every list/table component; no `key={index}` on mutable lists | Some hot components default | No strategy on the main list pages, `detectChanges()` in loops, index keys on editable lists |
| Lazy routes | All feature routes lazy (`loadChildren`/`loadComponent`, `lazy()`, `() => import()`); only the shell and the landing route eager | 1-30% of feature routes eager, or lazy routes without a preloading strategy on a large app | >30% eager or a single-chunk app |
| Bundle budgets | Budgets configured with an `error` threshold (Angular `maximumError`, Vite `chunkSizeWarningLimit` + CI size check, `size-limit`/`bundlesize`) and the build fails in CI when exceeded | Budgets configured but warning-only or not run in CI | None |
| Production build | `optimization`/`minify` on, `sourceMap` off (or hidden and not deployed), hashed filenames, licenses extracted, `namedChunks` off; CI passes the production configuration | One of the above off, or CI uses a configuration you could not confirm | Source maps in the deployed bundle, minification off, or dev server used in production |
| Lint config | ESLint config present with the framework plugin (`@angular-eslint`, `eslint-plugin-react-hooks`, `eslint-plugin-vue`), `lint` script runs without error, lint is a CI step | Config present but the script fails (missing package) or lint not in CI | No lint config |
| Legacy/modern mixing | No hits from `patterns/<stack>.json` in `src/` outside vendor/generated dirs | Hits confined to a few legacy areas (count them) | Hits spread across shared/core code |

## Severity mapping for findings

- Fail on Production build with source maps deployed: Medium (High if maps reveal internal
  hosts, keys, or the app is public-facing with sensitive logic).
- Fail on Production build with optimization/minification off: High.
- Fail on Strict type checking: Medium (Low if the codebase is small or a migration branch exists).
- Fail on Lazy routes: Medium for consumer apps (first-load cost), Low for internal tools.
- Fail on Component model due to an EOL platform (Vue 2, CRA): High, reference CWE-1104.
- Fail on Bundle budgets: Low (it is a missing guard rail, not a defect).
- Fail on Lint config: Low.
- Partial anything: Low or Info, unless the count is large enough to block a migration.

## Counting rules

- Count files, not lines, for mixing categories: "31/118 components use `*ngIf`".
- Exclude `node_modules`, `dist`, generated (`*.g.ts`, `api-client/` from OpenAPI), and
  `*.spec.ts`/`*.test.tsx` from the mixing counts; include them for the strict-mode count
  only if the spec tsconfig is part of the CI build.
- Routes: count route records with a `path` and either `component`/`element` or a lazy loader.
  Redirects, wildcards, and `children: []` containers are not counted.
- If the framework has no concept for a category (Vue has no OnPush; React has no budgets),
  mark `n/a` with the closest equivalent noted, and do not count it in the totals.
