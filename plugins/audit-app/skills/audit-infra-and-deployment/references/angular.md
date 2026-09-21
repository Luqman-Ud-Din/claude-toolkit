# Angular (and Ionic/Capacitor) reference for audit-infra-and-deployment

On the frontend, this topic covers how the SPA is built, packaged, served and
rolled back. Browser security headers (CSP, HSTS) belong to
`audit-security-headers-and-middleware`, and bundle settings (source maps,
budgets) to `audit-frontend-best-practices`. This file covers the container,
static hosting, per-environment builds and release rollback.

## Stack markers
- `angular.json`, `package.json` with `@angular/core`; `src/environments/environment*.ts`.
- SSR: `@angular/ssr` (Angular 17+) or `@nguniversal/*`, with `server.ts` and output `dist/<project>/server/server.mjs`. SSR runs as a Node container, so read `node-express.md` too.
- Mobile: `capacitor.config.ts`, `ionic.config.json`, `android/`, `ios/`. These ship through app stores, not containers.
- Hosting markers: `Dockerfile` + `nginx.conf`, `staticwebapp.config.json` (Azure SWA), `firebase.json`, `vercel.json`, `netlify.toml`, S3/CloudFront Terraform, `web.config` (IIS URL rewrite).

## Where the relevant code lives
- `angular.json` `configurations` (production, staging, ...) and `fileReplacements` for `environment.*.ts`.
- `Dockerfile`, `nginx.conf` / `default.conf`, `docker-entrypoint.d/*.sh` (runtime config injection).
- `ngsw-config.json`: service worker caching, which affects rollback.
- `proxy.conf.json` is used only by the dev server. Production routing must be set up in nginx, the ingress or the gateway.

## Dangerous / interesting APIs and patterns
- `CMD ["ng", "serve", ...]`, `npm start` (usually `ng serve`) or `ng serve --host 0.0.0.0` in a Dockerfile, compose file or manifest. That is the dev server in production: no production build guarantees, dev-mode diagnostics, and not hardened.
- A final image `FROM node:*` just to serve static files. A web server image (`nginx:1.27-alpine`, `nginxinc/nginx-unprivileged:1.27-alpine`, `caddy:2-alpine`) is smaller and carries no build toolchain.
- The stock `nginx` image runs its master process as root and listens on 80. `nginxinc/nginx-unprivileged` runs as uid 101 on 8080, so update `containerPort` and probes to match.
- Output path: the Angular 17+ application builder writes to `dist/<project>/browser`. Copying `dist/<project>` instead serves a directory listing or 404s.
- No SPA fallback (`try_files $uri $uri/ /index.html;`): deep links 404 after a reload.
- Caching: `index.html` must be `Cache-Control: no-cache`, and hashed bundles `max-age=31536000, immutable`. If `index.html` is cached for long, users don't see a rollback or roll-forward.
- Environment parity: building one image per environment with `ng build --configuration=staging|production` means the artefact tested in staging is not the one shipped. Prefer build once, then inject runtime config: an `assets/config.json` loaded in an `APP_INITIALIZER` / `provideAppInitializer`, rendered by an entrypoint script or mounted from a ConfigMap.
- Secrets: everything in `environment*.ts` ships to every browser. Map and Firebase API keys are public by design; server keys are not (owned by `audit-client-auth-and-storage` / `audit-secrets-and-config`).
- `ngsw` service worker: after a bad release, clients keep the cached app until the service worker updates. The rollback plan must include `SwUpdate` handling or a kill switch (`safety-worker.js`).
- `--source-map` in production images: see `audit-frontend-best-practices`.

## What "good" looks like
```dockerfile
FROM node:22-alpine@sha256:<digest> AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npx ng build --configuration production

FROM nginxinc/nginx-unprivileged:1.27-alpine@sha256:<digest>
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/app/browser /usr/share/nginx/html
EXPOSE 8080
```
```nginx
server {
  listen 8080;
  root /usr/share/nginx/html;
  location = /index.html { add_header Cache-Control "no-cache"; }
  location ~* \.(js|css|woff2)$ { add_header Cache-Control "public, max-age=31536000, immutable"; }
  location / { try_files $uri $uri/ /index.html; }
  location = /healthz { return 200 "ok"; }
}
```

## Manual trace checklist
1. How the production bundle is produced (which configuration), and whether the same artefact is promoted across environments.
2. Serving image: base, user, port, SPA fallback, caching headers, and the health path the probes use.
3. Where TLS terminates (ingress/CDN), and that HTTP redirects to HTTPS there.
4. The production API routing that replaces `proxy.conf.json` (ingress paths, gateway, CORS).
5. Rollback: previous image tag, CDN version or Static Web Apps environment, plus service worker behaviour.
6. Mobile (Capacitor/Ionic): staged rollout percentage in Play Console or phased release in App Store Connect, and whether live-update channels (Capgo, Appflow) allow reverting a bundle.

## Stack-specific false positives
- A `node` image in the build stage.
- `ng serve` in `docker-compose.override.yml`, `.devcontainer`, or README dev instructions.
- Public browser keys (Firebase web config, Maps JS keys restricted by referrer) in `environment.prod.ts`.
- Stock `nginx:alpine` where the pod `securityContext` sets `runAsNonRoot` and a custom config listens on 8080. Confirm the config.

## Tooling
- `npx ng build --configuration production --stats-json` to confirm the output path.
- `hadolint Dockerfile`, `trivy config .`. Run `docker run --rm -p 8080:8080 img`, then `curl -I localhost:8080/some/deep/link` (expect 200) and `curl -I localhost:8080/index.html` (expect no-cache).
- `gixy nginx.conf` for nginx misconfiguration.

## References
- Angular "Deployment" guide (server configuration, fallback to index.html), "Service worker in production" (safety worker).
- nginx-unprivileged image docs; CIS Docker Benchmark 4.1/4.3; CWE-319, CWE-525 (cache).
