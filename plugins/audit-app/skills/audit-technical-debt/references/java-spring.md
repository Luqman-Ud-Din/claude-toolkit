# Java / Spring reference for audit-technical-debt

## Stack markers

`pom.xml` or `build.gradle(.kts)` with `spring-boot-starter-*`; `@SpringBootApplication`.
Variants: Spring Boot 2.x (javax namespace, `WebSecurityConfigurerAdapter`) vs 3.x
(jakarta, `SecurityFilterChain`); multi-module Maven builds; Kotlin sources (`.kt`,
measured by grep patterns only - `complexity.py` does not parse Kotlin).

## Where the relevant code lives

- Hotspots: `service/`, `*ServiceImpl.java`, `domain/`, batch `*Job.java` / `*Step.java`,
  `*Mapper` classes, `@Scheduled` methods. Lombok hides accessors, so file length
  understates class size and overstates nothing.
- Suppressions: `@SuppressWarnings`, `@SuppressFBWarnings`, `spotbugs-exclude.xml`,
  `pmd-ruleset.xml` exclusions, `checkstyle-suppressions.xml`, `// NOSONAR`, `// NOPMD`.
- Currency: `<parent>spring-boot-starter-parent</parent>` version, `<java.version>`,
  `maven.compiler.release`, Gradle `JavaLanguageVersion.of(n)`, `Dockerfile` JDK image.
- Excluded: `target/`, `build/`, `generated-sources/` (MapStruct, OpenAPI generator, JOOQ).

## Dangerous / interesting APIs and patterns

Mirrored in `scripts/patterns/java-spring.json`.
- **Deprecated / removed**: `WebSecurityConfigurerAdapter`, `antMatchers`,
  `authorizeRequests` (Spring Security 6); `javax.servlet|persistence|validation`
  (Boot 3 needs jakarta); boxed-primitive constructors, `finalize()`, `Thread.stop`
  (deprecated for removal); `org.apache.log4j` (Log4j 1, EOL 2015); Springfox.
  Anything annotated `@Deprecated(forRemoval = true)` in the project's own code.
- **EOL markers**: Java 8/11/17 depend on the vendor (Temurin, Corretto, Oracle differ -
  `eol-dates.json` uses Temurin); Spring Boot OSS support ends about 13 months after
  each minor release (2.7 ended 2023-11-24).
- **Suppressions**: `@SuppressWarnings("all")`, `("unchecked")` on whole classes,
  `("deprecation")` hiding migration work; `@SuppressFBWarnings` on `SQL_*`, `CRYPTO_*`,
  `PATH_TRAVERSAL_*` (security - launch-risk candidate).
- **Inconsistent patterns**: RestTemplate + WebClient + RestClient + Feign; Jackson + Gson;
  JPA + JdbcTemplate + MyBatis in one module; field `@Autowired` beside constructor
  injection; JUnit 4 beside JUnit 5; `java.util.Date` beside `java.time`.
- **Complexity shapes**: service methods with nested `if (x != null)` ladders instead of
  `Optional`/guard clauses; giant `switch` on status strings; `@Transactional` methods that
  orchestrate five repositories.

## What "good" looks like

One HTTP client style (RestClient or WebClient), constructor injection with `final`
fields, records for DTOs, `SecurityFilterChain` beans, jakarta namespace, a PMD or Sonar
quality gate in CI with complexity rules enforced, and suppressions carrying a
`justification`:

```java
@SuppressFBWarnings(value = "EI_EXPOSE_REP", justification = "immutable list from List.copyOf")
```

## Manual trace checklist

1. Top hotspot: list the branches, the rules they encode, and the tests that pin them.
2. Boot 2 -> 3 upgrade: count javax imports and security-config classes; that count sizes
   the effort (OpenRewrite `UpgradeSpringBoot_3_x` dry run gives the diff).
3. Dead-code candidates: search for the class in `@ComponentScan` packages, XML config,
   `spring.factories` / `AutoConfiguration.imports`, JPQL strings and reflection.
4. Security suppressions and `// NOSONAR` on crypto, SQL or file paths.
5. For each mixed family, decide whether a migration is under way (ADR, newest code
   uses the new style) or the codebase has simply drifted.

## Stack-specific false positives

- Stereotype beans (`@Service`, `@Component`, `@Configuration`), `@Bean` factory methods,
  `@EventListener`, `@Scheduled`, JPA entities referenced only in JPQL, MapStruct mapper
  interfaces - all used without a type reference. `dead_code.py` skips common annotations.
- Lombok-generated duplication (builders) does not appear in source and is not counted.
- `@SuppressWarnings("serial")` and `("unused")` on JPA default constructors are routine.

## Tooling

- PMD 7: `pmd check -d src/main/java -R category/java/design.xml/CyclomaticComplexity,category/java/design.xml/CognitiveComplexity,category/java/design.xml/GodClass,category/java/design.xml/ExcessiveMethodLength -f json -r pmd.json`
- Copy/paste: `pmd cpd --minimum-tokens 100 --dir src/main/java --language java --format xml`
- Deprecated JDK APIs: `jdeprscan --release 21 --class-path 'target/lib/*' target/app.jar`;
  `javac -Xlint:deprecation`; internal APIs: `jdeps --jdk-internals target/app.jar`.
- Currency: `mvn versions:display-dependency-updates versions:display-plugin-updates`;
  Gradle `dependencyUpdates` (ben-manes plugin, add in a scratch copy).
- Upgrade sizing: `mvn -U org.openrewrite.maven:rewrite-maven-plugin:dryRun -Drewrite.activeRecipes=org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_4`
  (writes a patch under `target/`, does not change sources).
- Dashboards: SonarQube (`mvn sonar:sonar`), SpotBugs, Checkstyle.

## References

CWE-1121, CWE-1080, CWE-561, CWE-1041, CWE-477, CWE-1104, CWE-546. Spring Boot support
table: https://spring.io/projects/spring-boot#support ; Spring Security 6 migration:
https://docs.spring.io/spring-security/reference/migration/ ; PMD rules:
https://docs.pmd-code.org/latest/pmd_rules_java_design.html
