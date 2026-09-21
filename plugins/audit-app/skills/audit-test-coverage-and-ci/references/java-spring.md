# Java / Spring reference for audit-test-coverage-and-ci

## Stack markers

`pom.xml` / `build.gradle(.kts)` with `spring-boot-starter-test` (JUnit 5, Mockito, AssertJ),
`src/test/java/**`. Integration: `@SpringBootTest`, `@DataJpaTest`, `@WebMvcTest`,
`org.testcontainers:*` (`@Testcontainers`, `@Container`, `@ServiceConnection`), Flyway/Liquibase
on test start. E2E: Selenium, Playwright for Java, REST Assured against a running app,
Karate. Surefire runs `*Test.java`, Failsafe runs `*IT.java` in `verify` - a pipeline that runs
`mvn test` but not `mvn verify` never runs the integration tests.

## Where the relevant code lives

`src/test/java/**` (unit), `src/test/resources/application-test.yml` (H2 vs real DB),
`src/integrationTest/**` (Gradle source set), `pom.xml` `<plugin>` blocks (surefire, failsafe,
jacoco, spotbugs, dependency-check), `build.gradle` `test { }`/`jacocoTestReport`,
`.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile` (`sh 'mvn ...'`).
Production units: `@RestController`, `@Service`, `@Component` handlers, `@Repository`,
`@Scheduled` jobs, `@KafkaListener`/`@RabbitListener` consumers.

## Dangerous / interesting APIs and patterns

- Skipped: `@Disabled` / `@Disabled("reason")` (JUnit 5), `@Ignore` (JUnit 4),
  `@DisabledIf`/`@DisabledOnOs`/`@EnabledIfEnvironmentVariable` (conditional - check what CI
  sets), `Assumptions.assumeTrue(false)`, `@Tag("manual")` excluded by surefire `<excludedGroups>`.
- In-memory substitute: `jdbc:h2:mem:` or `spring.datasource.url=jdbc:hsqldb:mem` in
  `application-test.yml` while production is PostgreSQL/MySQL/SQL Server; `@DataJpaTest`
  without `@AutoConfigureTestDatabase(replace = NONE)` silently swaps in H2. Native queries,
  JSONB, sequences, locking (`@Lock`) behave differently.
- Tests against a shared server: `jdbc:postgresql://db-staging` in test resources.
- Hygiene: `Thread.sleep(`, `@DirtiesContext` everywhere (slow, hides state bugs),
  `@MockBean` on the class under test, static mutable state, `LocalDateTime.now()` in assertions,
  `@Transactional` on tests hiding commit-time constraint failures.
- Auth: `@WithMockUser` only with the admin role; no test for `@PreAuthorize` denial (403);
  `spring.security` disabled in the test profile.
- CI: `mvn test` only (Failsafe never runs), `-DskipTests`, `-Dmaven.test.skip=true`,
  `-DskipITs`, `gradle build -x test`, `testFailureIgnore=true`, `|| true`; no `spotbugs`/
  `checkstyle`/`errorprone`; no `dependency-check` / `snyk` / `trivy`; no JaCoCo `check` goal
  with `<rules>`; no `-Werror` (`<compilerArgs><arg>-Werror</arg>`).
- Reproducibility: version ranges (`[1.0,)`), `LATEST`/`RELEASE`, no Maven wrapper (`mvnw`),
  Gradle without `--locked`/dependency locking; artifacts deployed without a build number or
  GPG signature (`maven-gpg-plugin`, `signing` plugin).

## What "good" looks like

```java
@SpringBootTest(webEnvironment = RANDOM_PORT)
@Testcontainers
class OrderApiIT {
    @Container @ServiceConnection
    static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:16-alpine");
    @Autowired TestRestTemplate rest;

    @Test void customer_cannot_read_other_tenants_order() {
        var res = rest.withBasicAuth("bob@tenantB", "pw").getForEntity("/api/orders/123", String.class);
        assertThat(res.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }
}
```
```xml
<!-- pom.xml: failsafe runs *IT in verify; jacoco fails below threshold on critical packages -->
<plugin><artifactId>maven-failsafe-plugin</artifactId><executions><execution><goals><goal>integration-test</goal><goal>verify</goal></goals></execution></executions></plugin>
<plugin><groupId>org.jacoco</groupId><artifactId>jacoco-maven-plugin</artifactId>
  <executions><execution><id>check</id><goals><goal>check</goal></goals><configuration><rules><rule>
    <element>PACKAGE</element><includes><include>com.acme.payment.*</include></includes>
    <limits><limit><counter>LINE</counter><value>COVEREDRATIO</value><minimum>0.80</minimum></limit></limits>
  </rule></rules></configuration></execution></executions></plugin>
```
CI: `./mvnw -B verify` (not `test`), `./mvnw org.owasp:dependency-check-maven:check`,
`./mvnw spotbugs:check checkstyle:check`.

## Manual trace checklist

1. Auth: tests for `@PreAuthorize` denials and expired JWTs; security not disabled in tests.
2. Money: pricing/invoice/payment services - boundary and rounding tests (`BigDecimal` scale).
3. Data mutation: repository/integration tests run on the production DB engine via
   Testcontainers, not H2; migrations applied in tests.
4. Messaging/scheduled jobs: any test?
5. CI: `verify` vs `test`; skip flags; JaCoCo `check` present; branch protection.

## Stack-specific false positives

- `@Disabled` on a test class in `src/test/.../manual/` intentionally excluded and documented:
  Info, list it anyway.
- H2 for a pure JPA-mapping smoke test alongside a Testcontainers suite: fine; the finding is
  H2 as the *only* database test.
- `@Tag("slow")` excluded on PRs but run nightly: partial, cite the nightly job.

## Tooling

`./mvnw test -Dtest=None -DfailIfNoTests=false` (compile check), `./mvnw verify` with
`jacoco:report` (`target/site/jacoco/index.html`), `./mvnw org.pitest:pitest-maven:mutationCoverage`
on the payment package, `./mvnw versions:display-dependency-updates`, `gradle test --tests`.

## References

- JUnit 5 `@Disabled` and conditions: https://junit.org/junit5/docs/current/user-guide/#writing-tests-conditional-execution
- Testcontainers + Spring Boot `@ServiceConnection`: https://docs.spring.io/spring-boot/reference/testing/testcontainers.html
- JaCoCo check goal: https://www.jacoco.org/jacoco/trunk/doc/check-mojo.html
- CWE-1120, ASVS-1.14.4, ASVS-14.1.x.
