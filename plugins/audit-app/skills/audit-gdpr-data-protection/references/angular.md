# Angular reference for audit-gdpr-data-protection

The backend owns the rights endpoints, retention jobs, server logs and
processor calls (see the backend stack file). The frontend's GDPR surface is:
how consent is *asked* (affirmative, unticked, versioned), whether the UI
offers the rights (delete account, download my data, manage consent), what the
browser persists, and which client-side vendors fire before consent. Browser
storage security belongs to `audit-client-auth-and-storage`.

## Stack markers
`package.json` with `@angular/core`; `angular.json`. Variants: Ionic/Capacitor
(native storage, push tokens), PWA (`ngsw-config.json` caches).

## Where the relevant code lives
- Consent UI: signup/profile forms (`formControlName="marketingConsent"`), cookie banner components, `environment.ts` policy version constants.
- Rights UI: account/settings pages (`deleteAccount()`, `downloadData()`, `privacySettings`), the `api.service.ts` calls they make.
- Client persistence: `core/services/storage.service.ts`, `localStorage`, IndexedDB, `@capacitor/preferences`, `ngsw-config.json` `dataGroups`.
- Client-side vendors: `index.html` tags (GTM, GA, Hotjar, Clarity, Intercom), `@angular/fire` analytics, `@sentry/angular`.
- Logout/erasure cleanup: `auth.service.ts` `logout()` - does it clear persisted profile data?

## Dangerous / interesting APIs and patterns
- Consent checkbox pre-checked (`new FormControl(true)`, `[checked]="true"`) or bundled with T&Cs in one control.
- Consent submitted as a bare boolean with no `policyVersion` in the request model.
- No UI path for delete account / download data although the backend has endpoints (or vice versa).
- Tracking tags in `index.html` loaded before any consent decision; no consent-mode integration.
- `Sentry.setUser({ email })`, `replaysSessionSampleRate > 0` without input masking.
- Profile persisted in `localStorage` and not cleared on logout/erasure.
- `HttpParams().set('email', ...)` on GET requests.

## What "good" looks like
```ts
form = this.fb.group({ acceptTerms: [false, Validators.requiredTrue], marketingConsent: [false] });
submit() { this.api.post('/account/consent', { marketing: this.form.value.marketingConsent, policyVersion: environment.privacyPolicyVersion }); }
deleteAccount() { return this.api.delete('/users/me').pipe(tap(() => this.storage.clear())); }
// index.html: load GTM only after the consent service resolves; gtag('consent', 'default', { analytics_storage: 'denied' })
```

## Manual trace checklist
1. Consent forms: default state, separate controls per purpose, version sent.
2. Rights UI -> backend endpoint mapping (fill the "endpoint" column of the matrix from both sides).
3. Tag loading order vs consent banner; consent-mode defaults.
4. Logout and erasure: what is cleared client-side (storage, service-worker caches).
5. Error tracker / replay configuration.

## Stack-specific false positives
- `email` form controls on login: collection is expected.
- `localStorage` holding only a token and user id: fine for this skill (token handling is another skill's).
- Cookie banner component present but tags still load unconditionally: still a finding.

## Tooling
- `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/angular.json`
- `grep -rn "consent\|optIn\|marketing" src/app --include=*.ts --include=*.html`
- `grep -rn "deleteAccount\|downloadData\|export" src/app --include=*.ts`

## References
GDPR Art.4(11), 7, 12, 25; ePrivacy Directive Art.5(3) (cookies/tags); CWE-359, CWE-922;
ASVS 8.2, 8.3; Google Consent Mode docs. Sibling skills: `audit-client-auth-and-storage`,
`audit-privacy-data-flow-mapper`; backend rights: the matching backend stack file.
