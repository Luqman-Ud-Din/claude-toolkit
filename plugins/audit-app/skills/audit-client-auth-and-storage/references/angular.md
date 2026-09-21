# Angular (incl. Ionic/Capacitor) reference for audit-client-auth-and-storage

## Stack markers
`package.json` with `@angular/core`; `angular.json` (`fileReplacements` tell you which `environment.*.ts` ships per configuration); Ionic/Capacitor: `@capacitor/core`, `capacitor.config.ts`, `@capacitor/preferences` (NOT secure), `capacitor-secure-storage-plugin`/`@aparajita/capacitor-secure-storage` (secure). Libraries: `angular-oauth2-oidc`, `@auth0/auth0-angular`, `@azure/msal-angular`, `angularx-jwt`/`@auth0/angular-jwt`, `ngx-cookie-service`, `crypto-js` (bundled-key "encryption").

## Where the relevant code lives
`src/app/core/services/auth.service.ts` (login/logout/refresh), `core/services/storage.service.ts` (wrapper around `localStorage` - the single place to check), `core/interceptors/*.interceptor.ts` (`HttpInterceptorFn` or class `HttpInterceptor`), `core/guards/*.guard.ts` (`CanActivateFn`, `CanMatchFn`), `app.config.ts`/`app.module.ts` (`provideHttpClient(withInterceptors([...]))`, `HTTP_INTERCEPTORS` multi-providers - order and which client), `src/environments/*.ts`, `src/environments/firebase-config.ts`, `angular.json` build `fileReplacements`, `ngsw-config.json` (cached API responses with tokens?), `capacitor.config.ts`, `proxy.conf.json` (which hosts count as "own API" in dev).

## Dangerous / interesting APIs and patterns
- STORE: `localStorage.setItem('token'|'access_token'|'jwt'|'refresh_token'|...)`, `sessionStorage.setItem(`, `StorageService.set(` wrappers, `Preferences.set({ key: 'token' })` (Capacitor Preferences = plain SharedPreferences/UserDefaults), `CryptoJS.AES.encrypt(token, environment.secretKey)` (key in bundle), `document.cookie = 'token=...'` (non-HttpOnly), NgRx/signal stores persisted with `localStorageSync`.
- INTERCEPT: `req.clone({ setHeaders: { Authorization: ... } })` without `req.url.startsWith(environment.apiUrl)`; `withCredentials: true` set globally; `PUBLIC_ENDPOINTS` lists (check completeness); token appended to `params` (`?token=`); `HttpBackend` used for third-party calls (good) vs shared `HttpClient`.
- REFRESH: `refreshToken()` without `shareReplay`/`BehaviorSubject` gating (`isRefreshing` flag pattern); `catchError` on 401 calling `refresh` then `next.handle` with old token; `jwtDecode(token).exp` / `JwtHelperService.isTokenExpired`; `setInterval` refresh timers not cleared; refresh endpoint excluded from the interceptor?
- LOGOUT: `localStorage.removeItem('token')` only (vs `clear()` or full key list), stores not reset (`store.dispatch(reset())`), `Subject`s holding user state not `next(null)`, `clearInterval` missing, `router.navigate(['/login'])` before clearing, server logout endpoint not called for cookie sessions, service worker cache (`caches.delete`) not touched.
- GUARD: `CanActivateFn` checking `storage.get('token')` or decoding roles - UX only; `CanLoad`/`CanMatch` hiding lazy modules; `*ngIf="isAdmin"` around admin buttons.
- SECRET: `environment.prod.ts` keys: `apiKey`, `secret`, `clientSecret`, `privateKey`, `smsApiKey`, `encryptionKey`, `jwtSecret`, `connectionString`, `serviceAccount`; `firebase-config.ts` (public identifiers); `capacitor.config.ts` plugin keys; hard-coded `Basic ` auth headers; `environment.ts` values imported into production because `fileReplacements` is missing for a configuration.
- TRANSPORT: `apiUrl: 'http://...'` in `environment.prod.ts`; `console.log(token)`; `window.postMessage(token, '*')`; `ws://` URLs with token in query.

## What "good" looks like
```ts
// Access token in memory, refresh via HttpOnly cookie set by the API
@Injectable({ providedIn: 'root' })
export class AuthService {
  private accessToken = signal<string | null>(null);
  private refresh$?: Observable<string>;
  login(dto) { return this.http.post<{ accessToken: string }>(`${environment.apiUrl}/auth/login`, dto, { withCredentials: true })
    .pipe(tap(r => this.accessToken.set(r.accessToken))); }
  refresh(): Observable<string> {                       // single-flight
    return this.refresh$ ??= this.http.post<{ accessToken: string }>(`${environment.apiUrl}/auth/refresh`, {}, { withCredentials: true })
      .pipe(map(r => r.accessToken), tap(t => this.accessToken.set(t)), finalize(() => this.refresh$ = undefined), shareReplay(1));
  }
  logout() { this.http.post(`${environment.apiUrl}/auth/logout`, {}, { withCredentials: true }).subscribe();
    this.accessToken.set(null); this.store.dispatch(resetState()); clearInterval(this.timer); this.router.navigate(['/login']); }
}
// Interceptor scoped to own origin
export const tokenInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService); const token = auth.token();
  const own = req.url.startsWith(environment.apiUrl) || req.url.startsWith('/');
  return next(token && own ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req);
};
// Third-party calls bypass interceptors
constructor(backend: HttpBackend) { this.raw = new HttpClient(backend); }
```
Mobile: `@aparajita/capacitor-secure-storage` (Keychain/Keystore) for refresh tokens; never `@capacitor/preferences`.

## Manual trace checklist
1. `auth.service.ts` login: response shape -> `storage.set` calls -> which keys, which backing store (open `storage.service.ts`; a `crypto-js` wrapper is still localStorage).
2. Interceptor: the exact condition before `clone`; list every host the app calls (`grep -r "https://" src/app --include=*.ts`) and check which get the header.
3. 401 path: refresh single-flight, request replay, failure -> logout; refresh endpoint excluded from the token interceptor.
4. Logout: enumerate every storage key written anywhere (`grep -r "setItem\|storage.set" src`) and compare with what logout removes.
5. Guards: list them, confirm each protected route's API is authorized server-side (authz report).
6. `angular.json` configurations -> which environment file ships; run `scan_secrets.py` on `src/environments` and on `dist/` if built.
7. Ionic: deep-link handlers (`App.addListener('appUrlOpen')`) receiving tokens; `Browser.open` for OAuth with PKCE (`angular-oauth2-oidc` `responseType: 'code'`, not implicit).

## Stack-specific false positives
- `localStorage` for theme, language, layout, last-visited page - not credentials.
- `@auth0/angular-jwt` `tokenGetter` with `allowedDomains` configured - that is the origin check; verify the list.
- `JwtHelperService.decodeToken` for display (user name) - fine.
- Firebase `apiKey` in `firebase-config.ts` - public identifier; Info with referrer-restriction check.
- `withCredentials: true` when the API is same-site and uses HttpOnly cookies - that is the good pattern.

## Tooling
- `ng build --configuration production` then `python scripts/scan_secrets.py <repo> --bundle dist` (checks what actually ships).
- `npx source-map-explorer dist/**/*.js` to confirm environment values in the bundle.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/angular.json`.
- DevTools: Application tab -> Local Storage after login (runtime confirmation, if the app can be run).

## References
Angular HTTP interceptors and `provideHttpClient` docs; OWASP JWT for Java cheat sheet (storage section applies), OWASP Session Management cheat sheet, OWASP HTML5 Security cheat sheet (Web Storage); Capacitor Preferences docs (not for secrets). CWE-522, CWE-922, CWE-798, CWE-613, CWE-539; ASVS 3.2.3, 3.3.x, 3.5.2, 8.2.2, 8.3.x, 14.3.x; OWASP A02:2021, A07:2021.
