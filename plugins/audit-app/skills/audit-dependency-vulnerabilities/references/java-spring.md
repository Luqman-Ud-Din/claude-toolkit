# Java / Spring reference for audit-dependency-vulnerabilities

## Stack markers
`pom.xml` (Maven), `build.gradle` / `build.gradle.kts` + `settings.gradle`
(Gradle), `gradle/libs.versions.toml` (version catalogs), `mvnw`/`gradlew`
wrappers. Variants: Spring Boot with `spring-boot-starter-parent` (versions are
managed by the BOM - the effective version is not in the pom you are reading);
multi-module builds (parent pom + `<modules>`).

## Where the relevant code lives
- Direct dependencies: `<dependencies>` in each module pom; Gradle `dependencies { implementation(...) }`.
- Managed versions: `<dependencyManagement>`, `<properties><x.version>`, the Spring Boot BOM,
  Gradle `platform(...)` / version catalog.
- Repositories: `<repositories>` / `settings.xml` mirrors; Gradle `repositories { maven { url } }`.
- Effective graph: `mvn dependency:tree` or `gradle dependencies --configuration runtimeClasspath`.
- Images: `Dockerfile` (`FROM eclipse-temurin:17-jre`) or Jib config in the pom.

## Dangerous / interesting APIs and patterns
- Famous manifest versions to grep: `log4j-core` 2.0-2.16 (Log4Shell),
  Spring Framework 5.3.0-5.3.17 / 5.2.x (Spring4Shell, CVE-2022-22965),
  `spring-cloud-function` < 3.1.7 (CVE-2022-22963), `jackson-databind` <= 2.12
  (gadget CVEs), `commons-text` 1.5-1.9 (Text4Shell), `snakeyaml` 1.x (CVE-2022-1471),
  `commons-collections` 3.2.1 (deserialization), `struts2`, `xstream` < 1.4.20,
  `spring-security` < 5.7.x/5.8.x (authorization bypass CVEs 2022-2023), `tomcat-embed` < 9.0.9x.
- Unpinned versions: `LATEST`, `RELEASE`, ranges `[1.0,)`, Gradle `+`, snapshots in prod.
- Shaded/uber jars and vendored jars in `lib/` - invisible to the dependency graph.
- `<repositories>` over `http://` and third-party repositories with no checksum policy.

## What "good" looks like
```xml
<parent>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-parent</artifactId>
  <version>3.3.4</version>   <!-- supported line; BOM pins log4j, jackson, snakeyaml -->
</parent>
<build><plugins>
  <plugin>
    <groupId>org.owasp</groupId><artifactId>dependency-check-maven</artifactId>
    <version>10.0.4</version>
    <configuration><failBuildOnCVSS>7</failBuildOnCVSS><formats><format>JSON</format></formats></configuration>
    <executions><execution><goals><goal>check</goal></goals></execution></executions>
  </plugin>
</plugins></build>
```
Gradle: `plugins { id("org.owasp.dependencycheck") version "10.0.4" }` and
`dependencyCheck { failBuildOnCVSS = 7f; formats = listOf("JSON") }`.

## Manual trace checklist
1. Effective versions first: `mvn help:effective-pom` or `gradle dependencies`; the
   BOM may already have moved a package past the vulnerable range even though the
   grep hit an old property.
2. For every Critical/High: is the vulnerable class on the runtime classpath
   (`runtimeClasspath`, not `testImplementation`) and reachable (logging of user
   input for log4j; `@RequestMapping` with bound POJOs for Spring4Shell; YAML/JSON
   parsing of request bodies for snakeyaml/jackson)?
3. Transitives: `mvn dependency:tree -Dincludes=<g>:<a>` gives the parent; fix via
   parent bump or `<dependencyManagement>` pin; Gradle `constraints {}` or
   `resolutionStrategy.force`.
4. Spring Boot line support: 2.x is out of OSS support; an old Boot line means
   dozens of unpatched transitives at once - one High finding, not thirty.
5. Base image JDK patch level (`trivy image`).

## Stack-specific false positives
- dependency-check matches on CPE and produces false positives for artifacts with
  generic names (`spring-core` matched to unrelated "spring" products); check the
  CVE text names the artifact.
- `log4j-api` alone is not vulnerable to Log4Shell; only `log4j-core`.
- `log4j-to-slf4j` / `log4j-over-slf4j` bridges are not log4j-core.
- Test-scope dependencies (`<scope>test</scope>`, `testImplementation`) do not ship.
- Managed-but-unused declarations in `<dependencyManagement>` only matter if some
  module actually declares the artifact.

## Tooling
- `mvn org.owasp:dependency-check-maven:check -Dformat=JSON` (set `-DnvdApiKey`)
- `gradle dependencyCheckAnalyze`
- `mvn versions:display-dependency-updates` / `gradle dependencyUpdates` (ben-manes plugin) for outdated
- `trivy fs --scanners vuln .` reads `pom.xml` and Gradle lockfiles
- `mvn dependency:tree -Dverbose` to see version conflicts
- Snyk / OSS Index (`mvn org.sonatype.ossindex.maven:ossindex-maven-plugin:audit`) as a faster, no-NVD alternative

## References
CWE-1395, CWE-502 (deserialization - most Java dependency CVEs), OWASP A06:2021,
ASVS 14.2, Spring Security advisories (spring.io/security), GitHub Advisory
Database (ecosystem=maven), OWASP dependency-check docs (jeremylong.github.io/DependencyCheck).
