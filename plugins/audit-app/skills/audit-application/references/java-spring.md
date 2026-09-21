# Java / Spring reference for audit-application

What the orchestrator needs to know about a Java/Spring codebase before it plans and
runs the children. Topic detail lives in each child's own `references/java-spring.md`.

## Stack markers

- `pom.xml`, `build.gradle`, `build.gradle.kts` (detect_stack id `java-spring`). A
  `spring-boot-starter-*` dependency confirms Spring. Without it detect_stack notes "generic
  Java", and the children use their generic sections.
- `spring-boot-starter-web` / `-webflux`: HTTP service. `spring-boot-starter-thymeleaf`,
  `src/main/resources/templates/*.html`, `*.jsp`, `*.ftl`: server-rendered HTML.
- Multi-module builds: a parent `pom.xml` with `<modules>` or `settings.gradle` with
  `include`. Name every deployable module in scope.

## Where the relevant code lives

- `src/main/java/**` (controllers `@RestController`, services, repositories),
  `src/main/resources/application*.yml|properties` (profiles, datasource, actuator),
  `src/main/resources/db/migration` (Flyway) or `db/changelog` (Liquibase),
  `src/test/java/**`.
- Security: `SecurityFilterChain` beans / `WebSecurityConfigurerAdapter` (legacy).
- Jobs: `@Scheduled`, Quartz, Spring Batch, `@KafkaListener` / `@RabbitListener`.

## Dangerous / interesting APIs and patterns

Setup signals (they shape questions and applicability; they are not findings):

- **Multi-tenant hints:** Hibernate `@TenantId`, `CurrentTenantIdentifierResolver`,
  `MultiTenantConnectionProvider`, `AbstractRoutingDataSource`, `@Filter`/`@FilterDef` on a
  tenant column, `tenant_id`/`organization_id` columns, tenant headers read in a
  `OncePerRequestFilter`.
- **Background work:** `@Scheduled(cron=...)` (the zone matters for datetime), ShedLock
  (concurrency), Spring Batch.
- **Messaging and integrations:** Kafka/RabbitMQ consumers (tenant context in consumers,
  idempotency), `RestTemplate`/`WebClient` (timeouts for performance and readiness).
- **Actuator:** `management.endpoints.web.exposure.include`. Headers, readiness and secrets
  all read it.

## What "good" looks like

- JDK matching `maven.compiler.release` / `java.toolchain` installed: `java -version`.
- Build possible offline or with network: `./mvnw -q -DskipTests package` or
  `./gradlew assemble`. The wrapper downloads Maven/Gradle on first use.
- Dependency data: OWASP dependency-check needs the NVD database (network, and ideally an NVD
  API key). Without it dependency-vulnerabilities records "not checked".
- Read-only DB access, or Flyway/Liquibase migrations in the repo, for db-schema and orm.
- Test URL + two users (authz probe), two tenants (tenant probe), staging URL (headers),
  running instance (leak and performance load tests). Full git history.

## Manual trace checklist

Prerequisites to confirm at setup:

1. JDK installed and the build runs -> test-coverage (`mvn verify` with JaCoCo),
   technical-debt (PMD/SpotBugs). Missing: `--limited "build not possible"`.
2. Dependency resolution possible (`~/.m2/repository` or network) -> dependency-vulnerabilities,
   licensing. Missing: `--limited "dependencies not resolved; licences unknown"`.
3. Migrations present or read-only DB access -> db-schema, orm, concurrency (`@Version`, unique
   constraints).
4. Which Spring profile is production (`application-prod.yml`, `SPRING_PROFILES_ACTIVE` in
   Dockerfile/manifests) -> secrets, readiness, logging.
5. Test/staging URLs and accounts for the probes.
6. Git history not shallow.

## Stack-specific false positives

Wrong applicability calls to avoid:

- **REST-only Spring app:** frontend-best-practices, frontend-memory-leak and client-auth are n/a.
  XSS and accessibility are n/a only when no Thymeleaf/JSP/FreeMarker templates exist.
  `plan.py` checks `templates/*.html`, `.jsp`, `.ftl`.
- **A SPA bundled into `src/main/resources/static` or built from `src/main/frontend`:**
  detect_stack only sees the SPA if its `package.json` is within four directory levels. If the
  frontend is present but undetected, add the frontend children with `--profile custom` or
  `--skill`, and say why in the run.
- **Generic Java (no Spring marker):** do not mark backend children n/a. The children fall back
  to their generic sections; record that in the plan warnings.

## Tooling

```bash
java -version
./mvnw -v            # or: mvn -v / ./gradlew --version
./mvnw -q -DskipTests package
./mvnw org.owasp:dependency-check-maven:check -DnvdApiKey=$NVD_API_KEY   # network; slow on first run
./mvnw verify        # tests + JaCoCo if configured
./mvnw dependency:tree -DoutputType=text
./gradlew dependencies --configuration runtimeClasspath
git rev-parse --is-shallow-repository
```

Build commands write only `target/`/`build/`. Ask before running them in the user's tree.

## Child applicability for Java/Spring repos

| Repo shape | n/a children |
|---|---|
| REST API only | frontend-best-practices, frontend-memory-leak, client-auth-and-storage; XSS and accessibility unless templates exist |
| MVC with Thymeleaf/JSP | frontend-best-practices, frontend-memory-leak (no SPA); client-auth applies only if tokens reach browser storage |
| Batch / consumer service | expect api-contract and headers to record "no HTTP surface" |

## References

- Child references: `../audit-authz-and-access-control/references/java-spring.md`,
  `../audit-multi-tenant-isolation/references/java-spring.md`, `../audit-dependency-vulnerabilities/references/java-spring.md`.
- Spring Security reference, Hibernate multitenancy guide, OWASP Dependency-Check docs.
