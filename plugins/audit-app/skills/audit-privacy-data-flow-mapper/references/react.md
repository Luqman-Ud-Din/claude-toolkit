# React reference for audit-privacy-data-flow-mapper

The frontend collects personal data (forms), caches it in the browser, shows
it, and leaks it to client-side vendors (analytics, error tracking, session
replay). The backend stack file owns storage, server logs and server-to-vendor
flows. Next.js/Remix blur the line: `app/api/**`, server actions and
`middleware.ts` are server code - apply `node-express.md` rules to them.
Browser storage security belongs to `audit-client-auth-and-storage`.

## Stack markers
`package.json` with `react` (+ `next`, `remix`, `gatsby`, `vite`). Variants:
Next.js App Router (server components, server actions), React Native (AsyncStorage,
push tokens), Redux Persist / Zustand persist middleware.

## Where the relevant code lives
- Collection: form components (`<input name="email">`, react-hook-form `register('email')`,
  Formik `Field`), upload components, `types/*.ts` shapes mirroring API DTOs.
- Browser storage: `localStorage`/`sessionStorage` helpers, `redux-persist` config
  (`whitelist`), `zustand/middleware persist`, IndexedDB (`idb`, Dexie), React Query
  `persistQueryClient` (cached API responses), service worker caches, cookies set client-side.
- Client-side processors: `console.*`, analytics hooks (`useAnalytics`, `gtag`,
  `posthog`, `segment`), `Sentry.setUser`, `@vercel/analytics`, LogRocket/FullStory session replay.
- Transmission: API client (`axios.create`, `fetch` wrappers), direct calls to third-party hosts
  (maps, address lookup, Stripe Elements), Next.js server actions posting to vendors.
- Templates: React email (`react-email`, `@react-email/components`) rendered on the server - a template source.

## Dangerous / interesting APIs and patterns
- `console.log(user)` in components/hooks left in production builds.
- `localStorage.setItem('profile', JSON.stringify(user))`; `redux-persist` `whitelist: ['auth', 'user']`.
- `gtag('event', ..., { email })`, `posthog.identify(email, { name })`, `Sentry.setUser({ email })`,
  `LogRocket.identify(userId, { email })`.
- `fetch(\`/api/users?email=${email}\`)` - PII in query string; Next.js `searchParams` with PII.
- `<Script src="https://www.googletagmanager.com/...">` / Hotjar / Clarity in `_app`/`layout` without input masking.
- React Query `persistQueryClient` persisting customer lists to localStorage.
- Server actions / route handlers posting to `api.hubapi.com` etc. with the full form payload.
- `dangerouslySetInnerHTML` of user-supplied content - XSS topic, but note it renders PII.

## What "good" looks like
```ts
posthog.identify(user.id);                       // pseudonymous id, no traits with PII
Sentry.init({ sendDefaultPii: false, beforeSend: scrub });
persist(store, { name: 'ui', partialize: (s) => ({ theme: s.theme }) });   // no user slice persisted
```

## Manual trace checklist
1. The API client + `types/`: every PII field that leaves the browser (request shapes) and arrives (response shapes).
2. Persistence config (`redux-persist`, `zustand persist`, React Query persister): which slices hold PII?
3. Analytics/error/replay SDK init: `identify`/`setUser` payloads and `sendDefaultPii`.
4. Third-party `<Script>` tags and their masking attributes.
5. Next.js server code: route handlers, server actions and middleware that call vendors (apply `node-express.md`).
6. React Native: AsyncStorage / SecureStore contents, push token registration.

## Stack-specific false positives
- `console.log` stripped by the bundler (`drop_console`/`babel-plugin-transform-remove-console`) - check the build config before reporting.
- `email` inputs on login/signup forms - expected collection.
- `{user.email}` JSX display - not a flow edge.

## Tooling
- `python scripts/pii_scan.py <repo> ...`; `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/react.json`
- `grep -rn "persist\|localStorage\|AsyncStorage" src app`
- `grep -rn "identify(\|setUser(" src app`
- `grep -rn "https\?://" src app | grep -v localhost` for direct third-party hosts

## References
GDPR Art.5(1)(c), Art.25, Art.28; ePrivacy; CWE-532, CWE-359, CWE-922, CWE-598;
ASVS 8.2, 8.3. Sibling skills: `audit-client-auth-and-storage`,
`audit-frontend-xss-and-dom-safety`; backend flows: `node-express.md`.
