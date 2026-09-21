# React (and Next.js) reference for audit-licensing-and-compliance

The frontend side of licence compliance for React SPAs and Next.js apps. The client
bundle is distributed to every browser (and to stores via React Native/Expo), so treat
the client as `--model proprietary` regardless of the backend model. Next.js server code
(API routes, server components) follows the backend rules (SaaS unless shipped on-prem).

## Stack markers
`package.json` with `react`, `react-dom`, `next`; `package-lock.json` / `pnpm-lock.yaml` /
`yarn.lock`; `vite.config.ts` / `next.config.js`; `public/` (static assets copied verbatim);
`app/` or `pages/`; `expo`/`react-native` for mobile (store distribution).

## Where the relevant code lives
- Runtime deps: `dependencies`; build-only: `devDependencies` (Vite, Next itself is a runtime dep for SSR, ESLint, testing).
- What ships: `npx vite-bundle-visualizer` / `@next/bundle-analyzer` - client chunks contain transitives; server chunks (Next) stay on your server.
- `public/` and `<link>`/`<script>` tags in `index.html` / `app/layout.tsx`: fonts, icon sets, CDN scripts not in `package.json`.
- `next/font/google` downloads Google Fonts at build time and self-hosts them (OFL - ship the licence); `next/font/local` uses files under `public/fonts` or `app/fonts`.
- Vendored code: `src/vendor/`, `lib/` folders copied from other projects (grep pass).
- Attribution: a `/licenses` route or About page rendering `THIRD-PARTY-NOTICES.md`; Vite has no automatic 3rd-party licence file (use `rollup-plugin-license` or `vite-plugin-license`); Next has none either. React Native/Expo: an "Open source licences" screen (`react-native-oss-license` or `expo-licenses`).

## Dangerous / interesting APIs and patterns
- Copyleft/commercial packages common in React apps: **ag-grid-enterprise**, **Highcharts** / **highcharts-react-official** (commercial), **amCharts**, **MUI X Pro/Premium** (commercial; `@mui/x-data-grid` community is MIT), **Kendo React / Syncfusion / DevExtreme** (commercial), **CKEditor 5** (GPL-2.0-or-later or commercial), **TinyMCE 7** (GPL-2.0+; 6 is MIT), **react-pdf** (MIT) vs **@react-pdf/renderer** (MIT), **pdfjs-dist** (Apache), **FullCalendar premium** (commercial), **Font Awesome Pro**, **react-icons** (MIT wrapper; each icon set has its own licence - Font Awesome CC-BY-4.0, Simple Icons CC0, etc.), **Mapbox GL JS 2+** (proprietary ToS - use `maplibre-gl` BSD for a free fork), **Google Maps JS** (ToS), **Lottie** (MIT; animations from LottieFiles have their own licences).
- `"license"` missing in small community hooks/components - unknown.
- `react-native` native modules: each brings a native SDK licence (analytics, ads, payment SDKs are proprietary with ToS).
- Static assets in `public/` (images, fonts, icons) without a licence note.
- `patch-package` patches on dependencies: modifying an LGPL/MPL package triggers the share-alike duty for that package.

## What "good" looks like
```ts
// vite.config.ts
import license from 'rollup-plugin-license';
export default { build: { rollupOptions: { plugins: [license({ thirdParty: { output: 'dist/THIRD-PARTY-NOTICES.txt', includePrivate: false } })] } } };
```
```jsonc
// package.json
"scripts": { "licenses:check": "license-checker --production --onlyAllow 'MIT;ISC;BSD-2-Clause;BSD-3-Clause;Apache-2.0;0BSD;CC0-1.0;OFL-1.1;CC-BY-4.0'" }
```
A `/licenses` page reads the generated file; mobile apps link it from Settings.

## Manual trace checklist
1. Analyse the client bundle: which packages are in client chunks (distributed) vs server-only.
2. `public/` and `<link>`/`<script>` tags: fonts, icons, CDN scripts - licence or ToS for each.
3. Grid/chart/editor/map libraries: edition and version; commercial keys configured?
4. `patch-package` / `pnpm patches`: is any patched package weak-copyleft?
5. Mobile (Expo/RN): native SDK licences and a licences screen.
6. Vendored GPL/AGPL code from the grep pass: remove or replace (High - the bundle is distributed).

## Stack-specific false positives
- `devDependencies` (Vite, Babel, ESLint, Jest, `@types/*`) - not in the bundle.
- `react`, `react-dom`, `next`, `@tanstack/*`, `zustand`, `redux` - MIT; `unknown` only when the cache is empty.
- `react-icons` itself is MIT; only the icon sets actually imported matter.
- Google Fonts via `next/font/google` - OFL; ship the licence text, no other obligation.

## Tooling
- `npx license-checker --production --json`, `pnpm licenses list --prod`, `yarn licenses list --production`.
- `rollup-plugin-license` / `vite-plugin-license` / `webpack-license-plugin` for automatic notices.
- `@next/bundle-analyzer`, `vite-bundle-visualizer` for what ships.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py --patterns scripts/patterns/react.json` - vendored GPL headers in JS/TS/TSX/CSS, copyleft manifest licences, git/URL deps, bundled fonts/icons, CDN scripts.

## References
npm licence field docs; rollup-plugin-license README; Font Awesome Free licence; SIL OFL FAQ; Mapbox ToS vs MapLibre;
SPDX licence list; ASVS 4.0.3 V14.2; CWE-1104.
Sibling skills: `audit-dependency-vulnerabilities` (CVEs), `audit-security-headers-and-middleware` (SRI for CDN scripts).
