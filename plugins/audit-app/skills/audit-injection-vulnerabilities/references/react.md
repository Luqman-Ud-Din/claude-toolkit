# React (incl. Next.js) reference for audit-injection-vulnerabilities

Injection is a backend topic; this file covers the client half and, for Next.js,
the server code that lives in the same repo.

## Stack markers
`package.json` with `react` and/or `next`; `src/**`, `app/**`, `pages/**`. Next.js means **backend code is present**: `pages/api/**`, `app/**/route.ts`, Server Actions (`"use server"`), `middleware.ts`, `getServerSideProps`. Run the `node-express.md` patterns over those folders too.

## Where the relevant code lives
- Client: `src/api/**`, `services/**`, `hooks/use*.ts` (fetch wrappers building URLs), form components submitting file names, URLs, sort/filter fields; React Native `react-native-fs`, `expo-file-system`, `Linking.openURL`.
- Server (Next.js): route handlers and Server Actions receiving `request.json()`, `formData()`, `searchParams`; `prisma.$queryRawUnsafe`, `child_process`, `fs`, `fetch(userUrl)` inside them; `next.config.js` `images.remotePatterns` (an open `**` hostname turns the image optimizer into an SSRF/proxy).

## What this skill checks on the client
- URL and query building from user input (`` `${API}/files/${name}` ``, `new URLSearchParams(formState)`) - record parameter names for the backend trace in `audit/evidence/audit-injection-vulnerabilities/client-params.md`.
- Forms that send a URL to a backend fetch/import/preview endpoint (SSRF trace target).
- React Native/Expo file APIs with user-supplied paths; `Linking.openURL(userUrl)` allowing arbitrary schemes.
- `eval`/`new Function`/`dangerouslySetInnerHTML` - owned by `audit-frontend-xss-and-dom-safety`; note here only when the evaluated string is server-provided.

## Server-side checks specific to Next.js
- Server Actions: arguments are attacker-controlled even when the UI never exposes them; treat every argument as a request body field.
- `route.ts`: `params.slug` into `fs.readFile(path.join(CONTENT_DIR, slug))` - classic path traversal in content sites.
- `next/image` with `remotePatterns: [{ hostname: '**' }]` or a custom `loader` fetching arbitrary URLs.
- `revalidatePath(userInput)` / `redirect(userUrl)` (open redirect, report under headers/authz skills if out of scope).
- Prisma: `$queryRaw` tagged template is safe, `$queryRawUnsafe` with interpolation is not.

## What "good" looks like
```ts
// client
const qs = new URLSearchParams({ SearchTerm: term, SortColumn: sort }).toString();
fetch(`${API}/sales?${qs}`);
// server (route.ts)
const safe = path.basename(params.slug); const full = path.resolve(CONTENT_DIR, safe);
if (!full.startsWith(CONTENT_DIR + path.sep)) return new Response(null, { status: 404 });
```

## Manual trace checklist
1. Data-table/search components: which state fields end up as query params.
2. Upload/download components and any `download?name=` links.
3. "Import from URL", OG-preview, avatar-by-URL features.
4. Next.js: every `route.ts`, `pages/api/*`, and `"use server"` function - run the Node patterns and trace as backend code.
5. `next.config.js` image and rewrite configuration.

## Stack-specific false positives
- `encodeURIComponent` around every interpolated value in a client URL.
- `fetch` to a constant `process.env.NEXT_PUBLIC_API_URL` plus a validated id.
- `eval` inside bundler shims/test files.

## Tooling
`npx eslint-plugin-security`, `semgrep --config p/react --config p/nextjs` (run `p/nodejs` over server folders).

## References
Next.js docs "Data Security" and "Server Actions security"; OWASP SSRF cheat sheet. Sibling skills: `audit-frontend-xss-and-dom-safety`, `audit-client-auth-and-storage`, `audit-api-contract`.
