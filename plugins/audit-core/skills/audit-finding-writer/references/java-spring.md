# Java / Spring reference for audit-finding-writer

## Stack markers
`pom.xml` or `build.gradle(.kts)` containing `spring-boot`, `src/main/java`, `application.yml|properties`.

## Where the relevant code lives
`@RestController` classes, `SecurityConfig` / `SecurityFilterChain` beans, `@Service`, `@Repository` / Spring Data interfaces, `@Scheduled` jobs, `application-*.yml`.

## Remediation idioms
- Secrets: `${ENV_VAR}` placeholders in `application.yml`, Spring Cloud Vault / AWS Secrets Manager; never literals in `application-prod.yml`.
- AuthZ: `http.authorizeHttpRequests(...)` with explicit matchers, `@PreAuthorize("hasRole('ADMIN') and #id == principal.id")`, method security enabled with `@EnableMethodSecurity`.
- Input: `@Valid` + Bean Validation annotations on request records; map to entities explicitly (MapStruct) to avoid binding entity fields.
- Data: JPQL/Criteria with named parameters, `@Query` with `:param`; `@EntityGraph` / `JOIN FETCH` for N+1; `Pageable` on list endpoints; `@Transactional` boundaries on multi-write services.
- Async: `CompletableFuture` with a bounded executor, `@Async` with a configured `TaskExecutor`; `RestClient`/`WebClient` beans with timeouts; never `.block()` inside reactive chains.
- Headers: `http.headers(h -> h.contentSecurityPolicy(...).httpStrictTransportSecurity(...))`; CSRF enabled for session auth, disabled only for stateless token APIs.
- Multi-tenancy: Hibernate `@TenantId` / `@Filter`, tenant resolved from `SecurityContextHolder`, `AbstractRoutingDataSource` for db-per-tenant.
- Logging: SLF4J parameterized (`log.info("order {}", id)`), Logback JSON encoder, MDC for correlation id.
- Dates: `Instant`/`OffsetDateTime`, `Clock` injected, JDBC `TIMESTAMP WITH TIME ZONE`.

## Recurring references
CWE-798, CWE-89, CWE-639, CWE-915, CWE-352, CWE-502 (deserialization, Jackson default typing), CWE-611 (XXE), ASVS 4.x, 5.3, 5.5, 14.4; OWASP A01, A02, A03, A05, A08.

## Stack-specific false positives
`csrf().disable()` on a pure bearer-token API is correct; `permitAll()` on actuator health with a separate management port; `@Query(nativeQuery = true)` with `:params` is parameterized.

## Tooling
`mvn org.owasp:dependency-check-maven:check`, `./gradlew dependencyCheckAnalyze`, SpotBugs + FindSecBugs, Checkstyle/PMD, `jcmd <pid> GC.heap_info` for leaks.
