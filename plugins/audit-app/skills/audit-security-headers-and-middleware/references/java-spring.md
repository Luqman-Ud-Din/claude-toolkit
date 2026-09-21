# Java / Spring Boot reference for audit-security-headers-and-middleware

## Stack markers
`pom.xml`/`build.gradle` with `spring-boot-starter-web`/`webflux`, `spring-boot-starter-security`, optional `spring-cloud-gateway`, `bucket4j`, `spring-session`. Config in `application*.yml|properties`.

## Where the relevant code lives
`SecurityConfig.java` (`@Bean SecurityFilterChain filterChain(HttpSecurity http)` - the pipeline: `http.csrf()`, `cors()`, `headers()`, `sessionManagement()`, `authorizeHttpRequests()`, `oauth2ResourceServer()`, `addFilterBefore/After`), `WebMvcConfigurer` (`addCorsMappings`, `addInterceptors`), `@ControllerAdvice` (error responses), custom `OncePerRequestFilter`s (JWT, rate limit, headers), `application*.yml` (`server.servlet.session.cookie.*`, `spring.servlet.multipart.max-*`, `server.error.include-stacktrace`, `server.error.include-message`, `management.endpoints.web.exposure.include`), gateway `RouteLocator`/`spring.cloud.gateway.routes` filters, controllers using `ResponseCookie`/`Cookie`.

## Dangerous / interesting APIs and patterns
- Headers: `http.headers(h -> h.disable())` or `.headers().disable()`; `frameOptions().disable()` (often added for H2 console and left in prod); no `contentSecurityPolicy(...)` (Spring sets X-Content-Type-Options, X-Frame-Options DENY, HSTS on HTTPS, Cache-Control by default - CSP, Referrer-Policy, Permissions-Policy are **not** default); `httpStrictTransportSecurity().disable()`; `maxAgeInSeconds` < 15552000; `referrerPolicy(NO_REFERRER_WHEN_DOWNGRADE)`; `server.server-header` set to a version string; Tomcat `server.error.whitelabel` disclosure.
- Order: `addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class)` missing (filter registered as a plain `@Component` runs outside Security order and for every request); `authorizeHttpRequests()` before `oauth2ResourceServer()` is fine (declarative), but `anyRequest().permitAll()` placed before specific matchers wins (first-match); `requestMatchers("/**").permitAll()`; `.anyRequest().permitAll()` at the end; `securityMatcher` chains ordered so a permissive chain (`@Order(1)`) shadows the API chain; CORS handled by a servlet filter after Security (preflight gets 401) - `http.cors()` must be enabled so `CorsFilter` runs early.
- CORS: `@CrossOrigin` with no origins (`*`), `@CrossOrigin(origins = "*", allowCredentials = "true")`, `allowedOriginPatterns("*")` + `allowCredentials(true)`, `CorsConfiguration.applyPermitDefaultValues()` with credentials, `setAllowedOrigins(List.of("*"))`.
- Cookies: `server.servlet.session.cookie.http-only=false`, `secure=false` in prod profile, `same-site` unset (Spring Boot 2.6+ supports `server.servlet.session.cookie.same-site=strict`), `ResponseCookie.from(...)` without `.httpOnly(true).secure(true).sameSite(...)`, `new Cookie(...)` without `setHttpOnly/setSecure`, `rememberMe()` with default key and long validity.
- CSRF: `http.csrf(csrf -> csrf.disable())` / `.csrf().disable()` while session or cookie auth exists (`formLogin`, `httpBasic` with sessions, `spring-session`, `JSESSIONID`); `CookieCsrfTokenRepository.withHttpOnlyFalse()` is fine (double-submit for SPAs) but requires the SPA to send the header; `ignoringRequestMatchers("/**")`.
- Rate limiting: no `bucket4j`/`resilience4j-ratelimiter`/gateway `RequestRateLimiter` on `/login`, `/auth/**`, `/otp`, `/password/reset`; `Bucket` keyed on `X-Forwarded-For` without a trusted proxy.
- Body limits: `spring.servlet.multipart.max-file-size=-1`/`max-request-size=-1`; `server.tomcat.max-swallow-size=-1`; `server.max-http-request-header-size` huge; WebFlux `spring.codec.max-in-memory-size=-1`.
- Errors: `server.error.include-stacktrace=always`, `include-message=always`, `include-binding-errors=always` in prod; `@ExceptionHandler` returning `ex.getMessage()`/stack; actuator `management.endpoints.web.exposure.include=*` unauthenticated (`/actuator/env`, `/heapdump`).

## What "good" looks like
```java
@Bean SecurityFilterChain api(HttpSecurity http, JwtAuthFilter jwt) throws Exception {
    http.securityMatcher("/api/**")
        .csrf(csrf -> csrf.disable())                          // bearer-only API, no cookies (document it)
        .cors(Customizer.withDefaults())                       // CorsConfigurationSource bean with explicit origins
        .headers(h -> h
            .contentSecurityPolicy(c -> c.policyDirectives("default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"))
            .referrerPolicy(r -> r.policy(ReferrerPolicyHeaderWriter.ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN))
            .permissionsPolicy(p -> p.policy("camera=(), microphone=(), geolocation=()"))
            .httpStrictTransportSecurity(s -> s.maxAgeInSeconds(31536000).includeSubDomains(true)))
        .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
        .exceptionHandling(e -> e.authenticationEntryPoint(new HttpStatusEntryPoint(HttpStatus.UNAUTHORIZED)))
        .authorizeHttpRequests(a -> a.requestMatchers("/api/auth/login", "/api/auth/refresh").permitAll().anyRequest().authenticated())
        .addFilterBefore(jwt, UsernamePasswordAuthenticationFilter.class);
    return http.build();
}
```
```yaml
server.servlet.session.cookie: { http-only: true, secure: true, same-site: strict }
spring.servlet.multipart: { max-file-size: 10MB, max-request-size: 12MB }
server.error: { include-stacktrace: never, include-message: never }
```
Rate limit: `bucket4j` filter on `/api/auth/**` keyed by IP + username, 5/min.

## Manual trace checklist
1. Every `SecurityFilterChain` bean and its `@Order`/`securityMatcher`; resolve first-match precedence for `permitAll`.
2. `headers()` block: what is set, what is disabled; CSP/Referrer/Permissions presence.
3. Auth model: `formLogin`/sessions vs `oauth2ResourceServer`/JWT -> CSRF decision; `csrf().disable()` justification.
4. Cookie properties in `application-prod.yml` and every `ResponseCookie`/`Cookie` in controllers.
5. CORS source: `CorsConfigurationSource` bean, `@CrossOrigin` annotations, `addCorsMappings`; compare with frontend host.
6. Rate limiting on auth endpoints; gateway filters if Spring Cloud Gateway.
7. Multipart/body limits; actuator exposure; error disclosure settings per profile.

## Stack-specific false positives
- `csrf().disable()` on a stateless bearer-only chain with `SessionCreationPolicy.STATELESS` and no cookies - Info (document).
- `frameOptions().sameOrigin()` for the H2 console in the **dev** profile only.
- Spring's default X-Content-Type-Options/X-Frame-Options/HSTS are emitted without explicit code - do not report them missing unless `headers().disable()`.
- `CookieCsrfTokenRepository.withHttpOnlyFalse()` - intended for SPA double-submit.

## Tooling
- `python scripts/extract_middleware.py <repo> --stack java-spring` (bundled; parses `http.*` chain and `addFilter*` calls).
- `python scripts/check_headers.py https://host` (bundled) when a URL is supplied.
- `mvn dependency:tree | grep -i "bucket4j\|resilience4j\|spring-session"`.
- `spotbugs` + `findsecbugs` (SPRING_CSRF_PROTECTION_DISABLED, COOKIE_USAGE, INSECURE_COOKIE, HTTPONLY_COOKIE).

## References
Spring Security "Security HTTP Response Headers", "CSRF", "CORS", "Filter ordering" docs; Spring Boot common application properties; OWASP HTTP Headers and CSRF cheat sheets. CWE-306, CWE-1004, CWE-614, CWE-352, CWE-942, CWE-307, CWE-400, CWE-209; ASVS 1.4.4, 3.4.x, 4.2.2, 13.2.x, 14.4.x, 14.5.x; OWASP A01/A05/A07:2021.
