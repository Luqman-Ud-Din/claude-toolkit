# Node / Express (NestJS, Fastify, Koa) reference for audit-frontend-xss-and-dom-safety

XSS is mostly a client topic; this file covers the Node server side: view
engines (EJS, Pug, Handlebars, Nunjucks), HTML strings sent with `res.send`,
and server-side sanitization a frontend bypass may rely on.

## Stack markers
`package.json` with `express`/`@nestjs/core`/`fastify`/`koa` plus a view engine (`ejs`, `pug`, `handlebars`/`hbs`, `nunjucks`, `mustache`, `@fastify/view`), or `res.send`/`res.type('html')` usage; `views/**`, `public/**`.

## Where the relevant code lives
`views/**` (`.ejs`, `.pug`, `.hbs`, `.njk`), `public/js/**` (raw DOM code), route handlers using `res.send(html)`, `res.render(view, data)` (which fields are HTML), `res.redirect(userUrl)`, error middleware building HTML, email/PDF builders, `sanitize-html`/`dompurify` (server via `isomorphic-dompurify`/`jsdom`)/`xss` usage (server-side sanitizers), NestJS `@Render()` controllers and `ServeStaticModule`.

## Dangerous / interesting APIs and patterns
- Bypasses (BYPASS/SSR): EJS `<%- x %>` (unescaped; `<%= %>` escapes), `include` with user path; Pug `!= x` and `!{x}` (unescaped; `= x`/`#{x}` escape), `script.` blocks with interpolation; Handlebars `{{{x}}}` triple-stash, `Handlebars.SafeString(x)`, `{{{{raw}}}}`; Nunjucks `{{ x | safe }}`, `autoescape: false` in `nunjucks.configure`; Mustache `{{{x}}}` / `{{& x}}`; `marked(x)` output without sanitizer (marked removed `sanitize` option), `markdown-it({ html: true })`.
- HTML strings: `res.send("<h1>" + x)`, `res.send(\`...${x}...\`)`, `res.write(html + x)`, `res.end(...)`, `res.type('html')`, `reply.type('text/html').send(str)` (Fastify), `ctx.body = "<html>" + x` (Koa), `@Header('Content-Type','text/html')` in Nest; default error pages echoing `req.url` (Express `finalhandler` escapes; custom ones often do not).
- Script context: `<script>var d = <%- JSON.stringify(data) %></script>` - `</script>` breakout; use `serialize-javascript` or replace `<` with `<`.
- URLs: `res.redirect(req.query.returnUrl)` (open redirect, CWE-601), `<a href="<%= user %>">` (escaped but scheme unchecked).
- Static/raw JS (`public/js/**`): `innerHTML =`, `document.write(`, `$(...).html(`, `.append(str)`, `eval(`, `location.href = location.hash`, `postMessage` listeners without origin check.
- SRI/INLINE: layout views with `<script src="https://cdn...">` without `integrity`; inline `<script>` and `onclick=`; `helmet` CSP with `'unsafe-inline'` (owned by headers skill, link the findings).
- Sanitizers: `sanitize-html` (`sanitizeHtml(x, { allowedTags })`), `xss` (`filterXSS`), `isomorphic-dompurify`. Frontend "the API sanitizes" claim is justified only if one runs on the **write** path for that field (`create`/`update` handlers or a Nest pipe).

## What "good" looks like
```ejs
<%# EJS escapes with <%= %> %>
<p><%= comment.body %></p>
<%# Justified unescaped output: sanitized in helpService.render() with sanitize-html allow-list %>
<div><%- article.safeHtml %></div>
<script>window.__data = <%- JSON.stringify(data).replace(/</g, '\\u003c') %>;</script>
<script src="https://cdn.example.com/lib.js" integrity="sha384-..." crossorigin="anonymous"></script>
```
```ts
import sanitizeHtml from 'sanitize-html';
entity.description = sanitizeHtml(dto.description, { allowedTags: ['p','b','i','a','ul','li'], allowedAttributes: { a: ['href'] } }); // on write
// redirects: allow-list relative paths only
const target = req.query.returnUrl; res.redirect(/^\/[^/\\]/.test(target) ? target : '/');
```

## Manual trace checklist
1. Every unescaped template construct (`<%-`, `!=`, `!{`, `{{{`, `| safe`, `{{&`): the data field and its origin.
2. `res.send`/`res.write` with template literals or concatenation and a `text/html` type.
3. Layout templates: third-party scripts (SRI), inline scripts/handlers (CSP), JSON embedding in `<script>`.
4. `res.redirect` and `Location` headers from request data.
5. If the SPA relies on API sanitization: find the sanitizer on the write path (and confirm it is not only on read).
6. `public/js/**` DOM sinks and `postMessage` handlers.
7. Email templates (HTML injection -> phishing, Medium).

## Stack-specific false positives
- `<%- include('partials/header') %>` with a literal path - not a sink.
- `{{{x}}}` on markup produced by a helper with no user data - Info.
- `res.send(JSON)` with `application/json` - not HTML.
- `eval` in tests, build scripts, or vendored `public/js/lib/**`.
- `nunjucks.configure({ autoescape: true })` (the default in recent versions).

## Tooling
- `npx eslint-plugin-no-unsanitized`, `eslint-plugin-security` (`detect-eval-with-expression`).
- `semgrep --config p/nodejs --config p/expressjs` (`express-res-send-xss`, `ejs-unescaped`, `handlebars-triple-stash`), `--config p/javascript`.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/node-express.json`; `scan_html_scripts.py` over `views/**` and `public/**`.

## References
OWASP XSS Prevention Cheat Sheet; EJS/Pug/Handlebars escaping docs; `sanitize-html` README; OWASP SRI. CWE-79, CWE-80, CWE-601, CWE-829; ASVS 5.3.1-5.3.3, 14.2.3; OWASP A03:2021, A05:2021.
