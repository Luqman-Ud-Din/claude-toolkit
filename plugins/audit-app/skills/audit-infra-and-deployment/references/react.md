# React (Vite, CRA, Next.js) reference for audit-infra-and-deployment

On the frontend, this topic covers build, packaging, static hosting, runtime
config and release rollback. Headers belong to
`audit-security-headers-and-middleware`, bundle settings to
`audit-frontend-best-practices`, and secrets in the bundle to
`audit-client-auth-and-storage`.

## Stack markers
- `package.json` with `react`, plus `vite` (`vite.config.*`), `react-scripts` (CRA, deprecated), or `next` (`next.config.*`).
- Next.js `output: 'standalone'`, or any SSR (`next start`, Remix, React Router framework mode), is a Node server container, so read `node-express.md` too. `output: 'export'` produces static files.
- Hosting markers: `Dockerfile` + `nginx.conf`, `vercel.json`, `netlify.toml`, `amplify.yml`, `staticwebapp.config.json`, `firebase.json`, S3 + CloudFront IaC.

## Where the relevant code lives
- Build output: Vite `dist/`, CRA `build/`, Next `.next/` (standalone: `.next/standalone`, `.next/static`, `public/`), static export `out/`.
- `.env`, `.env.production`: `VITE_*`, `REACT_APP_*` and `NEXT_PUBLIC_*` values are inlined into the bundle at build time.
- `Dockerfile`, `nginx.conf`, and entrypoint scripts that write `env-config.js`.

## Dangerous / interesting APIs and patterns
- Dev servers in production: `vite`, `vite preview` (its own docs say not for production), `react-scripts start`, `next dev`, `npm run dev`, or `npm start` when it maps to one of those.
- `serve -s build` in a Node image works, but it keeps a Node runtime and `npm` around for static files. Prefer nginx/caddy or a CDN.
- Per-environment builds: a `VITE_API_URL` baked in at build time means staging and production run different artefacts. Build once, then inject `window.__ENV__` at container start (`/docker-entrypoint.d/40-env.sh` with `envsubst` in nginx images) or fetch `/config.json`.
- Secrets in `VITE_*`/`REACT_APP_*`/`NEXT_PUBLIC_*` build args (e.g. `ARG VITE_STRIPE_SECRET`) end up in the JS bundle and in image history.
- A Next.js standalone image running as root (the `node:*` default). Add `USER node` or the `nextjs` user from the official example, and set `HOSTNAME=0.0.0.0` and `PORT`.
- Missing SPA fallback for client-side routing: nginx `try_files ... /index.html`, an S3/CloudFront custom error response mapping 403/404 to `/index.html`, or SWA `navigationFallback`.
- A long-cached `index.html` on a CDN: users don't see a rollback until the TTL expires. Invalidate it (`aws cloudfront create-invalidation --paths "/index.html"`).

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
COPY env.sh /docker-entrypoint.d/40-env.sh
EXPOSE 8080
```
Next.js standalone runtime stage: `COPY --from=build --chown=node:node /app/.next/standalone ./`, `COPY --from=build /app/.next/static ./.next/static`, `USER node`, `CMD ["node", "server.js"]`.

## Manual trace checklist
1. Which command produces the artefact, and whether it is promoted unchanged across environments.
2. The serving process in production (nginx, CDN or `node server.js`, never a dev server), its user and port.
3. SPA fallback, and cache headers for `index.html` vs hashed assets.
4. The TLS termination point (CDN, ingress, PaaS) and the HTTP-to-HTTPS redirect.
5. Rollback mechanism: Vercel Instant Rollback / `vercel rollback`, Netlify "Publish deploy" on a previous deploy, versioned S3 prefixes, or the previous image tag. Check whether it has ever been exercised.
6. Preview environments (Vercel/Netlify/SWA) that point at production APIs or data.

## Stack-specific false positives
- `vite` or `next dev` in compose files for local development, or in `.devcontainer`.
- `NEXT_PUBLIC_*` values that really are public (analytics ids, publishable Stripe keys `pk_*`).
- No Dockerfile at all when hosting is Vercel/Netlify/SWA. Check the platform config instead.

## Tooling
- `hadolint Dockerfile`, `trivy config .`, `checkov -d .` (for S3/CloudFront IaC).
- `npx vercel ls`, `npx vercel rollback --help`, `netlify api listSiteDeploys --data '{"site_id":"..."}'`.
- `curl -I https://host/deep/link` (expect 200) and `curl -I https://host/index.html` (expect no-cache).

## References
- Vite "Deploying a Static Site" and "Env Variables and Modes"; Next.js "Deploying" (standalone output, Docker example).
- CIS Docker Benchmark 4.1/4.3; CWE-319, CWE-540 (information in source), CWE-525.
