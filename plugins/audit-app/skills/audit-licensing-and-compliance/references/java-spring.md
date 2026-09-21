# Java / Spring reference for audit-licensing-and-compliance

Where licence information lives for Maven/Gradle dependencies, what resolves offline,
which common artifacts carry copyleft or commercial terms, and how the notices file is
shipped in a Spring Boot product.

## Stack markers
`pom.xml` (single or multi-module with `<modules>`), `build.gradle(.kts)` + `settings.gradle`,
`gradle.lockfile` / `dependencies.lock`, `~/.m2/repository` local cache, `~/.gradle/caches/modules-2`.
Spring Boot's BOM (`spring-boot-dependencies`) manages most versions, so `<version>` is often
absent in the POM - the script then reports "managed version" and cannot open the cached POM.

## Where the relevant code lives
- Direct dependencies: `<dependencies>` in each module POM; `dependencyManagement` in the parent; Gradle `implementation(...)` / `runtimeOnly(...)`.
- Resolved graph: `mvn dependency:tree` / `./gradlew dependencies --configuration runtimeClasspath` (not read by the script).
- Licence metadata: the artifact POM `<licenses><license><name>Apache License, Version 2.0</name>` in `~/.m2/repository/<group>/<artifact>/<version>/`; frequently only in the **parent** POM (`<parent>` chain) - the script reads one level only.
- Shaded/fat jars (`maven-shade-plugin`, Spring Boot repackage) bundle dependencies into one artifact: distribution of every transitive dependency.
- `META-INF/LICENSE`, `META-INF/NOTICE` inside jars - Apache-2.0 NOTICE contents must be reproduced.
- Non-repository jars: `<scope>system</scope>` with `<systemPath>`, `libs/*.jar` on the classpath, `flatDir` repositories in Gradle.
- Shipping the notices: `src/main/resources/META-INF/THIRD-PARTY.txt` (what `license-maven-plugin` generates) and/or the About/Help page.

## Dangerous / interesting APIs and patterns
- **iText 7 / itextpdf 5** (AGPL-3.0 or commercial), **JasperReports** (LGPL - fine as library, but its engine bundles iText), **mysql-connector-java / mysql-connector-j** (GPL-2.0 with Universal FOSS exception - proprietary needs Oracle's commercial licence; `MariaDB Connector/J` is LGPL), **Hibernate ORM** (LGPL-2.1 - fine unmodified), **javassist** (MPL/LGPL/Apache tri-licence - fine), **JavaFX / OpenJFX** (GPL with Classpath exception - fine), **Oracle JDK** (commercial for production since 8u211 - use Temurin/OpenJDK), **Aspose**, **JxBrowser** (commercial), **Ehcache 3** (Apache) vs **Terracotta** (commercial), **Elasticsearch client 7.11+** (SSPL/Elastic-2.0 server; client is Apache), **MongoDB Java driver** (Apache; server SSPL), **Kotlin** (Apache).
- GPL-with-Classpath-exception artifacts (`javax.*` from GlassFish, OpenJDK modules): fine to link; the exception is what makes it fine - verify the exception text is present.
- `system` scope and `flatDir` jars: no licence metadata; vendor lookup needed.
- Shade plugin with `minimizeJar` / relocation: still distribution; NOTICE files must be merged (`ApacheNoticeResourceTransformer`).

## What "good" looks like
```xml
<plugin>
  <groupId>org.codehaus.mojo</groupId>
  <artifactId>license-maven-plugin</artifactId>
  <version>2.4.0</version>
  <executions><execution><goals><goal>add-third-party</goal></goals>
    <configuration>
      <excludedScopes>test,provided</excludedScopes>
      <failOnBlacklist>true</failOnBlacklist>
      <excludedLicenses>GNU General Public License|GNU Affero|SSPL</excludedLicenses>
    </configuration></execution></executions>
</plugin>
```
The generated `THIRD-PARTY.txt` goes into `META-INF/` and is referenced from the About page.

## Manual trace checklist
1. For each `unknown` artifact with a managed version: resolve the version from `mvn dependency:tree`, open the POM and its parent for `<licenses>`.
2. Confirm the JDK used in the Dockerfile (`FROM eclipse-temurin` fine; `FROM oracle/jdk` needs a licence).
3. Shaded jar? Check the shade plugin config merges NOTICE/LICENSE files.
4. Reporting/PDF stack: JasperReports + iText version - iText 2.1.7 (MPL/LGPL) vs 5+/7 (AGPL).
5. Database drivers: MySQL connector licence vs product model.
6. Where is `THIRD-PARTY.txt` shipped - inside the jar, in the image, on the About page?

## Stack-specific false positives
- `org.springframework.*`, `jakarta.*` (EPL-2.0 with GPL-2.0 Classpath exception secondary), `com.fasterxml.jackson.*` - Apache/EPL; `unknown` only when the cache is missing.
- `<scope>test</scope>` and `<scope>provided</scope>` dependencies are not shipped.
- Lombok (MIT), MapStruct (Apache) - compile-time only.
- LGPL Hibernate used unmodified via Maven is `review` at most, normally approved.

## Tooling
- `mvn license:add-third-party` / `license:aggregate-add-third-party` (license-maven-plugin).
- `./gradlew generateLicenseReport` (com.github.jk1.dependency-license-report).
- `mvn org.cyclonedx:cyclonedx-maven-plugin:makeAggregateBom` - SBOM with licence ids.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py --patterns scripts/patterns/java-spring.json` - vendored GPL headers, copyleft POM licences, system-scope jars, known-copyleft artifacts.

## References
license-maven-plugin docs; Maven POM reference (`licenses`); Oracle MySQL FOSS License Exception; iText licensing FAQ;
SPDX licence list; ASVS 4.0.3 V14.2; CWE-1104.
