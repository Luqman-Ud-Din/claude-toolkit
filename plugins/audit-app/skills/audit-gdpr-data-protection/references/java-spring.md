# Java / Spring reference for audit-gdpr-data-protection

## Stack markers
`pom.xml`/`build.gradle` with `spring-boot-starter-*`; JPA entities, `@RestController`,
`@Scheduled`, Logback/Log4j2, Spring Security. Variants: Spring Data REST
(auto-exposed repositories can expose PII without a controller), Kotlin.

## Where the relevant code lives
- Consent: entity fields (`consent`, `marketingOptIn`, `termsAccepted`), signup DTOs, `UserService`.
- Rights endpoints: `@DeleteMapping` / `@PutMapping` on `UserController`/`AccountController`;
  `export`, `anonymize` service methods; Spring Data REST repositories (`@RepositoryRestResource`).
- Retention: `@Scheduled` methods, Quartz jobs, Spring Batch jobs, Flyway data scripts.
- Minimisation: `log.*` calls (Lombok `@Slf4j`), `MDC`, `spring.jpa.show-sql`, Sentry `sendDefaultPii`, `@RequestParam` PII.
- Encryption: `server.ssl.*`, `requiresChannel().anyRequest().requiresSecure()`, JDBC URL `sslmode`/`useSSL`,
  `@Convert(converter = ...)` field encryption, Jasypt, KMS/Vault config.
- Audit: `@EnableJpaAuditing`, `@CreatedBy/@LastModifiedBy` (writes only), Envers `@Audited` (history), custom `AuditLog`.
- Breach signals: `AuthenticationFailureBadCredentialsEvent` listeners, `spring-security` lockout, Actuator/ Micrometer alerts, log shipping (Logstash appender).

## Dangerous / interesting APIs and patterns
- `private boolean marketingConsent;` alone.
- `@SQLDelete` / `deleted = true` soft delete without purge.
- `log.info("User {} registered", user)` with Lombok `@ToString`.
- `spring.jpa.show-sql=true`, `org.hibernate.type=TRACE` in a prod profile.
- `management.endpoints.web.exposure.include=*` (httpexchanges/env expose request data).
- `@GetMapping("/users/{email}")`, `@RequestParam String email`.
- JDBC `useSSL=false`, `sslmode=disable`, `trustServerCertificate=true`.
- `@RepositoryRestResource` on a `UserRepository` - full CRUD and search on PII with no controller code to audit.
- Erasure that calls `userRepository.deleteById` but not the mail provider, Elasticsearch index, S3 documents, or Kafka retention.

## What "good" looks like
```java
@Entity class Consent { UUID userId; String purpose; String policyVersion; Instant givenAt; Instant withdrawnAt; String source; }
@DeleteMapping("/me") public ResponseEntity<Void> eraseMe(@AuthenticationPrincipal UserDetails u) { erasure.anonymise(u.getUsername()); return accepted(); }
@Scheduled(cron = "0 0 3 * * *") public void purgeInactive() { retention.purgeOlderThan(Duration.ofDays(730)); }
log.info("user {} registered", user.getId());
spring.jpa.show-sql=false
http.requiresChannel(c -> c.anyRequest().requiresSecure());
```

## Manual trace checklist
1. Erasure: from the delete entry point, walk `@OneToMany(cascade=...)`, file storage, search indexes, caches (`@CacheEvict`), Kafka topics, vendors from the inventory.
2. Consent: fields, writers (signup DTO -> entity), readers (marketing sender, analytics).
3. Retention: every `@Scheduled`/Quartz job vs data category; Logback `maxHistory`; broker retention.
4. Spring Data REST exposure of PII repositories.
5. Profiles: check `application-prod.yml` specifically for `show-sql`, actuator exposure, SSL.

## Stack-specific false positives
- `@DeleteMapping` on product/order controllers is not erasure.
- `@CreatedBy` alone is not an audit trail of *access*.
- `show-sql=true` only in `application-dev.yml`: Low.
- `log.debug` guarded by `isDebugEnabled()`: still list, rate Low.

## Tooling
- `python scripts/gdpr_check.py <repo> --out ... --md ...`
- `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/java-spring.json`
- `grep -rn "@DeleteMapping\|anonymi\|@Scheduled" src/main`
- `grep -rn "show-sql\|exposure.include\|useSSL\|sslmode" src/main/resources`

## References
GDPR Art.5, 7, 12-22, 25, 28, 30, 32-35; CWE-532, CWE-359, CWE-312, CWE-319; ASVS 8.3, 7.1, 9.1;
Spring Security channel security docs; Hibernate Envers; Spring Boot Actuator security.
