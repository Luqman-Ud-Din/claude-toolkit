# React reference for audit-dependency-vulnerabilities

## Stack markers
`package.json` with `react` (+ `react-dom`); `next` for Next.js; `vite.config.*`,
`react-scripts` (Create React App), `remix`, `gatsby`. Lockfile decides the
manager. Variants: Next.js/Remix run server code (middleware, API routes, SSR) so
server-side advisories are reachable from the internet; CRA is unmaintained
(`react-scripts` 5 pins old webpack and dozens of dev advisories).

## Where the relevant code lives
- Direct deps: `dependencies` (client bundle and, for Next/Remix, server) vs
  `devDependencies` (bundler, test tools).
- Framework version: `next`, `react`, `react-dom`; Next.js security patches land
  in the two most recent minors.
- `overrides`/`resolutions` show existing transitive pins.
- Edge/server code: `middleware.ts`, `app/api/**/route.ts`, `pages/api/**`.

## Dangerous / interesting APIs and patterns
- Next.js: middleware auth bypass CVE-2025-29927 (fixed 15.2.3 / 14.2.25 / 13.5.9),
  SSRF in server actions CVE-2024-34351 (< 14.1.1), cache poisoning CVE-2024-46982.
- Client libraries with advisories: `dompurify` < 3.1.3 (mXSS - directly feeds
  `dangerouslySetInnerHTML`), `react-markdown` < 8 with `allowDangerousHtml`,
  `lodash` < 4.17.21, `axios` < 1.6.0 / < 0.21.2, `serialize-javascript` < 3.1.0
  (SSR), `jsonwebtoken` < 9 (Next API routes), `formidable` < 3.5.x,
  `sharp` < 0.32.6 (libwebp CVE-2023-4863 in image optimisation).
- `react-scripts` present at all: unmaintained toolchain (Low, but signals the
  dependency tree will never be clean).
- `*`/`latest` versions, git URL deps, `.npmrc audit=false`.

## What "good" looks like
```json
{
  "dependencies": { "next": "15.2.4", "react": "19.0.0", "dompurify": "^3.1.7" },
  "overrides": { "semver": "^7.5.4" }
}
```
CI: `npm ci --ignore-scripts && npm audit --omit=dev --audit-level=high`;
Renovate/Dependabot with grouped minor updates and separate security PRs.

## Manual trace checklist
1. Next.js version against the middleware-bypass and server-action advisories:
   if middleware is the only auth check, a vulnerable version is Critical.
2. `dangerouslySetInnerHTML` sites: which sanitizer version guards them (hand the
   DOM question to `audit-frontend-xss-and-dom-safety`, keep the version finding here).
3. API routes / server actions: server-side packages (`jsonwebtoken`, `formidable`,
   `sharp`) follow `node-express.md` reachability rules.
4. Transitive advisories through `react-scripts`/`webpack`: build-time only unless
   the dev server is exposed; group as one Low.
5. Lockfile present and CI uses `npm ci`/`pnpm install --frozen-lockfile`.

## Stack-specific false positives
- The bulk of CRA `npm audit` output (nth-check, postcss, svgo) is build-time.
- `react`/`react-dom` themselves rarely have advisories; version age is a
  maintenance finding, not a vulnerability.
- Duplicate reports for hoisted vs nested copies of one package - one finding,
  unless different versions.

## Tooling
- `npm audit --json`, `pnpm audit --json`, `yarn npm audit --all --json`
- `npx npm-check-updates` / `npm outdated --long`
- `trivy fs .`, `osv-scanner --lockfile package-lock.json`
- `npx next info` (version + Node version), `npm view next time --json`

## References
CWE-1395, CWE-79 (client-side sanitizer bypasses), CWE-918 (SSRF in server
actions), OWASP A06:2021, ASVS 14.2, Next.js security advisories
(github.com/vercel/next.js/security/advisories). Sibling skills:
`audit-frontend-xss-and-dom-safety`, `audit-client-auth-and-storage`.
