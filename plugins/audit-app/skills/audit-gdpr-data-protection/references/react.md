# React reference for audit-gdpr-data-protection

The backend owns rights endpoints, retention, server logs and processors
(backend stack file). The React surface is consent UX, rights UI, browser
persistence, client-side vendors, and - for Next.js/Remix - the server code in
`app/api`, server actions and middleware, which follows `node-express.md`.

## Stack markers
`package.json` with `react` (+ `next`, `remix`, `vite`). Variants: React Native
(AsyncStorage, push tokens), Next.js App Router (server components/actions).

## Where the relevant code lives
- Consent UI: signup forms (react-hook-form `register('marketingConsent')`), cookie-consent components, policy version constants.
- Rights UI: account/settings pages (`deleteAccount`, `downloadData`, consent preferences) and the API client calls.
- Client persistence: `redux-persist` whitelist, `zustand persist`, React Query persister, `localStorage`, AsyncStorage.
- Client-side vendors: `<Script>` tags in `_app`/`layout`, `@vercel/analytics`, PostHog/Segment init, `@sentry/react`, LogRocket.
- Next.js server: `app/api/**/route.ts`, `actions.ts`, `middleware.ts` - vendor calls and logging (apply `node-express.md`).

## Dangerous / interesting APIs and patterns
- `defaultChecked` on consent checkboxes; one checkbox for T&Cs + marketing.
- Consent posted as a bare boolean without policy version.
- Missing rights UI although endpoints exist (or UI buttons calling non-existent endpoints).
- Tracking `<Script strategy="afterInteractive">` loaded before consent; no consent mode.
- `Sentry.setUser({ email })`, `LogRocket.identify(id, { email })`, replay without masking.
- `redux-persist` whitelist including `user`/`auth` slices with profile data; not purged on logout/erasure.
- `fetch(\`/api/users?email=${email}\`)`.
- Server actions forwarding the whole form payload to HubSpot/Mailchimp regardless of consent.

## What "good" looks like
```tsx
<input type="checkbox" {...register('marketingConsent')} />           // unchecked by default, separate from terms
await api.post('/account/consent', { marketing: data.marketingConsent, policyVersion: PRIVACY_POLICY_VERSION });
const deleteAccount = () => api.delete('/users/me').then(() => persistor.purge());
posthog.init(key, { opt_out_capturing_by_default: true });           // opt in after consent
```

## Manual trace checklist
1. Consent forms: defaults, granularity, version sent.
2. Rights UI -> endpoint mapping (both directions).
3. Vendor script loading vs consent state; consent-mode defaults.
4. Persisted slices and their cleanup on logout/erasure.
5. Next.js server code: logging and vendor calls, consent checks (use `node-express.md`).

## Stack-specific false positives
- Login/signup forms collecting email: expected.
- `console.log` stripped by the bundler: check config, rate Low.
- A cookie banner that only hides itself without gating tags: still a finding.

## Tooling
- `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/react.json`
- `grep -rn "consent\|optIn\|marketing" src app --include=*.tsx --include=*.ts`
- `grep -rn "deleteAccount\|downloadData\|persist(" src app`

## References
GDPR Art.4(11), 7, 12, 25; ePrivacy Art.5(3); CWE-359, CWE-922; ASVS 8.2, 8.3;
Google Consent Mode; PostHog opt-in docs. Sibling skills: `audit-client-auth-and-storage`,
`audit-privacy-data-flow-mapper`; backend rights: `node-express.md` for Next.js server code.
