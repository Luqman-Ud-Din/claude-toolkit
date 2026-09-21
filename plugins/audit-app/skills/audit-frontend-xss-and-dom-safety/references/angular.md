# Angular reference for audit-frontend-xss-and-dom-safety

## Stack markers
`package.json` with `@angular/core`; `angular.json`; `src/app/**`. Variants: NgModules vs standalone; Ionic (`ion-*` components, `@capacitor/*` bridges expose native APIs to DOM XSS); AngularJS 1.x (`angular.module`, `$sce.trustAsHtml`, `ng-bind-html`) is a different, much weaker model - treat every `$sce.trustAs*` as a bypass.

## Where the relevant code lives
`*.component.ts` (bypasses, `ElementRef`, `Renderer2`), `*.component.html` (`[innerHTML]`, `[href]`, `[src]`, `[srcdoc]`), `*.pipe.ts` (a `SafeHtmlPipe`/`SafeUrlPipe` wrapping `bypassSecurityTrust*` is the most common shared root cause), `*.directive.ts` (`nativeElement` writes), `src/index.html` (third-party scripts, inline snippets), `angular.json` `scripts`/`styles` arrays (bundled vendor code), `src/assets/i18n/*.json` if rendered with `[innerHTML]`, `ngx-translate` `translate` pipe with HTML strings, markdown/editor wrappers (`ngx-markdown`, `ngx-quill`, `ckeditor`).

## Dangerous / interesting APIs and patterns
- Bypasses (BYPASS): `DomSanitizer.bypassSecurityTrustHtml`, `bypassSecurityTrustStyle`, `bypassSecurityTrustScript`, `bypassSecurityTrustUrl`, `bypassSecurityTrustResourceUrl`; AngularJS `$sce.trustAsHtml/Url/ResourceUrl/Js`, `ng-bind-html` with `$sce`, `$sceProvider.enabled(false)`.
- Raw HTML (HTML): `.innerHTML =`, `.outerHTML =`, `insertAdjacentHTML(`, `document.write(`, jQuery `$(...).html(x)`, `.append(userString)`.
- Element access (DOM): `ElementRef.nativeElement.innerHTML`, `nativeElement.setAttribute('href'|'src'|'srcdoc'|'on*')`, `Renderer2.setProperty(el, 'innerHTML', x)`, `Renderer2.setAttribute(el, 'href', x)`, `@ViewChild` + `nativeElement` writes, `document.getElementById(...).innerHTML`.
- URLs (URL): `[href]="user"` (sanitized by Angular - blocks `javascript:` - but open redirect remains), `window.open(user)`, `location.href = user`, `document.location = user`, `[src]` on `<iframe>`/`<object>`/`<embed>` (requires `bypassSecurityTrustResourceUrl` - check the value), `[attr.href]`, `[attr.src]` (attribute bindings for known URL attributes are still sanitized; `[attr.formaction]`, `[attr.xlink:href]` are), `routerLink` with external strings (not XSS).
- Code (EVAL): `eval(`, `new Function(`, `setTimeout("..."`, `setInterval("..."`, `Function(`; Angular JIT `Compiler.compileModuleAsync` on runtime templates; `ngx-dynamic-hooks`-style runtime template rendering.
- Trusted Types: `angular.json` / server CSP with `require-trusted-types-for 'script'` and `trusted-types angular angular#unsafe-bypass` - if the bypass policy is enabled, bypasses silently work; note it.
- SRI/INLINE: `src/index.html` `<script src="https://...">` without `integrity`; inline `<script>` for GTM/analytics/theme init; `angular.json` `"scripts": ["https://..."]` is not allowed, so CDN scripts are always in `index.html` or added dynamically (`document.createElement('script')` in a service).

## What "good" looks like
```ts
// Let Angular sanitize: no bypass needed for ordinary HTML
@Component({ template: `<div [innerHTML]="comment.body"></div>` })   // Angular strips script/on*/javascript:

// When a bypass is unavoidable (rich text with allowed tags), sanitize the same value first and say why
import DOMPurify from 'dompurify';
// Justified bypass: CMS HTML must keep <table>/<style>; DOMPurify runs with a fixed allow-list.
this.safeHtml = this.sanitizer.bypassSecurityTrustHtml(
  DOMPurify.sanitize(article.html, { ALLOWED_TAGS: ['p','b','i','a','table','tr','td'], ALLOWED_ATTR: ['href'] }));

// URLs: check the scheme yourself before trusting
const u = new URL(link, location.origin);
this.safeUrl = ['http:', 'https:'].includes(u.protocol) ? u.toString() : '#';

// DOM writes: use text, not HTML
this.renderer.setProperty(el.nativeElement, 'textContent', value);

// index.html third-party script
<script src="https://cdn.example.com/lib@1.2.3/lib.min.js" integrity="sha384-..." crossorigin="anonymous"></script>
```

## Manual trace checklist
1. Every `bypassSecurityTrust*` call and every pipe wrapping one: list callers in templates (`| safeHtml`), then the data source of each binding.
2. Rich-text fields end to end: editor component -> API -> stored -> list/detail/print/PDF views. Sanitized at render, not just at input?
3. `[innerHTML]` bindings on API data: safe by default, but verify no `bypass` upstream and no Trusted Types bypass policy.
4. `ElementRef`/`Renderer2` in directives (tooltips, highlight-search-term directives are classic: `innerHTML = text.replace(term, '<mark>$&</mark>')`).
5. `window.open`/`location.href` with query-string values (`returnUrl`, `redirect`) - open redirect and `javascript:`.
6. `src/index.html`: third-party scripts (SRI), inline init scripts (CSP), `<base href>`.
7. Notification/toast services rendering server-provided messages as HTML (`enableHtml: true` in ngx-toastr).
8. Translations rendered with `[innerHTML]` when the i18n files are editable by non-developers.

## Stack-specific false positives
- `[innerHTML]="x"` without a bypass: sanitized by Angular; only report if a bypass or Trusted Types policy is involved, or the content is styled by untrusted `style` (CSS injection, Low).
- `bypassSecurityTrustResourceUrl` on a constant or on a URL built from a constant base plus an encoded id (`https://www.youtube.com/embed/${encodeURIComponent(id)}`) - justified; still Info.
- `bypassSecurityTrustStyle` on a constant background-image URL from assets.
- `ElementRef.nativeElement.focus()`, `.scrollIntoView()`, `.value`, `.textContent =` - not sinks.
- `eval` in test specs, polyfills, or vendor bundles under `node_modules`/`dist` (excluded by the scanner).

## Tooling
- `npx eslint . --ext .ts` with `@angular-eslint/template/no-inline-styles`, `no-any` on bypass wrappers; `eslint-plugin-no-unsanitized` (`no-unsanitized/property`, `no-unsanitized/method`).
- `semgrep --config p/typescript --config r/typescript.angular` (rules `angular-bypasssecuritytrust*`, `angular-domsanitizer`).
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/angular.json`; `scan_html_scripts.py` for `src/index.html`.
- Runtime: Chrome DevTools with a CSP of `require-trusted-types-for 'script'` in a test build to surface every raw sink.

## References
Angular Security guide (Sanitization and security contexts; Trusted Types); OWASP DOM based XSS Prevention Cheat Sheet; OWASP Subresource Integrity; MDN CSP nonces. CWE-79, CWE-95, CWE-601, CWE-829; ASVS 5.3.3, 5.3.10, 14.2.3 (SRI), 14.4.3 (CSP); OWASP A03:2021, A05:2021, A08:2021.
