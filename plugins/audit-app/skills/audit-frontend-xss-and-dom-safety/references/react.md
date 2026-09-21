# React (incl. Next.js, React Native WebView) reference for audit-frontend-xss-and-dom-safety

## Stack markers
`package.json` with `react`, `react-dom`, `next`, `gatsby`, `remix`. Variants: class components vs hooks (same sinks), Next.js App Router (server components can build HTML strings that client components inject), React Native (`react-native-webview` `injectedJavaScript`, `source={{ html }}`).

## Where the relevant code lives
`src/**/*.jsx|tsx`, `components/**`, `app/**` and `pages/**` (Next), `public/index.html` (CRA) or `app/layout.tsx` / `pages/_document.tsx` (Next: `<Script>` and `<script>` tags), `next.config.js` (`headers()` CSP), markdown renderers (`react-markdown` with `rehype-raw`, `marked` + `dangerouslySetInnerHTML`), editors (`react-quill`, `draft-js` HTML export), chart/tooltip libraries with `html` options.

## Dangerous / interesting APIs and patterns
- Bypasses (BYPASS): `dangerouslySetInnerHTML={{ __html: x }}` - the only React bypass; also `React.createElement('div', { dangerouslySetInnerHTML })`, `renderToStaticMarkup` output re-injected, `rehype-raw`/`allowDangerousHtml: true` in `react-markdown`/`remark`, `html-react-parser`/`react-html-parser` (`parse(userHtml)` renders tags and `on*` handlers as props are stripped but `<script>` in `iframe srcdoc`, `<a href="javascript:">` survive), `DOMPurify` missing before any of these.
- Raw HTML (HTML): `.innerHTML =`, `.outerHTML =`, `insertAdjacentHTML(`, `document.write(`, jQuery inside React.
- Element access (DOM): `ref.current.innerHTML`, `useRef` + `innerHTML`, `findDOMNode(...).innerHTML`, `document.getElementById(...).innerHTML`, `createPortal` into a node whose HTML is set by hand.
- URLs (URL): `<a href={user}>` (React blocks `javascript:` since 16.9 with a warning only - check version; `data:` allowed), `<iframe src={user}>`, `<iframe srcDoc={user}>`, `<form action={user}>`, `<img src={user} onError>` (not XSS by itself), `window.open(user)`, `location.href = user`, `router.push(user)` (open redirect), `<Link href={user}>` external.
- Props spreading: `<div {...userObject}>` can inject `dangerouslySetInnerHTML` if the object comes from JSON (`{"dangerouslySetInnerHTML": {"__html": ...}}`) - report as HTML class.
- Code (EVAL): `eval(`, `new Function(`, `setTimeout("...")`, `vm`-style sandboxes in the browser, `React Native WebView injectedJavaScript={user}`, `source={{ html: user }}`.
- Server components / SSR: `getServerSideProps` returning HTML strings rendered with `dangerouslySetInnerHTML`; `__NEXT_DATA__` JSON embedding - Next escapes `<` in JSON; custom `<script>{JSON.stringify(data)}</script>` in `_document` does not (`</script>` breakout).
- SRI/INLINE: `<script src>` in `public/index.html`, `next/script` `<Script src="https://..."/>` without `integrity` (supported prop), `strategy="beforeInteractive"` inline code, GTM snippets in `_document.tsx`, `dangerouslySetInnerHTML` on `<script>` tags for JSON-LD (safe only if the JSON escapes `<`).

## What "good" looks like
```tsx
// Default JSX escaping is the control - no bypass needed for text
<p>{comment.body}</p>

// Rich text: sanitize the same value right before the bypass, with a stated reason
import DOMPurify from 'dompurify';
// Justified: CMS help articles contain tables; DOMPurify with a fixed allow-list.
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(article.html, { ALLOWED_TAGS: [...] }) }} />

// Markdown: keep rehype-raw off, or sanitize with rehype-sanitize
<ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>

// URLs
const safeHref = (u: string) => { try { const p = new URL(u, location.origin); return ['http:','https:'].includes(p.protocol) ? p.href : '#'; } catch { return '#'; } };

// Next.js third-party script with SRI
<Script src="https://cdn.example.com/lib.js" integrity="sha384-..." crossOrigin="anonymous" />
```

## Manual trace checklist
1. Every `dangerouslySetInnerHTML`: the `__html` source, and whether a sanitizer runs on the same value in the same expression or the line above.
2. Markdown/HTML parser components and their plugin options (`rehype-raw`, `allowDangerousHtml`, `skipHtml: false`).
3. `href`/`src`/`srcDoc`/`action` props bound to API or URL data; React version for the `javascript:` block.
4. `ref.current` writes in custom hooks and in "highlight" or "tooltip" utilities.
5. Prop spreading from JSON configs (`{...field.props}`) for `dangerouslySetInnerHTML` injection.
6. `_document.tsx`/`layout.tsx`/`public/index.html`: third-party scripts, inline JSON embedding, GTM.
7. React Native: `WebView` `source.html`, `injectedJavaScript`, `onMessage` handlers acting on `postMessage` data, deep links (`Linking`) rendered into WebViews.

## Stack-specific false positives
- `dangerouslySetInnerHTML={{ __html: SVG_ICON }}` with an imported constant SVG - justified, Info.
- JSON-LD `<script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, '\\u003c') }}>` - safe when the replace is present.
- `href={'mailto:' + email}` with validated email; `href={`/items/${id}`}` relative paths.
- `eval` in tests, storybook, or bundler shims.
- `ref.current.focus()`, `.scrollIntoView()`, `.value` reads.

## Tooling
- `npx eslint --plugin react` with `react/no-danger`, `react/no-danger-with-children`; `eslint-plugin-no-unsanitized`.
- `semgrep --config p/react` (`react-dangerouslysetinnerhtml`, `react-href-var`, `react-insecure-request`), `--config p/nextjs`.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/react.json`; `scan_html_scripts.py` for `public/*.html` and `_document.tsx`.

## References
React docs "dangerouslySetInnerHTML"; Next.js `next/script` and CSP docs; OWASP DOM based XSS Prevention Cheat Sheet; OWASP SRI. CWE-79, CWE-95, CWE-601, CWE-829; ASVS 5.3.3, 5.3.10, 14.2.3, 14.4.3; OWASP A03:2021, A05:2021, A08:2021.
