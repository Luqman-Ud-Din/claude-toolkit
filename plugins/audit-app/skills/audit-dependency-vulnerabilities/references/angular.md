# Angular reference for audit-dependency-vulnerabilities

## Stack markers
`package.json` with `@angular/core`; `angular.json`; lockfile (`package-lock.json`
usually). Variants: Ionic/Capacitor apps (`@ionic/angular`, `@capacitor/core`,
native Android/iOS dependencies in `android/build.gradle` and `ios/Podfile`),
Nx workspaces, SSR (`@angular/ssr` - the server bundle runs Node code and
server-side advisories become reachable).

## Where the relevant code lives
- Direct deps: `dependencies` (ships in the bundle) vs `devDependencies`
  (`@angular-devkit/*`, `karma`, `webpack-dev-server` - build only).
- Angular's own version: `@angular/core` in package.json; support windows are 18
  months (6 active + 12 LTS).
- Native side of hybrid apps: `android/app/build.gradle`, `ios/Podfile.lock` -
  Maven/CocoaPods ecosystems that `npm audit` does not see.
- Runtime polyfills and crypto: `crypto-js`, `moment`, `lodash` imported in
  `core/services` and `shared/`.

## Dangerous / interesting APIs and patterns
- `@angular/core` <= 16 (out of support): sanitizer fixes not backported.
- Browser-reachable libraries with advisories: `lodash` < 4.17.21, `crypto-js` < 4.2.0
  (PBKDF2 weak default, CVE-2023-46233 - relevant when it encrypts local storage),
  `moment` < 2.29.4 (ReDoS), `dompurify` < 3.1.3 (mXSS), `marked` < 4.0.10,
  `angular` (AngularJS 1.x - EOL, multiple unfixed XSS), `xlsx` (SheetJS npm
  package < 0.20.2 prototype pollution, unfixed on npm), `jspdf` < 2.5.2.
- Dev-server issues: `webpack-dev-server` < 5.2.1, `vite` (esbuild dev server in
  Angular 17+) - local exposure only.
- `*` / `latest` versions, git deps, and `npm audit` disabled in `.npmrc`.

## What "good" looks like
```bash
ng update @angular/core@19 @angular/cli@19      # framework kept in support window
npm audit --omit=dev --audit-level=high         # what ships to browsers
npx cap sync && (cd android && ./gradlew dependencyCheckAnalyze)   # native side
```
Keep `dependencies` to what the browser bundle needs; everything else in
`devDependencies` so `--omit=dev` gives an honest production view.

## Manual trace checklist
1. Browser-reachable Critical/High: does user-controlled data reach the
   vulnerable API (`_.merge` on API responses is attacker-controlled if the API
   echoes user input; `DomSanitizer.bypassSecurityTrust*` around a vulnerable
   markdown/sanitizer library - hand off to `audit-frontend-xss-and-dom-safety`).
2. `crypto-js` used for storage encryption: version and PBKDF2 parameters;
   hand the storage question to `audit-client-auth-and-storage`.
3. Angular version vs support window; the jump size (`ng update` path is one
   major at a time - list the majors).
4. Hybrid apps: run the Gradle/CocoaPods audit separately or list the native
   side under Not checked.
5. SSR: server bundle deps (`express` under `@angular/ssr`) are backend-reachable;
   use `node-express.md` rules for them.

## Stack-specific false positives
- Most `npm audit` output for an Angular repo is `devDependencies` (karma,
  webpack, socket.io in the dev server): Low, never High, unless CI is exposed.
- `@angular/*` packages all move together; one finding for the framework line.
- Transitive `semver`/`tar`/`minimatch` ReDoS reported through `@angular-devkit`:
  build-time only.

## Tooling
- `npm audit --json`, `npm audit --omit=dev --json`
- `ng update` (lists framework/CLI updates), `ng version`
- `npm outdated --long`, `npm view <pkg> time.modified`
- `trivy fs .` (reads `package-lock.json`, `android/**/build.gradle`, `Podfile.lock`)
- `npx browserslist` to see which polyfills are actually needed

## References
CWE-1395, CWE-1104, OWASP A06:2021, ASVS 14.2, Angular release/support policy
(angular.dev/reference/releases), GitHub Advisory Database (ecosystem=npm).
Sibling skills: `audit-frontend-xss-and-dom-safety` (how a vulnerable sanitizer
is reached), `audit-client-auth-and-storage` (crypto-js usage).
