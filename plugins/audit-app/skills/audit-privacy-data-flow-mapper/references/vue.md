# Vue reference for audit-privacy-data-flow-mapper

The frontend collects personal data (forms), caches it in the browser (Pinia/
Vuex persisted state, localStorage), displays it, and leaks it to client-side
vendors (analytics, error tracking, session replay). The backend stack file owns
storage, server logs and server-to-vendor flows. Nuxt `server/**` is server code
- apply `node-express.md` rules there. Browser storage security belongs to
`audit-client-auth-and-storage`.

## Stack markers
`package.json` with `vue` / `nuxt`. Variants: Vue 2 + Vuex vs Vue 3 + Pinia,
`pinia-plugin-persistedstate` / `vuex-persistedstate`, Nuxt 3 (`useFetch`,
`server/api`), Quasar/Vuetify forms, Capacitor/Cordova builds.

## Where the relevant code lives
- Collection: `v-model="form.email"` in components, VeeValidate/Vuelidate schemas,
  upload components, `types/` or `models/` mirroring API DTOs.
- Browser storage: `stores/*.ts` with `persist: true` (Pinia) or `createPersistedState`
  (Vuex), `localStorage` helpers, `useStorage` (VueUse), IndexedDB, Nuxt `useCookie`
  (client-set cookies), service-worker caches (PWA plugin).
- Client-side processors: `console.*`, `vue-gtag`/`vue-analytics`, `@sentry/vue` `setUser`,
  `posthog-js`, Hotjar/Clarity tags in `index.html` or `nuxt.config` `app.head.script`.
- Transmission: API plugin (`axios` instance, `$fetch` wrapper) - the single place to see what leaves the browser;
  direct calls to third-party hosts; Nuxt server routes calling vendors.
- Templates: Nuxt email templates (`vue-email`) rendered server-side.

## Dangerous / interesting APIs and patterns
- `console.log(user)` in components / composables in production builds.
- Pinia `persist: true` on a `user`/`auth` store holding email/phone/profile; Vuex persisted `user` module.
- `this.$gtag.event('signup', { email })`, `posthog.identify(email)`, `Sentry.setUser({ email })`.
- `useFetch(\`/api/users?email=${email}\`)`, `router.push({ query: { email } })` - PII in URL/history.
- `nuxt.config` `app.head.script` loading GTM/Hotjar/Clarity without masking; `useCookie('profile')` with PII.
- `useStorage('profile', user)` (VueUse) - reactive persistence of the whole profile.
- Nuxt `server/api/*.post.ts` forwarding the request body to a vendor.

## What "good" looks like
```ts
export const useUserStore = defineStore('user', { state: () => ({ id: '', roles: [] }),
  persist: { pick: ['id', 'roles'] } });          // no contact data persisted
Sentry.init({ app, sendDefaultPii: false, beforeSend: scrub });
posthog.identify(user.id);
```

## Manual trace checklist
1. API plugin + models: PII fields in request/response shapes.
2. Store persistence config: which state is persisted and where (`localStorage`, cookies).
3. Analytics/error SDK init and `identify`/`setUser` payloads.
4. Third-party tags in `index.html` / `nuxt.config` and masking attributes.
5. Nuxt server routes calling vendors (apply `node-express.md`).
6. Capacitor/Cordova storage plugins on mobile builds.

## Stack-specific false positives
- `console.log` removed by `vite`/`terser` `drop_console` - check `vite.config`/`nuxt.config` before reporting.
- `v-model="form.email"` on login forms - expected collection.
- `{{ customer.email }}` display bindings - not a flow edge.

## Tooling
- `python scripts/pii_scan.py <repo> ...`; `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/vue.json`
- `grep -rn "persist\|useStorage\|localStorage\|useCookie" src stores composables`
- `grep -rn "identify(\|setUser(" src`
- `grep -rn "https\?://" src nuxt.config.* | grep -v localhost` for direct third-party hosts

## References
GDPR Art.5(1)(c), Art.25, Art.28; ePrivacy; CWE-532, CWE-359, CWE-922, CWE-598;
ASVS 8.2, 8.3. Sibling skills: `audit-client-auth-and-storage`,
`audit-frontend-xss-and-dom-safety`; backend flows: `node-express.md`.
