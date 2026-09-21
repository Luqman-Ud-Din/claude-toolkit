# XSS sink classes, sources, and the justified/unjustified rubric

## Sink classes and pattern-id prefixes

| Prefix | Class | What it is | CWE |
|---|---|---|---|
| BYPASS | Framework sanitizer bypass | `bypassSecurityTrust*`, `dangerouslySetInnerHTML`, `v-html`, `Html.Raw`, `th:utext`, `<%- %>`, `|safe`/`mark_safe` | CWE-79 |
| HTML | Raw HTML write | `innerHTML =`, `outerHTML =`, `insertAdjacentHTML`, `document.write(ln)`, jQuery `.html()/.append(str)`, `$(userString)` | CWE-79 |
| DOM | Unsafe element access | `ElementRef.nativeElement.*`, `ref.current.innerHTML`, `document.getElementById(...).innerHTML`, `Renderer2.setProperty(el,'innerHTML')` | CWE-79 |
| URL | URL/attribute injection | `href`/`src`/`action`/`formaction`/`xlink:href` from input; `javascript:`, `data:text/html`, `vbscript:` schemes; `window.open(user)`, `location.href = user`, `iframe.src = user` | CWE-79, CWE-601 |
| EVAL | Code from strings | `eval`, `new Function`, `setTimeout/setInterval(string)`, `execScript`, template compilers on runtime strings (`Vue.compile`, `$compile`), `srcdoc` | CWE-95 |
| SRI | Third-party script without integrity | `<script src="https://other-origin/...">` without `integrity` + `crossorigin` | CWE-829 |
| INLINE | Inline script / handler | `<script>...</script>`, `onclick="..."`, `style="..."` with expressions - incompatible with a nonce/hash CSP; also `unsafe-inline` in a CSP | CWE-1021 (context), OWASP-A05 |
| SSR | Server-rendered echo | template auto-escaping disabled, HTML built in controllers and returned as `text/html`, error pages echoing input | CWE-79 |

## Sources (how "user-controlled" is decided)

1. Fields any user can type: names, comments, notes, descriptions, product titles, custom-field values, file names, addresses.
2. API responses that echo (1) - most SPA XSS is *stored*: the payload is saved by one user and rendered for another.
3. Route params, query strings, `location.hash`, `document.referrer`, `postMessage` data, `window.name`.
4. Storage: `localStorage`/`sessionStorage`/IndexedDB values written from (1)-(3).
5. Third-party content: CMS articles, help centres, marketing snippets, translations edited by non-developers (i18n JSON files count when they are editable at runtime).
6. Admin-entered content is user-controlled when admins are tenants of a SaaS (a tenant admin is not your admin).

Constants in source, build-time environment values, and strings produced by the app's own code (a formatted date) are trusted.

## Justified vs unjustified bypass

A bypass is **justified** only when all three hold:

1. **Sanitized or constant.** A real sanitizer runs on the *same value* immediately before the bypass (`DOMPurify.sanitize`, Angular `sanitizer.sanitize(SecurityContext.HTML, v)`, `sanitize-html`, `xss`, `bleach.clean`, Jsoup `clean` with a safelist, `HtmlSanitizer` in .NET), or the value is a constant / build-time asset / server-controlled resource URL nobody can edit at runtime. Angular's `[innerHTML]` binding on its own is *not* a bypass; it is the sanitized path.
2. **Same context.** The sanitizer's output context matches the bypass (`HTML` for `bypassSecurityTrustHtml`, URL scheme check for `bypassSecurityTrustUrl`/`ResourceUrl`, none exists for `bypassSecurityTrustScript` - that one is unjustified unless the script text is a literal).
3. **Stated.** A comment, docstring, or ADR says why the bypass exists. Missing statement alone does not make it unjustified, but downgrade `confidence` to `likely` and ask.

Everything else is **unjustified**. Common near-misses that remain unjustified:
`escape()`/`encodeURIComponent()` before an HTML bypass (wrong context), a regex that strips `<script>` (bypassable), "the backend sanitizes it" without a visible server-side sanitizer call on the write path, sanitizing once at write time but re-editing later without sanitizing again.

Justified bypasses are recorded as **Info** findings (`tags: ["bypass","justified"]`) so the register is complete.

## URL rules

- `href`/`src` from input: safe only if the scheme is checked (`http:`/`https:`/`mailto:`/relative) *after* parsing (`new URL(v, base).protocol`). Frameworks: Angular sanitizes `[href]`/`[src]` (blocks `javascript:`), React does since v16.9 for `javascript:` in `href` (warns) but not for `srcdoc`/`formaction`, Vue does **not** sanitize `:href`.
- `bypassSecurityTrustResourceUrl` for `<iframe src>`/`<object data>`: justified only for a constant or an allow-listed host.
- Open redirect (`location.href = returnUrl`) is reported here as URL class with CWE-601 when no other skill owns it.

## SRI and inline rules

- Every `<script src>` and `<link rel=stylesheet href>` from an origin the team does not control needs `integrity="sha384-..."` and `crossorigin="anonymous"`. Scripts loaded dynamically (`document.createElement('script')`) need `script.integrity`. Exception: scripts whose content legitimately changes (tag managers, some analytics) - then the CSP `script-src` host allow-list is the control; record it as Low with that note.
- Inline `<script>` blocks and `on*=` handlers in `index.html` or templates force `'unsafe-inline'` in CSP. Report as Low (Medium if the app already ships a CSP with `'unsafe-inline'` because of them) with the fix: move to a file, or add a nonce/hash.
- `'unsafe-eval'` in CSP is required by `eval`/`new Function` usage - link the two findings.

## Severity anchors

- Critical: stored XSS rendered in an admin/super-admin screen or across tenants; XSS in a payment/checkout flow.
- High: stored XSS visible to other ordinary users; unjustified `bypassSecurityTrustScript`/`eval` on server-provided strings; DOM XSS reachable from a URL on a page most users visit.
- Medium: reflected/DOM XSS needing a crafted link on a less-visited page; `v-html`/`dangerouslySetInnerHTML` on content only admins (your own staff) can edit; a bypass with a weak home-made sanitizer.
- Low: self-XSS (only the author sees it); missing SRI; inline scripts that block a strict CSP; `javascript:` blocked by the framework but present in code.
- Info: justified bypasses; sanitizer present but undocumented.
