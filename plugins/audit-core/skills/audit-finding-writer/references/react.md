# React (and Next.js) reference for audit-finding-writer

## Stack markers
`package.json` with `react` (`next` for Next.js). Variants: CRA/Vite SPA vs Next.js app router with server components.

## Where the relevant code lives
`src/`, `app/` or `pages/` (Next), `hooks/`, `lib/api.ts`, `.env*` (`NEXT_PUBLIC_*`/`VITE_*` are public), `middleware.ts` (Next edge), `next.config.js`.

## Remediation idioms
- XSS: JSX escapes by default; `dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(x) }}` only, with a comment; no `href={userUrl}` without scheme allow-list; no `eval`.
- Client auth: HttpOnly cookie sessions (Next `cookies()` on the server) preferred; if using a bearer token keep it in memory/React state, not `localStorage`; `fetch` wrapper attaches credentials only to `API_BASE`; refresh with a single promise; logout clears query cache (`queryClient.clear()`), state, and storage.
- Route protection: client checks are UX; `middleware.ts` or server components enforce, and the API enforces again.
- Secrets: anything prefixed `NEXT_PUBLIC_`/`VITE_`/`REACT_APP_` is in the bundle; move secrets to server-only env and route via API routes.
- Leaks: `useEffect` cleanup returns for listeners, intervals, observers, subscriptions, `AbortController` for fetch; third-party widgets destroyed in cleanup.
- Best practice: `"strict": true` in tsconfig, function components + hooks only, `React.lazy`/dynamic imports per route, `productionBrowserSourceMaps: false`, ESLint `react-hooks` plugin, memoization only where profiling shows re-render cost, TanStack Query or SWR for request de-duplication and caching.
- a11y/i18n: semantic elements, `aria-*` on custom widgets, focus management in modals (`react-focus-lock`/Radix), `react-intl`/`i18next` for strings, `Intl.DateTimeFormat`/`Intl.NumberFormat`.
- Dates: `date-fns-tz`/`luxon`; parse API ISO strings with offsets.

## Recurring references
CWE-79, CWE-922, CWE-200, CWE-401, CWE-601 (open redirect via router), ASVS 5.3.3, 8.2, 3.x, 14.4; OWASP A03, A05, A07; WCAG 2.2 AA.

## Stack-specific false positives
`dangerouslySetInnerHTML` fed by a build-time Markdown pipeline with a sanitizer step; `localStorage` for theme/locale only; `NEXT_PUBLIC_` values that are genuinely public (analytics id, public map key with referrer restrictions).

## Tooling
`npm audit`, `npx eslint-plugin-react-hooks`, `npx @axe-core/cli`, `vite-bundle-visualizer` / `@next/bundle-analyzer`, React DevTools Profiler, Chrome heap snapshots.
