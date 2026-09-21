# Vue (2/3, Nuxt, Quasar) reference for audit-client-auth-and-storage

## Stack markers
`package.json` with `vue`, `nuxt`, `quasar`. Libraries: `axios`, `ofetch`/`$fetch` (Nuxt), `pinia` + `pinia-plugin-persistedstate`, `vuex-persistedstate`, `vue-router` (`beforeEach`), `@sidebase/nuxt-auth`, `nuxt-auth-utils`, `@auth0/auth0-vue`, `oidc-client-ts`, `js-cookie`, `useCookie` (Nuxt), `jwt-decode`, Quasar `LocalStorage`/`SessionStorage` plugins, Capacitor (same as Angular).

## Where the relevant code lives
`src/api/**`/`src/boot/axios.ts` (Quasar boot file with interceptors), `src/stores/auth.ts` (Pinia), `src/router/index.ts` (`beforeEach` guards), `src/plugins/**`, Nuxt: `plugins/api.ts` (`$fetch.create` with `onRequest`), `composables/useAuth.ts`, `middleware/auth.global.ts` (route middleware - client-side unless it runs on server), `server/api/auth/**` (cookie issuance), `nuxt.config.ts` `runtimeConfig` (`public` block ships to the client; top-level keys are server-only), `.env`, `.env.production` (`VITE_*`, `NUXT_PUBLIC_*` are public), `quasar.config.js` `env`.

## Dangerous / interesting APIs and patterns
- STORE: `localStorage.setItem('token'...)`, `sessionStorage.setItem(`, Pinia `persist: true` on the auth store (persists tokens by default) or `persist: { paths: [...] }` including `token`, `vuex-persistedstate` `paths` including auth, Quasar `LocalStorage.set('token')`, `useCookie('token')` set client-side (not HttpOnly), `Cookies.set('token')`, Nuxt `useState('token')` hydrated into the HTML payload (visible in page source), `Preferences.set` (Capacitor).
- INTERCEPT: `axios.interceptors.request.use` on the global instance; `$fetch.create({ onRequest({ options }) { options.headers.Authorization = ... } })` without checking `request` URL; `useFetch` default `headers` set globally in a plugin; `credentials: 'include'` globally; token in `query`.
- REFRESH: `onResponseError` 401 -> refresh without a shared promise; `beforeEach` decoding `exp` and refreshing on navigation only; `setInterval` refresh in `App.vue` not cleared; Nuxt server middleware refreshing but client keeping a stale copy in Pinia.
- LOGOUT: `token.value = null` in the store but persisted plugin still holds the old value until next write; `localStorage.removeItem` of one key; `$reset()` not called on other stores; `useCookie('token').value = null` for a non-HttpOnly cookie; no server call for HttpOnly sessions; `router.push('/login')` before clearing; `queryCache`/`useAsyncData` cache (`clearNuxtData()`) not cleared.
- GUARD: `router.beforeEach((to) => { if (to.meta.requiresAuth && !store.token) return '/login' })` - UX only; Nuxt `definePageMeta({ middleware: 'auth' })` - runs on server for SSR navigation, still not authorization; `v-if="isAdmin"` on admin UI.
- SECRET: `runtimeConfig.public.*` secrets (`public: { apiSecret }`), `.env.production` `VITE_*`/`NUXT_PUBLIC_*` secrets, `quasar.config.js` `build.env` secrets, `nuxt.config.ts` `app.head.script` with keys, hard-coded `Basic` headers, imported `firebase.json`/service-account files.
- TRANSPORT: `http://` API URL in production `runtimeConfig.public.apiBase`; `console.log(token)`; `postMessage(token, '*')`.

## What "good" looks like
```ts
// stores/auth.ts - memory-only access token; refresh via HttpOnly cookie
export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(null);          // not persisted
  let refreshing: Promise<string> | null = null;
  async function refresh() {
    refreshing ??= $fetch<{ accessToken: string }>('/api/auth/refresh', { method: 'POST', credentials: 'include' })
      .then(r => (accessToken.value = r.accessToken)).finally(() => (refreshing = null));
    return refreshing;
  }
  async function logout() { await $fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
    accessToken.value = null; useUserStore().$reset(); clearNuxtData(); await navigateTo('/login'); }
  return { accessToken, refresh, logout };
}, { persist: false });
// plugins/api.ts - own-origin scoped
export default defineNuxtPlugin(() => {
  const config = useRuntimeConfig(); const auth = useAuthStore();
  const api = $fetch.create({ baseURL: config.public.apiBase,
    onRequest({ request, options }) {
      const url = typeof request === 'string' ? request : request.url;
      const own = !/^https?:/i.test(url) || url.startsWith(config.public.apiBase);
      if (auth.accessToken && own) options.headers = { ...options.headers, Authorization: `Bearer ${auth.accessToken}` };
    } });
  return { provide: { api } };
});
```
`pinia-plugin-persistedstate`: `persist: { pick: ['user.name'] }` never `token`. Nuxt server-only secrets: top-level `runtimeConfig` keys (not `public`).

## Manual trace checklist
1. Login action in the auth store -> where tokens go (ref, persisted store paths, cookie flags).
2. Every axios/`$fetch` instance: header condition; list absolute third-party URLs.
3. 401 handling: single-flight, retry, failure -> logout.
4. Logout: all writers vs what logout clears; persisted-state plugin behaviour; `$reset` on stores; `clearNuxtData`.
5. Guards/middleware: `beforeEach`, `definePageMeta`, `v-if` role checks - cross-reference the authz report.
6. `nuxt.config.ts` `runtimeConfig.public`, `.env*`, `quasar.config.js`: run `scan_secrets.py`; build (`nuxi build`/`vite build`) and scan `.output/public`/`dist`.
7. Capacitor/Quasar mobile: storage plugin for tokens; deep links.

## Stack-specific false positives
- `localStorage` for theme/locale/layout.
- `runtimeConfig.public.apiBase`, Sentry DSN, GA id - public identifiers.
- `useCookie` reading a cookie the server set as HttpOnly - the client cannot read it; `useCookie` on the server side during SSR is fine.
- `jwtDecode` for display.
- `credentials: 'include'` with a same-site cookie API.

## Tooling
- `npm run build` then `python scripts/scan_secrets.py <repo> --bundle dist` (Vite) / `--bundle .output/public` (Nuxt).
- `npx nuxi analyze` / `npx vite-bundle-visualizer` to confirm what ships.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/vue.json`.

## References
Nuxt "Runtime Config" (public vs private) and "Sessions and Authentication" docs; pinia-plugin-persistedstate docs; OWASP Session Management and HTML5 Security cheat sheets. CWE-522, CWE-922, CWE-798, CWE-613, CWE-539; ASVS 3.2.3, 3.3.x, 3.5.2, 8.2.2, 8.3.x, 14.3.x; OWASP A02:2021, A07:2021.
