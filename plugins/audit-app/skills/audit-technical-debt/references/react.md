# React reference for audit-technical-debt

Framework-idiom debt (class components, `UNSAFE_` lifecycles, legacy root API, string
refs, PropTypes in TS, CRA, derived-state effects) is detected by
`audit-frontend-best-practices` (FEBP); effect cleanup by `audit-frontend-memory-leak`
(FELEAK). This skill consumes those and adds end-of-life, hotspots, duplication, dead
components, TODO age, suppressions, archived libraries and mixed library choices.

## Stack markers

`package.json` with `react` and `react-dom`; `vite.config.*`, `next.config.*`, or
`react-scripts`. Variants: Next.js pages router (`pages/`) vs app router (`app/**/page.tsx`),
Remix, React Native (`react-native` - mobile-specific upgrade debt is larger).

## Where the relevant code lives

- Hotspots: page-level components (`pages/`, `app/**/page.tsx`, `routes/`), form
  components with validation, table/grid components, custom hooks (`use*.ts`) with
  several effects, `store/` reducers or slices.
- Suppressions: `// eslint-disable-next-line react-hooks/exhaustive-deps` (the most
  meaningful one: a stale-closure bug waiting to happen), `@ts-ignore`, `@ts-expect-error`
  without a reason, `/* eslint-disable */` file headers.
- Currency: `react` major (only the latest major gets fixes: 18 stopped when 19 shipped on
  2024-12-05), `next` major, `react-router` major, `engines.node`.

## Dangerous / interesting APIs and patterns

Mirrored in `scripts/patterns/react.json` (only what FEBP does not already grep).
- **Archived / deprecated libraries**: Enzyme (no React 18/19 adapter - blocks upgrades),
  `react-dom/test-utils` and `react-test-renderer` (deprecated in 19), Recoil (archived),
  `react-helmet` (unmaintained).
- **Inconsistent patterns**: Redux + Zustand + MobX + Context stores; TanStack Query +
  SWR + `useEffect` fetching; styled-components + CSS modules + Tailwind; axios + fetch;
  moment + date-fns.
- **Complexity shapes**: components over 300 lines with nested ternaries in JSX (each
  ` ? ` counts as a branch), `useEffect` chains that sync state to state, reducers with a
  30-case `switch`, prop drilling through five levels.
- **Dead code**: components never imported, exported hooks with no callers, Storybook
  stories for deleted components, feature flags that are always on.

## What "good" looks like

A supported React major, one server-state library, one client-state approach, one
styling system, component files under ~250 lines with logic in hooks that have tests,
and `react-hooks/exhaustive-deps` suppressions each explained:

```tsx
// eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount; onReady is a stable ref from the parent
```

## Manual trace checklist

1. Count `react-hooks/exhaustive-deps` suppressions per file; the top files are both
   debt and bug risk.
2. Top hotspot component: split rendering, data fetching and business rules; list what a
   test would need to pin.
3. Upgrade blockers: Enzyme tests, libraries pinned to an old React peer range
   (`npm ls react`), class components (FEBP counts).
4. Dead-component candidates: check Next.js file routes, `React.lazy(() => import(...))`
   with computed paths, Storybook, MDX.
5. Mixed state/data libraries: which one new code uses; the rest is migration debt.

## Stack-specific false positives

- Next.js and Remix file-based routes (`page.tsx`, `layout.tsx`, `route.ts`, `pages/*`)
  are never imported; `dead_code.py` treats them as entry points.
- JSX ternaries and `&&` render guards inflate the keyword-count complexity of view
  components; compare with cognitive complexity before rating.
- Test files with repeated `render(<X />)` setups show up as duplicates; impact is lowered.

## Tooling

- `npx knip` (React, Next, Vite, Storybook plugins) for unused files, exports and dependencies.
- `npx eslint src --rule '{"complexity": ["warn", 15], "max-lines-per-function": ["warn", 120]}' -f json`;
  `eslint-plugin-sonarjs` for cognitive complexity; `react/no-deprecated`.
- `npx jscpd --min-lines 6 --reporters json src`, `npm outdated --json`, `npx npm-check-updates`
  (listing only), `npm ls react` for peer-range blockers.

## References

CWE-1121, CWE-1080, CWE-561, CWE-1041, CWE-477, CWE-1104, CWE-546. React versioning
policy: https://react.dev/community/versioning-policy ; React 19 upgrade guide:
https://react.dev/blog/2024/04/25/react-19-upgrade-guide ; sibling skills:
`audit-frontend-best-practices`, `audit-frontend-memory-leak`.
