# Angular reference for audit-licensing-and-compliance

The frontend side of licence compliance. An Angular production bundle is *distributed* to
every browser (and, with Ionic/Capacitor, to app stores), so the frontend is always
`--model proprietary` even when the backend is SaaS: GPL/AGPL code in the bundle is a
distribution of that code, and every MIT/BSD/Apache/OFL component needs attribution
reachable from the app. The backend's obligations are covered by the backend stack file;
`audit-dependency-vulnerabilities` owns CVEs.

## Stack markers
`package.json` with `@angular/core`, `angular.json` (`assets`, `styles`, `scripts` arrays
pull in non-npm files), `package-lock.json` (v2/v3 carry `license` per package),
`src/assets/fonts`, `src/assets/i18n`, `capacitor.config.ts` (mobile = store distribution),
`ngsw-config.json` (PWA).

## Where the relevant code lives
- Runtime deps: `dependencies` in `package.json` - everything that ends up in `dist/`. `devDependencies` (Angular CLI, Karma, ESLint) are build-only.
- Bundle contents: `ng build --configuration production --stats-json` then `webpack-bundle-analyzer dist/.../stats.json` shows exactly which packages shipped (transitives included).
- `angular.json` `styles` / `scripts` / `assets`: CSS frameworks, icon fonts, third-party JS copied verbatim - not always in `package.json`.
- Fonts: `src/assets/fonts/*.woff2`, `@font-face` in SCSS, Google Fonts `<link>` in `index.html` (OFL - ship the licence).
- Icons: `@fortawesome/*` (Free = OFL/CC-BY/MIT split; Pro = commercial), `ionicons` (MIT), `@angular/material` icons (Apache-2.0).
- Vendored code: `src/vendor/`, `src/app/shared/lib/` copied from somewhere (grep pass finds GPL headers).
- CDN scripts in `index.html` (`<script src="https://...">`) - ToS, not package licence; also an SRI concern for `audit-security-headers-and-middleware`.
- Showing attribution: an About/Licenses page or route (`/licenses`) that renders `THIRD-PARTY-NOTICES.md`, or `assets/3rdpartylicenses.txt` - Angular CLI writes `dist/<app>/3rdpartylicenses.txt` automatically for bundled packages (`extractLicenses: true`, default in production). Mobile apps: an "Open source licences" screen is expected by app-store reviewers.

## Dangerous / interesting APIs and patterns
- Copyleft/commercial packages common in Angular apps: **ag-grid-enterprise**, **Highcharts** (commercial), **amCharts** (commercial without licence key), **Kendo UI / Syncfusion / DevExtreme** (commercial), **ngx-extended-pdf-viewer** (Apache; bundles pdf.js Apache - fine), **pdfjs-dist** (Apache), **jsPDF** (MIT), **html2canvas** (MIT), **CKEditor 5** (GPL-2.0-or-later or commercial - AGPL-style for SaaS use of newer versions), **TinyMCE** (MIT for 6; GPL-2.0+ for 7 - check the version), **FullCalendar premium** (commercial), **Font Awesome Pro** (commercial), **Chart.js** (MIT), **ngx-charts** (MIT), **moment** (MIT), **crypto-js** (MIT).
- `"license"` missing in small `ngx-*` community packages - unknown.
- Fonts with no licence file next to them in `assets/fonts/`.
- `extractLicenses: false` in `angular.json` production config removes the auto-generated `3rdpartylicenses.txt`.
- Capacitor/Cordova plugins: each has its own licence (most MIT/Apache); native SDKs (Firebase Apache, but some analytics SDKs are proprietary with ToS).

## What "good" looks like
```jsonc
// angular.json -> projects.app.architect.build.configurations.production
"extractLicenses": true,           // dist/3rdpartylicenses.txt generated on every build
"assets": [{ "glob": "THIRD-PARTY-NOTICES.md", "input": "./", "output": "/" }]
```
```ts
// licenses.component.ts: fetch('/3rdpartylicenses.txt') and render in a <pre>; linked from the About page and the mobile settings screen.
```
CI: `npx license-checker --production --onlyAllow "MIT;ISC;BSD-2-Clause;BSD-3-Clause;Apache-2.0;0BSD;CC0-1.0;OFL-1.1"`.

## Manual trace checklist
1. Build the production bundle (or read `stats.json`) and compare shipped packages with the inventory - transitive copyleft code is what matters in a bundle.
2. Open `angular.json` `styles`/`scripts`/`assets` for non-npm files and find their licences.
3. Fonts and icon sets: licence files present under `assets/fonts/`? Font Awesome Free vs Pro?
4. Rich-text editor and grid/chart libraries: which edition and version (CKEditor 5, TinyMCE 7, ag-grid, Highcharts)?
5. Is `3rdpartylicenses.txt` / a licences screen reachable from the UI? For Capacitor apps, does the store listing need it?
6. Vendored GPL/AGPL files found by the grep pass: replace or remove before launch (High - the bundle is distributed).

## Stack-specific false positives
- `devDependencies` (CLI, test runners, linters, `@types/*`) - never in the bundle.
- `@angular/*`, `rxjs`, `zone.js`, `tslib` - MIT; `unknown` only means the cache was empty.
- `3rdpartylicenses.txt` present in `dist/` means bundled-package attribution is already handled; the finding then only covers fonts/icons/vendored files.
- Google Fonts loaded from `fonts.googleapis.com` - OFL, attribution satisfied by shipping the licence text; no bundle.

## Tooling
- `npx license-checker --production --json`, `pnpm licenses list --prod`.
- `ng build --configuration production --stats-json` + `webpack-bundle-analyzer` / `source-map-explorer` for what actually ships.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py --patterns scripts/patterns/angular.json` - vendored GPL headers in TS/SCSS, copyleft manifest licences, git/URL deps, bundled fonts/icons, CDN scripts.

## References
Angular CLI `extractLicenses` option; npm licence field docs; Font Awesome Free licence; SIL OFL FAQ;
SPDX licence list; ASVS 4.0.3 V14.2; CWE-1104.
Sibling skills: `audit-dependency-vulnerabilities` (CVEs), `audit-security-headers-and-middleware` (SRI for CDN scripts).
