# React reference for audit-frontend-best-practices

## Stack markers

`package.json` with `react` (+ `react-dom`); `next` marks Next.js. Bundler is
told by `vite.config.*` (Vite), `next.config.*` (Next), `react-scripts` in
scripts (CRA, legacy), `webpack.config.*`, or `remix.config.*`/`@remix-run`.
Read the `react` major: 18+ enables concurrent features; 19 adds `use`, form
actions, and deprecates `forwardRef`-heavy patterns.

## Where the relevant code lives

- `tsconfig.json`: `strict`, `noImplicitAny`, `strictNullChecks`, `jsx` (`react-jsx` is
  current; `react` needs the old `import React`). JS-only projects: check for
  `// @ts-check` or `checkJs`; absence is a Fail for "Strict type checking" only if the
  repo claims TypeScript.
- `vite.config.*`: `build.sourcemap`, `build.minify`, `build.rollupOptions.output.manualChunks`,
  `build.chunkSizeWarningLimit` (the only built-in "budget").
- `next.config.*`: `productionBrowserSourceMaps`, `swcMinify` (default true 13+), `compress`,
  `experimental.optimizePackageImports`, `images`.
- CRA: `GENERATE_SOURCEMAP` in `.env.production`; `react-scripts` version (CRA is unmaintained -
  Partial at best for "Production build" unless ejected/migrated).
- Routes: `react-router` (`createBrowserRouter`, `<Routes>`), `@tanstack/react-router`,
  Next `app/` (file-based, lazy by default) or `pages/`.
- Lint: `eslint.config.*` / `.eslintrc.*` with `eslint-plugin-react-hooks` and `eslint-plugin-react`.

## Dangerous / interesting APIs and patterns

- Legacy component model: `extends React.Component`, `extends Component`, `extends PureComponent`,
  `createReactClass`, `this.setState` alongside hooks elsewhere (mixing).
- Deprecated lifecycles: `componentWillMount`, `componentWillReceiveProps`,
  `componentWillUpdate`, `UNSAFE_componentWill*`.
- Legacy roots and APIs: `ReactDOM.render(` (18+ needs `createRoot`), `ReactDOM.hydrate(`,
  `findDOMNode`, string refs (`ref="x"`), `React.createFactory`, legacy `Context` (`contextTypes`).
- Type discipline: `: any`, `as any`, `PropTypes` in a TypeScript project, `React.FC<any>`.
- Rendering cost: `useEffect` with `[]` that sets state from props (derived state), inline object
  props on memoized children, list rendering without `key` or with `key={index}` on mutable lists,
  no `React.memo`/`useMemo` on heavy tables.
- Routes: `<Route path="/x" element={<X />} />` where `X` is a static import (eager); no
  `<Suspense>` boundary around lazy routes; Next `pages/` with barrel imports of heavy libs.
- Build: `sourcemap: true` in `vite.config` build block; `productionBrowserSourceMaps: true`;
  `GENERATE_SOURCEMAP=true`; `minify: false`.
- Bundle-hostile imports: `import _ from 'lodash'`, `import moment from 'moment'`,
  `import * as Icons from 'react-icons/fa'`, `import { Button } from '@mui/material'`
  (fine with modern bundlers, but check `optimizePackageImports`/babel plugin on older ones).
- State: two global stores (Redux + Zustand + Context all holding server data), no server-state
  library while hand-rolling fetch caches in `useEffect`.

## What "good" looks like

```tsx
// router.tsx
const Reports = lazy(() => import('./features/reports/Reports'));
export const router = createBrowserRouter([
  { path: '/', element: <Home /> },
  { path: '/reports', element: <Suspense fallback={<Spinner />}><Reports /></Suspense> },
]);
// ProductTable.tsx
export const ProductTable = memo(function ProductTable({ rows }: { rows: Product[] }) {
  const sorted = useMemo(() => [...rows].sort(byName), [rows]);
  return <>{sorted.map(r => <Row key={r.id} row={r} />)}</>;
});
```
```ts
// vite.config.ts
export default defineConfig({ build: { sourcemap: false, minify: 'esbuild', chunkSizeWarningLimit: 500,
  rollupOptions: { output: { manualChunks: { vendor: ['react', 'react-dom'] } } } } });
```
```js
// next.config.js
module.exports = { productionBrowserSourceMaps: false, compress: true, reactStrictMode: true };
```

## Manual trace checklist

1. Entry (`main.tsx` / `_app.tsx` / `app/layout.tsx`): which feature components are imported
   statically? Those are in the initial chunk; compare with `route_scan.py`.
2. The build script CI runs (`vite build --mode`, `next build`): read the matching config
   branch; Vite `mode`-specific settings can re-enable sourcemaps.
3. Heaviest table/list: `memo`, stable keys, `useMemo` for derived arrays, virtualization if
   >200 rows. `React DevTools Profiler` counts if available.
4. Count class components vs function components; deprecated lifecycles are a Fail regardless
   of count.
5. Next.js only: `pages/` vs `app/` mixing, `getServerSideProps` on static pages,
   `next/image` vs `<img>` (Partial in "Production build" if images unoptimized).

## Stack-specific false positives

- Error boundaries must be class components (`componentDidCatch` has no hook) - do not count
  them as legacy.
- `React.Component` inside `node_modules` types or `.d.ts` files: skip.
- `key={index}` on a static, never-reordered list is acceptable; only mutable/reorderable
  lists are findings.
- `sourcemap: 'hidden'` in Vite is fine when maps are uploaded to an error tracker and not
  deployed.
- Next `app/` router routes are code-split automatically; `route_scan.py` reports them as lazy
  by convention.

## Tooling

- `npx vite build --mode production` then `npx vite-bundle-visualizer` or
  `rollup-plugin-visualizer` (already a devDependency in many repos).
- `ANALYZE=true npx next build` with `@next/bundle-analyzer`.
- `npx eslint . --ext .ts,.tsx` (requires `eslint-plugin-react-hooks`; missing rule
  `react-hooks/exhaustive-deps` is a Partial for "Lint config").
- `npx tsc --noEmit --strict` to count errors strict mode would introduce.
- `npx react-codemod` (`rename-unsafe-lifecycles`, `class-to-function` via `react-declassify`).

## References

- React docs "Legacy React APIs" and "Rules of React": https://react.dev/reference/react/legacy, https://react.dev/reference/rules
- Vite build options: https://vitejs.dev/config/build-options.html
- Next.js `productionBrowserSourceMaps`: https://nextjs.org/docs/app/api-reference/config/next-config-js/productionBrowserSourceMaps
- CWE-540 (source maps expose source), CWE-1104 (unmaintained components, e.g. CRA), ASVS-14.3.2, ASVS-14.2.1.
