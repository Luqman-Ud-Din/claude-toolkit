# Node / Express reference for audit-frontend-best-practices

This skill audits frontend code. A Node backend (Express, Fastify, Koa, NestJS)
in the same repo owns only how the built SPA is served, plus - because the
tooling is shared - whether the backend's `package.json` scripts build the
frontend correctly. Check those; defer the rest (end of file).

## Stack markers

`package.json` with `express` / `fastify` / `koa` / `@nestjs/core`. Frontend-serving variants:
`express.static('dist')` / `@fastify/static` / `ServeStaticModule` (Nest); an SSR framework
(Next, Nuxt, Remix, Angular SSR) whose Node server *is* the backend; or a separate CDN.

## Where the relevant code lives

`server.js|ts`, `app.js|ts`, `main.ts` (Nest), `src/app.module.ts` (`ServeStaticModule.forRoot`);
`package.json` `scripts` (`build`, `start`, `postinstall`); monorepo root `package.json` /
`turbo.json` / `nx.json` for the build graph; `Dockerfile` copy of `dist/` (covered by
`audit-infra-and-deployment`, but note if `.map` files are copied).

## Dangerous / interesting APIs and patterns (this skill's slice only)

- `express.static(dir)` without `maxAge` / `immutable` for hashed assets, or with `maxAge` that
  also applies to `index.html`.
- No `compression()` middleware (`app.use(compression())`) and no compression at the proxy.
- `app.get('*', ...)` SPA fallback missing (deep links 404) or placed before the API routes
  (API calls return `index.html`).
- `express.static` serving the project root or `src/` (source and `.env` reachable) - report
  here as a frontend-serving misconfiguration and cross-reference `audit-secrets-and-config`.
- `*.map` files in the served directory; `Dockerfile` `COPY dist/ ./dist/` without excluding maps.
- `scripts.build` that runs the dev build (`vite build --mode development`, `ng build` without
  `--configuration production`, `NODE_ENV` unset).
- `"start": "ng serve"` / `"start": "vite"` used as the production start command in the
  deploy config (dev server in production; also a Fail for "Production build").
- Nest `ServeStaticModule.forRoot({ rootPath })` without `serveStaticOptions: { maxAge, immutable }`.

## What "good" looks like

```js
app.use(compression());
app.use('/assets', express.static(path.join(dist, 'assets'), { maxAge: '1y', immutable: true }));
app.use(express.static(dist, { maxAge: 0, index: false }));
app.use('/api', apiRouter);
app.get('*', (req, res) => res.sendFile(path.join(dist, 'index.html'), { headers: { 'Cache-Control': 'no-cache' } }));
```
```json
{ "scripts": { "build": "vite build --mode production", "start": "node dist/server.js" } }
```

## Manual trace checklist

1. Does the Node app serve the SPA? If not (separate CDN / static host), record it and stop.
2. Middleware order: compression -> static (hashed, long cache) -> API -> SPA fallback.
3. Which script does the deploy run (Dockerfile `CMD`, `Procfile`, pipeline)? Confirm it is the
   production build and not a dev server.
4. Served directory contents: `.map`, `.env`, `src/` reachable?

## Stack-specific false positives

- Compression handled by nginx / Cloudflare in front: fine; name the layer.
- `express.static` `maxAge: 0` on the directory that only holds `index.html`: correct.
- SSR frameworks (Next, Nuxt) manage static serving themselves; only check their config keys
  (see `react.md` / `vue.md`).

## Tooling

`curl -I --compressed http://localhost:3000/assets/index.js` (look for `content-encoding` and
`cache-control`); `npx serve -s dist` is a dev convenience, not a production server; `ls dist | grep .map`.

## Deferred to sibling skills

Security headers / CSP / helmet: `audit-security-headers-and-middleware`. API performance:
`audit-performance-and-scalability`. Dockerfile and deploy scripts: `audit-infra-and-deployment`.
Secrets reachable via static serving: `audit-secrets-and-config`.

## References

Express production best practices: https://expressjs.com/en/advanced/best-practice-performance.html;
`compression` middleware; CWE-540 (source maps), CWE-538 (file exposure), ASVS-14.3.2.
