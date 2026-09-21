# Java / Spring reference for audit-client-auth-and-storage

Client auth is a frontend topic; this file covers what Spring Security
contributes to the client's flow - token issuance shape and lifetime, refresh
and logout endpoints, and what the server hands the client. Validation and
role enforcement belong to `audit-authz-and-access-control`; cookie flags, CORS
and headers to `audit-security-headers-and-middleware`.

## Stack markers
`pom.xml`/`build.gradle` with `spring-boot-starter-security`, `spring-boot-starter-oauth2-resource-server`, `spring-security-oauth2-authorization-server`, `jjwt`/`java-jwt`/`nimbus-jose-jwt`, `spring-session-*`.

## Where the relevant code lives
`SecurityConfig.java` (`SecurityFilterChain`, `oauth2ResourceServer().jwt()`, `sessionManagement().sessionCreationPolicy(STATELESS)`, `formLogin`, `logout()`), `AuthController`/`LoginController` (`/login`, `/refresh`, `/logout`), `JwtTokenProvider`/`JwtService` (`Jwts.builder().setExpiration(...)`, `JWT.create().withExpiresAt(...)`), `RefreshToken` entity/repository, `application.yml` (`jwt.expiration`, `jwt.secret`, `server.servlet.session.cookie.*`, `spring.security.oauth2.*`), WebSocket config (`STOMP` interceptors reading tokens from headers or query).

## What this skill checks on the server side
- **Issuance shape**: JWT in the response body (`ResponseEntity.ok(new TokenResponse(access, refresh))`) versus `ResponseCookie.from("access_token", jwt).httpOnly(true).secure(true).sameSite("Lax")` on `Set-Cookie`; session-cookie (`JSESSIONID`) model with Spring Session is the HttpOnly path by default.
- **Lifetimes**: `setExpiration(new Date(now + jwtExpirationMs))` with `jwt.expiration: 2592000000` (30 days) is a server contribution to the client storage risk; `withExpiresAt` missing entirely; `JwtDecoder` with `JwtTimestampValidator` clock skew.
- **Refresh**: `/auth/refresh` endpoint exists; refresh tokens random (`UUID`/`SecureRandom`), stored hashed, rotated, revocable, bound to user; read from body or from an HttpOnly cookie.
- **Logout / revocation**: `logout().logoutUrl("/logout").deleteCookies("JSESSIONID", "refresh_token").invalidateHttpSession(true)`; for JWT a `/auth/logout` that deletes the refresh token row; `SecurityContextLogoutHandler`.
- **Where the token is read**: `BearerTokenResolver` customizations reading query params (`allowUriQueryParameter(true)`) or cookies - tells you what the client may legitimately do.
- **Public identifiers vs secrets**: `/api/config` endpoints exposing `@Value` properties to the client.
- **CORS**: `allowedOrigins("*")` with `allowCredentials(true)` (rejected by Spring at runtime, but `allowedOriginPatterns("*")` with credentials is accepted and dangerous) - headers skill, cite here if cookies are used.

## What "good" looks like
```java
@PostMapping("/login")
public ResponseEntity<TokenResponse> login(@RequestBody LoginRequest req) {
    Authentication auth = authManager.authenticate(new UsernamePasswordAuthenticationToken(req.username(), req.password()));
    String access = jwt.createAccessToken(auth, Duration.ofMinutes(15));
    String refresh = refreshTokens.issue(auth.getName());          // random, hashed, rotated on use
    ResponseCookie cookie = ResponseCookie.from("refresh_token", refresh).httpOnly(true).secure(true)
            .sameSite("Strict").path("/api/auth/refresh").maxAge(Duration.ofDays(14)).build();
    return ResponseEntity.ok().header(HttpHeaders.SET_COOKIE, cookie.toString()).body(new TokenResponse(access, 900));
}
@PostMapping("/logout") public ResponseEntity<Void> logout(@CookieValue("refresh_token") String rt) {
    refreshTokens.revoke(rt); return ResponseEntity.noContent().header(HttpHeaders.SET_COOKIE, expiredCookie()).build(); }
```
```yaml
jwt:
  access-expiration: 15m
  refresh-expiration: 14d
```

## Manual trace checklist
1. Login endpoint: response DTO fields and `Set-Cookie` usage.
2. Token provider: access/refresh TTL values in `application*.yml`; `setExpiration` present.
3. Refresh endpoint: rotation, reuse detection, source of the refresh token.
4. Logout: `logout()` configuration or `/auth/logout` revoking refresh tokens.
5. `/config` endpoints leaking properties.
6. WebSocket/STOMP: token in query string or `CONNECT` header; not logged.

## Stack-specific false positives
- Access token in the body with a short TTL and HttpOnly refresh cookie - the recommended pattern.
- `sessionCreationPolicy(STATELESS)` with bearer tokens - not a finding by itself.
- `JwtTimestampValidator` default 60s skew.

## Tooling
- `grep -rn "setExpiration\|withExpiresAt\|expiration" --include=*.java --include=*.yml`.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/java-spring.json`.

## References
Spring Security "OAuth2 Resource Server JWT", "Logout", "Session Management" docs; OWASP Session Management and JWT cheat sheets. CWE-613, CWE-522, CWE-384; ASVS 3.2-3.5; OWASP A07:2021. Sibling skills: `audit-authz-and-access-control`, `audit-security-headers-and-middleware`, `audit-secrets-and-config`.
