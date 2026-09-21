# Java / Spring reference for audit-soc2-controls-evidence

## Stack markers

`pom.xml` / `build.gradle(.kts)` with `spring-boot-starter-*`. Sub-variants: Spring
Security with local users vs `spring-boot-starter-oauth2-client` /
`oauth2-resource-server` (IdP-backed), servlet vs WebFlux, JPA/Hibernate vs JDBC,
Flyway vs Liquibase. The dependency list answers most "does a control exist"
questions before you open any Java file.

## Where the relevant code lives

- `config/SecurityConfig*.java` - `SecurityFilterChain`, method security.
- `src/main/resources/application*.yml|properties` - `spring.security.oauth2.*`,
  `management.endpoints.*`, `spring.datasource.*`, `logging.*`, secret imports.
- `logback-spring.xml` / `log4j2-spring.xml` - appenders and sinks.
- Controllers/services with `@PreAuthorize`, `@Secured`, `@RolesAllowed`.
- Entities with `@Audited`, `@Version`, `@Column(unique = true)`.
- `src/main/resources/db/migration` (Flyway) or `db/changelog` (Liquibase).
- `Jenkinsfile`, `.github/workflows/`, `.gitlab-ci.yml`.

## Dangerous / interesting APIs and patterns

- CC6.1 auth: `SecurityFilterChain`, `oauth2Login()`, `oauth2ResourceServer().jwt()`,
  `saml2Login()`. Bad: `permitAll()` on `/**` or `/api/**`, `csrf().disable()` on a
  cookie-session app, `WebSecurityConfigurerAdapter` (removed in Boot 3).
- MFA: Spring Security one-time-token login / MFA support, or the IdP `amr`/`acr`
  claim checked; otherwise organisational (IdP policy export).
- CC6.1 rbac: `@EnableMethodSecurity`, `@PreAuthorize("hasRole('ADMIN')")`,
  `requestMatchers(...).hasRole(...)`, `hasAuthority`.
- CC7.2 security events: `AuthenticationSuccessEvent`,
  `AbstractAuthenticationFailureEvent`, `AuthorizationDeniedEvent` handled with
  `@EventListener`; Actuator `AuditEventRepository`.
- CC6.1 admin-log / PI1.3: Hibernate Envers `@Audited` + `_AUD` tables; Spring Data
  `@CreatedBy` / `@LastModifiedBy` with `@EnableJpaAuditing`.
- CC6.3 deprovisioning: `UserDetails.isEnabled()`, `setEnabled(false)`,
  `SessionInformation.expireNow()`, OAuth2 token revocation.
- A1.1: `spring-boot-starter-actuator`, `management.endpoint.health.probes.enabled=true`.
- C1: `spring.config.import=vault://` (Spring Cloud Vault), `aws-secretsmanager:`
  (Spring Cloud AWS), Azure Key Vault starter, Jasypt `ENC(...)` (the key must come
  from outside the repo), JPA `@Convert(converter = EncryptedStringConverter.class)`.
- PI1: `@Valid`, `@NotNull`, `@Size`, `@Pattern`, `@Version` optimistic locking,
  unique constraints in migrations.

## What "good" looks like

```java
@Bean SecurityFilterChain api(HttpSecurity http) throws Exception {
  return http
    .authorizeHttpRequests(a -> a
        .requestMatchers("/actuator/health/**").permitAll()
        .requestMatchers("/api/admin/**").hasRole("ADMIN")
        .anyRequest().authenticated())
    .oauth2ResourceServer(o -> o.jwt(Customizer.withDefaults()))
    .build();
}

@Entity @Audited
class Customer { @Id Long id; @Version long version; @Column(unique = true) String email; }
```

Pipeline shape: `mvn -B verify` -> `mvn org.owasp:dependency-check-maven:check
-DfailBuildOnCVSS=7` -> image build and scan -> `flyway migrate` (or Liquibase
`update`) run by the deploy job in a protected environment.

## Manual trace checklist

1. `SecurityFilterChain`: every `permitAll()` justified; admin paths role-restricted.
2. Authentication/authorization events published and logged to a central sink.
3. Envers or equivalent covers user, role and financial entities.
4. User disable path ends existing sessions and refresh tokens.
5. CI: dependency-check, Snyk or Trivy present and failing the build; tests required.
6. Backups of the PostgreSQL/MySQL store (RDS automated backups, `pg_dump` job) plus
   a dated restore-test record.
7. Secrets from Vault/Secrets Manager; no plaintext in `application-prod.yml`.

## Stack-specific false positives

- `permitAll()` on `/actuator/health`, `/login`, `/error` and static assets.
- Jasypt `ENC(...)` values are fine only if `jasypt.encryptor.password` is external.
- `spring.flyway.enabled=true` in a profile used only by integration tests.
- `ConsoleAppender` in Kubernetes where Fluent Bit ships stdout centrally (partial,
  ask for platform evidence).

## Tooling

```bash
mvn -B org.owasp:dependency-check-maven:check -DfailBuildOnCVSS=7
./gradlew dependencyCheckAnalyze
mvn dependency:tree | grep -Ei "security|oauth2|envers|actuator|vault|flyway|liquibase"
grep -rnE "SecurityFilterChain|permitAll|@PreAuthorize|@Audited|@EventListener" src/main/java
```
SAST options: CodeQL (`java`), SpotBugs + find-sec-bugs, Semgrep `p/java`.

## References

- Spring Security reference (authorization, OAuth2, events); Spring Boot Actuator.
- Hibernate Envers; Spring Cloud Vault; Flyway and Liquibase docs.
- SOC2-CC6.1, CC6.3, CC7.1, CC7.2, CC8.1, A1.2, C1.1, PI1.3; CWE-284, CWE-778, CWE-1104.
