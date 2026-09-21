# React (incl. Next.js, React Native) reference for audit-client-auth-and-storage

## Stack markers
`package.json` with `react`, `next`, `react-native`, `expo`. Libraries: `axios` (interceptors), `@tanstack/react-query`, `swr`, `redux-persist`, `zustand/middleware` `persist`, `next-auth`/`auth.js`, `@auth0/auth0-react`, `@azure/msal-react`, `react-oidc-context`, `js-cookie`, `jwt-decode`, RN: `@react-native-async-storage/async-storage` (NOT secure), `react-native-keychain`/`expo-secure-store` (secure).

## Where the relevant code lives
`src/api/client.ts`/`lib/axios.ts` (`axios.create`, `interceptors.request.use`), `src/auth/**`, `context/AuthContext.tsx`, `hooks/useAuth.ts`, `store/**` (`redux-persist` `whitelist`, `zustand` `persist` `partialize`), `components/PrivateRoute.tsx`/`ProtectedRoute.tsx`, `.env`, `.env.production`, `.env.local` (`REACT_APP_*`, `VITE_*`, `NEXT_PUBLIC_*` are public), `next.config.js` `env`/`publicRuntimeConfig`, Next.js `middleware.ts` (edge guard reading cookies - can be a real control when it verifies the JWT), `app/api/auth/**` (route handlers issuing cookies), `pages/_app.tsx`, Expo `app.config.js` `extra`.

## Dangerous / interesting APIs and patterns
- STORE: `localStorage.setItem('token'|'accessToken'|'refreshToken'|...)`, `sessionStorage.setItem(`, `redux-persist` persisting an `auth` slice, `zustand` `persist` without `partialize` excluding tokens, `Cookies.set('token', ...)` via `js-cookie` (script-readable), `AsyncStorage.setItem('token')` (plain file on device), `localStorage` under `useEffect` after login, `window.__INITIAL_STATE__` with tokens (SSR), Next.js `cookies().set(...)` without `httpOnly: true`.
- INTERCEPT: `axios.interceptors.request.use(cfg => { cfg.headers.Authorization = ... })` on the default `axios` instance (applies to every host), instance with `baseURL` but interceptor not checking `cfg.url` absolute URLs, `fetch` wrappers adding the header to any URL, `withCredentials: true` on the global default, token in `params`.
- REFRESH: `interceptors.response.use` on 401 calling refresh without a shared promise (`isRefreshing`/`failedQueue` pattern missing), retry loop without `_retry` flag, `jwtDecode(token).exp` comparisons in local time (ms vs s), `setInterval` refresh in a component without cleanup, `next-auth` `jwt` callback not rotating/refreshing (`RefreshAccessTokenError` unhandled).
- LOGOUT: `localStorage.removeItem('token')` only, `persistor.purge()` missing, `queryClient.clear()` missing (react-query cache keeps other users' data on shared devices), `axios` default header not deleted (`delete axios.defaults.headers.common.Authorization`), `signOut()` without server call for cookie sessions, RN `Keychain.resetGenericPassword` missing.
- GUARD: `<PrivateRoute>` / `<Navigate to="/login">` on `!user` - UX only; `middleware.ts` matcher gaps (guard applied to `/dashboard` but not `/api`), role checks via `jwtDecode` in components.
- SECRET: `.env.production` with `REACT_APP_SECRET`, `VITE_API_KEY`, `NEXT_PUBLIC_*` secrets (anything `NEXT_PUBLIC_` is in the bundle), `next.config.js` `env: { SECRET: process.env.SECRET }` (inlines at build), server-only secrets imported by a client component (`"use client"` file importing a server config), Expo `extra` in `app.config.js`, hard-coded `Authorization: 'Basic ...'`.
- TRANSPORT: `http://` API URLs in `.env.production`, `console.log(token)`, `postMessage(token, '*')`, RN deep links carrying tokens, `Linking.openURL` OAuth flows without PKCE.

## What "good" looks like
```ts
// api/client.ts - own-origin scoped, single-flight refresh
export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL, withCredentials: true }); // HttpOnly cookie session
let accessToken: string | null = null;            // memory only
let refreshing: Promise<string> | null = null;
api.interceptors.request.use(cfg => {
  const own = !cfg.url || !/^https?:/i.test(cfg.url) || cfg.url.startsWith(import.meta.env.VITE_API_URL);
  if (accessToken && own) cfg.headers.Authorization = `Bearer ${accessToken}`;
  return cfg;
});
api.interceptors.response.use(r => r, async err => {
  const cfg = err.config;
  if (err.response?.status === 401 && !cfg._retry) {
    cfg._retry = true;
    refreshing ??= api.post('/auth/refresh').then(r => r.data.accessToken).finally(() => (refreshing = null));
    accessToken = await refreshing; return api(cfg);
  }
  throw err;
});
export async function logout() { await api.post('/auth/logout'); accessToken = null; queryClient.clear(); persistor.purge(); location.assign('/login'); }
```
Next.js: session in an HttpOnly cookie set by a route handler; `middleware.ts` verifies the JWT signature (`jose`) - then it is a control, note that. React Native: `expo-secure-store`/`react-native-keychain` for refresh tokens.

## Manual trace checklist
1. Login handler -> where the response tokens are written (state, storage, cookie) and by which library.
2. Every `axios` instance and `fetch` wrapper: header condition; list absolute third-party URLs called through it.
3. 401 handling: single-flight, `_retry`, failure -> logout.
4. Logout: all writers (`grep -r "setItem\|persist\|Cookies.set" src`) vs what logout removes; react-query/SWR cache.
5. Guards: `PrivateRoute`, `middleware.ts` matcher, role checks - cross-reference the authz report.
6. `.env*` files and `next.config.js`: run `scan_secrets.py`; build (`npm run build`) and scan `build/`/`.next/static`/`dist/`.
7. RN/Expo: storage plugin used for tokens; deep-link handler; `app.config.js` `extra`.

## Stack-specific false positives
- `localStorage` for theme/locale/onboarding flags.
- `NEXT_PUBLIC_API_URL`, `VITE_API_URL`, Sentry DSN, GA id - public identifiers.
- `next-auth` with database sessions and HttpOnly cookies - good pattern; check `NEXTAUTH_SECRET` is server-only (not `NEXT_PUBLIC_`).
- `jwtDecode` for displaying the user name.
- `withCredentials: true` with a same-site cookie API.

## Tooling
- `npm run build` then `python scripts/scan_secrets.py <repo> --bundle build` (CRA) / `--bundle dist` (Vite) / `--bundle .next/static` (Next).
- `npx source-map-explorer build/static/js/*.js`.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/react.json`.
- Next.js: `next build` prints which env vars are inlined; `grep -r NEXT_PUBLIC_ .env*`.

## References
Next.js "Environment Variables" (public prefix) and "Authentication" docs; axios interceptors docs; OWASP Session Management and HTML5 Security cheat sheets; Expo SecureStore docs. CWE-522, CWE-922, CWE-798, CWE-613, CWE-539; ASVS 3.2.3, 3.3.x, 3.5.2, 8.2.2, 8.3.x, 14.3.x; OWASP A02:2021, A07:2021.
