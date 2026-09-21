# Node / Express (and NestJS, Fastify, Next) reference for audit-infra-and-deployment

## Stack markers
- `package.json` with `express`, `fastify`, `koa` or `@nestjs/core`; a lockfile (`package-lock.json` / `pnpm-lock.yaml` / `yarn.lock`).
- Next.js (`next.config.*` with `output: 'standalone'`) and Nuxt/Remix SSR servers are Node containers too.
- Deployment markers: `Dockerfile`, `ecosystem.config.js` (pm2), `Procfile`, `vercel.json`, `serverless.yml`, `app.yaml`, Kubernetes/Helm.

## Where the relevant code lives
- `Dockerfile` and `.dockerignore`. The `.dockerignore` must exclude `node_modules`, `.env*`, `.npmrc` and `.git`.
- `src/main.ts` / `server.js` / `app.js`: listen port, `trust proxy`, SIGTERM handling, health route.
- `.npmrc` (private registry tokens such as `//registry.npmjs.org/:_authToken=`), `.env*` files, `config/` folders.
- Migration tools: `prisma/migrations`, `knexfile`, TypeORM `migrations/`, Sequelize `migrations/`.

## Dangerous / interesting APIs and patterns
Images:
- `FROM node:22` (full Debian, about 1 GB) as the final image. Prefer `node:22-alpine`, `node:22-bookworm-slim`, or `gcr.io/distroless/nodejs22-debian12:nonroot` for the runtime stage.
- `RUN npm install` is not reproducible; use `npm ci`, which respects the lockfile. In the runtime stage use `npm ci --omit=dev` (npm 8+; older npm uses `--only=production`) or copy a pruned `node_modules` from a build stage.
- No `USER`: official node images run as root but ship a `node` user (uid 1000). Use `USER node` and `COPY --chown=node:node`.
- `CMD ["npm", "start"]` or `CMD npm run start`: npm does not forward SIGTERM reliably, so pods are killed with SIGKILL after the grace period and in-flight requests drop. Use `CMD ["node", "dist/main.js"]`, plus `tini`/`dumb-init` (or `docker run --init`) if the app spawns child processes.
- `nodemon`, `ts-node`, `ts-node-dev`, `vite`, `next dev`, `--inspect` or `--inspect=0.0.0.0:9229` in the image or manifest command.
- `ENV NODE_ENV=development`, or `NODE_ENV=production` missing. Express only caches views and trims error output in production mode.
- `pm2` inside a container duplicates the orchestrator's job. If it is used, run `pm2-runtime` with one process per container.
- A `--max-old-space-size` larger than the memory limit, or none set on Node < 20, where heap sizing ignores cgroup limits.

Secrets:
- `COPY .npmrc`, or `ARG NPM_TOKEN` + `RUN echo "//registry...:_authToken=$NPM_TOKEN" > .npmrc`: the token stays in layer history. Use `RUN --mount=type=secret,id=npmrc,target=/root/.npmrc npm ci`.
- `COPY .env` into the image, or `dotenv` loading a baked-in file in production.

Runtime:
- Missing health route. Use NestJS `@nestjs/terminus` (`HealthCheckService`), Fastify `@fastify/under-pressure`, or a simple `/healthz` plus a `/readyz` that checks the DB pool.
- Behind an ingress: set `app.set('trust proxy', 1)` (Express) or `trustProxy: true` (Fastify). Otherwise `req.secure` and per-IP rate limits are wrong.
- Graceful shutdown: `process.on('SIGTERM', () => server.close(...))`, or NestJS `app.enableShutdownHooks()`.
- Migrations at startup (`prisma migrate deploy` in `CMD`) race across replicas. Prefer a Job or pipeline step.

## What "good" looks like
```dockerfile
# syntax=docker/dockerfile:1
FROM node:22-alpine@sha256:<digest> AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc npm ci
COPY . .
RUN npm run build && npm prune --omit=dev

FROM node:22-alpine@sha256:<digest>
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build --chown=node:node /app/node_modules ./node_modules
COPY --from=build --chown=node:node /app/dist ./dist
USER node
EXPOSE 3000
CMD ["node", "dist/main.js"]
```
Next.js: copy `.next/standalone`, `.next/static` and `public/`, then run `node server.js`.

## Manual trace checklist
1. Runtime stage base, user and command (node directly, not npm), and `NODE_ENV`.
2. How private-registry tokens reach `npm ci` (BuildKit secret vs ARG/COPY).
3. Health and readiness routes exist and match the probe paths and ports.
4. SIGTERM handling against `terminationGracePeriodSeconds` / compose `stop_grace_period`.
5. Secrets in the running environment: `secretKeyRef`, a cloud secret manager SDK, or literals in manifests.
6. Migrations, and rollback compatibility with the previous release.
7. Serverless/PaaS (Vercel, Netlify, Lambda): rollback is `vercel rollback <deployment>`, a Lambda alias shift, or a redeploy. Record which one, and whether it was ever used.

## Stack-specific false positives
- `npm install` in a build stage of a repo that deliberately commits no lockfile (a library). Still recommend a lockfile, at lower severity.
- The full `node:22` image in the build stage only.
- `--inspect` in `docker-compose.override.yml` or a `.vscode` launch config is local only.
- Distroless node images with no `USER`: the `:nonroot` tag is already non-root.

## Tooling
- `hadolint Dockerfile` (DL3016 pin npm versions, DL3025 JSON CMD), `trivy config .`, `checkov -d .`.
- `docker run --rm img id -u` or `docker inspect --format '{{.Config.User}}' img` to confirm the user.
- `dockerfilelint` is unmaintained; prefer hadolint.

## References
- Node.js Docker best practices (nodejs/docker-node `docs/BestPractices.md`); Snyk "10 best practices to containerize Node.js web applications with Docker".
- Express "Production best practices: performance and reliability", "Health checks and graceful shutdown".
- CIS Docker Benchmark 4.1/4.3/4.10; CWE-250, CWE-489, CWE-798.
