# Vue (Vite, Vue CLI, Nuxt) reference for audit-infra-and-deployment

On the frontend, this topic covers build, packaging, static hosting, runtime
config and rollback. Headers belong to `audit-security-headers-and-middleware`,
bundle settings to `audit-frontend-best-practices`, and secrets in the bundle to
`audit-client-auth-and-storage`.

## Stack markers
- `package.json` with `vue`, plus `vite` (`vite.config.*`), `@vue/cli-service` (`vue.config.js`, in maintenance mode), or `nuxt` (`nuxt.config.*`).
- Nuxt 3 `nuxi build` produces a Nitro server (`.output/server/index.mjs`), which is a Node container, so read `node-express.md` too. `nuxi generate` produces static files in `.output/public`.
- Hosting markers: `Dockerfile` + `nginx.conf`, `netlify.toml`, `vercel.json`, `staticwebapp.config.json`, `firebase.json`, S3/CloudFront IaC.

## Where the relevant code lives
- Build output: Vite `dist/`, Vue CLI `dist/`, Nuxt `.output/`.
- `.env.production`, `.env.staging`: `VITE_*` / `VUE_APP_*` values are inlined at build time. Nuxt `runtimeConfig.public` can be overridden at runtime with `NUXT_PUBLIC_*` env vars.
- `vite.config.*` `base` / `vue.config.js` `publicPath` must match the path the app is served under.

## Dangerous / interesting APIs and patterns
- Dev servers in production: `vite`, `vite preview`, `vue-cli-service serve`, `nuxi dev`, or `npm run dev`/`serve` in a Dockerfile, compose file or manifest.
- Static output served from a `node:*` final image, or from the stock root `nginx` image on port 80, instead of `nginxinc/nginx-unprivileged` on 8080 (uid 101).
- Per-environment builds with `vite build --mode staging` produce different artefacts per environment. Prefer build once plus runtime config: `/config.json`, `window.__ENV__` via an nginx `docker-entrypoint.d` script, or Nuxt `NUXT_PUBLIC_*` runtime env.
- Secrets passed as `ARG VITE_*` build args ship in the bundle and image history.
- History-mode router (`createWebHistory`) without a server fallback (`try_files $uri $uri/ /index.html;`): deep links 404.
- A `base`/`publicPath` that doesn't match the ingress path makes assets 404 after deploy. That is a common trigger for an emergency rollback.
- A Nuxt server image running as root, `NITRO_PORT`/`PORT` not matching the probes, or no health route (add `server/routes/healthz.ts`).
- A long-cached `index.html` defeats rollback. Hashed assets can be immutable.

## What "good" looks like
```dockerfile
FROM node:22-alpine@sha256:<digest> AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine@sha256:<digest>
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
```
Nuxt server runtime stage: `COPY --from=build --chown=node:node /app/.output ./.output`, `USER node`, `ENV NODE_ENV=production PORT=3000`, `CMD ["node", ".output/server/index.mjs"]`.

## Manual trace checklist
1. Build command and mode per environment, and whether one artefact is promoted.
2. Serving process, user, port, SPA fallback, and the `base` path against the ingress path.
3. Cache headers for `index.html` and assets, and CDN invalidation on deploy and rollback.
4. TLS termination point and redirect.
5. Rollback mechanism (previous image tag, Netlify/Vercel previous deploy, versioned bucket prefix) and evidence that it has been used.

## Stack-specific false positives
- `vite` or `nuxi dev` in compose overrides or dev containers.
- `VITE_*` values that are public by design (public API base URL, analytics id).
- `node` in the build stage. Nuxt server images use `node` at runtime legitimately.

## Tooling
- `hadolint Dockerfile`, `trivy config .`, `checkov -d .`.
- `npx nuxi build`, then `node .output/server/index.mjs` locally to confirm the port and health route.
- `curl -I` a deep link and `/index.html` against the running container or CDN.

## References
- Vite "Deploying a Static Site"; Vue Router "Different History modes" (server configuration examples); Nuxt "Deployment" and "Runtime Config".
- CIS Docker Benchmark 4.1/4.3; CWE-319, CWE-525.
