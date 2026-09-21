# Java / Spring reference for audit-secrets-and-config

## Stack markers
`pom.xml`/`build.gradle`, `application.properties`/`application.yml`, `application-{profile}.*`.

## Where the relevant code lives
`application.properties`/`.yml` and per-profile variants, `SecurityConfig`/`WebConfig` (CORS, HTTPS), `bootstrap.yml` (Spring Cloud Config/Vault), `Dockerfile`/`k8s` manifests (`SPRING_PROFILES_ACTIVE`, secret mounts).

## Dangerous / interesting keys and patterns
- Secrets in properties: `spring.datasource.password`, `*.secret`, `jwt.secret`, `*.api-key`. Should be `${ENV_VAR}` placeholders resolved from env/Vault, not literals.
- Debug in prod: `debug=true`, `server.error.include-stacktrace=always`, `spring.h2.console.enabled=true`, `management.endpoints.web.exposure.include=*` in `application-prod`.
- Active profile: confirm `SPRING_PROFILES_ACTIVE=prod` (or `production`) in the deploy.
- HTTPS/HSTS: `server.ssl.*` and `http.headers().httpStrictTransportSecurity()`.
- CORS: `allowedOrigins("*")` / `addAllowedOrigin("*")` / `@CrossOrigin("*")` together with `allowCredentials(true)`.

## What "good" looks like
```yaml
spring:
  datasource:
    password: ${DB_PASSWORD}     # from env / Vault, never a literal
```
```java
config.setAllowedOrigins(List.of("https://app.example.com"));
config.setAllowCredentials(true);   // explicit origins, never "*"
```

## Manual trace checklist
1. Every `application*.properties/.yml` - literal secret vs `${VAR}` placeholder?
2. Production profile disables debug/stacktrace/h2-console and does not expose all actuator endpoints.
3. CORS config: wildcard + credentials?
4. `git_secret_scan.py` over history.

## Stack-specific false positives
`${VAR}` placeholders; `*-example`/`*-local` profiles; actuator wide-open only in a `local` profile.

## Tooling
Spring Cloud Vault, `find-sec-bugs`, plus `references/tool-candidates.md`. Scripts: `git_secret_scan.py`, `config_key_inventory.py`.

## References
CWE-798, CWE-321, CWE-489, CWE-942, CWE-16. ASVS 2.10, 14.1, 14.4/14.5. OWASP A05:2021, A02:2021.
