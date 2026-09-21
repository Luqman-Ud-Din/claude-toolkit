# Node / Express reference for audit-secrets-and-config

## Stack markers
`package.json`, `.env`/`.env.*`, `config/*.js|json`, `Dockerfile`.

## Where the relevant code lives
`.env` files (should be git-ignored; `.env.example` is the committed template), `config/` modules, `app.js`/`server.js` (CORS via the `cors` package, `helmet`, HTTPS), `process.env.*` reads, `Dockerfile`/compose (`NODE_ENV`).

## Dangerous / interesting keys and patterns
- Secrets: `apiKey`/`secret`/`token`/`password`/`clientSecret` assigned a literal, DB URLs `mongodb+srv://user:pass@...`, `sk_live_...`. Read from `process.env` instead, loaded from a secret manager in prod.
- A committed `.env` with real values (vs `.env.example` placeholders). Check `.gitignore` covers `.env`.
- Debug/prod: `NODE_ENV=development` in a deploy config; missing `helmet`; source maps in prod.
- CORS: `cors()` with no options (reflects the request origin) or `origin: '*'` together with `credentials: true`.

## What "good" looks like
```js
const dbUrl = process.env.DATABASE_URL;              // from env / secret manager
app.use(cors({ origin: ['https://app.example.com'], credentials: true }));  // explicit list
app.use(helmet());
// .env is git-ignored; .env.example ships placeholders only
```

## Manual trace checklist
1. Is `.env` git-ignored, and is any committed `.env`/config holding real secrets?
2. Every `process.env` fallback like `process.env.KEY || 'hardcoded'` - the fallback is a leaked secret.
3. CORS options: reflected/wildcard origin + credentials?
4. `NODE_ENV` is `production` in deploy; helmet present.
5. `git_secret_scan.py` over history (a rotated `.env` may still be in old commits).

## Stack-specific false positives
`.env.example`/`.env.sample` with placeholders; `cors()` on a truly public, cookie-less API (note it, lower severity); test fixtures with fake keys.

## Tooling
`dotenv`, `helmet`, plus `references/tool-candidates.md`. Scripts: `git_secret_scan.py`, `config_key_inventory.py`.

## References
CWE-798, CWE-321, CWE-489, CWE-942, CWE-16. ASVS 2.10, 14.1, 14.4/14.5. OWASP A05:2021, A02:2021.
