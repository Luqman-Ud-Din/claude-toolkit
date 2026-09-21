# Node / Express (NestJS, Fastify, Koa) reference for audit-report-generator

What the report should enumerate and how to phrase findings when the backend is Node.
The generator is stack-agnostic; this file guides the scope table, executive wording and
remediation grouping for Node services.

## Stack markers
`package.json` with `express`, `@nestjs/core`, `fastify`, `koa`, `hapi`; `src/main.ts`
(Nest), `app.js|ts`, `server.js|ts`; `Dockerfile` with `node:` base; `pm2`/`ecosystem.config.js`.
Monorepos (`apps/*`, `packages/*`, workspaces): one scope row per deployable app.

## Where the relevant code lives (what "Scope" must enumerate)
- Deployable apps and their bootstrap file (middleware order lives there).
- Entry points: routers / Nest controllers, WebSocket gateways, queue workers (BullMQ, SQS consumers), cron jobs (`node-cron`).
- Auth: passport strategies, `jsonwebtoken.verify` call sites, Nest guards and the global guard registration.
- Config: `.env*` files present in the repo, `config/` folder, `process.env` reads.
- Out-of-repo for "Not checked": reverse proxy / CDN headers, secret manager contents, runtime Node version.

## Findings that are typical launch blockers (and how to phrase them)
| Engineering finding | Executive wording |
|---|---|
| Router mounted before the auth middleware; `@Public()` on admin controller | "Administrative functions are reachable without logging in." |
| `findUnique({ where: { id } })` from `req.params` without user/tenant predicate | "One customer can read or change another customer's records." |
| `$queryRawUnsafe` / `sequelize.query` with template literals | "A crafted input can read or delete the whole database." |
| `exec(\`... ${userInput}\`)` | "A crafted input can run commands on the server." |
| `Model.create(req.body)` on a model with role/owner columns | "A user can make themselves an administrator by adding a field to a request." |
| `.env` with production secrets committed; `jwt.decode` used as verification | "Anyone with repository access can impersonate any user." |
| No `express.json({ limit })`, no `multer` limits | "A single request can take the service down." |

## What "good" looks like (remediation plan wording)
- "Mount `authenticate` before `apiRouter` in `app.ts`; add a supertest case expecting 401."
- "Add `ownerId: req.user.id` to the `where` clause in `orders.service.ts`; return 404 on miss."
- "Replace `$queryRawUnsafe` with the tagged `$queryRaw` template."
- "Enable `ValidationPipe({ whitelist: true, forbidNonWhitelisted: true })` globally (Nest) or a zod schema per route."
- "Add `helmet()` and `cors({ origin: allowList })` in the bootstrap; set `express.json({ limit: '1mb' })`."
Group tickets by bootstrap file (all middleware/header items), by service module (ownership items), by `.env` (secret items).

## Report review checklist (manual trace)
1. Scope table names the bootstrap file per app and states whether middleware order was reviewed.
2. Queue workers and cron jobs are listed (they run without HTTP auth).
3. Dependency findings cite `npm audit --json` output with CVE ids and the affected path (direct vs transitive).
4. Every Critical/High cites a file under `src/`, not `dist/` or `node_modules/`.
5. If the app is behind an API gateway that sets headers, the report says so and marks V14.4 as verified there or not checked.

## Stack-specific false positives
- `cors()` open on a public read-only API with no cookies.
- `$queryRaw` tagged template (parameterized).
- `.env.example` with placeholder values.
- `eval`-like hits inside `node_modules` or build output.

## Tooling (evidence to expect in Appendix B)
`npm audit --json`, `npx retire --outputformat json`, `eslint-plugin-security` output,
`npx semgrep --config p/nodejs --json`, `curl -sI` header dumps, `--heapsnapshot` files for leak findings.
Export: `pandoc audit/audit-report.md -o audit/audit-report.docx --toc --from gfm`.

## Executive glossary (translate before the summary goes out)
- "middleware order" -> "the order in which the server checks each request".
- "guard" / "passport strategy" -> "the login check".
- "raw query" -> "hand-written database query".
- "transitive dependency" -> "a library pulled in by another library".

## References
Express "Production Best Practices: Security"; NestJS security docs (Helmet, CORS, Rate limiting);
OWASP NodeJS Security Cheat Sheet; ASVS 4.0.3 V4, V5, V12.1, V14.4; CWE-306, CWE-639, CWE-89, CWE-78, CWE-915.
