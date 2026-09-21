# Vue reference for audit-gdpr-data-protection

The backend owns rights endpoints, retention, server logs and processors
(backend stack file). The Vue surface is consent UX, rights UI, persisted
stores, client-side vendors, and - for Nuxt - `server/**` code, which follows
`node-express.md`.

## Stack markers
`package.json` with `vue` / `nuxt`. Variants: Pinia vs Vuex persisted state,
Nuxt 3 server routes, Capacitor/Cordova mobile builds.

## Where the relevant code lives
- Consent UI: signup forms (`v-model="form.marketingConsent"`), cookie-consent components (`vue-cookie-consent`, custom), policy version constants.
- Rights UI: account/settings views (`deleteAccount`, `downloadData`, consent preferences) and the API plugin calls.
- Client persistence: Pinia `persist`, `vuex-persistedstate`, `useStorage`, `useCookie`, `localStorage`.
- Client-side vendors: `index.html` / `nuxt.config` `app.head.script` (GTM, Hotjar, Clarity), `vue-gtag`, `@sentry/vue`, PostHog.
- Nuxt server: `server/api/**`, `server/middleware/**` - logging and vendor calls (apply `node-express.md`).

## Dangerous / interesting APIs and patterns
- Consent state initialised `true`; one checkbox for T&Cs + marketing.
- Consent posted as a bare boolean without policy version.
- Missing rights UI although endpoints exist (or UI actions calling non-existent endpoints).
- Tracking scripts in `nuxt.config` head loaded unconditionally; `vue-gtag` without `bootstrap: false` / consent plugin.
- `Sentry.setUser({ email })`, replay without masking.
- Persisted `user` store not cleared on logout/erasure.
- `router.push({ query: { email } })`.
- Nuxt server route forwarding form payloads to a marketing vendor regardless of consent.

## What "good" looks like
```vue
<input type="checkbox" v-model="form.marketingConsent" />   <!-- false by default, separate from terms -->
```
```ts
await api.post('/account/consent', { marketing: form.marketingConsent, policyVersion: config.public.privacyPolicyVersion });
const deleteAccount = () => api.delete('/users/me').then(() => userStore.$reset());
createGtag({ bootstrap: false });  // start only after consent
```

## Manual trace checklist
1. Consent forms: defaults, granularity, version sent.
2. Rights UI -> endpoint mapping (both directions).
3. Script loading vs consent state.
4. Persisted stores and their cleanup on logout/erasure.
5. Nuxt server code: logging and vendor calls (use `node-express.md`).

## Stack-specific false positives
- Login/signup forms collecting email: expected.
- `console.log` dropped by `vite` `drop_console`: check config, rate Low.
- A cookie banner that does not gate tags: still a finding.

## Tooling
- `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/vue.json`
- `grep -rn "consent\|optIn\|marketing" src --include=*.vue --include=*.ts`
- `grep -rn "deleteAccount\|downloadData\|persist" src stores`

## References
GDPR Art.4(11), 7, 12, 25; ePrivacy Art.5(3); CWE-359, CWE-922; ASVS 8.2, 8.3;
vue-gtag consent docs. Sibling skills: `audit-client-auth-and-storage`,
`audit-privacy-data-flow-mapper`; backend rights: `node-express.md` for Nuxt server code.
