# Node / Express (NestJS, Fastify, Koa) reference for audit-client-auth-and-storage

Client auth is a frontend topic; this file covers what the Node API
contributes to the client's flow - token issuance shape and lifetime, refresh
and logout endpoints, and what the server hands the client. Validation and
role enforcement belong to `audit-authz-and-access-control`; cookie flags, CORS
and headers to `audit-security-headers-and-middleware`.

## Stack markers
`package.json` with `jsonwebtoken`/`jose`/`@nestjs/jwt`, `passport`/`passport-jwt`/`@nestjs/passport`, `express-session`/`cookie-session`/`@fastify/secure-session`, `cookie-parser`, `lucia`, `next-auth` (server side of a Next app).

## Where the relevant code lives
`src/auth/**` (`auth.controller.ts`, `auth.service.ts`, `jwt.strategy.ts`, `refresh.strategy.ts`), `routes/auth.js`, `middleware/auth.js`, `config/jwt.ts` / `.env` (`JWT_SECRET`, `JWT_EXPIRES_IN`, `REFRESH_EXPIRES_IN`), `app.ts`/`main.ts` (`cookieParser`, `session(...)`, `cors(...)`), Socket.IO `io.use((socket, next) => socket.handshake.auth.token)` handlers, `prisma/schema.prisma` `RefreshToken` model.

## What this skill checks on the server side
- **Issuance shape**: `res.json({ accessToken, refreshToken })` versus `res.cookie('refresh_token', rt, { httpOnly: true, secure: true, sameSite: 'strict', path: '/auth/refresh', maxAge })`; `express-session` cookie model is HttpOnly by default (`cookie.httpOnly` defaults true).
- **Lifetimes**: `jwt.sign(payload, secret, { expiresIn: '30d' })` or no `expiresIn` (never expires); `JwtModule.register({ signOptions: { expiresIn } })`; `ignoreExpiration: true` in `passport-jwt` `ExtractJwt` strategy options; `session.cookie.maxAge` very long with `rolling: false`.
- **Refresh**: `/auth/refresh` exists; refresh tokens random (`crypto.randomBytes(48)`) not JWTs signed with the same secret and no state; stored hashed; rotated; revocable; read from body vs HttpOnly cookie.
- **Logout / revocation**: `/auth/logout` deleting the refresh row and `res.clearCookie(...)` with the same options; `req.session.destroy()` for sessions; JWT denylist or short TTL.
- **Where the token is read**: `ExtractJwt.fromUrlQueryParameter('token')` (query strings - logged), `fromAuthHeaderAsBearerToken()`, custom extractors from cookies - tells you what the client may do.
- **Public identifiers vs secrets**: `/api/config` or `/env.js` endpoints exposing `process.env` values to the client; Next.js `getServerSideProps` returning secrets as props (serialized into the HTML).
- **CORS**: `cors({ origin: true, credentials: true })` or `origin: '*'` with credentials (reflects any origin) - headers skill, cite here if cookies are used.

## What "good" looks like
```ts
// auth.controller.ts (Nest)
@Post('login') async login(@Body() dto: LoginDto, @Res({ passthrough: true }) res: Response) {
  const user = await this.auth.validate(dto);
  const accessToken = await this.jwt.signAsync({ sub: user.id, tid: user.tenantId }, { expiresIn: '15m' });
  const refresh = await this.refreshTokens.issue(user.id);   // randomBytes, hashed in DB, rotated on use
  res.cookie('refresh_token', refresh, { httpOnly: true, secure: true, sameSite: 'strict', path: '/auth/refresh', maxAge: 14 * 864e5 });
  return { accessToken, expiresIn: 900 };
}
@Post('logout') async logout(@Req() req, @Res({ passthrough: true }) res) {
  await this.refreshTokens.revoke(req.cookies.refresh_token); res.clearCookie('refresh_token', { path: '/auth/refresh' });
}
```
```ts
// passport-jwt strategy
super({ jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(), ignoreExpiration: false, secretOrKey: config.jwtSecret });
```

## Manual trace checklist
1. Login handler: response shape and `res.cookie` usage/flags.
2. `jwt.sign` options: `expiresIn` present and short; refresh TTL.
3. Refresh handler: rotation, reuse detection, token source.
4. Logout handler: revoke + `clearCookie` with matching `path`; `session.destroy`.
5. Config/env endpoints or SSR props leaking `process.env`.
6. Socket.IO/WebSocket auth: token in query vs `auth` payload; not logged by `morgan`/`pino-http` (redact).

## Stack-specific false positives
- Access token in the body with a short TTL and HttpOnly refresh cookie - the recommended pattern.
- `express-session` with a store and `httpOnly` default - HttpOnly path.
- `ExtractJwt.fromAuthHeaderAsBearerToken()` - the normal extractor.

## Tooling
- `grep -rn "expiresIn\|ignoreExpiration\|fromUrlQueryParameter\|res.cookie\|clearCookie" src`.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/node-express.json`.

## References
`jsonwebtoken` docs (`expiresIn`), NestJS Authentication docs, `passport-jwt` options, OWASP Session Management and JWT cheat sheets. CWE-613, CWE-522, CWE-384; ASVS 3.2-3.5; OWASP A07:2021. Sibling skills: `audit-authz-and-access-control`, `audit-security-headers-and-middleware`, `audit-secrets-and-config`.
