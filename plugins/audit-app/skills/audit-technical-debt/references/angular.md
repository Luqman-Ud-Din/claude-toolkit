# Angular reference for audit-technical-debt

Framework-idiom debt in Angular (legacy control flow, NgModules beside standalone,
deprecated Angular/RxJS APIs, `any`, `@ts-ignore` sprawl, eager routes) is detected by
`audit-frontend-best-practices` (prefix FEBP) and teardown leaks by
`audit-frontend-memory-leak` (FELEAK). This skill consumes those findings and adds what
they do not measure: framework end-of-life, complexity and churn hotspots, duplication,
dead components, TODO age, suppressions, tooling deprecations and mixed library choices.

## Stack markers

`package.json` with `@angular/core`; `angular.json`; `tsconfig.app.json`. Variants:
Ionic/Capacitor apps (`@ionic/angular`, `capacitor.config.ts`), Nx workspaces
(`nx.json`, `project.json`), Angular Universal/SSR (`server.ts`).

## Where the relevant code lives

- Hotspots: `src/app/features/**/*.component.ts` for list/detail/editor screens,
  `core/services/*.service.ts` (API wrappers, auth, storage), `shared/` utilities that
  every feature imports. Templates (`.html`) are not measured by `complexity.py`; long
  templates with nested `*ngIf`/`@if` need a manual look.
- Suppressions: `// eslint-disable`, `// @ts-ignore`, `// @ts-nocheck`, `"rules": {"x": "off"}`
  in `.eslintrc.json` / `eslint.config.js`, `angularCompilerOptions.strictTemplates: false`.
- Currency: `@angular/core` major (18-month support per major: 19 ended 2026-05-19,
  20 ends 2026-11-28), `rxjs` major, `typescript`, `zone.js`, Ionic/Capacitor majors,
  `engines.node`.

## Dangerous / interesting APIs and patterns

Mirrored in `scripts/patterns/angular.json` (only what FEBP does not already grep).
- **Tooling past EOL**: TSLint (`tslint.json`, `@angular-devkit/build-angular:tslint`),
  Protractor (`protractor.conf.js`), `@angular/flex-layout`; `@angular/animations`
  deprecated since v20.2 (plan, not urgent).
- **Inconsistent patterns**: `HttpClient` beside `fetch`/axios (bypasses interceptors);
  NgRx beside `BehaviorSubject` services beside signals stores; Angular Material +
  PrimeNG + Ionic components for the same controls; moment + date-fns + dayjs;
  reactive forms beside `[(ngModel)]`.
- **Complexity shapes**: components over 500 lines doing API calls, mapping and
  permission checks; `ngOnInit` with 100+ lines; services chaining five `subscribe`
  callbacks; `switch` on route params to render different screens.
- **Dead code**: components declared but never routed or used by selector, pipes and
  directives never referenced in templates, `environment.*.ts` keys nobody reads,
  translation keys without usage (i18n audit owns the key check).

## What "good" looks like

A supported Angular major updated with `ng update` every six months, one state approach,
one HTTP path through `HttpClient` + interceptors, feature components under ~300 lines
with logic in services or signals stores, angular-eslint in CI with `complexity` and
`max-lines-per-function` warnings, and suppressions with reasons:

```ts
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- payload shape comes from the FBR API, typed in #512
```

## Manual trace checklist

1. `npx ng update` (no package arguments: it only lists) - how many majors behind, and
   which third-party libraries (PrimeNG, Ionic, ngx-*) block the next major.
2. Top hotspot component: separate view logic from business rules; which rules also exist
   on the backend (duplicated rules drift).
3. Dead-component candidates: search selectors in `.html`, `loadComponent`/`loadChildren`,
   dialogs opened by class (`dialog.open(MyComponent)`), `entryComponents`, Ionic modals.
4. Mixed libraries: count usages per variant; the minority variant is the quick win.
5. Cross-check FEBP findings for the same files before writing a debt item; link, do not repeat.

## Stack-specific false positives

- Components used only in templates by selector or opened by class reference are
  found by name search; components registered through `CUSTOM_ELEMENTS_SCHEMA` or
  dynamic `ViewContainerRef.createComponent(type)` from a map may look unused.
- `*.spec.ts` TestBed boilerplate duplicates heavily; `duplicates.py` flags test-only clones
  with lower impact.
- `lint` configured in `angular.json` without `@angular-eslint` installed means the
  project has no working lint - that is a FEBP finding, not a suppression.

## Tooling

- `npx knip` (Angular plugin: unused files, exports, dependencies), `npx ts-prune -p tsconfig.app.json`.
- `npx eslint "src/**/*.ts" --rule '{"complexity": ["warn", 15], "max-lines-per-function": ["warn", 80]}' -f json`
  (requires angular-eslint; if it is not installed, run in a scratch copy - never install into the repo).
- `npx jscpd --min-lines 6 --reporters json src/app`, `npm outdated --json`, `npx ng update`.
- SonarQube TypeScript analysis covers cognitive complexity per component method.

## References

CWE-1121, CWE-1080, CWE-561, CWE-1041, CWE-477, CWE-1104, CWE-546. Angular support
policy: https://angular.dev/reference/releases ; update guide: https://angular.dev/update-guide ;
sibling skills: `audit-frontend-best-practices`, `audit-frontend-memory-leak`.
