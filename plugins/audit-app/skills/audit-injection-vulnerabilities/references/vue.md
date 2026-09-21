# Vue (incl. Nuxt) reference for audit-injection-vulnerabilities

Injection is a backend topic; this file covers the client half and, for Nuxt,
the server code that lives in the same repo.

## Stack markers
`package.json` with `vue` and/or `nuxt`; `src/**`, `pages/**`, `composables/**`, `server/**`. Nuxt means **backend code is present**: `server/api/**`, `server/routes/**`, `server/middleware/**` (Nitro/h3). Run the `node-express.md` patterns over `server/**` too.

## Where the relevant code lives
- Client: `src/api/**`, `services/**`, `composables/useApi.ts` (URL/query building), stores (`pinia`) holding filter/sort state, form components for file names/URLs; Quasar/Capacitor/Tauri wrappers with native file/URL APIs (`@tauri-apps/api/fs`, `shell.open`).
- Server (Nuxt/Nitro): `defineEventHandler` with `getQuery(event)`, `readBody(event)`, `getRouterParam(event, 'name')`; `$fetch(userUrl)` inside handlers; `serveStatic`/`sendStream(createReadStream(path.join(dir, name)))`; `useStorage().getItem(user)`.

## What this skill checks on the client
- URL and query building from user input - record parameter names in `audit/evidence/audit-injection-vulnerabilities/client-params.md` for the backend trace.
- Forms that send a URL to a backend fetch/import/preview endpoint (SSRF trace target).
- Native wrappers: Tauri `fs.readTextFile(userPath)` (scope config in `tauri.conf.json` is the real control), `shell.open(userUrl)`, Capacitor `Filesystem`.
- `eval`, `new Function`, `v-html` - owned by `audit-frontend-xss-and-dom-safety`; note here only when the evaluated string is server-provided.

## Server-side checks specific to Nuxt / Nitro
- `getRouterParam(event, 'file')` into `fs`/`sendStream` - path traversal.
- `$fetch(body.url)` / `ofetch` in a handler - SSRF.
- `useStorage()` keys built from input (`assets:` mount reading arbitrary files).
- Nitro `routeRules` proxies (`proxy: 'https://x/**'`) with user-influenced targets.
- Prisma/Drizzle raw SQL in `server/utils/db.ts` - same rules as Node: tagged `sql` templates are safe, string concatenation is not.

## What "good" looks like
```ts
// client
const { data } = await useFetch('/api/sales', { query: { SearchTerm: term, SortColumn: sort } }); // encoded
// server/api/files/[name].get.ts
const name = path.basename(getRouterParam(event, 'name') ?? '');
const full = path.resolve(ROOT, name); if (!full.startsWith(ROOT + path.sep)) throw createError({ statusCode: 404 });
```

## Manual trace checklist
1. Data-table/search composables: which state fields become query params.
2. Upload/download components and `download?name=` style links.
3. "Import from URL" / preview / avatar-by-URL features.
4. Nuxt: every `server/api/**` and `server/routes/**` handler - trace as backend code with the Node patterns.
5. `nuxt.config.ts` `routeRules`, `nitro.storage` mounts, `runtimeConfig` (public vs private keys - hand to `audit-client-auth-and-storage`).

## Stack-specific false positives
- `useFetch`/`$fetch` with a `query` object (encoded) and a constant base path.
- Tauri fs calls confined by `tauri.conf.json` `allowlist.fs.scope` - verify the scope, then mark false-positive.
- `eval` inside bundler shims/test files.

## Tooling
`npx eslint-plugin-security`, `semgrep --config p/nodejs` over `server/**`; `npx nuxi analyze` to confirm what ships client-side.

## References
Nuxt "Server" docs (h3 utilities); Tauri security guide (allowlist/scope); OWASP SSRF cheat sheet. Sibling skills: `audit-frontend-xss-and-dom-safety`, `audit-client-auth-and-storage`, `audit-api-contract`.
