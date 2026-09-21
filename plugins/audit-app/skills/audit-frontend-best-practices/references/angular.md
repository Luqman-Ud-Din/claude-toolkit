# Angular reference for audit-frontend-best-practices

## Stack markers

`package.json` with `@angular/core`, `angular.json` (or `project.json` in an
Nx workspace), `src/main.ts`. Read the major version from `@angular/core`; the
"current" idioms below assume v17+. Variants worth separating in the report:
NgModule-based vs standalone bootstrap (`bootstrapApplication` in `main.ts`),
Ionic/Capacitor wrappers (extra `ionic` budgets), SSR (`@angular/ssr`).

## Where the relevant code lives

- `tsconfig.json` (+ `tsconfig.app.json`, `tsconfig.spec.json`): `compilerOptions.strict`,
  `angularCompilerOptions.strictTemplates`, `strictInjectionParameters`,
  `strictInputAccessModifiers`. The app build uses `tsconfig.app.json` which
  `extends` the root; check the effective chain.
- `angular.json` -> `projects.<name>.architect.build`: `options.budgets`,
  `configurations.production.{optimization,sourceMap,outputHashing,namedChunks,
  extractLicenses,buildOptimizer,aot}` and `builder` (`@angular-devkit/build-angular:application`
  = esbuild, current; `:browser` = webpack, legacy; `:browser-esbuild` = transitional).
- Routes: `app.routes.ts`, `*.routes.ts`, `*-routing.module.ts` (`RouterModule.forRoot/forChild`).
- Components: `*.component.ts` (decorator metadata) and `*.component.html`.
- Lint: `.eslintrc.*` / `eslint.config.*` with `@angular-eslint`; `angular.json`
  `architect.lint` target.

## Dangerous / interesting APIs and patterns

- Strict: `"strict": false` or missing; `"strictTemplates": false`; `"noImplicitAny": false`;
  `// @ts-ignore`, `// @ts-nocheck`, `: any`, `as any`.
- Legacy component model: `@NgModule({ declarations: [...] })`, `standalone: false`,
  `entryComponents`, `ModuleWithProviders`.
- Legacy control flow: `*ngIf`, `*ngFor`, `*ngSwitch`, `[ngSwitch]` when the same repo
  also has `@if`/`@for`/`@switch` (mixing). `@for` without `track` is a compile error, so
  `trackBy` absence only matters for `*ngFor`.
- Change detection: `@Component` without `changeDetection: ChangeDetectionStrategy.OnPush`
  on list/table components; explicit `ChangeDetectionStrategy.Default`; `ChangeDetectorRef.detectChanges()`
  called in loops; `NgZone.run` everywhere.
- State: mixing `BehaviorSubject` services with NgRx / signals stores; `signal()` and
  `BehaviorSubject` for the same state; `@Input()` decorators next to `input()` signals.
- Routes: `component:` for feature areas (eager); `loadChildren` using the string syntax
  `'./x.module#XModule'` (removed in v9 but still seen); `preloadingStrategy` absent.
- Build: `sourceMap: true` in `production`; `optimization: false`; `outputHashing: "none"`;
  `budgets` missing or `maximumError` absent (warning only); `namedChunks: true` in prod;
  `"builder": "@angular-devkit/build-angular:browser"` on v17+.
- Bundle-hostile imports: `import * as _ from 'lodash'`, `import moment from 'moment'`,
  `import { ... } from '@angular/material'` (barrel), `rxjs/operators` full barrel is fine
  in v7+ but `import 'rxjs/Rx'` is not.
- Deprecated APIs: `ReflectiveInjector`, `ComponentFactoryResolver`, `ViewEngine`
  markers (`enableIvy: false`), `HttpModule`, `Renderer` (v1), `@angular/flex-layout`.

## What "good" looks like

```ts
// app.routes.ts
export const routes: Routes = [
  { path: '', loadComponent: () => import('./features/home/home.component').then(m => m.HomeComponent) },
  { path: 'reports', loadChildren: () => import('./features/reports/reports.routes').then(m => m.REPORTS_ROUTES) },
];
// product-list.component.ts
@Component({ standalone: true, changeDetection: ChangeDetectionStrategy.OnPush, imports: [CommonModule], ... })
export class ProductListComponent {
  products = input.required<Product[]>();
}
```
```html
@for (p of products(); track p.id) { <app-product-row [product]="p" /> } @empty { <p>No products</p> }
```
```json
// angular.json production
"optimization": true, "sourceMap": false, "outputHashing": "all", "namedChunks": false,
"budgets": [{ "type": "initial", "maximumWarning": "500kB", "maximumError": "1MB" },
            { "type": "anyComponentStyle", "maximumWarning": "4kB", "maximumError": "8kB" }]
```
```json
// tsconfig.json
"compilerOptions": { "strict": true, "noImplicitOverride": true, "noPropertyAccessFromIndexSignature": true },
"angularCompilerOptions": { "strictTemplates": true, "strictInjectionParameters": true }
```

## Manual trace checklist

1. `main.ts` -> root routes: which feature modules/components are imported statically? Each is
   in the initial chunk. Cross-check with `route_scan.py` and, if built, `bundle.json`.
2. The CI/deploy script (`package.json` `build:prod`, pipeline yaml): which `--configuration`
   does it pass? Read *that* block in `angular.json`, not `production` by assumption.
3. Largest list/table component (POS grid, dashboard): OnPush? `track` on `@for` / `trackBy`
   on `*ngFor`? Async pipe or manual subscribe?
4. `src/app/shared` and `src/app/core`: count `*ngIf` vs `@if`, `@Input()` vs `input()`,
   `standalone: false` vs `true`. Mixed = one finding with counts.
5. `tsconfig.app.json` overrides: a strict root can be undone by `"strict": false` in the app
   tsconfig; `config_check.py` resolves the chain but confirm by eye.

## Stack-specific false positives

- `*ngIf` inside a library `node_modules` or generated code: excluded by the shared walker's skip list (`repo_walk.SKIP_DIRS` in `../audit-code-scan`); do not count.
- `sourceMap: { "hidden": true }` is acceptable (maps produced for error tracking, not
  referenced from bundles) - check the deploy step does not copy `*.map`.
- `standalone: false` on a v19 app that sets `standalone` defaults explicitly during
  migration - a Partial, not Fail, if `ng generate` schematics default to standalone.
- Ionic apps commonly exceed default `anyComponentStyle` budgets; judge by the app's
  own budgets, not Angular CLI defaults.
- `ChangeDetectionStrategy.Default` on tiny leaf components with no inputs is harmless.

## Tooling

- `ng build --configuration production --stats-json` then `npx webpack-bundle-analyzer dist/<app>/stats.json`
  (webpack builder) or `npx esbuild-visualizer --metadata dist/<app>/stats.json` (application builder).
- `npx ng lint` (requires `@angular-eslint/builder` in devDependencies; if missing, that is
  itself a Partial for "Lint config").
- `npx @angular/cli@latest update --dry-run` lists outdated framework packages.
- Migrations that prove a category is fixable: `ng generate @angular/core:control-flow`,
  `ng generate @angular/core:standalone`, `ng generate @angular/core:signal-inputs`.
- `npx tsc -p tsconfig.app.json --noEmit --strict` to preview how many errors strict would add
  (count goes in the finding's Impact).

## References

- Angular style guide and update guide: https://angular.dev/style-guide, https://angular.dev/update-guide
- Budgets: https://angular.dev/tools/cli/build#configuring-size-budgets
- Control flow migration: https://angular.dev/reference/migrations/control-flow
- CWE-540 (source code exposure via source maps), CWE-1104 (unmaintained third-party components), ASVS-14.3.2 (debug modes disabled), ASVS-14.2.1 (components up to date).
