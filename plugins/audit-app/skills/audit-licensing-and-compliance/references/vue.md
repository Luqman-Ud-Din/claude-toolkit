# Vue (and Nuxt) reference for audit-licensing-and-compliance

The frontend side of licence compliance for Vue SPAs and Nuxt apps. The client bundle is
distributed to every browser, so treat the client as `--model proprietary` regardless of
the backend model. Nuxt server code (`server/api`, Nitro) follows backend rules (SaaS
unless shipped on-prem).

## Stack markers
`package.json` with `vue`, `nuxt`; `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock`;
`vite.config.ts` / `nuxt.config.ts` (`app.head.link/script`, `css`, `modules`); `public/`
(static assets copied verbatim); `assets/fonts`; Quasar/Capacitor/Tauri wrappers for
desktop/mobile (store distribution).

## Where the relevant code lives
- Runtime deps: `dependencies`; build-only: `devDependencies` (Vite, Nuxt CLI tooling, ESLint, Vitest).
- What ships: `npx nuxi analyze` / `vite-bundle-visualizer` - client chunks contain transitives; Nitro server chunks stay on your server.
- `nuxt.config.ts` `app.head.link` (Google Fonts, CDN CSS) and `app.head.script` (CDN JS): not in `package.json`.
- `@nuxtjs/google-fonts` / `@nuxt/fonts` download and self-host fonts (OFL - ship the licence); `assets/fonts` for local files.
- Nuxt modules (`modules: [...]`) pull their own dependency trees; each module has its own licence (most MIT).
- Vendored code: `src/vendor/`, `plugins/` copied from other projects (grep pass).
- Attribution: a `/licenses` page rendering `THIRD-PARTY-NOTICES.md`; Vite has no automatic licence file (use `rollup-plugin-license`); Quasar/Capacitor apps need an "Open source licences" screen.

## Dangerous / interesting APIs and patterns
- Copyleft/commercial packages common in Vue apps: **ag-grid-vue** enterprise, **Highcharts** / **highcharts-vue** (commercial), **amCharts**, **Kendo Vue / Syncfusion / DevExtreme** (commercial), **PrimeVue** (MIT; PrimeBlocks commercial), **Vuetify** (MIT), **Element Plus** (MIT), **CKEditor 5** (GPL-2.0-or-later or commercial), **TinyMCE 7** (GPL-2.0+), **Tiptap** (MIT; Pro extensions commercial), **FullCalendar premium**, **Font Awesome Pro**, **Mapbox GL JS 2+** (proprietary ToS; `maplibre-gl` BSD), **Google Maps** (ToS), **vue-pdf-embed** (MIT; pdfjs Apache), **Lottie** animations (per-file licence).
- `"license"` missing in small community components - unknown.
- Nuxt modules from GitHub (`github:user/nuxt-module`) - no registry metadata.
- Static assets in `public/` without a licence note.
- `patch-package` / `pnpm patches` on weak-copyleft packages trigger share-alike for that package.

## What "good" looks like
```ts
// nuxt.config.ts
export default defineNuxtConfig({
  vite: { build: { rollupOptions: { plugins: [license({ thirdParty: { output: '.output/public/THIRD-PARTY-NOTICES.txt' } })] } } },
  modules: ['@nuxt/fonts']   // self-hosts Google Fonts (OFL); ship the licence text
})
```
```jsonc
// package.json
"scripts": { "licenses:check": "license-checker --production --onlyAllow 'MIT;ISC;BSD-2-Clause;BSD-3-Clause;Apache-2.0;0BSD;CC0-1.0;OFL-1.1;CC-BY-4.0'" }
```
A `/licenses` page reads the generated file; packaged apps link it from Settings.

## Manual trace checklist
1. Analyse the client bundle: which packages are in client chunks (distributed) vs Nitro server-only.
2. `nuxt.config.ts` head links/scripts and `public/`: fonts, icons, CDN scripts - licence or ToS for each.
3. Grid/chart/editor/map libraries: edition and version; commercial keys configured?
4. Nuxt modules from git: upstream licence.
5. Packaged apps (Quasar/Capacitor/Tauri): licences screen present.
6. Vendored GPL/AGPL code from the grep pass: remove or replace (High - the bundle is distributed).

## Stack-specific false positives
- `devDependencies` (Vite, Nuxt devtools, ESLint, Vitest, `@types/*`) - not in the bundle.
- `vue`, `nuxt`, `pinia`, `vue-router`, `@vueuse/*` - MIT; `unknown` only when the cache is empty.
- `@nuxt/fonts` / Google Fonts - OFL; ship the licence text only.
- Nuxt server-only packages (Nitro presets, DB drivers) follow backend rules, not bundle rules.

## Tooling
- `npx license-checker --production --json`, `pnpm licenses list --prod`, `yarn licenses list --production`.
- `rollup-plugin-license` / `vite-plugin-license` for automatic notices; `npx nuxi analyze` for what ships.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py --patterns scripts/patterns/vue.json` - vendored GPL headers in JS/TS/Vue/CSS, copyleft manifest licences, git/URL deps, bundled fonts/icons, CDN scripts (incl. `nuxt.config` head scripts).

## References
npm licence field docs; rollup-plugin-license README; Nuxt `app.head` docs; SIL OFL FAQ;
SPDX licence list; ASVS 4.0.3 V14.2; CWE-1104.
Sibling skills: `audit-dependency-vulnerabilities` (CVEs), `audit-security-headers-and-middleware` (SRI for CDN scripts).
