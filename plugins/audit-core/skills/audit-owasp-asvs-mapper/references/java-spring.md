# Java / Spring reference for audit-owasp-asvs-mapper

Which ASVS 4.0 controls Spring Boot + Spring Security satisfy by default, which need
explicit configuration to count as Verified, and where the evidence lives.

## Stack markers
`pom.xml` / `build.gradle(.kts)` with `spring-boot-starter-*`, `@SpringBootApplication`,
`application.yml|properties`. Variants: Spring MVC vs WebFlux; Spring Security filter
chain (`SecurityFilterChain` bean) vs legacy `WebSecurityConfigurerAdapter`; JWT resource
server vs session/form login.

## Where the relevant code lives
- Security config: `SecurityConfig.java` (`http.authorizeHttpRequests`, `csrf()`, `headers()`, `cors()`).
- Auth: `@PreAuthorize`, `@Secured`, `@RolesAllowed` on services/controllers; `JwtDecoder` bean.
- Data: `@Query` with `nativeQuery = true`, `EntityManager.createNativeQuery`, `JdbcTemplate`.
- Config/secrets: `application-*.yml`, `bootstrap.yml`, Spring Cloud Config / Vault.
- Errors: `@ControllerAdvice`, `server.error.include-stacktrace`, `include-message`.
- Actuator: `management.endpoints.web.exposure.include` (V14.3 exposure).

## Controls the framework satisfies by default (confirm nothing disabled them)
| ASVS | Spring default | What disables it / look for |
|---|---|---|
| 4.2.2 anti-CSRF | Enabled for session-based auth in Spring Security | `.csrf(csrf -> csrf.disable())` - acceptable only for stateless JWT APIs (record N/A) |
| 14.4.4 nosniff, 14.4.7 X-Frame-Options DENY, 14.4.5 HSTS (on HTTPS) | All set by `headers()` defaults | `.headers(h -> h.frameOptions().disable())`, `.headers().disable()`, `hsts().disable()` |
| 5.3.3 output encoding | Thymeleaf `th:text` escapes | `th:utext`, `[(...)]` inline, JSP `<%= %>` |
| 5.3.4 parameterized queries | JPA/JPQL named params, Spring Data derived queries | String-built JPQL, `nativeQuery` with concatenation, `JdbcTemplate.query("..." + x)` |
| 2.4.1 password storage | `DelegatingPasswordEncoder` (bcrypt) via `PasswordEncoderFactories` | `NoOpPasswordEncoder`, `MessageDigest("MD5")` |
| 3.2.1 session fixation | `sessionManagement().sessionFixation().migrateSession()` default | `.sessionFixation().none()` |
| 3.4.2 HttpOnly | Servlet container sets HttpOnly on JSESSIONID | `server.servlet.session.cookie.http-only=false` |
| 3.4.1 Secure | Only if `server.servlet.session.cookie.secure=true` (not default) | Missing property behind TLS |
| 14.3.2 debug | `server.error.include-stacktrace=never` (Boot 2.3+) | `always`, `spring.devtools` on the prod classpath |
| 7.4.1 generic error | Boot `BasicErrorController` white-label page | `include-message=always` with exception text |
| 5.5.3 deserialization | Jackson default typing off | `enableDefaultTyping()`, `@JsonTypeInfo(use = CLASS)`, `ObjectInputStream` on request bodies |

## Controls that always need explicit evidence
- 4.1.1 / 4.2.1: every `authorizeHttpRequests` chain ends with `.anyRequest().authenticated()`;
  ownership checks in the repository query (`findByIdAndOwnerId`) or `@PostAuthorize`.
- 2.10.4 / 6.4.1: no passwords in `application.yml` committed; Vault / env placeholders `${DB_PASSWORD}`.
- 14.5.3 CORS: `@CrossOrigin("*")` on authenticated endpoints, or `allowedOrigins("*")` with credentials = Failed.
- 14.3.3 / V14.3: actuator `env`, `heapdump`, `beans` exposed without auth.
- 3.5.3 JWT: `NimbusJwtDecoder` with issuer/audience validators; custom parsers with `parse()` instead of `parseClaimsJws()` fail.
- 7.1.1 / 7.1.2: `logging.level.org.springframework.web=DEBUG` in prod logs request bodies.

## What "good" looks like
```java
@Bean SecurityFilterChain api(HttpSecurity http) throws Exception {
  return http
    .csrf(c -> c.disable())                       // stateless JWT: ASVS 4.2.2 N/A, document it
    .headers(h -> h.contentSecurityPolicy(c -> c.policyDirectives("default-src 'self'"))) // 14.4.3
    .cors(c -> c.configurationSource(allowListSource()))                                  // 14.5.3
    .authorizeHttpRequests(a -> a.requestMatchers("/actuator/health").permitAll()
                                  .anyRequest().authenticated())                          // 4.1.1
    .oauth2ResourceServer(o -> o.jwt(Customizer.withDefaults()))                          // 3.5.3
    .build();
}
```

## Manual trace checklist
1. Read the whole `SecurityFilterChain`; every `permitAll()` is deliberate (V4.1.1).
2. One repository per aggregate: derived query includes the owner/tenant column (V4.2.1).
3. `headers()` block: what was disabled and why (V14.4).
4. Actuator exposure list against `management.endpoints.web.exposure.include` (V14.3).
5. `application-prod.yml` for literal secrets and `include-stacktrace` (V2.10, V14.3.2).

## Stack-specific false positives
- `csrf().disable()` on a pure bearer-token API is not a 4.2.2 failure; mark N/A in scope.checked.
- `@Query(nativeQuery = true)` with `:param` binding is parameterized.
- `permitAll()` on `/actuator/health`, `/login`, `/swagger-ui/**` in non-prod profiles.

## Tooling
- `mvn org.owasp:dependency-check-maven:check` (V14.2.1; its report carries CVE + CWE ids).
- SpotBugs + `find-sec-bugs` (bug patterns map to CWE, e.g. SQL_INJECTION_JPA = CWE-89).
- `curl -I` against a running instance for V14.4 evidence.

## References
- Spring Security reference: "Security HTTP Response Headers", "CSRF", "CORS".
- ASVS 4.0.3 V3.4, V4.1, V4.2, V5.3, V14.3, V14.4; CWE-89, CWE-79, CWE-352, CWE-502, CWE-639.
