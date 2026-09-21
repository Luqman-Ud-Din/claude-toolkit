# Angular reference for audit-injection-vulnerabilities

Injection is a backend topic; this file covers the client half so a frontend-only
repo still gets a useful pass, and it names what is handed to sibling skills.

## Stack markers
`package.json` with `@angular/core`; `angular.json`; `src/app/**`. Ionic/Capacitor wrappers add native file/URL plugins that widen the surface.

## Where the relevant code lives
`core/services/api.service.ts` (how query strings and paths are built from user input), `*.service.ts` calling `HttpClient`, `*.component.ts` with `window.open`/`location.href`, `environments/*.ts` (base URLs), Capacitor `Filesystem`/`Browser`/`Http` plugin calls, `proxy.conf.json` (which backend hosts the client talks to).

## What this skill checks on the client
- **URL and query building that feeds backend injection**: `HttpParams` built from free-text fields, template-literal paths (`` `${api}/files/${name}` ``) where `name` comes from user input - the client is not the vulnerable party, but the trace tells the backend pass which parameters arrive untrusted. Record the parameter names in `audit/evidence/audit-injection-vulnerabilities/client-params.md`.
- **Client-side "SSRF"-shaped flows**: components that accept a URL and forward it to a backend "fetch/import/preview" endpoint; flag the backend endpoint for the SSRF trace.
- **Path segments from user input**: `Capacitor Filesystem.readFile({ path: userValue })`, `Filesystem.writeFile` with a name from a form, `@capacitor/browser` `Browser.open({ url })` with user URLs (opens arbitrary schemes on device).
- **Client-side query builders**: IndexedDB/SQLite plugins (`@capacitor-community/sqlite` `db.query("... " + x)`) - real SQL injection on device data; treat as SQL class, Medium (single-user data).
- **Template/eval on the client**: `eval`, `new Function`, `setTimeout(string)` - handed to `audit-frontend-xss-and-dom-safety`; note here only if the evaluated string comes from the API (server-controlled code execution on the client).

## What "good" looks like
```ts
// Encode every user value; never interpolate raw into paths
const params = new HttpParams().set('SearchTerm', term);          // encoded by Angular
this.http.get(`${environment.apiUrl}/files/${encodeURIComponent(id)}`);
// Capacitor: fixed directory + sanitized name
Filesystem.readFile({ directory: Directory.Data, path: `exports/${safeName}` });
```
Client-side encoding is a correctness measure, not a security control; the backend still has to parameterize.

## Manual trace checklist
1. Search / filter / sort UI: which fields become `SortColumn`, `SearchTerm`, `Filter` params (see `buildHttpParams` in the api service) - list them for the backend trace.
2. File download/preview components: is the file name or path sent as-is?
3. Any "import from URL" / "webhook" / "logo URL" form.
4. Native plugin calls (`Filesystem`, `Browser`, `Http`) with user-supplied paths/URLs.

## Stack-specific false positives
- Angular's `HttpParams` and `HttpClient` percent-encode values; a raw `+` concatenation into a query string is a bug but not injection by itself.
- `[href]` / `[src]` bindings: Angular sanitizes URL contexts (blocks `javascript:`); XSS skill owns this.

## Tooling
`npx eslint --plugin security` for `detect-eval-with-expression`; otherwise none specific - the value of this pass is the parameter inventory.

## References
Angular Security guide (security contexts); Capacitor Filesystem docs (path traversal note). Sibling skills: `audit-frontend-xss-and-dom-safety` (DOM/URL sinks), `audit-client-auth-and-storage` (interceptor targets and storage), `audit-api-contract` (parameter naming).
