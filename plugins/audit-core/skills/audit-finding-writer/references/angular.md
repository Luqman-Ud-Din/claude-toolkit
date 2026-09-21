# Angular reference for audit-finding-writer

## Stack markers
`package.json` with `@angular/core`, `angular.json`, `src/app`. Variants: NgModules vs standalone components; Ionic/Capacitor wrappers.

## Where the relevant code lives
`core/interceptors/`, `core/guards/`, `core/services/` (api, auth, storage), `environments/*.ts`, `*.component.ts|html`, `app.routes.ts`/`*-routing.module.ts`, `angular.json` build configs.

## Remediation idioms
- XSS: rely on template binding (`{{ }}`, `[innerHTML]` still sanitized); `DomSanitizer.bypassSecurityTrust*` only after sanitizing with `DOMPurify` and document why; no `ElementRef.nativeElement.innerHTML =`; no `eval`/`new Function`.
- Client auth: prefer HttpOnly cookie sessions; if a JWT must live in the browser keep it in memory, not `localStorage`; interceptor attaches `Authorization` only when `req.url.startsWith(environment.apiUrl)`; refresh via a single in-flight observable (`shareReplay(1)`); logout clears store, storage, and cancels timers.
- Guards: `CanActivateFn` for UX only; state in the finding that server-side authorization is the control.
- Secrets: nothing secret in `environment.*.ts` (they ship in the bundle); public keys only.
- Leaks: `takeUntilDestroyed()` / `DestroyRef`, `async` pipe, `ngOnDestroy` clears `setInterval`, observers, and third-party widgets (`chart.destroy()`).
- Best practice: `strict: true`, `strictTemplates`, `ChangeDetectionStrategy.OnPush`, `@if/@for` control flow, `loadComponent`/`loadChildren` lazy routes, `budgets` in `angular.json`, `sourceMap: false` for production, `optimization: true`.
- a11y/i18n: `aria-*` on custom controls, `cdkTrapFocus` in dialogs, `@angular/localize` or `ngx-translate` for every user-facing string, `formatDate`/`DatePipe` with locale and timezone, `dir="rtl"` support via logical CSS properties.
- Dates: parse ISO strings with offsets; never `new Date("2024-01-01")` for a local date.

## Recurring references
CWE-79 (XSS), CWE-922 (insecure storage), CWE-200, CWE-401/772 (leaks), CWE-1021 (clickjacking, with server headers), ASVS 5.3.3, 8.2, 3.x (session), 14.4; OWASP A03, A05, A07; WCAG 2.2 AA criteria 1.1.1, 1.3.1, 2.1.1, 2.4.3, 4.1.2.

## Stack-specific false positives
`bypassSecurityTrustResourceUrl` for a fixed, non-user-controlled iframe src; `localStorage` used only for UI preferences; `innerHTML` bound via `[innerHTML]` (sanitized by Angular).

## Tooling
`ng build --configuration production --stats-json` + `webpack-bundle-analyzer`, `ng lint` (needs `@angular-eslint`), `npx axe` / `@axe-core/cli`, Chrome DevTools heap snapshots, `npm audit`.
