# Angular reference for audit-report-generator

How frontend findings from an Angular (optionally Ionic/Capacitor) app should appear in
the final report: what the scope table enumerates, how to word client-side risks for a
non-engineer, and which frontend findings are launch blockers versus hygiene.

## Stack markers
`package.json` with `@angular/core`, `angular.json`, `src/app`, `src/environments/*.ts`,
`ngsw-config.json` (PWA), `capacitor.config.ts` (mobile shells). Report the Angular major
version and whether the app is served as a PWA and/or packaged for Android/iOS.

## Where the relevant code lives (what "Scope" must enumerate)
- Build configurations in `angular.json` (production: `optimization`, `sourceMap`, `budgets`).
- `src/environments/environment*.ts` (what ships to the browser; must not hold secrets).
- `core/interceptors`, `core/guards`, `core/services/{auth,storage,api}.service.ts`.
- Feature modules / lazy routes (`loadChildren`/`loadComponent`) - name the modules reviewed.
- i18n assets (`src/assets/i18n/*.json`) and RTL support if `audit-accessibility-and-i18n` ran.
- Out-of-repo for "Not checked": CDN/hosting headers, Capacitor native plugins' configuration, app store settings.

## Findings that are typical launch blockers (and how to phrase them)
| Engineering finding | Executive wording |
|---|---|
| `bypassSecurityTrustHtml(userContent)` / `nativeElement.innerHTML =` | "Content entered by one user can run code in another user's browser and take over their session." |
| JWT / refresh token in `localStorage` (even encrypted with a bundled key) | "A single injected script can steal every user's login and reuse it from anywhere." |
| Secret API keys in `environment.prod.ts` | "Keys that should be private are downloadable by every visitor." |
| Guards are the only access control (backend `[Authorize]` missing) | "Hiding a menu item does not stop a user from calling the function directly." (this is a backend blocker; cross-reference the authz finding) |
| `http://` API URL in production environment | "Logins and data travel unencrypted on the network." |

Hygiene (Medium/Low/Info, post-launch): missing `OnPush`, subscription leaks on rarely
visited pages, `sourceMap: true`, unused i18n keys, budget overruns.

## What "good" looks like (remediation plan wording)
- "Remove `bypassSecurityTrustHtml`; bind with `[innerHTML]` (Angular sanitizes) or sanitize with DOMPurify first and document why."
- "Keep the access token in memory in `AuthService`; use an HttpOnly refresh cookie; clear on logout."
- "Move keys out of `environment.prod.ts`; only public keys (Firebase web config) may remain - name them."
- "Set `sourceMap: false` in the production configuration in `angular.json`."
- "Use `takeUntilDestroyed()` in `ProductListComponent`."
Group tickets by service (`auth`/`storage` items), by component set (XSS items), by `angular.json` (build items).

## Report review checklist (manual trace)
1. Scope table lists the build configuration reviewed as production and the environment file it maps to.
2. Any client-side authorization finding is paired with the backend finding that is the real blocker; do not list a guard-only finding as Critical on its own.
3. PWA / service-worker caching of authenticated responses is stated as checked or not checked.
4. Mobile shells (Capacitor) are explicitly in or out of scope.
5. Evidence for storage findings is a DevTools screenshot or the exact `storage.service.ts` lines.

## Stack-specific false positives
- `bypassSecurityTrustResourceUrl` for a constant URL.
- `localStorage` holding theme/language/layout only.
- `[innerHTML]` on server-sanitized content (Angular re-sanitizes).
- Missing CSP meta tag when the server sends a CSP header (check the headers skill's evidence).

## Tooling (evidence to expect in Appendix B)
`npm audit --json`, `ng build --configuration production --stats-json` bundle report,
`@axe-core/cli` output for accessibility findings, Chrome DevTools heap snapshots for leak findings.
Export: `pandoc audit/audit-report.md -o audit/audit-report.docx --toc --from gfm`.

## References
Angular Security guide; Angular deployment guide; OWASP Cheat Sheets (DOM XSS Prevention, HTML5 Security);
ASVS 4.0.3 V3.2.3, V5.3.3, V8.2, V14.4.3; CWE-79, CWE-922, CWE-602.
Sibling skills: `audit-frontend-xss-and-dom-safety`, `audit-client-auth-and-storage`, `audit-frontend-best-practices`.
